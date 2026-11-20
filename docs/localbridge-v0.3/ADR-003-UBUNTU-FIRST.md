# ADR-003: Ubuntu-first LocalBridge 통합 자동화 아키텍처

- 날짜: 2026-11-20
- 상태: **방향 확정, 구현·실기기 검증 전**
- 관련 설계: PROJECT_SPEC.md, ARCHITECTURE.md, UPSTREAM_DOCUMENT_ENGINES.md, KAKAO_INTAKE_CLASSIFICATION.md
- 이 문서가 정의하는 **운영 대상 변경**: Windows GUI 우선 → **Ubuntu 상주 엔진 우선**
- 범위: 우선 제품으로 Windows Agent/Excel COM/AutoCAD COM/HwpObject를 요구하지 않음. 기존 Windows 설계는 필요 시 호환성·비상용 대안으로 보존.
- 저장소: 기존 main/v0.2 소스 변경 금지. 이 설계만 문서 전용 design 브랜치/PR에 추가.

## 1. 사용자 목표
모바일·PC의 ChatGPT 대화창에서 자연어 업무 명령을 받으면 Ubuntu에서 직접 업무자료를 접수·분류·조회·편집·검증·저장하고 결과를 반환한다. Windows PC를 화면으로 조작하는 방식과 Desktop Commander를 최종 제품의 필수 조건으로 사용하지 않는다. 업무 자료의 원본 및 개인·회사 자격증명을 보존한다.

중요: ChatGPT 모델의 추론은 원격 ChatGPT 서비스에서 이루어진다. "모든 것이 Ubuntu에서"란 **파일·자동화·작업 제어 엔진이 Ubuntu에서 실행**된다는 의미이고, ChatGPT 서버도 Ubuntu에서 실행된다는 뜻은 아니다.

## 2. 목표 아키텍처
```text
[휴대폰/PC ChatGPT]  (지원권한·모바일 write capability 미검증)
         |
[인증된 원격 MCP Gateway / outbound 터널] (미구현)
         |
[Ubuntu LocalBridge Hub]
  ├── Actor/Device 정책, 사용자별 승인, 비밀키 격리
  ├── Durable Job Queue + Checkpoint DB(SQLite) + 감사 + 긴급정지
  ├── 읽기/계획/승인/실행/사후 검증 분리
  ├── 문서 엔진 제한 실행기 (버전·해시 고정, sandbox)
  │     ├── DWG: OpenCAD Studio --serve / --mcp
  │     ├── HWP/HWPX: rhwp mcp-serve 또는 승인된 hwp-mcp
  │     ├── XLSX: openpyxl/LibreOffice headless (파일별 검증)
  │     └── PDF/OCR: Ubuntu CLI/라이브러리 (합성 데이터로 검증)
  ├── Inbox/File Watcher → 분류 → 작업별 보관/색인
  └── 결과 문서/도면 + 메타데이터 + SHA256 + 검증 보고서
```

핵심: 문서 엔진은 최초 단계에서 로컬 stdio IPC로 호출한다. OpenCAD의 TCP/HTTP 모드는 네트워크 노출, 인증/권한 제어가 준비되기 전 사용하지 않는다. 범용 실행/파일경로/MCP 도구를 모델에 직접 개방하지 않는다.

## 3. 운영체제별 실제 역할
| 자원 | 신규 기본 용도 | 필수 여부 |
|---|---|---|
| Ubuntu 24.04 서버/VM | 상시 LocalBridge 실행, 문서·도면 편집·분류·결과 저장 | 필수 |
| Windows PC | 합성 결과의 Excel/AutoCAD/한컴 호환성 교차 검증, 미지원 고유 기능 수동 처리 | **선택** |
| WSL2 | Windows 호스트에서 Linux 앱을 간단히 돌리는 대안 | **불필요**, 이미 Hyper-V Ubuntu VM이 있음 |
| 기존 Hyper-V Ubuntu VM | 초판 기능/프로토콜/보안 실험 환경 | 사용 가능하지만 해당 Windows 호스트가 꺼지면 VM도 종료 |
| 별도 물리 Ubuntu 장치 | 24시간 운영, 사용자의 Windows를 끄고도 요청을 받는 완성 운영 형태 | 상시 운영이 목표라면 권장 |

구축 초기에는 현재 Ubuntu VM에서 **읽기 전용 샘플 실험**을 진행. Windows 호스트 안전 감시와 VM baseline checkpoint를 유지하고 기존 SSH/키, 가상 네트워크·방화벽은 사용자 승인 없이 변경하지 않는다.

