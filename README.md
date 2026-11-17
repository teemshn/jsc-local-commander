# JSC Local Commander v0.2 — Security preview

**WINDOWS PRODUCTION DEPLOYMENT BLOCKED.** This release implements a split local named-pipe broker, hardens document writes, and adds crash reconciliation. It is **not** a verified Windows sandbox, and **does not** implement general PowerShell, Docker, service mutations or browser/GUI control.

## Components

```text
Codex CLI (or other local MCP host)
      |
      | stdio, NO filesystem methods in MCP frontend
      v
jsc-local-commander serve (unprivileged gateway)
      |
      | authenticated local Windows named pipe, no network server
      v
jsc-local-commander broker (separate restricted Windows identity)
      |
      v
administrator-defined workspace (TXT / MD / CSV only)
```

Broker authentication uses an admin-provisioned, 32-byte random `C:\ProgramData\JSCCommander\gateway.key`; no default key is generated, no remote listener is exposed. **The shared key is authentication, NOT Windows privilege isolation.** The broker identity, filesystem ACLs, installed Python interpreter, dependencies, broker code, parent directories and policy must all be protected against modification by the gateway/AI identity.

## Implemented MCP tools (11)

`get_status`, `get_system_info`, `diagnose_processes`, `diagnose_services`, `list_workspace`, `search_files`, `read_text`, `get_file_info`, `plan_edit`, `apply_edit`, `get_audit_events`.

There is deliberately **no shell**, subprocess execution, process-kill, Windows-service mutation, deletion, Docker or network-access MCP tool. There is no MCP-controlled stop/resume/recovery. Those are reserved for an offline administrator.

## Security properties

- Workspace-only extension allowlist: `.txt`, `.md`, `.csv`. Sensitive names, credential directories, UNC/device prefixes, links/junctions and hard-linked *write targets* are rejected.
- 256 KiB maximum read/write file size, with bounded FD reads and file identity checks (not a fully race-free Windows path API).
- Deny-by-default Windows start-up checks: refuse elevated broker and missing/locally writable policy or code location.
- SHA-256 check, redacted preview, durable `applying` intent, original backup, atomic replacement, post-replacement SHA verification, idempotent receipt.
- **At most one write in progress**; if the process stops mid-write, persisted `applying` state forces emergency stop at startup. No automatic retry.
- Persistent actor-hour and task budgets, limited search/time/outputs. Calls from many freshly minted task IDs share the same hourly budget.
- Offline operator recovery verifies whether the file equals the original or planned hash. Mismatches are never overwritten automatically.

## Setup (ONLY for an isolated Windows test VM)

1. Use two distinct Windows standard accounts: a restricted **broker** account with access to only its workspace and state, and an unprivileged **gateway** account allowed to access only the authentication key. Never run either as SYSTEM or administrator. Disable interactive logon for the broker via administrator-managed policy where appropriate.
2. Administrator provisions an immutable installation under an ACL-protected directory (e.g., Program Files) including the **Python interpreter and dependencies**. Do not run the broker from a user-writable checkout, `%TEMP%`, Desktop, Downloads, or a writable `.venv`.
3. Create `%ProgramData%\JSCCommander\policy.json` (administrator-owned, not writable by either account) with *exactly* `{"workspace":"D:\\JSC-AI-Workspace","state":"C:\\ProgramData\\JSCCommander\\State"}`. These are examples, not detected local paths.
4. Generate 32 cryptographically random bytes as `%ProgramData%\JSCCommander\gateway.key`. Grant **read-only** access to broker and gateway identities; no write/delete/ACL-change rights. Never commit this file. Administrator restricts access to the state folder to the broker account and administrators only; grant no gateway write access to workspace or state.
5. Independently audit effective Windows access rights, symlinks and inherited ACEs. Run the provided **read-only** `scripts/audit-windows-host.ps1`. It is **only an informational audit**, not a certification or installer. First use a disposable test workspace; do not link it to real JSCPC production folders.
6. `py -3.11 -m pip install -e ".[test]"` is for **test VMs only**, not the production runtime. Execute `python -m pytest -q` under Windows. The Windows named-pipe round-trip test runs only on Windows.
7. Start the broker under its separate identity with `python -m jsc_local_commander broker`, then launch the stdio gateway with `python -m jsc_local_commander serve`. Only after VM validation register the gateway with Codex (`codex mcp add ...`).

**Do not reuse the old direct stdio command:** v0.2 requires the separate broker to be running; it intentionally fails closed when the pipe/key cannot be reached.

## Offline recovery (broker must be STOPPED first)

An administrative operator first checks `python -m jsc_local_commander doctor` and the incident ledger, then runs:

```powershell
python -m jsc_local_commander review-recovery --plan-id <GUID>
# Only after verifying the displayed file_state and backup:
python -m jsc_local_commander reconcile-recovery --plan-id <GUID> --observed-state original
# OR --observed-state applied (requires a validated backup)
python -m jsc_local_commander resume
```

The recovery command **never writes the target file**. If the current hash is neither original nor planned, do not force reconciliation. Restore manually from a known-good backup, then inspect before restarting. Resume refuses if any unresolved write remains.

## Constraints and deployment gate

- Local stdio connection to Codex is not equivalent to ChatGPT web access; this release **does not offer ChatGPT web remote access**.
- NTFS path racing and alternate data streams require real Windows attack/ACL tests. The broker must run under a truly restricted identity. Even with the broker, other unrestricted MCPs or an unrestricted Codex shell can bypass the broker: enforce OS-level isolation for the **whole AI process**, not only this MCP.
- Tests passing in CI do not imply the isolation is correct. No Windows production rollout until VM tests, actual identity/ACL verification, file-lock races, named-pipe attack review, kill/reboot drills and restore drills are successful.

Details: [SECURITY.md](SECURITY.md), [docs/VALIDATION.md](docs/VALIDATION.md), [docs/REVIEW_V02.md](docs/REVIEW_V02.md).
