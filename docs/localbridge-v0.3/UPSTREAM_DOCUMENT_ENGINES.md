# 업스트림 재사용 설계: OpenCAD Studio / rhwp (2026-11-20)

상태: 설계 제안. GitHub 업스트림 문서를 확인했지만 실제 JSCPC 설치·통합·업무파일 시험은 하지 않음.
출처: 사용자 카카오톡 이미지에 등장한 "OpenCAD Studio", "rhwp". 대화 상대방의 실제 코드·성능·보안·카카오톡 연결 구현은 보지 못했으므로 추정 금지.
보호: 기존 jsc-local-commander v0.2 코드와 main 불변; design/localbridge-v0.3-20261120 문서만 변경.

## 공개 소스 확인
| 엔진 | GitHub | 기능 및 핵심 호출 | 조건/한계 |
|---|---|---|---|
| OpenCAD Studio | https://github.com/HakanSeven12/OpenCADStudio | Rust DWG/DXF native 읽기·쓰기(R14~2018), Windows portable/MSI, OpenCADStudio --mcp, --serve, audit, save_verified | GPL-3.0, AutoCAD Xref/proxy/custom entities, 글꼴, 치수 및 인쇄 호환은 샘플별 검증 |
| rhwp | https://github.com/edwardkim/rhwp | Rust/WASM HWP/HWPX 처리, rhwp mcp-serve, hwp_info/hwp_search/hwp_fill_fields, 렌더/PDF | MIT, HWP 버전별 보존·쪽배치/특수요소 호환은 실기기 검증 |
| hwp-mcp | https://github.com/treesoop/hwp-mcp | rhwp 기반 AI 편의 MCP 래퍼, 로컬 요약/치환/템플릿 채움과 업스트림 rhwp 도구 노출 | MIT, 로컬 HW PX 쓰기와 rhwp 엔진을 통한 HWP 바이너리 직접 쓰기의 기능 범위 구분 |
| python-hwpx (대안) | https://github.com/airmang/python-hwpx | HWPX ZIP XML 구조를 안전하게 부분 편집, HWP 읽기 → HWPX 저장 | Apache-2.0, HWP 원본 형식으로의 쓰기는 실험 단계 |

AutoCAD 코드를 불법 복제하거나 역공학했다는 제3자의 추측은 확인된 사실이 아니다. OpenCAD Studio의 저장소는 독립 Rust CAD 앱이라고 설명한다.

## 구조 변경 제안
ChatGPT 모바일/PC [실제 권한과 custom MCP 지원 우선 검증]
  → 인증된 원격 중계 [OAuth, 장치 페어링, 요청자 scope]
  → JSC Local Commander MCP facade (기존 v0.2)
  → 보호된 Named Pipe Policy Broker [OS ACL/SID/approval/job ID/감사/중지]
  → 등록된 typed recipe만 수행하는 별도 엔진 실행기
     → CAD : OpenCADStudio --mcp 또는 --serve
     → HWP : rhwp mcp-serve (간단한 명령은 hwp-mcp 래퍼 검증)
     → Excel : 기존 별도 Windows LocalBridge COM 합성 파일 시험 경험 재활용
     → GUI : 해당 엔진에서 불가능한 작업에 한해 제한적 UI Automation
  → 저장 결과 재열기/검증/원본 해시 불변 증명 → 결과 반환.

중요: 원격 ChatGPT에 OpenCAD Studio의 범용 명령 실행/파일 경로나 rhwp의 전체 MCP 도구들을 직접 노출하지 않는다. 기존 JSC 브로커가 등록된 작업 유형만 승인된 문서 대상으로 실행시켜야 한다. Python/Node 소스의 코드·정책 변경 권한은 워커에게 주지 않는다. GUI보다 headless API 우선.

