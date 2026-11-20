# SAFETY_DEBUG_MATRIX — 보안·자원·무한루프·복구 시험 명세

상태: 설계용 시험 목록. 이 문서의 모든 항목은 새 v0.3에 대해 미실행이며, 기존 v0.2 테스트 성공을 주장하지 않는다.
근거: 기존 docs/VALIDATION.md의 필수 실기기 34개, SECURITY.md, docs/THREAT_MODEL.md, docs/REVIEW_V02.md와 새 Excel/HWP/CAD/GUI/REMOTE 설계.

## 1. 공통 시험 규칙
- 테스트는 Windows 격리 VM의 합성 자료만 대상으로 한다. 실제 운영 PC의 Excel/HWP/DWG 원본, 개인폴더, 자격증명, SSH, 운영 DB 수정 금지.
- 실행 전 VM 기준 스냅샷, 테스트용 ACL/계정, 해시/백업/복구 계획, CPU/RAM/디스크·로그 용량 한도 기록.
- 각 시험 로그는 TEST-ID, run_id, commit_sha, recipe_version, worker/app version, OS version, broker_user SID (마스킹), source/output SHA, expected/actual, exit_code, incident_state, cleanup evidence를 포함.
- 유해·파괴적 입력은 합성/목업 서비스 대상으로만. 전체 시스템 부하 실험은 리소스 예산이 있는 격리 VM에서만 실행하고 watchdog/시간 상한 적용.
- PASS 조건: 기대 결과뿐 아니라 원본·기존 사용자 프로세스 불변, 예산 준수, cleanup/감사·복구 가능까지 확인. FAIL 또는 UNKNOWN은 출시 차단.
- 하드 중지 발생 시 변경 재시도 0회, 상태 UNCERTAIN/LOCKED, 오프라인 operator hash 점검 후만 resume.
- 수동 확인이 필수인 검증은 사람이 승인하기 전 자동 PASS 불가. CI 가상환경 PASS와 실제 Windows VM PASS를 구분한다.

## 2. 기존 v0.2 필수 34 시나리오: v0.3에서 전부 계승
| ID | 격리 VM 자극/조건 | 관측 항목 | 안전 기대 결과 |
|---|---|---|---|
| BASE-01 | 다른 드라이브 경로 입력 | file_id, volume_id, policy | 허용 루트 밖 거부 |
| BASE-02 | ../ 상위경로 도주 | canonical_path, root_identity | 접근 거부 |
| BASE-03 | UNC/네트워크 경로 | path_classification | 원격공유 거부 |
| BASE-04 | NTFS ADS 경로 | ADS detection | 대체 데이터스트림 거부 |
| BASE-05 | Windows 예약 이름 | filename normalized | 특수 장치 거부 |
| BASE-06 | 폴더 junction | reparse_tag/handle | 루트 탈출 거부 |
| BASE-07 | 디렉터리 symlink | reparse_tag/target | 추적·수정 거부 |
| BASE-08 | 파일 symlink | file_identity | 대상 파일 수정 거부 |
| BASE-09 | hardlink된 보호 파일 | link_count/inode | 기존 중요 파일 불변 |
| BASE-10 | 파일 경로 rename 경합 | before/after file IDs | 바뀐 대상 거부 |
| BASE-11 | symlink 대상 교체 경합 | handle_identity | 새 대상 기록 금지 |
| BASE-12 | 동시에 수정하는 두 broker worker | global applying lock | 단 1건만 진입 |
| BASE-13 | 읽는 중 파일 크기 증가 | bounded_read_bytes | 읽기 크기 상한 유지 |
| BASE-14 | 잘못된 expected SHA | plan_hash/actual SHA | 수정 요청 거부 |
| BASE-15 | 동일 idempotency 키 재활용 | key/plan binding | 중복 변경 0건 |
| BASE-16 | OS ACL로 보호된 파일 | effective_access | 정책 우회 거부 |
| BASE-17 | API key 파일 조회/로그 포함 시도 | redaction/secret path | 읽기/유출 차단 |
| BASE-18 | 384KiB 초과 IPC 요청 | frame_size | 요청 거부·메모리 상한 |
| BASE-19 | 잘못된 MCP/JSON-RPC 데이터 | parser_error | 프로세스 무중단 또는 안전 거부 |
| BASE-20 | 잘못된 pipe 인증키 | peer/auth outcome | broker 접속 거부 |
| BASE-21 | pipe squatting 시도 | pipe owner/SID | 다른 프로세스 접속 불가 |
| BASE-22 | 다른 Windows 사용자 접근 | SID/ACL | 거부·감사 |
| BASE-23 | gateway가 소스 변경 가능한 디렉터리 | install_acl | 운영 시작 거부 |
| BASE-24 | 정책 파일이 쓰기 가능 | policy_acl | 운영 시작 거부 |
| BASE-25 | 적용 의도 journal 직후 프로세스 종료 | intent state | emergency latch, 수정 재실행 0 |
| BASE-26 | 백업 만들기 직전 종료 | artifact/journal state | 자동 재실행 금지 |
| BASE-27 | 백업 만든 직후 종료 | backup hash, incident | 안전 격리·수동 확인 |
| BASE-28 | 실제 파일 교체 직후 종료 | source/candidate hash, receipt | 불확실 상태 잠금·수동 조정 |
| BASE-29 | 파일 쓰기 도중 긴급 중지 | STOP flag/commit step | 이후 추가 변경 금지 |
| BASE-30 | 잘못된 recovery 상태 선택 | observed hash/plan hash | 자동 복구 거부 |
| BASE-31 | 초당 다량의 새 task IDs | actor hourly budget | 요청제한 영속성 |
| BASE-32 | 스토리지/SQLite 용량 부족 | disk/DB/backup budget | 작업거부, 기존 데이터 불변 |
| BASE-33 | broker 사용자 권한 격리 실패 | SID/group/token/ACL | 배포 차단 |
| BASE-34 | 백업 후 복원 리허설 | backup/input/result SHA | 검증된 원본 복원 |

