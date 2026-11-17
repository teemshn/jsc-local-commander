# 보안 아키텍처

## 데이터 흐름

```text
JSCPC 로컬 Codex CLI (AI / 비신뢰 입력에 노출됨)
      │ MCP stdio / 구조화 도구
      ▼
MCP stdio Facade (명령 실행 없음; 사용자 세션 프로세스)
      │ 로컬 Named Pipe + ACL/발신자 SID 검증
      ▼
Policy Broker (별도 제한 서비스; deny-by-default / 승인 / 예산)
      │           ├─ SQLite: 작업 상태·예산·감사 로그
      │           └─ 관리자 전용 승인 CLI (모델과 별도 채널)
      ▼
Restricted Worker (전용 Windows 표준 사용자 계정)
      ├─ File adapter: allowlisted workspace only
      ├─ Read-only diagnostics adapter
      └─ Isolated bounded jobs (Windows Job Objects)
      ▼
승인된 파일·허용 작업만 접근
```

## 신뢰 경계

1. 사용자 지시/AI 생성 인자/파일·웹 콘텐츠는 모두 불신 입력. 도구 설명만으로 접근 권한이 결정되지 않는다.
2. 정책과 감사 기록은 워커 계정이 수정할 수 없는 관리자 소유 위치에 둔다.
3. stdio Facade는 권한 있는 파일·시스템 API를 호출하지 않는다. 권한 검사는 별도 제한 서비스의 **Policy Broker가 실행 직전** 재검증한다. Named Pipe는 Windows ACL과 클라이언트 SID를 검증한다.
4. 대량 변경의 경우 사전 계획과 변경 대상 목록 해시를 승인에 바인딩해 TOCTOU 방지.
5. 서비스가 오류를 반환하거나 정책·DB가 이용 불가능하면 모든 변경 작업은 거부(읽기도 접근 정책을 검증).

## 프로세스/권한

- `JSC-AI-Worker`라는 이름의 별도 표준 사용자 계정(실제 계정 이름은 설치 시 결정), 관리자가 아님. 별도 제한 서비스와 worker를 이 계정으로 실행한다.
- Codex가 실행하는 stdio Facade 자체에는 파일 변경/프로세스 실행 기능을 두지 않는다. **사용자 로그인 세션이나 Codex가 관리자 권한인 경우에도 OS 권한을 작업에 전달하지 않도록** 서비스 경계를 분리하고, 일반 사용자를 권장한다.
- `SeDebugPrivilege`, `SeBackupPrivilege`, `SeRestorePrivilege`, 서비스 제어 및 자격증명 디렉터리 접근 없음.
- 실행 바이너리·정책 파일·로그 디렉터리의 ACL은 워커에게 쓰기 거부; 정책 업데이트는 로컬 관리자가 별도 CLI로 수행.
- 허용 워크스페이스에만 NTFS ACL Modify; Windows/Program Files/사용자 자격증명에는 쓰기 불가.
- 작업 전용 제한 토큰, 가능한 경우 App Control for Business 정책으로 실행 허용 목록 적용.
- Docker Engine 소켓/Named Pipe에 제한 작업자 계정이 직접 접근할 수 없도록 한다. Docker 권한은 사실상 호스트 전체 권한으로 상승할 수 있으므로, 진단은 별도 좁은 읽기전용 중개 API 또는 주기적 상태 스냅샷으로 제공한다.
- 파일 작업은 별도 프로세스/스레드로 분리해 제한 범위를 명확하게 한다.
- 신뢰할 수 없는 소스의 빌드/테스트 스크립트는 호스트에서 실행하지 않는다. 향후 실행 시 격리 Windows VM/Windows Sandbox 및 네트워크 차단이 필요하다. Job Objects만으로 공격 코드를 격리할 수 없다.

## 파일 경로 검증

`D:\JSC-AI-Workspace` 같은 구체적 workspace root만 허용하며 경로 문자열 prefix 검사만으로 판단하지 않는다.

- 절대 경로 정규화, UNC/네트워크 공유/장치 네임스페이스/ADS/상위 경로(`..`) 차단.
- `junction`, symbolic link, 다른 NTFS reparse point를 경유하는 쓰기 거부.
- 최종 파일 핸들을 열어 최종 경로·볼륨·대상 식별자 확인 및 허용 루트 내부 여부 재검증.
- 보호 파일로 이어지는 hardlink는 쓰기 금지(여러 링크 보유 파일 쓰기 차단을 기본값으로 검토).
- 검사와 쓰기 사이 대상 교체를 막기 위해 가능한 한 같은 핸들·잠금/열기 모드 사용.
- 대량 작업은 파일 개수·용량 상한으로 제한; 이름만 바꿔서 정책을 우회하는지 테스트.

## 승인 경로 (GUI 없음)

- 로컬 관리자 셸에서 `jscctl pending`, `jscctl approve <request-id>`로 **사용자가 직접** 검토·승인.
- 승인은 해시된 실행 계획(도구, 인자, 대상 파일 목록, 경로, 변경량), 요청자, 만료시간, nonce에 결합.
- 승인 유효기간 예: 2분, 1회용; 승인 후 인자 변경 시 무효.
- AI/콘텐츠가 보낸 `approve=true`, 대화 중 '승인합니다'는 승인 토큰이 아님.
- 승인 CLI가 없는 환경에서는 위험 작업 불가(조용히 우회하지 않음).

## 저장/복구

- 스냅샷은 워커가 삭제할 수 없는 보호 디렉터리, 용량 및 보존 기간 제한. 스냅샷 파일에도 민감정보가 포함될 수 있어 별도 ACL과 필요 시 DPAPI 등 보호를 적용한다.
- 기존 파일 SHA-256 해시와 사용자가 승인한 예상 버전 비교 후 변경.
- 임시 파일을 같은 볼륨에 생성하고 flush 후 ReplaceFile/MoveFileEx 방식으로 교체, 성공 시 해시 검사.
- 여러 파일의 변경은 원자적이지 않을 수 있음. 전체 변경 manifest와 개별 파일 복원 계획 유지.
- 로그에는 비밀 키·토큰·원문 기밀 데이터 저장 금지. 출력은 크기 제한 및 비밀정보 마스킹.

## v1 범위 제외

- 사용자 세션의 GUI 클릭/타이핑, 임의 바이너리 실행, 브라우저 인증서·암호 저장소 접근, OS 패치/레지스트리 변경, 서비스 중지, 관리자 권한 상승.
- 원격 ChatGPT 접속은 v2 별도 보안 경계(OAuth/HTTPS/Origin 검증/요청자별 권한) 마련 후 판단.
