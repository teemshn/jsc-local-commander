# ARCHITECTURE — 안전한 Windows 프로그램 제어 확장

상태: 설계 초안 / 프로세스 격리와 원격 연결은 아직 구현 전

## 1. 논리 구조
    ChatGPT 모바일/PC (실제 지원 여부 G0)
        → 인증된 중계/도구 호출 (기본 outbound only, G5)
        → MCP stdio facade (기존 v0.2 Python, 권한 없음)
        → Windows Named Pipe + 송신자 인증 + 384 KiB 제한
        → Policy Broker (저권한 별도 계정·ACL·SQLite, 기존 v0.2)
           ├─ 폴더/권한/사용자/작업계획/해시/중복/예산 검사
           ├─ durable job journal / 감사 / 백업 / 긴급 정지
           └─ 제한된 앱별 worker launcher [신규, 승인 전 없음]
                ├─ Excel COM worker
                ├─ HWP COM worker
                ├─ AutoCAD API worker
                └─ GUI UIA worker (로그인된 제한 세션만)
                     → 허용된 테스트/업무 파일 및 설치된 Windows 앱

주의: 별도 사용자 세션 GUI에서 Windows 설치 프로그램을 제어하려면 낮은 권한과 세션 접근 사이의 실제 권한 경계를 설계해야 한다. 제한된 broker가 사용자 세션으로 전환하는 임의 실행 발판이 되어선 안 된다. 부팅 서비스에 GUI 클릭 코드를 넣지 않는다. 세션 전용 launcher(사용자가 사전 설치·승인)와 고정된 레시피 통신만 허용한다.

## 2. 신뢰 경계
T1 ChatGPT 발화·파일 내용 = 비신뢰. MCP front는 인증/스키마 검증만, OS 변경 권한 없음.
T2 Named Pipe secret ≠ OS 샌드박스. 기존 v0.2에서 ACL/SID/pipe-squatting 실기기 검증 미완료. G1 전 브로커 확장/운영 금지.
T3 broker policy = 관리자가 보호한 파일/별도 계정에서만 수정, 실패 시 전부 거부.
T4 worker launch = 관리자 사전 등록한 서명·해시 고정 레시피, 절대 경로 고정, 인자는 타입과 범위 고정, shell=False.
T5 실제 문서 접근 = 별도 NTFS ACL/파일 핸들 기반 확인. 단순 문자열 경로 검사나 AI 지시만으로 허용 불가.
T6 승인 = 별도 채널·짧은 TTL·단건·plan hash/요청자/device/file/result에 결합, AI가 발급 불가.
T7 원격 = OAuth/장치인증/토큰 회전/테넌트·사용자 scope. 공개 무인증 포트/정적 공통 비밀번호 금지.

## 3. 메시지 계약 (초안)
| 메시지 | 최소 필드 | 제약 |
|---|---|---|
| JobRequest | job_id UUID, actor_id, device_id, recipe_id, recipe_version, args, submitted_at | 문자열 명령 대신 typed args, caller별 scope |
| Plan | plan_hash, target_identity, input_sha256, output_path, file_type, changes, policy_version, expires_at | 원본/스냅샷/변경량 및 영향 표시 |
| ApprovalReceipt | approval_id, plan_hash, actor_id, device_id, operator_id, expires_at, nonce | AI 비밀 유출/재사용 불가, 1회 consume |
| JobProgress | job_id, stage, heartbeat_at, bounded_metrics | 큰 문서 본문/토큰 로그 저장 금지 |
| JobResult | status, exit_reason, artifacts[{path,sha256}], validation, resource_summary | 성공과 '검증 안 됨' 분리 |
| Incident | job_id, error_code, stage, snapshot_state, remediation_status | crash 후 새 job 자동 재실행 금지 |

데이터 형식(JSON/SQLite)의 세부 필드·IPC/스키마는 코드검토 후 확정. 기존 v0.2의 tool schema를 절대 조용히 변경하지 않고 신규 도구 이름·버전으로 확장.

## 4. 영속 상태 기계
    DRAFT → INSPECTED → PLANNED → AWAITING_APPROVAL
          → APPROVED → QUEUED → RUNNING → VERIFYING
          → SUCCEEDED
    각 단계 → REJECTED / EXPIRED / FAILED / STOPPED / NEEDS_REVIEW
    RUNNING 중 불명확 종료 → UNCERTAIN → LATCHED_STOP (오프라인 확인 전 재실행 불가)

