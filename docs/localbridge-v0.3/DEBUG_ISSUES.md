# DEBUG_ISSUES — v0.3 설계·디버그 이슈 관리 원장

상태: 2026-11-20 최초 등록. 이슈 상태 NOT_VERIFIED / OPEN / BLOCKED / OBSERVED_LOCAL / RESOLVED_VM / VERIFIED_STAGING를 구분하며, '설계됨'은 '수정됨'이 아님.

## 1. 우선순위
P0 = 사용자 원본 손상/권한 상승/무한 실행/인증 우회/안전중지 실패
P1 = 문서 내용·도면 정확성/서식 손상/프로세스 잔류/모바일 연계 실패
P2 = 사용성·성능·진단/로그 품질. P0 미해결이면 운영 배포 금지.

## 2. 초기 이슈 등록 (현재 GitHub v0.2의 제약과 로컬 프로토타입 관찰을 구분)
| Issue ID | 심각도 / 상태 | 원인 가설·근거 | 재현·관측할 항목 | 해결·통과 조건 |
|---|---|---|---|---|
| LB-001 | P0 OPEN | v0.2 broker 별도 계정·NTFS ACL은 실기기 검증 전 | 두 Windows 계정, effective_access, 설정/코드 덮어쓰기 | gateway의 임의 broker/정책 수정 불가 |
| LB-002 | P0 OPEN | Named Pipe ACL·SID/pipe squatting 잔여 위험(기존 REVIEW_V02) | 위조 pipe 및 다른 사용자 접속 | 인증된 ID만 접속 |
| LB-003 | P0 OPEN | path 검사·rename/symlink/hardlink 경합(기존 SECURITY) | 핸들/볼륨/file_id 전후 추적 | 허용 경로 밖 영향 0 |
| LB-004 | P0 OPEN | mid-save crash·DB applying 기록과 산출물 불일치 | kill 지점 4가지, DB 및 파일 hash | uncertain 시 latch stop/재실행 0 |
| LB-005 | P0 OPEN | GUI 작업을 broker 동일 사용자·권한으로 실행하면 격리 무력화 | 사용자 토큰·Session ID/ACL, test app | 등록된 저권한 worker만 앱 제어 |
| LB-006 | P0 BLOCKED | 모바일 ChatGPT custom MCP 쓰기 권한 실제 미확인 | 실제 기기/플랜/UI/도구 결과 | 모바일에서 자체 read/tool 1회, 이어 승인된 write 실증 |
| LB-007 | P0 OPEN | 중계/모바일 인증 토큰·장치키 유출/재사용 | OAuth audience/scope/nonce/rotation | 다른 사용자·장치/재생 공격 100% 거부 |
| LB-008 | P0 OPEN | 워커 하드 중단/CPU·RAM·디스크 폭주 | synthetic hang, child process, quotas | 제한시간/자원/예산 내 정지·복구 |
| LB-009 | P0 OPEN | AI와 앱이 동일 파일에 동시 쓰기 | file lock/file id, hash drift | 레이스 시 변경 0·uncertain 상태 |
| LB-010 | P1 OBSERVED_LOCAL | 별도 Node 프로토타입 최초 Excel COM 후 숨은 EXCEL.EXE 잔류 관측; 프로토타입에 한정해 소유 PID 정리 검증 | 사용자 엑셀 PID와 worker pid, 수식/값 | GitHub broker 연동 후 다시 전용 PID 소유/종료 실증 |
| LB-011 | P1 OPEN | Excel 시트/공식/서식/호표 영향 과소평가 | calc mode, formula references, hidden sheets | 대상 외 구조 보존·합계 검증 |
| LB-012 | P1 BLOCKED | 설치된 한글 정확한 버전 및 라이선스·보안 승인모듈 검증 전 | app version, HwpObject capabilities, approval popup | 합성 문서 열기/SaveAs/문자/표/쪽 검증 |
| LB-013 | P1 OPEN | HWP 표/쪽나눔/도장/그림 등 변형 가능 | page count, paragraph/table structure, PDF render | 대상 외 내용·서식 동등 확인 |
| LB-014 | P1 BLOCKED | 설치된 CAD 에디션과 ActiveX 조작 가능 범위 미검증 | product edition, COM methods, license | 합성 DWG 객체 1개 이동/재열기·좌표 검증 |
| LB-015 | P1 OPEN | CAD UCS/WCS·INSUNITS·동적 블록/외부참조 | entity fingerprint/unit/layer/xref | 좌표/레이어/물량/외부참조 원본 비교 |
| LB-016 | P1 OPEN | Windows 잠금/로그오프/RDP/UAC에서 GUI 조작 실패 | session_id/UIA tree/HWND/locked | 불확실 화면에서 마우스·키보드 입력 0 |
| LB-017 | P1 OPEN | 기존 고객 문서나 열린 창에 실수로 연결 | before app PID, opened documents | 사용자 열려 있던 문서 0변경 |
| LB-018 | P1 OPEN | ACK 유실/오프라인 후 동일 명령 반복 | job_id, receipt, pending queue | 모든 승인된 수정 최대 1회 |
| LB-019 | P1 OPEN | Libre/office/HWP/CAD에서 locale·글꼴·내보내기 버전 차이 | locale, app version, output format | 기능지원 표에 맞는 결과만 성공 |
| LB-020 | P1 OPEN | 오래된 보호본/체크포인트 관리로 디스크 고갈 | storage budget, retention, backup restore | 회전/보관 규칙·복구 리허설 통과 |
| LB-021 | P1 OPEN | 인터넷/터널/플러그인 이용권 변화 | official support date, client features, pricing | 별도 비용 없이 가능 여부 또는 block 명시 |
| LB-022 | P2 OPEN | 로그에 민감한 계약 내용/파일 경로 저장 | redacted logs, capture policy | 필수 메타만 기록, 비밀값 0 노출 |

