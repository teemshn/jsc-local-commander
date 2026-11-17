# Security review v0.2 — 2026-11-17

**Scope:** source and pure unit tests; no physical JSCPC deployment, no Windows ACL verification, no VM claim. GitHub source review found v0.1 was a *direct* stdio in-process Commander, so its stated 'broker' boundary did not exist.

| Severity | v0.1 finding | v0.2 change | Remaining risk |
|---|---|---|---|
| Critical | Model-facing MCP calls policy engine in same process | stdio facade now forwards to separate authenticated AF_PIPE broker | Dedicated account and ACL provisioning not verified |
| High | File changed after disk replacement but DB record not committed | Persist `applying` intent; startup locks on unresolved writes; admin-only hash reconciliation | Crash mid-IO needs Windows kill/reboot drill |
| High | Emergency stop checked only on entry | Recheck under SQLite lock immediately before replacement | No mid-IO hard kill |
| High | Read file size checked before unbounded read | File descriptor bounded reads, fstat/inode verification | NTFS race-resistant handle algorithms outstanding |
| High | Reusing idempotency key for different plans | Unique global index and explicit collision rejection | State DB protected by OS ACL only |
| High | Write operations could overlap | Reject any globally active `applying` plan | Other programs may still modify workspace |
| Medium | Partial sensitive names allowed | Strict filename deny patterns added | Content may still contain undetected secrets |
| Medium | ACL check requested combined rights, allowing one denied bit to conceal granted bit | Individually probe write/delete/DAC/owner rights plus ancestor takeover | Not a full effective-access ACL/SID audit |
| Medium | Incomplete recovery instructions | Offline `review-recovery` and explicit `reconcile-recovery` (no file overwrite) | Requires broker stopped manually |
| High | Windows process/host isolation untested | Windows pipe smoke test + Windows CI matrix, audit script | CI != production ACL or sandbox proof |

**Deliberately not enabled:** PowerShell/shell, process termination, service control, Docker control, file deletion, GUI automation, network listener. They require a separate Windows privilege and resource-execution review.

**Deployment gate:** all Windows integration tests, two-account ACL checks, pipe hijack/DoS, path races, 34 scenario review, emergency stop/recovery and restart/kill trials under VM; then staged isolated host rollout. No production JSCPC installation now.

## Additional Windows CI findings

- GitHub Windows hosted runner executes as `runneradmin`. Synthetic temp-directory tests now pass `allow_admin=True`, while production broker construction still refuses elevation.
- Windows `Path.write_text()` default newline translation makes fixture SHA differ from LF-byte fixtures. Tests now use literal bytes for deterministic SHA-256 expectations, without weakening real file hash checks.
- Added independent policy validation denying whole drive roots, `Users`, `Windows`, `ProgramData`, `Recovery`, UNC and removable/network drives. This is layered on top of NTFS permissions, not an OS sandbox.