## CAD 구현 첫 실험 (합성 파일)
1. 공식 GitHub release에서 고정 버전/OS용 바이너리 SHA256, 파일 서명/라이선스, 악성코드 위험 확인. 실사용 PC 설치 없이 별도 격리 환경.
2. OpenCADStudio --mcp에서 initialize/tools/list, ocs_read(op=capabilities), 세션 분리, 종료 및 소유 PID 검증.
3. 시험 DWG 선 객체 1개의 handle/type/layer/geometry/unit/revision 식별. 중복·모호하면 거부.
4. 정확히 지정한 객체를 1회 수정, 변경 전후 형상 비교.
5. ocs_audit 대상 DWG target_version 확인. ocs_save_verified 신규 파일만 생성, raw 참조/semantic manifest/재열기/SHA256 비교; 원본 파일 불변.
6. DWG R14~2018 범위, Xref, 프록시·동적 블록·SHX/글꼴, 표제란/치수, 레이아웃/PDF, 다른 CAD에서 재열기 회귀. 손실 시 FAIL 또는 사람 검토.

공식 상세: https://github.com/HakanSeven12/OpenCADStudio/blob/main/docs/automation/README.md

## HWP/HWPX 구현 첫 실험 (합성 파일)
1. rhwp 버전·툴 목록 및 CLI 검증. 테스트용 HWP/HWPX 두 종류(본문, 표, 누름틀, 그림, 도장 형태의 가짜 이미지, 머리말/쪽설정) 준비.
2. rhwp mcp-serve에서 info→search→정확한 위치 1건 변경→새 파일에 저장→재열기/렌더/표·서식·쪽수 비교.
3. hwp-mcp 래퍼가 제공하는 동작과 rhwp native tool의 차이 검증. HWP 바이너리 직접 쓰기는 도구/릴리스 버전과 실제 문서별 재열기 검증 전 금지.
4. HWPX는 가능한 한 수정하지 않은 ZIP 파트 불변 검사, 문단/서식/이미지/표 구조 및 PDF 시각 비교.
5. 복잡한 HWP가 온전하게 저장되지 않으면 기존 한글 COM 또는 사람 검토로 라우팅. 원본 파일 덮어쓰기 금지.
6. 의존 바이너리 자동 내려받기/버전 변경을 기본값으로 금지. 고정 SHA와 관리자 승인 후 업데이트.

참조: https://github.com/edwardkim/rhwp/blob/main/README.md
https://github.com/treesoop/hwp-mcp/blob/main/README.md

## 디버그 포인트 (모두 미실행)
| ID | 재현/관찰 | 실패 시 필수 동작 |
|---|---|---|
| OSS-D01 | 바이너리 위조·해시/서명 불일치 | 설치/실행 중지 |
| OSS-D02 | MCP 도구 이름/스키마 변화 | 설정/지원버전 오류, 자동 권한 확대 금지 |
| OSS-D03 | DWG 버전/객체 lossiness 발생 | 저장 거부, 원본 보존 |
| OSS-D04 | Xref/proxy/SHX/동적 블록 손실 | REVIEW_REQUIRED, CAD 재검증 |
| OSS-D05 | 새 CAD 프로세스 잔류·다중 세션 오선택 | 소유 PID만 정리, 사용자 창 보호 |
| OSS-D06 | rhwp HWP 바이너리 한컴 호환 실패 | 결과 격리, 기존 HWP 원본 불변 |
| OSS-D07 | HWPX ZIP 섹션·글꼴·이미지/표/쪽 나눔 변화 | 출력 실패/사람 검토 |
| OSS-D08 | 100MB 대용량 도면·복잡 문서에서 CPU/RAM/디스크 소진 | 리소스 사전 확인, 타임아웃/Job Object, 중복 0 |
| OSS-D09 | 원격 범용 MCP 호출의 임의 경로·명령 남용 | typed allowlist, 강제 broker 검증 |
| OSS-D10 | ACK 유실·2중 요청으로 동일 도면 이중 수정 | 단건 idempotency ID, write retry 0 |
| OSS-D11 | GPL-3.0 소스 배포/수정 의무 및 서드파티 라이선스 | 통합·배포형태에 맞는 라이선스 검토 |
| OSS-D12 | 상대방 시스템의 성공 주장을 현지 환경에서도 성공으로 가정 | 직접 격리 Windows 샘플에서 검증 전에는 BLOCKED |

시험 증거: 제품 버전, tag/commit, 바이너리 SHA, MCP capability schema, 회사파일이 아닌 합성 입력/출력 SHA, 오류 코드, 실행시간, 피크 RAM/CPU, 작업 소유 PID, 작업/재시도 횟수, 복구 상태. GitHub에 고객 파일, 고객 개인정보, 인증키, 원본 로그 업로드 금지.
