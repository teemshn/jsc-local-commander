# Security: fail-closed first, defense in depth

## Threat model and trust boundaries

Treat everything received through a model/MCP call, including **file contents**, as untrusted. The model is **not** trusted to enforce any access decision. The only security boundary that may protect the host is the OS identity + NTFS ACL + protected installation/state/policy. The gateway authenticator does **not** elevate trust.

Assume the model can choose arbitrary strings as file paths, task IDs, replacement contents, and tool arguments, can ask to repeat calls indefinitely and can include malicious prompt-injection content from documents. Broker dispatch is an explicit tool allowlist, *never* dynamic user-provided method lookup. There is no raw command-execution API.

## Implemented safeguards

- Windows-only production policy load; missing config/key fails startup; no developer-friendly default credentials.
- Broker must be non-elevated, running under a distinct limited account; code, interpreter, package code, policy and key are ACL protected. Effective write/delete/ACL rights are probed individually where possible; this is not a full ACL verification.
- Local authenticated named pipe, JSON-only bounded messages (384 KiB), per-call waiting cap, exact method map, flat arguments, narrow structured responses. No TCP/HTTP listener.
- Only explicit workspace, three small text extensions. No raw command execution, filesystem deletions, Windows service control, Docker sockets, arbitrary process management or protected drive access.
- Bounded reads from descriptors with identity/size checks. Reject symlinks/reparse paths and hardlinks for changes. Windows native directory-handle-based race resistance is **not complete**; VM fuzzing is outstanding.
- Writes require a hash-based plan within TTL and unique idempotency key; commit `applying` intent before touching the file, save backup, recheck emergency state immediately before replacement and post-verify hash.
- On uncertain write outcome or crash, emergency stop is latched and all operations are denied pending offline hash-based reconciliation; no blind retry.
- Hourly and per-task request budget persisted to SQLite across broker restarts. No arbitrary subprocess or unlimited loop executor is exposed.

## Serious residual risks / NOT YET SECURE FOR PRODUCTION

1. Python implementation and interpreter/package directories must be installed under a true administrator-controlled ACL. If an AI-controlled user can modify installed code, they can replace policy logic.
2. Named-pipe default security descriptor and Windows client SID restrictions are **not independently verified**. The 32-byte secret mitigates unauthorized requests but does not prevent a local account that can read the key from making permitted requests; pipe squatting/DoS needs review.
3. Windows path validation has TOCTOU windows. Protection of system files depends on Windows ACL and limited identity, not a perfect Python path filter. Hardlink, junction, ADS, reparse and rename attacks need Win32 handle-level tests.
4. SQLite/backups must be writable by the broker identity only, otherwise a local adversary can clear emergency stop, alter receipts or backups.
5. In-process budget limits are not hard OS resource quotas; hostile filesystem drivers and an unresponsive network-mounted path can still block threads. No arbitrary command execution is supplied until Windows Job Objects and broker kill-on-timeout are implemented.
6. A `status` call is not budgeted; it is intentionally small but could be spammed. Future transport controls should cap such reads.
7. Offline recovery assumes the broker is already stopped by the operator; the code does not currently have an OS-enforced broker process lock for recovery. Never reconcile concurrently.
8. Basic plaintext masking is **not** a complete secrets detector. Point the workspace only at documents known to contain no secrets; the workspace should not hold real credentials.
9. This policy affects **this MCP only**. Any connected unrestricted MCP, shell, elevated Codex process or account with broad filesystem access can bypass it entirely.
10. Backup retention uses a 512 MiB cap and does not automatically delete backups; operator-driven cleanup and restore validation are needed.

## Operating rules

- Do not use a Windows administrator or SYSTEM identity for the broker or gateway.
- Do not deploy directly to a server hosting real services before disposable VM and actual host ACL tests.
- Do not attach Docker named pipes or administrative credentials to this broker.
- Do not store secrets/keys/IPs in GitHub, issues, CI logs or model prompts.
- Shut down the broker and use an administrator console for emergency stop/recovery only; these commands are absent from the MCP surface.

Security issues: report privately; do not post credentials or exploit traces in public issues.
