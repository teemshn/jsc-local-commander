# REMOTE_MOBILE — ChatGPT 대화 → Windows 에이전트 원격 제어 설계

상태: 디자인/권한 검증 전. GitHub의 기존 stdio MCP 서버와 현재 모바일 ChatGPT를 직접 연결했다고 주장하지 않는다.

## R-1. 핵심 목표
휴대폰의 ChatGPT 대화에서 작업요청을 보내고, Windows PC의 LocalBridge 제한 작업기에서 파일 확인 → 승인 → 새 문서·도면 생성 → 결과/에러 반환. 같은 사용자에게 PC 대화 인터페이스 제공. 원격은 기능이 아니라 새로운 보안 신뢰 경계다.

## R-2. 가장 먼저 확인할 현실적 제약 (G0)
- 사용자 실제 ChatGPT 계정/워크스페이스에서 자체 custom MCP 앱 등록 권한이 있는가?
- 모바일 UI에 custom MCP tool이 노출되고 읽기/쓰기 호출할 수 있는가? 브라우저/PC의 권한과 동일하다고 추정하지 않음.
- ChatGPT 제품 내장 Remote/Computer Use가 있다면 동일 목표를 제공하는지 별도 테스트. 이 기능은 자체 MCP 등록과 다르므로 섞어 성공으로 판정하지 않는다.
- OpenAI Platform Secure MCP Tunnel의 조직 권한·키 권한·워크스페이스 연결·비용 조건이 충족되는가?
- G0 합격 조건: 사용자가 실제 스마트폰 대화에서 신규 등록한 *자체* 안전 읽기도구 1회 호출, 도구 호출/결과/장치 IDs 확인. 이후 별도의 시험 파일 신규 생성 1회가 승인 경계와 함께 성공해야 쓰기 게이트 통과.
- 계정/모바일 미지원이면 'BLOCKED'로 기록. 인증된 별도 앱 UI 또는 지원되는 공식 원격 기능은 독립 대안으로 비교하되 원래 ChatGPT 모바일 대화 달성으로 보고하지 않는다.

공식 참고: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
https://developers.openai.com/api/docs/guides/custom-mcp-server
변동이 빠르므로 작업 당일 공식 안내와 계정 UI를 다시 확인한다.

## R-3. 추천 데이터 흐름 (가능성이 검증되면 구현)
    ChatGPT (사용자/워크스페이스 인증)
      → 사용자에게 승인된 MCP server endpoint
      → authenticated broker gateway (OAuth/사용자 식별/요청 scope)
      → 암호화된 장치발신 연결을 유지하는 Windows Device Agent
      → Windows Protected Policy Broker → 제한된 앱 Worker
      → 검증 결과/산출물 → 인증된 역방향 응답

Windows PC에 공인 인바운드 SSH·RDP·MCP 포트를 열지 않는다. 첫 버전은 외부 중계 서비스·로그인 수단이 정확히 검증되기 전까지 네트워크 연결 개발을 비활성화한다.

선택적 Ubuntu/WSL2 역할: Windows 위 Linux-only 터널 프로세스가 꼭 필요할 때만. Windows 프로그램 조작은 반드시 Windows에서 수행. Windows 전원이 꺼져 있으면 WSL2도 동작하지 않으므로 별도 24시간 Ubuntu PC일 때만 오프라인 접수·대기 역할 가능.

## R-4. 인증/승인
- 장치 초기 페어링은 PC 로컬에서 승인, 장치키를 PC 보안 저장소에 보호. 토큰은 로그/작업기 입력/모바일 대화에 그대로 공개하지 않음.
- 요청자 actor_id, workspace/tenant, device_id, action_scope, file_scope, 목적, 승인 유효시간의 정확한 결합 확인.
- 읽기권한과 쓰기권한 분리. 쓰기 토큰은 단기·대상별 서명/nonce/plan hash·일회성.
- 요청이 서명/요청자/장치/nonce/replay-window/모델 도구 scope 하나라도 실패하면 401/403과 감사 기록.
- 앱이 오프라인이면 작업은 안전한 '대기' 상태로만 유지. *재연결되었다고 이미 승인된 변경을 자동 재실행하지 않는다*. 원본 버전 재검증 및 필요시 새 승인 필수.
- 음성·메시지 자연어 중 '승인했다'는 권한 토큰이 아님. 실제 승인 UI가 별도 안전 채널로 수행되는지 실증.
- 민감한 설계도면·고객 계약서 본문은 중앙 서버로 전송하기보다 로컬 워커에서 처리하는 구조 우선.