각 BASE-n 항목의 기존 코드 커버 여부와 실제 Win32 테스트 증거는 새 개발 시 따로 기입한다. 원본 docs/VALIDATION.md는 34/34 완료를 선언하지 않으므로 여기서도 완료로 간주하지 않는다.

## 3. 신규 Windows 앱 제어 시험
| ID | 검증 자극 | 제한 및 예상 반응 |
|---|---|---|
| APP-01 | 이미 열린 사용자 Excel/CAD/HWP와 새 워커 동시 실행 | 사용자 HWND/PID/문서 불변 |
| APP-02 | COM worker 앱 프로세스 잔류 | 전용 pid 소유 확인 후만 정리 |
| APP-03 | Excel 수식셀 직접 수정 요청 | 사전 거부, 수식 유지 |
| APP-04 | 수식은 유지됐지만 계산 결과 불일치 | FAILED/REVIEW, 성공 주장 금지 |
| APP-05 | HWP 표 병합·쪽 수 변화 | 검증 실패/사람 검토 |
| APP-06 | 한글 파일보안 경고/모듈 부재 | 사용자 승인 없는 우회 금지 |
| APP-07 | AutoCAD mm/m 혼선 | 계획 단계 거부 |
| APP-08 | CAD 잠긴 레이어/Xref에 편집 요청 | 대상 수정 불가 |
| APP-09 | DWG 객체가 다른 객체로 바뀐 경우 | 객체 fingerprint 불일치 → 실행 중단 |
| APP-10 | Office/CAD SaveAs 때 기존 출력 선점 | 기존 출력 덮어쓰기 0 |
| APP-11 | 파일이 저장됐지만 원본 해시 달라짐 | FAIL, 원본/수정본 검사 격리 |
| APP-12 | AutoCAD/HWP 프로그램 라이선스 만료 | 설치·보안 설정 변경 없이 실패 |
| APP-13 | COM 호출 180초 이상 hang | timeout/owned job termination/incident |
| APP-14 | 둘 이상의 작업 동시 요청 | 파일·앱·세션별 1 active, 중복 거부 |
| APP-15 | 수정 중 다른 프로그램이 원본 변경 | file identity/hash 재검증, stop |
| APP-16 | 악성 office 매크로·외부 링크 포함 합성 파일 | 자동 실행/인터넷 로드 차단 |
| APP-17 | 저장 후 프로그램/worker 크래시 | journal->UNCERTAIN, write replay 0 |
| APP-18 | 5회 반복 요청/재연결 | 1회 receipt, 0 중복 저장 |
| APP-19 | 프로그램이 종료됐는데 숨은 popup/EXCEL.EXE 잔존 | owned_pid 정리/오염 탐지 |
| APP-20 | 작업 결과의 PDF 미리보기와 실제 문서 구조 불일치 | 검증 불합격/검토 필요 |