주의: LB-010의 로컬 관측은 별도 LocalBridge Node v0.2 샘플에서 수행한 것이며 이 GitHub 저장소의 버그가 재현됐다는 의미가 아니다. 로컬 버전의 '수정됨' 상태를 그대로 GitHub Python broker에 적용하면 안 된다.

## 3. 각 설계/결함 업데이트 필수 필드
새 이슈마다 다음을 빠짐없이 기록한다.
- issue_id / module / severity / status / owner / opened_at / updated_at / next_action
- 관련 Git SHA, branch, recipe/version, Windows/앱 버전, 테스트용 계정 SID(마스킹)
- 재현 자료 생성 코드/원본 해시, 초기 실행 상태/열려 있는 창·작업, 재현 정확한 순서
- expected vs actual, 에러 코드·exception class·관측 로그·프로세스/메모리·디스크 사용
- 작업의 영향을 받은 폴더/파일 수, 원본 불변 검증, 복구 방법/체크포인트
- 근본원인 가설 vs 검증된 원인(분리!), 대안, 수정 Commit/PR, 신규 회귀시험
- 해결 승인자, PASS_VM/PASS_STAGING 결과, 위험 재평가. 테스트 미실행/실패면 완료 상태 금지.

## 4. 디버그 운영 방법
1. 새 실패 → 운영 작업 자동 재시도 금지 → 사건 상태 기록/필요시 긴급중지.
2. 재현에 필요한 로그만 마스킹하고 합성 복사본/격리 VM에서 최대 횟수 1~3회 재현.
3. 실패한 단계의 입력·정책·실제 앱 상태를 분리해 원인 확인. 지원하지 않는 API/UI는 추측 클릭으로 우회하지 않는다.
4. 단일 변경 브랜치에서 수정을 테스트. 동일 원인 회귀 + 반례 + 기존 34개 필수 시나리오 영향 검토.
5. 해시·영향·복구 성과가 확인되면 리뷰 후 VERIFIED 상태로 변경. 잘못된 '완료'를 되돌릴 수 있도록 테스트 증거/코드 SHA 보존.

## 5. 긴급 중지와 복구 절차
- crash/hang/무한반복: Windows Job Object/서명된 워커 프로세스 소유 확인 후만 중지. 이미 수행된 문서 작업을 자동으로 재실행하지 않는다.
- backup/DB/설치파일 모두 안전한 위치·ACL로 관리. 실제 비밀키·업무 원본은 GitHub로 이동 금지.
- 원본/후보 출력 SHA가 승인 계획과 일치하는지 오프라인 검증. 불일치 파일을 덮어쓰기 복원하지 말고 사람 검토.
- 승인자와 작업요청 AI를 동일 권한으로 두지 않는다.

## 6. 항목별 교차 참조
- LB-001~009: ARCHITECTURE.md + SAFETY_DEBUG_MATRIX.md
- LB-010~011: EXCEL_ADAPTER.md
- LB-012~013: HWP_ADAPTER.md
- LB-014~015: CAD_ADAPTER.md
- LB-016~017: GUI_WORKER.md
- LB-018,021: REMOTE_MOBILE.md
- LB-019,020,022: SAFETY_DEBUG_MATRIX.md + VERSION_RELEASE_HANDOFF.md