## 4. Linux 네이티브 엔진 재사용
| 서식/작업 | 우선 엔진/방법 | 첫 실기기 검증 | 불합격 시 |
|---|---|---|---|
| DWG/DXF | https://github.com/HakanSeven12/OpenCADStudio (Rust, GPL-3.0). Linux 릴리스, --serve(headless)/--mcp, audit/save_verified | 파일 안에 선 1개를 만든 합성 도면, 객체 변환·재열기, 단위/버전/레이어/도면 해시 검사 | NEEDS_REVIEW, 원본 보존; AutoCAD 등으로 선택적 교차검증 |
| HWP/HWPX | https://github.com/edwardkim/rhwp (MIT), rhwp mcp-serve; hwp-mcp(옵션, MIT) | 합성 본문/표/누름틀 문서에서 한 곳만 수정 후 원본/쪽/표/글꼴/이미지 비교 | 지원 안 되는 구조는 미지원, 한컴 교차검증 또는 수동 |
| XLSX | Python openpyxl 등으로 사본만 편집; 계산 결과가 필요하면 LibreOffice Calc headless/UNO | 다중시트·공사내역서 모사 수식·서식·호표 및 참조의 전후 비교, 결과 Excel로 재검증 | 신뢰할 수 없는 자동 재계산 금지, 검토 상태 |
| PDF | Linux PDF 추출/렌더/생성 라이브러리 | 페이지 순서/서식/텍스트·한글 폰트 확인 | 암호/스캔·OCR 오류는 보류 |
| 분류 | 지정된 Inbox 감시, 파일 메타·본문·규칙 기반 사업명/문서종류 추정 | 중복파일·유사 공사명·다중 사업·손상 파일 합성 시험 | 자동 분류 확정 금지, 검토함 |

### 중요 호환성 주의
- OpenCAD Studio가 DWG 읽고 쓰기를 지원한다고 모든 AutoCAD 특수 객체, Xref, 동적블록, CTB/STB, 치수/출력 호환을 보장하지 않는다.
- rhwp가 HWP5 편집·저장을 지원한다고 법적 계약서의 쪽나눔/표/도장/서식이 한컴과 완전히 동일하다고 단정하지 않는다.
- LibreOffice가 XLSX를 열고 저장한다고 Excel 공식·매크로·피벗·인쇄설정·외부링크까지 똑같이 재계산된다는 뜻이 아니다.
- 초기 MVP는 한 문서당 단 하나의 허용된 변경을 수행하며 원본 파일은 덮어쓰지 않는다.

## 5. KakaoTalk 수집과 Ubuntu 처리의 정확한 분리
- 사용자 개인/단체 채팅 내용을 과거분까지 자동 조회하는 공개 카카오 API는 없다. 계정 우회/비공식 로그인 스크래핑을 핵심 기능에 포함하지 않는다.
- **MVP**: 스마트폰/PC 카카오톡에서 사용자가 업무파일을 명시적으로 전달 또는 저장 → Ubuntu Inbox(SFTP/브라우저 업로드/승인된 공유 디렉터리) → Ubuntu가 분류한다.
- **자동화 2단계**: Windows 다운로드 폴더의 허가된 파일만 Ubuntu Inbox로 전송하는 얇은 동기화 도구가 선택적으로 필요할 수 있다. 이것은 Windows 문서 편집 에이전트가 아니라 단방향 인박스 송신기이다.
- **선택 공식 채널**: 카카오톡 채널/챗봇에서 공식적으로 수신 가능한 신규 요청만 API 연동. 개인톡 자동 수집과 혼동 금지.
- 완전한 'Ubuntu만 가동' 상태에서 개인 PC 카카오톡 신규 첨부 자동 전달까지 무인 처리하려면 **별도 지원 수신 경로**가 필요하다. 이는 현재 기능 미검증 및 차단 조건이다.

## 6. 안전/복구 설계 (구현 전 테스트 필수)
1. 비신뢰 문서 내용이 "명령을 실행하라"고 해도 시스템 명령으로 승격하지 않는다.
2. Tool allowlist와 정확한 작업 레시피 ID, 대상 파일 ID/해시/수정 범위, 별도 승인 receipt를 검사.
3. 원본 변경 거부: 읽기 전 원본 해시, 스테이징 사본에서 1회 수정, 새 이름으로 저장, 재열기 및 비교.
4. 작업별 잠금 + 영속 idempotency key; 변경 명령 자동 재시도 **0회**. ACK 분실은 상태 재조회만.
5. 하드 타임아웃, 자식 프로세스 트리 소유 확인, CPU/RAM/디스크/출력/로그 한도. 비정상 종료 시 UNCERTAIN + 안전 정지.
6. 작업큐 초기 상한 10건/동시 문서 편집 1건. 상한 변경 전 벤치마크와 메모리 감시 필수.
7. 파일·프로세스·네트워크 권한: 별도 Linux 사용자, 실행 가능한 바이너리 고정, 승인된 Inbox/Work/Outbox 범위, 프로세스별 제한, outbound 기본 차단(공식 인증 갱신은 별도 승인).
8. 컨테이너/프로세스 격리만으로 보안을 입증했다고 판단하지 않는다. 적대적 파일/권한/심볼릭 링크/파일 핸들 경합을 실기기 시험.
9. 로그에 계약서 본문·인증토큰·고객 개인정보를 남기거나 GitHub에 업로드하지 않는다.
10. 체크포인트/백업은 버전·해시·복구 검증 기록이 있어야 완료. 일정 디스크 여유 미달 시 새 작업 중지.

