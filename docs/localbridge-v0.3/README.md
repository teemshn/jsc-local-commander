# LocalBridge Windows 업무자동화 확장 — v0.3 설계 인덱스

- 문서 상태: DESIGN / NOT IMPLEMENTED / NOT APPROVED FOR PRODUCTION
- 기준일: 2026-11-20
- 기존 코드 기준: jsc-local-commander main @ e56b9e083d1ec02652cbec7641e819b59f7fb802
- 작성 위치: design/localbridge-v0.3-20261120 브랜치, docs/localbridge-v0.3/ 아래 신규 문서 전용
- 변경 금지: main 코드, 기존 README/SECURITY/테스트, 운영 설치, 기존 계정·인증·로그·데이터
- 원칙: 별도 문서 PR 검토 후 후속 구현 브랜치에서 하나씩 개발. 이 설계가 통과 테스트를 뜻하지 않음.

## 최종 사용 목적
휴대폰 또는 PC의 ChatGPT 대화에서 작업 지시 → 인증된 PC에서 내용·프로그램 확인 → 권한·작업 범위 승인 → Excel/HWP/DWG/업무 프로그램 실행 → 원본 보존·수정본 생성 → 기계적/시각적 검증 → 모바일/PC 대화에 결과 반환. Desktop Commander 런타임 의존 없음.

## 반드시 구분할 세 가지 버전
| 명칭 | 실제 상태 | 배포 및 안정성 |
|---|---|---|
| JSC Local Commander v0.2 (GitHub) | Python stdio facade + 분리된 Windows Named Pipe broker, TXT/MD/CSV 파일 작업 11도구. 34개 실기기 검증 조건은 미완료 | 보안 프리뷰, 실제 업무 PC 배포 금지 |
| LocalBridge Windows Agent v0.2 (로컬 시험) | 별도 Node.js MCP stdio 시험 구현, 샘플 XLSX 한 셀 수정과 복사본 저장 실증. GitHub에 해당 소스 병합되지 않음 | 로컬 프로토타입, 격리/보안 합격 아님 |
| JSC Local Commander / LocalBridge v0.3 (이 문서) | 기존 v0.2를 기반으로 Windows 문서작업·승인·원격 제어를 확장하기 위한 미래 설계 | 문서 초안, 구현 및 검증 전 |

v0.3은 설계 대상 버전 이름이지 현재 배포 버전 번호가 아니다. 구현 태그/릴리스는 별도 검증 및 명시적 승인 후 부여한다.

## 설계 문서 지도
1. PROJECT_SPEC.md — 사용 사례, 범위, 요구사항과 실사용 합격 기준
2. ARCHITECTURE.md — 프로세스/권한 분리, IPC, 작업 상태·승인·정지
3. EXCEL_ADAPTER.md — Excel 전용 워커 및 수식·원본 보존 디버그
4. HWP_ADAPTER.md — 한글 HWP/HWPX COM 및 보안 팝업·서식 디버그
5. CAD_ADAPTER.md — AutoCAD DWG 객체·좌표·외부참조 검증
6. GUI_WORKER.md — UI Automation·세션 잠금·팝업·오작동 방지
7. REMOTE_MOBILE.md — ChatGPT 모바일 가능성 검증, 인증/터널, 오프라인 작업
8. SAFETY_DEBUG_MATRIX.md — 공통 34개 기존 시험 계승 + 신규 안전/장애 시험
9. DEBUG_ISSUES.md — 항목별 재현 가능 버그 레지스터, 관측 필드 및 미해결 이슈
10. VERSION_RELEASE_HANDOFF.md — 브랜치, 릴리스 게이트, 단계, 인수인계

## 설계 원칙 (변경 불가)
- AI 발화는 권한·로컬 승인으로 취급하지 않는다. 모델/파일 안의 지시문도 불신 입력.
- 기존 Python facade/broker 격리 경계를 우회해 Windows 문서 프로그램을 직접 실행하지 않는다.
- GUI/COM 워커는 전용 사용자 세션·별도 작업 프로세스·제한된 폴더/토큰을 사용하고, OS 수준 권한을 먼저 검증한다.
- 실제 회사 파일 대상 실험 금지: 합성 샘플만 사용. 기존 업무 폴더 등록은 안전 시험 이후 별도 승인.
- 기본 읽기 전용. 실제 변경은 해시·대상·행위·영향이 묶인 단기 1회 승인과 원본 보존 후 실행.
- 저장 성공과 작업 성공은 다르다. 파일 재열기/수식·객체·쪽수 등 검증 불합격이면 실패 또는 검토필요.
- 명령·UI·네트워크 재시도는 유한, 타임아웃·큐·로그 용량·디스크/RAM·동시성 상한 필수.
- 중복 실행·응답 유실·비정상 종료 시 변경 작업 자동 재송신 금지. 승인 전 재실행 금지.
- 긴급 정지는 새 작업 차단, 허용 범위 내 자식 작업 중지, 미확정 상태 잠금. 원상복구는 결과 확인 후 수동.
- 코드/로그/체크포인트와 비밀키·실제 계약서/설계도면을 GitHub에 올리지 않는다.

## 변경 단계와 게이트
| 단계 | 내용 | 통과 조건 |
|---|---|---|
| G0 | 실제 ChatGPT 모바일/웹 경로와 계정 권한 조사 | supported client와 쓰기 호출 1회 실증. 불가능하면 차단 이슈로 유지 |
| G1 | 코드/ACL/Named Pipe/경합/복구 VM 검증 | 기존 SECURITY.md, VALIDATION.md의 34개 요구 시나리오에 대한 증거 |
| G2 | Excel 합성 파일 워커 | 기존 사용자 Excel 보호, 저장후 재검증, 중지/잔류 프로세스 실험 |
| G3 | HWP·DWG 합성 파일 워커 | 대상 버전/API/라이선스 확인, 원본 불변, 출력 검증 |
| G4 | GUI 제한 세션 워커 | 화면 잠금/팝업/UAC/예상 밖 UI에서 중단 |
| G5 | 인증된 원격 전달 | 모바일 실기기 명령 → 장치 인증 → 승인 → 안전 시험 도구 → 결과 |
| G6 | 설치·업데이트·롤백·제거 | 기존 사용자 파일 보존, 테스트/로그/복구 리허설 완료 |

G0, G1을 건너뛰어 실제 업무 프로그램 제어에 연결할 수 없다. 설계 검토 자체는 병행 가능.

## 현재 확인된 사실과 근거
- GitHub 원본: README.md, SECURITY.md, docs/REVIEW_V02.md, docs/VALIDATION.md, docs/SECURITY_ARCHITECTURE.md.
- AutoCAD ActiveX: https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-ActiveX-Reference/files/GUID-ED0D0B02-25FC-4ED2-9DEE-2B0C9AA9416A.htm
- 한글 오토메이션: https://developer.hancom.com/en-us/hwpautomation
- Windows UI Automation: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview
- ChatGPT 사용자 지정 MCP: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt

## 사용·배포 상태
본 브랜치의 문서는 설계와 재현 시험 계획이며 로컬 설치, 서비스 실행, 방화벽 변경 또는 라이브 데이터 조작을 수행하지 않는다.
