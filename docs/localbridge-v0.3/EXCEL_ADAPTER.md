# Excel Adapter 설계 + 디버그 시나리오 (XLSX)

상태: 설계 초안. GitHub v0.2 Python broker에 아직 존재하지 않음.
참고: 별도 Windows 로컬 Node.js LocalBridge 프로토타입에서 Excel COM으로 합성 샘플 셀값 수정·수정본 검증 성공(2026-11-20). 이는 GitHub 코드의 통합·권한 격리·회귀 테스트 합격을 의미하지 않는다.

## EX-1. 목표와 원칙
목표: Windows에 설치된 실제 Excel을 호출해 XLSX의 명시된 셀·범위만 바꾸되, 수식/서식/호표/인쇄영역/숨김시트 등을 손상시키지 않고 새로운 사본으로 저장하며 재검증한다. 공사내역서는 품목·단가·노무비·제경비·원가계산서 연결이 중요하므로 단일 셀 성공으로 업무적 정합성을 주장하지 않는다.

첫 단계는 합성 통합문서에서 'B2 상수 12→24, B4 수식 SUM(B2:B3)' 수준의 편집. 실제 업무 시트는 명시적 리뷰 후 별도 범위를 적용한다.

## EX-2. 작업 계약 (신규 전용 tool/recipe 설계)
| 입력 | 필수 조건 |
|---|---|
| file_id 또는 broker가 허용한 파일 식별 | 경로·파일 고유 ID·입력 해시·수정 중 잠금 |
| sheet identifier | 실제 존재하는 시트명 및 중복/숨김/보호 여부 |
| cell/range | A1 좌표 상한, 병합/테이블/수식셀/이름정의 범위 확인 |
| expected_old_value | 원본 예상 값과 정확히 일치하지 않으면 거부 |
| new_value | 유형(문자열/숫자/날짜 등)을 엄격히 분리; 공식이 아닌 사용자 값 |
| output_name | 허용 폴더 내 새 이름, 기존 파일 덮어쓰기 불가 |
| expected_input_sha256 | 계획과 실행 시 동일한 입력 파일이라는 증거 |
| calculation_policy | 계산 방식/외부링크/계산 완료 조건 별도 확인 |

제안 도구: inspect_excel_document (read), plan_excel_edit (preview), apply_excel_copy_edit (approved write), verify_excel_artifact (read). 초판에는 임의 COM 속성명/스크립트 입력을 허용하지 않는다.

## EX-3. 실행 알고리즘
1. broker가 요청·승인·대상 폴더/파일 ID·백업 공간·기존 열려 있는 사용자 Excel을 조사한다.
2. 스테이징에 파일 복사, 원본 해시 보존, target output 경로에 파일이 없는지 검사한다.
3. GUI/COM Worker는 전용 저권한 Windows 세션에서 구동. 별도 Excel 프로세스 생성 시 실행 전 PID 목록과 창 핸들 소유 PID 비교.
4. 기존 사용자 Excel 인스턴스에 연결되었다면 안전 중단(별도 프로세스 검증 전 제어 금지).
5. 매크로/외부 연결 자동 실행 방지, 팝업 감시, 읽기 전용으로 입력 열기. 요구 범위와 예상값을 재검증.
6. 작업 셀에 기존 공식이 있거나 원본/버전이 다르면 중단. 등록된 레시피의 숫자/문자 값만 수정.
7. 결과를 새로운 XLSX에 SaveAs; 저장 완료 신호·크기·읽기 가능 여부 확인.
8. Excel 자체로 사본 재열기, 대상 셀/참조 수식/결과 합계/주요 문서 구조 검증.
9. Excel COM 객체 해제, 자기 소유 PID/창 종료 확인. 남아 있는 작업 전용 프로세스만 안전한 조건에서 정리. 사용자 프로세스는 건드리지 않음.
10. 승인·입력·출력 해시, 검증 항목, 오류 코드·시간을 기록하고 원본 불변 확인.

