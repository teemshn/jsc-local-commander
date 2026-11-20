# VERSION_RELEASE_HANDOFF — v0.3 설계의 버전 관리·검증·인수인계

기준일: 2026-11-20
저장소: https://github.com/teemshn/jsc-local-commander
기준 branch: main
기준 commit: e56b9e083d1ec02652cbec7641e819b59f7fb802
문서 branch: design/localbridge-v0.3-20261120
변경 정책: docs/localbridge-v0.3/*.md 신규 파일만 추가, 기존 코드 및 main은 보존.

## 1. 기존 코드와 차기 설계의 명확한 분리
| Version label | Source location | Validated status | Change control |
|---|---|---|---|
| JSC v0.2 Security Preview | GitHub main / src/jsc_local_commander/ | Named Pipe broker, 안전한 TXT/MD/CSV 도구 11개. 실제 Windows 운영 배포 차단 | 변경 없음 |
| LocalBridge Windows Agent v0.2 (별도 시험 원형) | Windows 사용자 로컬 문서 폴더, 이 Git 저장소와 무관 | Node stdio/Excel 시험 파일 수정 실증. 프로세스 정리 수정·재시험. 보안 sandbox 아님 | 원본 소스 Git에 자동 복사/병합 금지 |
| LocalBridge v0.3 Design | 이 문서 전용 브랜치 | 문서상 목표/재현시험 초안, 코드 구현 전 | draft PR / 보안 검토 |
| v0.3.0-beta.1 (향후) | feature/adapter-* 별도 구현 브랜치 | VM/Windows 테스트 증거가 있을 때만 버전 후보 | 사람 리뷰 후 단계별 병합 |
| v1.0 (향후) | 릴리스 태그·서명된 설치파일 | 모바일 명령부터 Windows 문서 작업, 실패복구까지 통합 승인 후 | 별도 릴리스 게이트 |

기존 v0.2가 이미 완제품이라고 표시하지 않는다. v0.3 문서 파일 생성은 런타임 semver 증가/새 설치파일 생성의 근거가 아니다. GUI/UI/원격을 성공한 것처럼 README를 덮어쓰지 않는다.

## 2. 구현 브랜치/PR 명명 규칙
- 문서 디자인: design/localbridge-v0.3-20261120 (이번 브랜치).
- 공통 보안 실기기 검증: test/v0.2-windows-security-gates.
- 수정 코드는 feature/v0.3-excel-worker, feature/v0.3-hwp-worker, feature/v0.3-cad-worker, feature/v0.3-gui-worker, feature/v0.3-remote-transport처럼 독립.
- 버그 수정: fix/v0.3-LB-###-short-description.
- 기본 변경은 한 기능/한 보안경계/한 PR. 기존 main에서 생긴 최신 수정사항은 PR 전 재검토, 강제 push 금지.
- docs/ 버전 폴더는 기존 v0.2 문서를 지우거나 이동하지 않고 병존.
- 라이브 설정, .env, 운영 DB, 백업/로그, 토큰/인증키, 실제 고객 문서는 Git 추적 금지.

## 3. 앞으로의 실제 개발 순서
| Milestone | 선행조건 | 구현 범위 | 완료 판단 |
|---|---|---|---|
| M0-PLAN | 지금 이 문서 PR | 보안/앱/인증/모바일 설계 검토 및 미확정 질문 정리 | 승인된 설계/PR |
| M1-SEC | 기존 v0.2 보안 감리 | 실제 Windows VM에서 ACL/Named Pipe/TOCTOU/34개 보안 시나리오 | 실기기 증거/안전 서명 |
| M2-EXCEL | M1 | signed recipe + 전용 Excel worker, 독립 실행·복사본 검증 | EX-D* 및 필수 APP-* PASS_VM |
| M3-HWP-CAD | M1 + 실제 설치버전·라이선스 검사 | 문서별 COM/API 워커를 각각 독립 검증 | HWP-D*, CAD-D* PASS_VM |
| M4-GUI | M1 + 세션/계정 격리 설계 합격 | UIA 제한 레시피, 잠금/팝업/중지 | GUI-D* 및 GUI-* PASS_VM |
| M5-REMOTE | 실제 모바일 MCP 사용 권한 G0 + M1 | 인증된 outbound 중계/승인/상태조회 | REM-* + 모바일 실기기 최소 2회 검증 |
| M6-PRODUCT | M2~M5 통과 | 설치·업데이트·제거·서명·롤백·문서화 | 전 과정 격리/스테이징 검증 |

M5 권한 검증 G0는 M1의 구현과 병행할 수 있지만, 권한 미확인 상태에서 외부 네트워크를 개방하거나 유료 서비스를 신청하지 않는다. G1/M1 통과 전 실사용 Windows에 worker 코드 설치/연결 금지.

## 4. PR 필수 리뷰 체크리스트
- [ ] 실제 main HEAD·branch·WIP 확인. origin/main 업데이트와 충돌 여부 점검.
- [ ] 변경 파일은 계획된 전용 모듈/문서에 국한, 운영 데이터/기존 설정 불변.
- [ ] 정책/툴 이름/스키마 변경 시 기존 11개 MCP 도구 회귀 확인.
- [ ] 서명/해시·OS 사용자/ACL/Named Pipe 위험 검토.
- [ ] 정적 문법 검사, 단위/통합/악성 입력, API GUI 무응답·작업 강제종료 시험.
- [ ] 기능 모듈별 DEBUG_ISSUES 항목과 TEST ID, 실패 증거, 변경 커밋 연결.
- [ ] 기존 프로세스·파일/DB·원본 해시·체크포인트 보존 확인.
- [ ] 작업 시간·큐·재시도·CPU/RAM/디스크·로그 크기 상한 확인.
- [ ] 사용자 직접 승인과 모델 실행 권한이 분리됨을 테스트.
- [ ] 사용자가 실제 모바일로 도구를 호출했는지 G0 증거로 확인(스크린샷 대신 비밀 마스킹된 최소 메타데이터).
- [ ] 코드를 잘못 실행해도 즉시 멈출 수 있고 복구 경로가 검증됨.
- [ ] 실제 운영 배포는 별도 명시 승인 전 금지.

## 5. 각 이슈 처리와 체크포인트
1. DEBUG_ISSUES.md에서 Issue ID 등록 또는 현 상태 갱신.
2. 테스트용 합성 자료와 기준 VM 체크포인트/로컬 보호본 확보 (이름+해시/복원검사).
3. 재현/근본원인/수정/회귀시험 각각 별도 commit. 동일 job 1회 이상 반복 실행 시 idempotency 증거.
4. 서식/도면 비교는 변경 전후 구조적 diff + 필요시 사람이 시각검토.
5. 실패한 후속 작업은 STOPPED/NEEDS_REVIEW, 장애 원인을 제거하기 전 자동 승인·자동 재시도 금지.
6. 빌드 성공·CI 성공·Windows VM 성공·실사용 성공을 각각 별도 상태로 보존.
7. 배포파일 버전/commit/SHA256 및 설치·제거·복구 테스트 증거가 없는 버전은 release 불가.

## 6. 개인 무료 백업 전략
- 코드: GitHub 공개 저장소의 설계문서와 소스 코드/커밋 히스토리. 인증정보, 실제 프로젝트 파일은 제외.
- 백업: 원본·수정본/DB/환경 checkpoint 중 개인정보가 있는 것은 회사 정책·접근권한에 맞는 별도 보호 저장소.
- Google Drive 같은 무료 개인 저장소를 사용할 경우에도 승인되지 않은 회사 문서/자격증명·기존 사용자 파일은 업로드하지 않는다.
- 무차별 체크포인트 보관으로 디스크가 고갈되지 않도록 용량 예산/보존 기간/수동 복구 절차를 확정한다.
- ZIP/스냅샷만 만들었다고 복구 가능으로 판단하지 않고 최소 1회 복원시험·무결성 확인.

## 7. 현재까지 검증한 것과 아직 검증 전인 것
- [확인] GitHub main v0.2 보안 프리뷰에는 텍스트 파일 도구 11개, 분리 broker, 사전 안전 게이트가 있음.
- [확인] docs/VALIDATION.md는 필수 34개 실제 배포 시나리오 미완료를 명시.
- [이전 별도 로컬 시험] Node.js 스탠드얼론 LocalBridge 샘플 Excel B2 수정→새 XLSX→SUM 수식 검증, 본인 프로세스만 정리 실증.
- [미검증] 로컬 Node 구현을 기존 Python broker 계정/ACL/승인 경계에 통합하는 방법.
- [미검증] 실제 HWP, AutoCAD API 편집; 제품 에디션·라이선스·폰트/Xref·문서 서식 정확도.
- [미검증] 로그인 세션/잠금 GUI 자동화·권한 및 작업 종료 안정성.
- [미검증] 현재 ChatGPT 모바일·계정에서 자체 custom MCP 실행/쓰기 지원 및 비용.
- [미검증] 임의 Python/Node 코드가 아닌 안전 설치파일로 실제 업무 PC에 배포하는 과정.

## 8. 새 개발자 / 새 ChatGPT 채팅 인수인계
- 시작점: 이 저장소 main과 이 design branch의 차이. 현재 main commit e56b9e083d1ec02652cbec7641e819b59f7fb802에서 디자인 브랜치 생성.
- 먼저 읽을 파일: README.md, SECURITY.md, docs/REVIEW_V02.md, docs/VALIDATION.md, docs/SECURITY_ARCHITECTURE.md → docs/localbridge-v0.3/README.md → PROJECT_SPEC.md → ARCHITECTURE.md → 작업 대상 ADAPTER → SAFETY_DEBUG_MATRIX.md → DEBUG_ISSUES.md.
- 공통 협업 규칙: https://github.com/teemshn/work-automation/blob/main/AGENTS.md 및 standards/GIT_WORKFLOW.md.
- 다음 행동: 설계 PR 검토, 미확정 G0/G1 실증, 구현 전 브랜치/권한/합성자료·백업 환경 확정. 별도 로컬 프로젝트 코드를 검증 없이 main에 복사하지 않음.
- 변경이 일어난 이후에는 README/버전표/이슈/게이트/작업인수인계/실제 커밋을 함께 갱신해야 한다.

마지막 원칙: 안전성 미확보 상태는 진척률을 높여 보이기보다 차단 요인과 테스트 필요성을 정확하게 남긴다.
