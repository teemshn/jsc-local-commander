# GitHub 비공개 저장소 생성·업로드

현재 ChatGPT 연결의 GitHub 도구에는 **새 저장소 생성 기능이 노출되어 있지 않으므로** 이 설계 묶음을 자동 업로드하지 못할 수 있습니다.

권장 저장소명: `jsc-local-commander` / **private**.

GitHub CLI가 인증된 Windows PowerShell에서 실행 가능하면:

```powershell
gh auth status
# 필요하면 gh auth login으로 사용자 인증
cd <압축을 푼 jsc-local-commander 폴더>
git init
git add .
git commit -m "docs: security-first architecture and threat review"
gh repo create jsc-local-commander --private --source . --remote origin --push
```

복수 GitHub 계정 사용 시 `gh auth status`와 `gh auth switch`로 **대상 계정 확인**. 저장소 소유자가 지정되지 않았다면 `gh repo create OWNER/jsc-local-commander ...`처럼 명시.

이 명령은 예시이고 **아직 실행하지 않았습니다**. 업로드 전에 폴더 안에 실제 IP, 토큰, 인증서, 개인정보가 포함되어 있지 않은지 확인하세요.
