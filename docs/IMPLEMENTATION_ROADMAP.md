# 단계별 개발 계획 및 산출물

## M0 — 사전 환경 조사 (읽기 전용)

- JSCPC OS/빌드, 계정 권한, 작업 공간, Python/정책, 기존 MCP 연결·접근 권한 확인.
- 사용자 데이터가 있는 실제 디스크·폴더·컨테이너를 직접 대상으로 테스트하지 않음.
- 기준 작업 공간 디렉터리와 Windows 전용 서비스 계정 승인 받기.

## M1 — 정책 우선 구현 (P0)

- Policy Broker, 저권한 Windows 사용자, ACL, 대상 경로/핸들 검증.
- read-only MCP tools, 감사 로그, 호출자·작업 식별 및 fail-closed.
- 아직 파일 수정/명령 실행은 미지원.

## M2 — 안전한 쓰기와 복구 (P0)

- diff/plan hash, snapshot, idempotency, optimistic concurrency, atomic replacement.
- 승인 CLI, 1회·단기 승인, 삭제 제한, 저장공간 예산.
- 격리 VM에서 파일 충돌·중단·권한 우회 테스트.

## M3 — 장시간 작업 관리 (P0/P1)

- Job Object, watchdog, 누적 budget, 중복 방지, 동시성 1~2개 제한, emergency-stop.
- 작업 완료 전 호스트 프로세스 사용량 및 로그 크기 모니터링.

## M4 — 진단/조건부 시스템 작업 (P1)

- Windows/Docker 읽기 전용 조회.
- 실제 서비스 재시작 등은 별도 signed recipe와 승인/롤백/헬스체크가 구현된 후 제한적으로 도입.

## M5 — JSCPC 통합

- stdio MCP를 Codex CLI에 연결. 로컬 무권한·읽기/쓰기·승인·중단을 각각 테스트.
- 기존 SSH MCP와 고위험 도구를 기본 프로필에서 분리.
- **모든 P0 안전성 검증이 완료되기 전에는 운영 서비스 연결 금지.**

## M6 — 선택적인 ChatGPT 웹/모바일 연결

- 별도 요청이 있을 때만 인증된 Streamable HTTP와 터널 추가.
- OAuth/audience/scope 검증·TLS·Origin 검사·요청자별 policy 검증·rate limit·재인증.
- 로컬 v1과 다른 공격 표면에 대해 침투 테스트 다시 수행.

## 배포 전 의사결정

1. 수정 가능한 workspace 경로를 정확히 어디까지 허용할지.
2. 읽기 전용 조회 범위를 사용자 업무 폴더로 제한할지.
3. 어떤 작업을 자동 승인할지 (기본값: 읽기 및 낮은 위험도 변경만).
4. 보호 스냅샷 저장 디스크와 보존 기간.
5. 어떤 Docker/Windows 서비스도 초기 버전에서 실제 재시작하지 않을 것인지.
