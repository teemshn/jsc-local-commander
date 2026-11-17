# v0.2 Validation status

## Executed here (Linux isolated unit environment)

- All core unit and adversarial tests in `tests/test_core.py` + `tests/test_hardening.py`.
- Windows-specific named-pipe integration test in `tests/test_windows_pipe.py` is **skipped** on non-Windows.
- Import/packaging syntax compilation. No real Win32 operations were executed here.

## Windows CI (required, not a production sign-off)

`.github/workflows/ci.yml` runs on `windows-latest` and `ubuntu-latest`, Python 3.11/3.12. Running on a hosted Windows runner exercises the local named-pipe roundtrip. CI runners have temporary, synthetic workspaces and are not a substitute for host hardening.

## Required 34 production release scenarios (NOT YET ALL VERIFIED)

1–8: drive escape, `..`, UNC, ADS, reserved names, junctions, directory symlinks, file symlinks.
9–16: hardlinks, rename racing, symlink swapping, concurrent writers, file growth while reading, wrong hash, duplicate idempotency, protected file ACL.
17–24: API key file exposure, oversize request, invalid protocol, forged/incorrect pipe key, pipe squatting, cross-user access, writable source tree rejection, writable policy rejection.
25–30: write crash immediately after journal, crash before backup, crash after backup, crash after replacement, emergency stop during write, operator recovery wrong choice.
31–34: infinite request attempts, filesystem/SQLite exhaustion, service account isolation, backup/restore drill.

The unit tests cover **some** of these behaviors and not all Win32 attack surfaces. Do not interpret a green CI job as 34/34 acceptance.

Windows Actions runners may execute elevated. Isolated unit tests explicitly opt in to `allow_admin=True` for synthetic temporary paths; a separate Windows test asserts the production constructor **refuses** an elevated runner. This test-only override must never be used to start the real broker.
