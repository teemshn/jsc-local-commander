# JSC Local Commander — 제한형 MCP 구현 v0.1

**Status: SECURITY PREVIEW — DO NOT DEPLOY TO PRODUCTION JSCPC YET.**

로컬 `stdio` MCP 서버로 **허용된 작업공간의 작은 일반 텍스트 파일만** 조회·검색·변경할 수 있습니다. 범용 PowerShell, 프로세스 실행, 관리자 권한 상승, 서비스 및 Docker 변경, 재귀 삭제, 외부 접속 기능은 **제공하지 않습니다**. 코드·설정·자격증명 파일은 수정할 수 없습니다.

## 사용 전 주의

- Windows 10/11에서 별도 **일반 사용자**로 실행하고, 관리자가 고정된 `%ProgramData%\JSCCommander\policy.json` 및 소스 코드에 쓰기 불가 ACL을 적용해야 합니다.
- `policy.json` 예시: `{"workspace":"D:\\JSC-AI-Workspace","state":"C:\\ProgramData\\JSCCommander\\State"}`. **예시 경로이므로 본인 PC에 존재하는지 확인해야 합니다.** 작업공간과 상태 폴더는 별도의 위치입니다.
- 설치 계정은 Windows, Program Files, 중요 서비스, Docker Engine Pipe 등에 쓰기 권한이 없어야 합니다. 정책 설정 파일은 관리자만 수정할 수 있어야 합니다.
- **로컬 MCP는 별도의 OS 보안 격리를 대체하지 못합니다.** 링크/파일 교체 경합, 악성 프로세스, 디스크 오류 등은 Windows VM 시험이 필요합니다.
- 현재 버전은 관리자 전용 브로커·Job Objects·구조화된 명령 레시피를 **아직 구현하지 않았습니다**. 프로덕션 승인 전까지 실서버에 연결하지 마세요.
- MCP stdio는 로컬 Codex에서만 호출할 수 있습니다. 이 ChatGPT 웹 대화에 자동 연결되지는 않습니다.
- 저장소에는 실제 PC IP, 비밀번호, 키 파일, 정책의 실경로를 올리지 마세요.

## 개발 환경 설치

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
```

## 실행

설치·ACL 분리·VM 검증 후 로컬 Codex에 stdio 도구로 등록할 수 있습니다.

```powershell
codex mcp add jsc-local-commander -- C:\path\to\repo\.venv\Scripts\python.exe -m jsc_local_commander
```

실제 `policy.json`에 등록된 workspace 내 `.txt`, `.md`, `.csv`만 접근합니다. `get_file_info`의 SHA256을 확인한 뒤 `plan_edit`으로 미리보기를 만들고, `apply_edit`에 고유한 `idempotency_key`를 전달합니다. 동일한 계획의 재실행은 차단하거나 결과만 반환합니다. 사용자에게 저장 경로에 대한 접근 권한이 없다면 운영체제가 거부합니다.

### 아직 지원하지 않는 것

- 임의 PowerShell, Docker, 서비스 관리, UI 조작, 바이너리/DOCX/XLSX 수정
- 관리자 전용 독립 Policy Broker 및 1회용 관리자 승인
- Windows Job Object 기반 외부 프로세스 제한(현재 외부 프로세스 실행 자체를 지원하지 않음)
- 장시간 작업 큐·자동 복구
- 경로 handle 기반 완전한 TOCTOU 방어

안전성 시험: `docs/VALIDATION.md` 참조. **CI 통과만으로 운영환경 안전성이 검증되는 것은 아닙니다.**
