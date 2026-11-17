# v1 MCP Tool Interface — 안전한 하위집합

**원칙:** 모든 작업은 구조화된 JSON 매개변수로, 절대경로 검증 및 정책 실행 후 수행. 범용 shell 인자 없음.

| Tool | Mode | Input (예시) | Safety |
|---|---|---|---|
| `get_status` | read | `{}` | 버전·정책 상태·보호 활성화 여부만 출력 |
| `list_workspace` | read | `{ "path":"D:\\JSC-AI-Workspace" }` | 허용 루트만 |
| `search_files` | read | `{ "root":"...", "glob":"*.py", "max_results":100 }` | 시간·검색 결과 상한; 링크 추적 금지 |
| `read_text` | read | `{ "path":"...", "start_line":1, "max_lines":200 }` | 인코딩/크기 제한, 민감정보 차단 |
| `get_file_info` | read | `{ "path":"..." }` | hash/metadata, 권한 검사 |
| `plan_edit` | preview | `{ "path":"...", "expected_sha256":"...", "replacement":"..." }` | 미리보기·diff·계획 해시 반환 |
| `apply_edit` | write | `{ "plan_id":"...", "idempotency_key":"..." }` | 사전 계획·hash·백업·예산 검증 |
| `copy_within_workspace` | write | `{ "src":"...", "dst":"...", "idempotency_key":"..." }` | 두 경로 재검증, 기존 대상 덮어쓰기 금지 |
| `list_jobs` | read | `{ "limit":20 }` | 호출자별 작업 조회 |
| `get_job_status` | read | `{ "job_id":"..." }` | 사용자·작업 결합, 폴링 제한 |
| `cancel_job` | safe-control | `{ "job_id":"..." }` | 자기 작업만, 상태 기록 |
| `get_audit_events` | read | `{ "task_id":"...", "limit":50 }` | 내용 비밀 제거, 읽기 권한 분리 |
| `diagnose_processes` | read | `{ "name":"...", "limit":20 }` | 프로세스 조회 전용 |
| `diagnose_services` | read | `{ "filter":"..." }` | 서비스 상태 조회 전용 |
| `diagnose_docker` | read | `{ "filter":"..." }` | 컨테이너 상태/헬스 조회 전용 |

**명시적으로 제외:** `execute`, `exec_shell`, `powershell`, `write_anywhere`, `rm`, `recursive_delete`, `manage_service`, `docker_exec`, `docker_prune`, `elevate`, `read_credentials`.

## v2 후보 (별도 보안 승인 후)

- `run_recipe(recipe_id, typed_args)`: 관리자 등록·서명된 작업 레시피만. 스크립트 문자열·임의 경로·실행파일 입력 금지.
- `restart_allowlisted_service(service_id)`: 임계 서비스 제외, 사전 계획/복구/헬스체크/로컬 승인 필수.
- `deploy_container(service_id, artifact_digest)`: 특정 컨테이너만, 이미지 다이제스트 고정, DB/볼륨 보호, 롤백 제공.
- GUI 자동화는 별도 Windows UI Automation 모듈로 분리, 사용자가 로그인한 별도 제한 세션에서만 운영.