## EX-4. 검증 정의
- 정확성: 셀 값/유형, 공식 텍스트, 계산된 값(캐시와 실제 재계산 별도), 참조 범위 모두 일치.
- 문서 구조: 시트 수/이름/순서, 숨김·보호 상태, 병합, 이름 정의, 테이블, 통합문서 링크, 조건부서식, 데이터 검증 규칙 변경 없음을 샘플 기반 회귀 검증.
- 업무 검증: 공내역서의 재료비·노무비·경비·일위대가 호표·원가계산서 연결, 원 단위/반올림 기준에 맞는지 별도 검사. 기존 템플릿/열 배치/서식 유지.
- 검증 수준 표시: MACHINE_PASS / VISUAL_REVIEW_REQUIRED / FAILED; '사본 저장 성공'만으로 완료 처리 불가.
- 지원범위 제외: 매크로·암호화 문서·외부 데이터갱신·공유통합문서·계산방식 모호한 문서. 허용 시 별도 기술검토·승인 필수.

## EX-5. 디버깅 레지스터
| ID | 재현/의심 요소 | 관측 필드 | 실패 시 안전 동작 | 통과 조건 |
|---|---|---|---|---|
| EX-D01 | New-Object/Dispatch가 열린 사용자 Excel에 붙음 | startup_pid_list, hwnd_pid, owned | 원본/열린 문서 수정 금지 | 새 PID 확인 또는 실행 거부 |
| EX-D02 | COM 워커 종료 후 EXCEL.EXE 잔류 | worker_pid, excel_pid, exit_time | 소유 PID만 정리/incident | 본인 PID 종료, 기존 PID 유지 |
| EX-D03 | Workbook.Open이 링크 업데이트/매크로 실행 | security_mode, link_flag | 실행 전 중단 | 네트워크/매크로 부작용 없음 |
| EX-D04 | 수식/수식셀 덮어쓰기 | cell_has_formula, formula_text | 거부 | 원본 및 참조 수식 동일 |
| EX-D05 | 날짜/숫자/텍스트 서식 자동 변환 | type_before_after, number_format | 수정본 검토요청 | 값·형식 일치 |
| EX-D06 | 숨김·병합·보호된 셀 변경 | sheet_state, protection, merge_area | 거부 | 보호/서식 불변 |
| EX-D07 | 파일이 Excel에서 이미 열림/잠김 | handle_lock, file_id | 대기 아닌 안전 중단 | 원본 사용자 작업 영향 0 |
| EX-D08 | 수식 계산이 수동/다단계 의존성 | calc_mode, formula_count, cached_vs_calculated | 검증불가 처리 | 재열기·재계산 비교 일치 |
| EX-D09 | SaveAs 중 대상 파일 경쟁 생성 | output_preexist, last_error | 덮어쓰기 금지 | 원본/기존 출력 불변 |
| EX-D10 | Excel 확인 팝업/암호 입력 | visible_windows, modal_class | 미확정 화면 중단 | 전용 GUI에서 확인 또는 실패 |
| EX-D11 | 다중 sheet의 링크/호표 깨짐 | sheet_hashes, names, referential_audit | 결과 격리 | 변경이 허가된 셀·계산값에 국한 |
| EX-D12 | timeout/프로세스 크래시 중 임시 파일 | stage, owned_pid, output_hash | 불확실 상태 latch, 재실행 0 | 복구 검사 후 수동 재승인 |
| EX-D13 | 최소 RAM/디스크 소진 | free_ram, free_disk, temp_budget | 작업 시작 거부/안전중단 | 호스트 안전 임계치 유지 |
| EX-D14 | 다른 버전 Excel 계산/외부링크 차이 | excel_version, locale | unsupported로 격리 | 지원표/회귀시험 결과 기록 |
| EX-D15 | 특수 서식 인쇄영역 손상 | print_area, page_breaks, render | REVIEW_REQUIRED | 내용·출력 비교 통과 |

## EX-6. 개발 및 회귀 순서
1. 합성 단순 XLSX 단일 셀 → 2. 수식 의존 통합문서 → 3. 보호/숨김/병합 반례 → 4. 팝업/잠금/죽은 세션 → 5. 내역서 모사 합성 템플릿 → 6. 승인을 받은 별도 사용자 복사본.
모든 테스트에서 로그와 입력·출력 해시, 사용자 Excel PID 불변 여부를 남긴다. 코드 실행 전 repo v0.2의 ACL/Named Pipe 실기기 게이트 G1 통과 필요.
