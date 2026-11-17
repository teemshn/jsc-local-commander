# 안전성 중심 재검토와 개선 이유

일자: 2026-11-17 · 버전: 설계 v0.1 · 변경 적용 상태: **제안, 미구현**

## 가장 중요한 결론

기존 설계의 `execute(command)` / `manage_service` / `docker_control`을 그대로 모델에 제공하는 방식은 위험하다. 로컬 도구라는 이유로 안전하지 않다. v1은 **허용목록 기반 구조화 도구**, **저권한 서비스 사용자**, **서버측 정책**, **운영체제 수준 자원 제한**, **수동 승인**으로 다시 설계한다.

| ID | 이전 가정·위험 | 변경 | 이유 | 우선순위 |
|---|---|---|---|---|
| R-01 | 범용 PowerShell/CMD 실행 | 기본 미제공; 제한된 진단·빌드 레시피만 허용 | 모델 실수/프롬프트 인젝션으로 시스템 변경 우회 방지 | P0 |
| R-02 | 경로 문자열 denylist만으로 Windows 보호 | 전용 저권한 계정 + 허용 루트 + 실제 파일 핸들 경로 검증 | junction/symlink/UNC/대체 경로 우회 방지 | P0 |
| R-03 | 프로세스 timeout만 적용 | 작업당·주체당 누적 예산, fingerprint 중복 탐지, Windows Job Objects | 재호출·하위 프로세스·장시간 작업 폭주 방지 | P0 |
| R-04 | 재시도 무제한 | 안전한 조회만 제한적 자동 재시도, 변경 작업은 idempotency key 검증 | 중복 삭제·재배포·데이터 손상 방지 | P0 |
| R-05 | 파일 수정 시 단순 덮어쓰기 | preimage hash + 임시 저장 + 원자적 교체 + 안전한 스냅샷 | 작업 실패·경합·전원 장애 영향 감소 | P0 |
| R-06 | 서비스 제어 일반 허용 | v1 조회만; 서비스 중지/재시작/삭제는 후속 별도 권한 프로파일 | Windows와 운영 컨테이너 장애 방지 | P0 |
| R-07 | AI가 사용자의 승인 메시지 해석 | 별도 로컬 `jscctl approve`의 단기·범위 한정 승인 | 문서/로그 내 지시문·챗봇 착각으로 승인 위조 방지 | P0 |
| R-08 | 감사 로그만 남김 | append-only 기록, 변경 전후 hash, 작업/승인/호출자 연결 | 장애 원인 조사·사후 검증 | P1 |
| R-09 | 하나의 프로세스가 전부 처리 | MCP 프런트와 저권한 워커, 정책 집행 분리 | 자원 폭주·오류 격리 | P1 |
| R-10 | 서버가 연결된 다른 고권한 도구는 고려하지 않음 | 기존 SSH MCP/원격 도구는 별도 고위험 프로파일로 분리 | 다른 도구로 정책 우회 가능 | P0 |
| R-11 | 네트워크 제공 기본값 | v1 stdio만; HTTP/터널은 별도 보안 검토 후 | 외부 공격 표면 최소화 | P0 |
| R-12 | AI 작업 완료 판정에만 의존 | 호출 결과·해시·테스트·헬스체크 근거로 검증 | 추측성 성공 보고 방지 | P1 |

| R-13 | stdio MCP를 Codex 관리자 계정에서 실행 시 권한 상속 | 무권한 stdio facade와 제한 Windows 서비스 분리, Named Pipe ACL/SID 검증 | 상위 사용자 권한이 worker로 전달되지 않도록 강제 | P0 |
| R-14 | Docker 조회 기능에 엔진 소켓 직접 연결 | 소켓 접근 금지 + 제한 조회 중개 | Docker 접근 자체가 사실상 호스트 관리자 권한임 | P0 |
| R-15 | workspace 안 스크립트 수정 후 빌드로 간접 명령 실행 | 실행 영향 변경 승인 + VM 격리 빌드 | allowlist 파일 쓰기를 통한 OS 명령 우회 방지 | P0 |

### 실제 보호 범위의 한계

- Windows ACL/표준 사용자 계정이 운영체제 강제 보호의 핵심이다. **AI에게 관리자 권한을 주면 정책 파일·파일 접근 제한을 우회할 수 있으므로 보장 불가**.
- Windows Job Objects는 자원·프로세스 트리 종료에 도움을 주지만 **악성 코드 격리 보안 경계는 아니다**. 임의 빌드 스크립트·테스트 코드는 VM/Windows Sandbox 등 별도 격리가 필요하다.
- MCP는 AI 모델의 내부 생각이나 토큰 루프까지 종료할 수 없다. **서버에서 계속되는 부작용·호출·프로세스 실행**을 차단할 수 있다.
- 다른 연결 도구에서 관리자 명령을 수행하면 이 서버의 보호를 받지 않는다. 일반 자동화 프로필에서 그런 도구를 분리한다.

### 참고 기준

- Microsoft Windows Access Control: https://learn.microsoft.com/windows/security/identity-protection/access-control/access-control
- Microsoft PowerShell Security: https://learn.microsoft.com/en-us/powershell/scripting/security/security-features
- OWASP MCP Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html
- MCP Security Best Practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
