# Security policy

This is a security preview, **not a Windows sandbox**. No security guarantees without OS-level standard-user isolation and independent Windows VM/ACL testing.

- Deny-by-default tools: no raw shell, network interface, Docker mutations, elevation, deletion or service actions.
- Workspace allowlist is enforced again before writes; symlinks, NTFS reparse points, hardlink writes and sensitive path components are rejected.
- Persistent SQLite budgets span model calls, across task IDs, per actor; writes require preview hash and idempotency key.
- Workspace backups are stored outside workspace; do not put secrets in any repository or task text.
- The ledger and backup store need OS ACLs. Since the broker is not yet independent, this preview does NOT defend against a malicious process running under the same OS account.
- Do not run Codex or this MCP as administrator. Other unrestricted MCP integrations can bypass these protections.
- Do not run on JSCPC production until all Windows-specific checks, multi-process races, emergency-stop permissions and restore drills are validated.

Report security issues privately; do not open public issues containing credentials or exploit details.
