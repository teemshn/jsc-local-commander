"""Local authenticated pipe gateway. Only usable on Windows.

Security boundary is the separate *Windows identity* running this broker,
plus NTFS ACLs. Python's authkey verifies possession of a shared secret; it
is NOT an elevation or remote access protocol.
"""
from __future__ import annotations

import json
import os
from multiprocessing.connection import Client, Listener
from pathlib import Path

from .core import Commander, Denied, Policy, _require_windows_readonly

PIPE_NAME = r'\\.\pipe\JSCCommanderV02'
KEY_PATH = Path(r'C:\ProgramData\JSCCommander\gateway.key')
MAX_REQUEST_BYTES = 384 * 1024  # 256KB file + JSON envelope
MAX_REPLY_BYTES = 384 * 1024

# There is no generic getattr dispatch: each callable is enumerated explicitly.
TOOLS = {
    'get_status': ('status', 0),
    'get_system_info': ('system_info', 1),
    'diagnose_processes': ('diagnose_processes', 3),
    'diagnose_services': ('diagnose_services', 3),
    'list_workspace': ('list_workspace', 3),
    'search_files': ('search_files', 4),
    'read_text': ('read_text', 4),
    'get_file_info': ('get_file_info', 2),
    'plan_edit': ('plan_edit', 4),
    'apply_edit': ('apply_edit', 3),
    'get_audit_events': ('audits', 2),
}


def _requires_windows():
    if os.name != 'nt':
        raise Denied('Local named-pipe broker is Windows-only')


def auth_key() -> bytes:
    """No defaults and no environment variables for security-critical secrets."""
    _requires_windows()
    if not KEY_PATH.is_file() or KEY_PATH.is_symlink():
        raise Denied('Administrator-provisioned gateway key missing')
    _require_windows_readonly(KEY_PATH)
    _require_windows_readonly(KEY_PATH.parent, directory=True)
    key = KEY_PATH.read_bytes()
    if len(key) != 32:
        raise Denied('Invalid gateway key')
    return key


def dispatch(commander: Commander, method: str, args: list) -> dict:
    if not isinstance(method, str) or method not in TOOLS:
        return {'error': 'POLICY_DENIED', 'reason': 'Unknown method'}
    if not isinstance(args, list) or len(args) > TOOLS[method][1]:
        return {'error': 'POLICY_DENIED', 'reason': 'Invalid argument count'}
    if any(isinstance(arg, (dict, list, tuple)) for arg in args):
        return {'error': 'POLICY_DENIED', 'reason': 'Nested arguments forbidden'}
    function = getattr(commander, TOOLS[method][0])
    try:
        value = function(*args)
        if isinstance(value, list):
            return {'events': value}
        if not isinstance(value, dict):
            return {'error': 'FAILED_CLOSED', 'reason': 'Invalid broker result'}
        return value
    except Denied as exc:
        return {'error': 'POLICY_DENIED', 'reason': str(exc)}
    except Exception:
        return {'error': 'FAILED_CLOSED', 'reason': 'Internal error; no automatic retries'}


class BrokerClient:
    def __init__(self, key: bytes | None = None, *, address: str = PIPE_NAME):
        _requires_windows()
        self.key = key if key is not None else auth_key()
        self.address = address

    def call(self, name: str, *args):
        if name not in TOOLS or len(args) > TOOLS[name][1]:
            raise Denied('Unsupported tool')
        data = json.dumps({'version': 1, 'method': name, 'args': list(args)},
                          ensure_ascii=False).encode('utf-8')
        if len(data) > MAX_REQUEST_BYTES:
            raise Denied('Request too large')
        with Client(self.address, family='AF_PIPE', authkey=self.key) as c:
            c.send_bytes(data)
            if not c.poll(10):
                raise Denied('Broker timeout')
            response = c.recv_bytes(MAX_REPLY_BYTES)
        value = json.loads(response)
        if not isinstance(value, dict):
            raise Denied('Invalid broker reply')
        return value


class BrokerService:
    """Single-process, single-request-at-a-time reference broker.

    Launch OUTSIDE Codex under a dedicated low-privilege Windows user; do NOT
    run it as SYSTEM/Administrator. Protect its files, Python runtime and
    configuration with NTFS ACLs. No external network listener is created.
    """
    def __init__(self, commander: Commander | None = None, key: bytes | None = None, *, address: str = PIPE_NAME):
        _requires_windows()
        self.commander = commander or Commander(Policy.load())
        self.key = key if key is not None else auth_key()
        if not address.startswith(r'\\.\pipe\JSCCommander'):
            raise Denied('Nonstandard named-pipe endpoint forbidden')
        self.address = address

    def _handle_one(self, listener):
        conn = listener.accept()
        with conn:
            if not conn.poll(3):
                return
            try:
                raw = conn.recv_bytes(MAX_REQUEST_BYTES)
                req = json.loads(raw)
                if (not isinstance(req, dict) or set(req) != {'version','method','args'}
                        or req['version'] != 1):
                    response = {'error':'POLICY_DENIED','reason':'Invalid request schema'}
                else:
                    response = dispatch(self.commander, req['method'], req['args'])
                output = json.dumps(response, ensure_ascii=False).encode('utf-8')
                if len(output) > MAX_REPLY_BYTES:
                    output = b'{"error":"FAILED_CLOSED","reason":"Reply too large"}'
                conn.send_bytes(output)
            except (OSError, ValueError, TypeError, EOFError, json.JSONDecodeError):
                # Reject malformed request without a fallback command handler.
                return

    def serve_once(self):
        """Single request: used for isolated Windows integration tests."""
        with Listener(self.address, family='AF_PIPE', authkey=self.key, backlog=2) as listener:
            self._handle_one(listener)

    def serve_forever(self):
        with Listener(self.address, family='AF_PIPE', authkey=self.key, backlog=2) as listener:
            while True:
                self._handle_one(listener)
