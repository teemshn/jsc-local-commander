# DWG / AutoCAD Adapter 설계 + 디버그 시나리오

상태: DESIGN ONLY. Windows에서 AutoCAD.Application COM 등록 흔적이 확인됐으나 제품 버전·에디션·라이선스 및 자동화 편집/SaveAs의 실기기 통과 여부는 확인 전.

## CAD-1. 목표
DWG 원본·외부참조를 손상시키지 않고 AutoCAD에서 특정 도형/블록/치수/문자를 정확히 조회·수정·재저장·검증. 처음에는 합성 도면의 길이·위치가 명시된 선 1개만 변경. 전기/통신 공사의 카메라·케이블 경로·표식·레이어와 연동은 후속 업무 레시피.

## CAD-2. 인터페이스 우선순위 및 제품 호환성
1. 현재 설치된 제품 AutoCAD 정식판 / LT / OEM / 버전 / 32·64bit, 관련 플러그인(특수 객체) 식별.
2. Autodesk 공식 문서 기준 Windows ActiveX/COM으로 Documents/Open/SaveAs 및 객체 제어 가능. AutoCAD LT는 일부 언어/외부 Automation 인터페이스 제약이 있으므로 제품별 실제 지원 검사 선행.
3. 정교한 DWG DB 변경은 제품이 허용하는 .NET API/AutoLISP/COM 중 안정적 레시피 채택. 스크립트 문자열 임의 실행 기능으로 열어두지 않는다.
4. API에서 지원 안 되는 메뉴만 로그인 사용자 세션의 UI Automation으로 보조. 화면 좌표만 이용한 객체 드래그는 정밀 설계변경의 기본 수단으로 채택하지 않는다.

공식 참조: https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-ActiveX-Reference/files/GUID-ED0D0B02-25FC-4ED2-9DEE-2B0C9AA9416A.htm
도면/객체 자료: https://help.autodesk.com/cloudhelp/2026/KOR/AutoCAD-ActiveX-Reference/files/GUID-9216BFCD-D358-4FC6-B631-B52E6693D242.htm

## CAD-3. DWG 작업 계약
- inspect_dwg: model/paper space, 단위(INSUNITS 등), UCS/WCS, 도면 버전, entity ID/handle, 레이어 잠금·동결, Xref/폰트/특수 객체 정보 조회.
- plan_dwg_edit: 객체 정확 식별(가능하면 handle + type + bounding box + 원본 도면 hash), 변경 전후 좌표·각도·길이·단위·공간 기록.
- apply_dwg_copy_edit: broker 승인 단건 변경, 원본 손대지 않고 새 DWG 파일에 SaveAs.
- verify_dwg: 결과를 재열어 단위/도형/블록/치수/참조/객체 수 비교, 지원되는 경우 AUDIT/regen 및 시각 검토 요구.

Typed input: source_file_id, source_hash, drawing_unit, coordinate_system, entity_ref, entity_type, operation enum(MOVE / SET_TEXT / SET_PROPERTY), exact numeric args, output_filename, approval_hash. command prompt/raw script/eval 사용자 입력 금지.

## CAD-4. 객체 수정 시 핵심 원칙
- 모델 공간/종이 공간 별도 확인, UCS/OCS/WCS 좌표 변환 일치.
- 도면 단위 mm/m/inch와 선형 길이 계산의 단위를 검증. '500 이동'은 단위 확인 전 실행 안 함.
- entity handle은 재저장 과정에서 참조 변경 가능; 원본 객체 식별자와 형상(좌표/레이어/속성) fingerprint를 함께 기록.
- 잠긴 레이어, 외부참조 Xref, 동적 블록, 주석축척, 프록시/custom entity는 기본 변경 금지 또는 검토 필요.
- 누락된 글꼴/SHX/외부참조/이미지/플롯 설정은 결과 도면 사용성과 출력을 바꿀 수 있으므로 경고·검증.
- SaveAs의 DWG 버전 옵션과 도면 스키마 차이, 별도 출력물(.pdf) 정확성 검토.
- 치수·선 개수 같아도 설계 의미가 달라질 수 있으므로 객체 속성 비교와 필요 시 사람 검토를 분리.

