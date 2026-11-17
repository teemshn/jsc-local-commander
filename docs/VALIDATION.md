# 구현 및 검증 상태

## 현재 구현

- MCP stdio 8개 도구 (`get_status`, `list_workspace`, `search_files`, `read_text`, `get_file_info`, `plan_edit`, `apply_edit`, `get_audit_events`)
- Windows 관리자 권한 실행 거부, 설정 미존재 시 fail closed
- 지정 작업폴더만 접근, 민감 경로/파일 종류 차단, 링크 차단, 해시 비교, 하드링크 쓰기 차단
- SQLite 영속 호출 예산(작업별·시간당), 변경 계획 TTL/중복 처리
- 원본 백업, 임시파일 flush + atomic replace, 변경 후 hash 확인
- 중요 시스템 관리 및 임의 명령 실행 도구 미제공

## 아직 미구현 / 배포 블로커

- 관리자 소유 분리된 Policy Broker + Named Pipe 인증/ACL/클라이언트 SID 검증
- 관리자 전용 승인 채널(코드/설정 변경은 현재 **완전 차단**)
- Windows 파일 핸들 기반 ACL/정규화/경합 방어와 TOCTOU 압박 시험
- Windows 전용 서비스 계정 설치 스크립트 및 ACL 실측 검증
- 장시간 실행 Job Objects (외부 실행 기능도 현재 없음)
- 별도 프로세스에 의한 state/backup 변조 방어, 백업 복원 시험
- Windows 10/11 테스트 VM에서 34개 시나리오 완료

**개발 빌드이며 실제 JSCPC 자동 수정 작업에는 사용하지 마세요.**