원칙:
- 승인 토큰은 단 한 건의 작업·해시·대상 경로·정확한 작업 레시피에만 유효.
- 기존 SQLite에 버전/테이블을 추가하더라도 additive migration; 이전 DB 원본 보존/백업.
- 상태 변경은 트랜잭션 + write-ahead journal + 파일백업 검증. 파일 시스템 외부 프로그램의 SaveAs는 DB와 원자적이지 않음 → 명시적 중간 상태.
- ACK 유실 시 idempotency receipt를 재조회하되 같은 쓰기를 다시 하지 않는다.
- STOP 상태에서 소켓/GUI/자식 worker 새 실행 금지. 긴급 정지 기능은 모델이 임의로 풀지 못한다.
- 출력을 검증하지 못하면 SUCCEEDED가 아니라 NEEDS_REVIEW.

## 5. 실제 실행 단계
1. 장치 및 요청자 등록, 설치된 앱/버전·활성 세션·파일 접근 정책을 읽기 전용 조회.
2. 대상 문서 식별(경로+볼륨+파일 ID+원본 해시); 수정 전후 diff 또는 객체 계획 생성.
3. 보호 백업 저장 가능 여부, 여유공간과 OS 계정/ACL 확인.
4. 별도 승인 UI에서 정확한 작업계획과 결과파일명을 확인.
5. 한 앱/세션에 한 작업, 파일 잠금 획득, 프로세스 spawn 상한과 중지/watchdog 적용.
6. 스테이징 또는 복사본만 수정하고 저장 후 다시 읽어 검증.
7. job receipt 및 검증된 새 산출물만 보고. 실제 운영 원본 교체는 별도 고위험 레시피로 분리.
8. 실패 시 불완전 결과 격리. 기존 문서·사용자 Excel/CAD/HWP 세션을 강제 종료하지 않는다.

## 6. 리소스·고장 상한 (실증 전 제안)
- 동시 GUI worker 1개/세션/앱. 대기열 최대 10. 업무파일별 단일 writer lock.
- 단계별 5~30초 소프트 타임아웃, 전체 단일 업무 180초 하드 한도(실증 결과로 조정).
- 자식 프로세스 묶음 Windows Job Object 또는 동등한 종료 감시/전체 트리 정리. 절대로 소유 증거 없이 작업관리자 프로세스를 죽이지 않는다.
- 네트워크 오류 연결 재시도 최대 3회+백오프; 쓰기 요청 자동 재시도 0회.
- 디스크/백업 용량, 메모리, CPU, 로그 크기, 워커 출력 크기 지속 점검. 임계치 도달 시 작업 시작 거부.
- 서명 안 된 레시피/미지원 버전/권한 또는 정책 파일 오류/데이터베이스 불일치 → 즉시 safe-stop.

## 7. Ubuntu/WSL2 위치
- Windows 업무 앱은 Windows 사용자 세션의 worker가 실행. WSL2 내부에서 GUI 앱을 직접 조작하는 코드는 만들지 않는다.
- Linux 전용 터널 컴포넌트가 필요할 경우 WSL2 Ubuntu는 별도의 relay/transport 역할로만 활용하고, 브로커로 전달하기 전 인증·권한 검증 유지.
- Ubuntu VM이 Windows Hyper-V 위에 있는 경우 호스트 Windows 종료 시 함께 종료됨. 24/7 서버가 필요하면 별도 물리 호스트/상시 켜진 장치로 배치.
- 인증·모바일 제공 범위가 불확실한 단계에서 WSL2/Ubuntu 추가 설치를 필수 요소로 채택하지 않는다.

## 8. 디버그 우선 지점
A-01 Named Pipe ACL/SID·브로커 실사용 권한; A-02 file identity 경합/기존 하드링크; A-03 승인 토큰 위조·재사용; A-04 단계 중 크래시·DB/출력 불일치; A-05 워커 프로세스 잔류; A-06 잠금 해제 후 레이스; A-07 다중 세션·모니터; A-08 비용/기억장치 고갈·무한 재시도.
모든 세부 재현 및 기대 결과는 SAFETY_DEBUG_MATRIX.md와 DEBUG_ISSUES.md에 연결한다.