## R-5. 최소 원격 도구 (신규 설계)
| MCP tool | 목적 | 초기 정책 |
|---|---|---|
| list_paired_devices | 자신의 승인된 장치 목록 | 상세 IP·토큰 노출 없음 |
| get_device_status | 전원·에이전트·승인 대기 상태 | 읽기 |
| plan_local_job | 등록된 recipe와 대상 파일 변경 미리보기 | 계획만 |
| submit_approved_job | 인증/승인 receipt와 plan hash 제출 | 1회 쓰기, 실행 중복 차단 |
| get_job_status | 상태·에러/검증 요약·아티팩트 메타데이터 | 호출자·시간 제한 |
| stop_local_job | 자기 소유 job 긴급 중단 요청 | 재개는 로컬 운영자만 |
| fetch_job_result | 민감도에 맞는 결과 링크/요약 | 다운로드 권한 제한, 만료 |

raw_shell/exec_command/arbitrary_click/browser_credentials와 같은 범용 기능은 초기 네트워크 노출 도구에 포함하지 않는다.

## R-6. 장애·디버그 시나리오
| ID | 유발 조건 | 로그 키/관측 | 통과 기준 |
|---|---|---|---|
| REM-D01 | ChatGPT 모바일 custom MCP 미지원 | app_version, client_type, tool_list | 차단 원인 명시, 성공 주장 없음 |
| REM-D02 | OAuth 만료/다른 사용자 토큰 | subject, audience, scope, expiry | 요청 거부, 재인증 유도 |
| REM-D03 | 장치키 유출/중복 등록 | device_pubkey_hash, last_pair | 권한 철회·재페어링 |
| REM-D04 | 중계에서 중복 패킷/ACK 유실 | job_id, idempotency_key, receipt | 변경 1회만 실행 |
| REM-D05 | 인터넷 끊김/복구 | offline_since, queue_depth | 안전 대기, 변경 재실행 0 |
| REM-D06 | 새 사용자 기기에 접근 | actor_device_binding | 사용자 승인 없는 접근 0 |
| REM-D07 | 잘못된 TLS/터널 대상 | endpoint_id, tls_cert | 중계 연결 실패·키 전송 금지 |
| REM-D08 | 파일 본문/토큰이 서버 로그로 유출 | redaction_event, egress audit | 민감 정보 제거/권한 제한 |
| REM-D09 | 한 요청이 수만 번 폴링 | actor_budget, token_bucket | rate limit, 리소스 변화 제한 |
| REM-D10 | 공격자가 다른 사용자의 승인 재사용 | plan_hash, subject, nonce | 403 및 보안 사건 기록 |
| REM-D11 | 사용자가 재시작 뒤 작업을 다시 요청 | state_version, file_hash | 결과 조회 또는 새 계획; 중복 수정 0 |
| REM-D12 | 터널 API 기능 또는 제품 정책 변경 | api_version, capability_map | 지원 불가로 안전 중단 |

## R-7. 완료 게이트
진짜 모바일 디바이스에서 '서버 상태 조회 → 테스트 폴더 신규 파일 생성 → 원본 파일 안전 수정 → 결과 반환' 순으로 분리 시험. 각각 실제 account permission, HTTP/MCP handshake, OS ACL, 감사, 로컬 승인, 도구 무효화 등을 검증해야 한다. 운영 문서나 회사 PC를 대상으로 하기 전에 전용 격리 환경에서 인증 경계 침투 테스트 필수.