## CAD-5. 단계별 안전 실행
1. 해당 PC 제품/라이선스/워커 권한 확인 후 합성 DWG 복사.
2. 사용자 기존 AutoCAD 프로세스/열린 도면을 명시적으로 분리; 신규 instance/창 소유 증거 없으면 조작 금지.
3. 입력 해시, 단위, 객체 ID, 레이어 상태, 도면 잠금, Xref 상태 read-only 확인.
4. 변경 계획에서 객체 before/after 위치, 범위, 예상 길이/면적/물량에 미치는 영향을 미리 표시.
5. 승인 이후 제한된 API 작업 레시피 실행, 저장은 새 경로로만.
6. 결과 DWG 재열기, 객체 수와 지정 객체 좌표·길이·레이어·도면 단위가 계획과 일치하는지 검증.
7. 시각 검토 필요 시 AutoCAD UI/PDF를 이용하되 출력 시 개인정보/기밀 도면 캡처 최소화.
8. 불일치·예외 발생 시 원본 불변 유지, 수정본 격리, 재시도하지 않고 중단.

## CAD-6. 디버그 케이스
| ID | 재현/의심 요소 | 관측 값 | 실패 처리/통과기준 |
|---|---|---|---|
| CAD-D01 | COM 등록은 있는데 AutoCAD 실행 안 됨 | app_edition, progid, license_error | 미지원/인증 불가 상태 표시 |
| CAD-D02 | AutoCAD LT/제품별 API 차이 | edition, automation_capabilities | 지원하지 않는 작업 금지 |
| CAD-D03 | 단위 mm↔m↔in 혼합 | INSUNITS, measurement, scale | 단위 모호 시 실행 거부 |
| CAD-D04 | UCS/OCS/WCS 변환 오류 | ucs_matrix, before/after coordinates | 계획 형상과 좌표 일치 검증 |
| CAD-D05 | 유사한 선/블록 선택 오류 | entity fingerprint, handle, layer | 객체 단일 식별 실패 시 중단 |
| CAD-D06 | 외부참조/이미지 유실 | xref_paths, resolved status | 결과물 검토요청 |
| CAD-D07 | 잠긴/동결/꺼진 레이어 | layer status, editability | 자동 해제/변경 금지 |
| CAD-D08 | 동적 블록/특수 CAD 객체 | proxy types, attribute states | 지원 안 되면 거부 |
| CAD-D09 | 치수기입 재계산/문자/폰트 변경 | dim styles, SHX, text bound | 값·서식 불일치면 실패 |
| CAD-D10 | SaveAs 포맷 버전 바뀜 | DWG version/input/output | 원본 포맷 유지 또는 명시 승인 |
| CAD-D11 | 사용 중인 AutoCAD 세션에 결합 | owned_pid, active_documents | 사용자 세션 건드리지 않음 |
| CAD-D12 | 화면 팝업/복구/라이선스 창 | modal_hwnd, app_state | 예상 밖 화면에서 중지 |
| CAD-D13 | 도면 열기/저장 중 멈춤 | stage, timeout, CPU/RAM | 제한시간/긴급중지, 임의 재시도 금지 |
| CAD-D14 | 결과 형상은 바뀌었으나 케이블 물량 오류 | units, geometry lengths, derived quantities | 업무 물량 검증 실패로 분리 |
| CAD-D15 | 도면 AUDIT/REGEN/PDF 결과 차이 | audit_report, render_hash, warnings | 수정본 검토 후 통과 |
| CAD-D16 | 외부 플러그인/SHX 보안·경고 | trusted_paths, security prompts | 신뢰되지 않은 코드 실행 거부 |

## CAD-7. 개발 완료 게이트
합성 DWG 선 1개 이동+새 SaveAs+정밀 좌표 재검증 성공. 인접/중복 entity 오선택, 잠긴 레이어, Xref, 다른 단위, 쓰기 중 강제 중단, 작업 전부터 열린 사용자 도면 간섭을 모두 분리 시험한다. 이후 실제 회사 도면 시험은 복사본·명시 승인·스테이징 환경에서만.