## 4. 신규 GUI·원격·리소스 시험
| ID | 자극 | 판정 |
|---|---|---|
| REM-01 | 모바일 ChatGPT 커스텀 도구 없음 | G0 미충족/기능 차단 |
| REM-02 | 유효기간 지난 OAuth·다른 사용자 token | 401/403, broker 명령 0 |
| REM-03 | 서명되지 않은 장치 교체/오염된 relay | 페어링 재승인 전 거부 |
| REM-04 | offline->online 뒤 오래된 승인/중복 packet | 자동 실행 0 |
| REM-05 | 반복 폴링/오류 폭주 | per actor/device rate cap, CPU/로그 상한 |
| GUI-01 | Windows 세션 잠금/로그오프 | 클릭·입력 0 |
| GUI-02 | 예상치 않은 UAC/파일 열기 팝업 | 자동 확인 0, 사용자 요청 |
| GUI-03 | 동일 제목의 2개 창 | 정확한 PID/HWND 못 찾으면 중단 |
| GUI-04 | DPI·화면 수·언어·UI 변경 | 미검증 selector 실행 금지 |
| GUI-05 | 사용자가 작업 중 마우스를 움직임 | 자동 포커스 강탈/입력 중복 금지 |
| SYS-01 | 이용 가능 RAM 급감 | 제한 전에 시작 거부 |
| SYS-02 | 디스크 여유 임계값 하회/저장공간 초과 | 변경 시작/저장 중단, 복구본 보존 |
| SYS-03 | 긴급 정지 요청 순간 GUI 동작 진행 | 새 입력 0, 미확정 상태 기록 |
| SYS-04 | 워커 무한루프/자식 프로세스 폭증 시뮬레이터 | Job Object/시간/CPU/RAM 제한 |
| SYS-05 | 재시작 시 stale lock/applying job | 임의 lock 해제 금지, 오프라인 검토 |
| SYS-06 | 비밀값/계약 내용이 로그·GitHub에 포함 | 저장 전 마스킹/정책 차단 |
| SYS-07 | VM checkpoint 중단/복구 테스트 | 승인된 백업 확인 후 재시작 |
| SYS-08 | 여러 변경 명령이 서로 다른 버전의 정책을 사용 | 정책 버전 충돌 시 stop |

## 5. 증거 및 결함 처리 기준
| 항목 | 작성 규칙 |
|---|---|
| 결과 구분 | NOT_RUN / PASS_VM / FAIL_VM / PASS_STAGING / BLOCKED |
| 로그 | 테스트용 run_id와 해시·에러코드·짧은 마스킹 로그만 GitHub 제출 |
| 재현성 | 준비 데이터 생성법/앱 버전/계정/클릭·명령 단계/한도 기록 |
| 체크포인트 | VM 또는 격리 백업 ID/버전/무결성, 복구 리허설 기록 |
| 실패 처리 | DEBUG_ISSUES.md 신규 이슈 → 수정 브랜치 → 동일 및 인접 회귀시험 |
| 완료 | 기존 baseline 34개 + 신규 필수 시험이 실제 Windows VM에서 통과, 보안 리뷰 승인을 받은 후 배포 후보 |

GitHub 저장소에 실제 고객 DWG/HWP/Excel, 캡처, 키, 로그 원문, 백업 파일을 올리지 않는다.