## 7. 구현 단계·디버그/수용 게이트
| 단계 | 할 일 | 실패 관찰 포인트 | 합격 기준 |
|---|---|---|---|
| U0 | Ubuntu VM의 자원/네트워크/현재 작업 상태 읽기 | VM 디스크/host RAM 위험, snapshot 보존 | 읽기전용 점검 및 백업 보존 |
| U1 | 상위 문서 엔진 바이너리 출처/라이선스/버전/해시 고정 | Linux 실행 의존성, glibc, GUI 필요, 프로세스 hang | 독립된 10초 내 버전·기능 목록 조회, 시간초과 안전종료 |
| U2 | rhwp HWPX/HWP 합성파일 읽기→한 곳 변경→새 문서 저장 | 표/폰트/쪽수/바이너리 손실 | 원본 해시 동일·수정 문장만 반영·재열기 가능 |
| U3 | OpenCAD headless 합성 DWG read/edit/save_verified | 오프스크린 그래픽 의존, 손실 보고, 좌표/단위·Xref | 실기기에서 출력 검증·재열기·객체 diff |
| U4 | XLSX+Calc/LibreOffice A/B 검증 | 계산 결과/호표/숨김 시트/인쇄 영역 차이 | 실제 Excel과 비교표, 불일치 시 REVIEW_REQUIRED |
| U5 | Ubuntu Inbox 자동분류 | 임시 다운로드 이벤트·중복·오분류·악성 파일 | 중복 실행 0, 검토함·원본 불변 |
| U6 | Ubuntu 안전 브로커/승인·작업큐/중지 | IPC 권한·요청 위조·루프·timeout | 소유 작업 안전중지·복원·감사·중복 0 |
| U7 | ChatGPT 모바일 원격 호출·인증 | custom MCP 모바일 권한·OAuth/터널 정책/요금 | **실제 모바일**에서 읽기도구 → 승인된 사본 변경 순서로 통과 |
| U8 | 24시간 운영 이전·재부팅/복구 검증 | Hyper-V 호스트 종료/전원·오프라인 상태 | 전용 Ubuntu 장치 + 복구/오프라인 정책 확인 |

원칙: U1-U4의 합성 문서 실험과 U7의 ChatGPT 계정 지원 가능성 검증은 병행 가능. 실제 업무 파일은 U6과 사본 승인 검증 전까지 접근하지 않는다.

## 8. v0.3 Windows 관련 기존 설계와 충돌 처리
- 이 ADR이 **현재 채택한 'Ubuntu-first 실행 환경'의 우선 방향**을 명시한다. 이전 ARCHITECTURE.md, HWP_ADAPTER.md, CAD_ADAPTER.md, GUI_WORKER.md의 Windows 전용 런타임은 **호환성 폴백 및 기술 참고**이며 Ubuntu MVP의 필수 구성 요소가 아니다.
- GitHub v0.2 Python Windows broker를 Linux에서 *그대로 실행할 수 있다*고 가정하지 않는다. Named Pipe/Windows ACL/SID 정책에 의존하므로 OS별 권한/IPC/실행기 새 포팅 및 설계 검증이 필요하다.
- Windows LocalBridge Node v0.2의 Excel COM 샘플 결과를 Linux 엔진 성공으로 간주하지 않는다.
- 모바일/PC ChatGPT 화면에서 승인된 도구를 실제로 호출해 검증하기 전까지 "원격 연결 완료"라고 표시하지 않는다.
- 이 문서만으로 구현, 기존 코드 교체, main merge, 새 서비스/포트 설치 또는 Linux 설정 변경은 승인되지 않는다.

## 참고 출처 (2026-11-20 검토)
- OpenCAD Linux/MCP/verified save: https://github.com/HakanSeven12/OpenCADStudio/blob/main/README.md
- OpenCAD automation: https://github.com/HakanSeven12/OpenCADStudio/blob/main/docs/automation/README.md
- rhwp Linux CLI/MCP: https://github.com/edwardkim/rhwp/blob/main/README.md
- hwp-mcp wrapper: https://github.com/treesoop/hwp-mcp
- LibreOffice Calc 26.2: https://books.libreoffice.org/en/GS262/GS26203-GettingStartedWithCalc.html
- 카카오 수집 제약: KAKAO_INTAKE_CLASSIFICATION.md의 공식 Kakao DevTalk/개발 문서 링크
