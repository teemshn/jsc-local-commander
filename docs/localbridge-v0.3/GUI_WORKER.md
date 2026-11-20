# GUI_WORKER — Windows 직접 화면제어 엔진 설계

상태: 설계안. 아직 화면 클릭·키보드·스크린샷 제어 기능을 기존 GitHub v0.2에 추가하지 않음.

## UI-1. 목적과 적용 범위
Excel/HWP/AutoCAD 등에서 공식 API를 쓸 수 없는 제한된 기능만 Windows UI Automation(UIA) / Win32 메시지 / 검증된 접근성 요소 기반으로 수행한다. 화면 좌표를 무제한 클릭하는 MCP 도구는 제공하지 않는다. 앱별 UI 절차를 명시적으로 서명·등록한 recipe로만 실행한다.

우선 순위: 공식 객체 API → Windows UI Automation의 AutomationId/ControlType/Name 및 Element tree → 활성 창 검증을 포함한 한시적 단축키 → 화면 좌표는 시험용 마지막 수단(운영 기본 비활성).

## UI-2. 프로세스·세션 격리
- GUI는 Session 0 Windows 서비스에서 직접 조작하지 않는다. 대상 앱이 실제로 실행된 로그인 사용자 세션을 명확히 식별한다.
- 별도 제한 계정/전용 작업 세션 실행 가능성을 검사한다. 화면 공유·활성 사용자의 마우스 조작과 충돌하면 중단한다.
- broker/launcher UI 실행 경계는 OS 토큰·ACL이 보호한다. 동작이 필요한 앱만 허용; shell/PowerShell 자유 실행 및 임의 실행파일 경로는 미노출.
- 대상 창은 단순 제목 문자열만으로 선택하지 않는다. EXE 서명/실행 경로, PID, 세션 ID, HWND, UIA 루트/문서 경로를 함께 검증.
- 자기 소유한 새 프로세스/작업창만 제어한다. 사용자가 연 다른 파일/창에 결합했을 가능성이 있으면 작업 거부.
- 별도 GUI worker kill은 Job Object/프로세스 소유 검증 필수. 오염된 작업이 원래 사용자 세션에 남으면 완료 판정 금지.

## UI-3. 제한된 명령 유형
| recipe primitive | 입력 | 검증 |
|---|---|---|
| await_window | 서명된 app_id, expected_window_class, pid, timeout | PID/HWND/세션 동일, 미발견 시 실패 |
| inspect_element | app_id, parent_selector, key | 구조화된 UIA 정보만 반환, 비밀 마스킹 |
| select_element | 정확히 하나의 자동화ID/role/name | 0건·복수건이면 거부 |
| click_control | allowlisted control + expected_current_state | 실행 후 화면 상태 확인, 재클릭 자동 금지 |
| type_text | 승인된 입력 대상, 값 해시/길이/문자열 유형 | 기존 선택영역/IME 상태 확인; 비밀번호/로그인 필드 차단 |
| safe_hotkey | allowlisted menu shortcut | 포커스·창 주인 증명, 전후 결과 확인 |
| capture_evidence | 앱 내부 제한 영역 | 개인정보/자격증명/계약 원문 자동 마스킹, 승인된 보존 기간 |
| cancel_job | 자기 job id, owned window/process | 중복 종료 방지, uncertain state 기록 |

UIA 경로에 해당 컨트롤이 없으면 곧바로 무한 스크린샷·랜덤 클릭으로 전환하지 않고 'MANUAL_REVIEW'로 중단한다.

## UI-4. 실행 전·중·후 상태 기계
PRECHECK(세션 잠금 여부·표시 해상도·DPI·포커스·UAC) → ACQUIRE(대상 창 고유 확인)
→ EXPECT(정확한 화면/컨트롤) → ACT_ONCE(1회 동작) → OBSERVE(변화 확인)
→ NEXT or VERIFIED → RELEASE.

- 한 단계당 제한 시간; 예시 5초 탐색, 2초 입력, 응답확인 5초. 전체 60초 기본·180초 하드상한(실기기 조정).
- EXPECT와 OBSERVE가 틀리면 즉시 STOPPED/NEEDS_REVIEW. 임의 대화상자를 자동으로 닫거나 반복 클릭하지 않음.
- 화면/잠금/해상도/프로세스 변경 이벤트는 같은 작업에서 즉각 중단 판정.
- 사용자의 물리 입력이 감지되면 충돌 방지를 위해 일시정지 후 중단(임의 포커스 탈취 금지).
- 캡처에는 개인정보·내부 문서가 나타날 수 있으므로 원본 전체 이미지를 무조건 로그/GitHub에 저장 금지.

## UI-5. 디버그 포인트
| ID | 실패 유발 조건 | 기록할 증거 | 실패 시/합격 |
|---|---|---|---|
| GUI-D01 | PC 잠금/로그오프/RDP 종료 | session_id, locked, desktop_name | 동작 중단, 클릭 0건 |
| GUI-D02 | RDP 최소화/포커스 소실 | foreground_hwnd, desktop_state | 안전 대기/실패, 입력 누락 감지 |
| GUI-D03 | UAC 보안 데스크톱 등장 | secure_desktop, expected_ui | 권한상승 시도 금지, 사용자 확인 |
| GUI-D04 | 프로그램 버전/언어별 셀렉터 변경 | app_version, UIA_tree_fingerprint | 미검증 셀렉터로 클릭 금지 |
| GUI-D05 | 동일 제목의 창 다수 | HWND, PID, document_path | 대상 단일 확인 실패 시 거부 |
| GUI-D06 | 팝업/모달/에러 창 | modal_class, window_stack | 예상 외 창이면 즉시 중단 |
| GUI-D07 | 해상도/DPI/복수 모니터 변경 | DPI, monitor_id, window_bounds | 좌표 클릭 금지, 요소 재확인 |
| GUI-D08 | 한글 IME/선택 블록 상태 | IME_mode, focused_element, selection | 입력 대상 정확히 일치 |
| GUI-D09 | 중복 클릭/입력이 두 번 수행됨 | action_id, before/after fingerprint | 1회성 action receipt, 재전송 금지 |
| GUI-D10 | 작업 중 사용자가 마우스 조작 | input_inactivity, foreground_change | 충돌 감지 후 중단 |
| GUI-D11 | 앱 무응답/대량 CPU·RAM 사용 | process_cpu, memory, heartbeat | 시간·자원 상한 종료, 내 문서만 격리 |
| GUI-D12 | 종료 시 앱 자동복구/저장 프롬프트 | owned_pid, unsaved_state | 사용자 열린 세션 보호, 팝업 무단 확인 금지 |
| GUI-D13 | UIA가 가상화된 목록/데이터그리드 접근 못함 | UIA patterns, scroll_target | 지원불가 표시, 무한 스크롤 금지 |
| GUI-D14 | 비밀·계약 내용이 진단 이미지에 포함 | capture_hash, redaction_status | 무마스킹 업로드 금지 |
| GUI-D15 | 화면 전환 중 중간 상태에 지시 도착 | stage, ui_state, request_id | 대기/거부, 다른 문서 조작 0 |

## UI-6. 최소 실증
합성 메모장 또는 격리 시험용 한글/Excel UI에서 읽기 전용 창 탐색을 먼저 구현. 3차 시험까지 실제 저장은 하지 않음. locked/RDP/UAC/복수 창 조건에서 클릭 0건을 증명한 후, 창·컨트롤·파일 명시된 소규모 수정 레시피만 허용.

참조: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview
