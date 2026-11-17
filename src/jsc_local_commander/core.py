"""Deny-by-default workspace operations. Not a host isolation boundary by itself."""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import time
import uuid
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path

MAX_TEXT = 256 * 1024
SAFE_EXTENSIONS = frozenset({'.txt', '.md', '.csv'})
SENSITIVE_PARTS = frozenset({'.ssh', '.aws', '.gnupg', 'npki', 'appdata', 'programdata',
                             'windows', 'system32', 'syswow64', 'program files',
                             'program files (x86)', 'system volume information',
                             '.git', '.env', 'credentials', 'secrets', 'private'})
WINDOWS_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)
SECRET_PATTERN = re.compile(r'(?im)^(\s*(?:api[_-]?key|secret|password|token|authorization)\s*[:=]\s*)[^\r\n]+')
PEM_PATTERN = re.compile(r'-----BEGIN [^-]+PRIVATE KEY-----.*?-----END [^-]+PRIVATE KEY-----', re.S)

class Denied(Exception):
    """Security policy denied the requested operation."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_text(text: str) -> str:
    return PEM_PATTERN.sub('[REDACTED PRIVATE KEY]', SECRET_PATTERN.sub(r'\1[REDACTED]', text))


def admin_mode() -> bool:
    if os.name != 'nt':
        return os.geteuid() == 0
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


@dataclass(frozen=True)
class Policy:
    root: Path
    state: Path
    actor: str = 'local'
    max_calls_task: int = 40
    max_calls_hour: int = 120
    max_writes_task: int = 12
    max_writes_hour: int = 20
    max_file_bytes: int = MAX_TEXT
    min_free_disk_bytes: int = 512 * 1024 * 1024
    plan_ttl_seconds: int = 120

    @classmethod
    def load(cls, allow_admin: bool = False) -> 'Policy':
        if os.name != 'nt':
            raise Denied('Windows-only runtime; other platforms are allowed only for isolated unit tests')
        if admin_mode() and not allow_admin:
            raise Denied('Refusing to run with administrator privileges')
        base = Path(r'C:\ProgramData\JSCCommander')
        cfg = base / 'policy.json'
        if not cfg.is_file() or cfg.is_symlink():
            raise Denied('Missing administrator-managed policy.json; fail closed')
        # Installation MUST protect this file with NTFS ACLs. See SECURITY.md.
        data = json.loads(cfg.read_text(encoding='utf-8'))
        if set(data) != {'workspace', 'state'}:
            raise Denied('Unexpected policy keys')
        root = Path(data['workspace'])
        state = Path(data['state'])
        if not root.is_absolute() or not state.is_absolute() or not root.is_dir():
            raise Denied('Invalid workspace or state configuration')
        if os.path.commonpath([os.path.realpath(root), os.path.realpath(state)]).casefold() == os.path.realpath(root).casefold():
            raise Denied('State may not be inside workspace')
        return cls(root=root, state=state)


class Commander:
    def __init__(self, policy: Policy, allow_admin: bool = False):
        self.p = policy
        if policy.root.is_symlink() or policy.state.is_symlink():
            raise Denied('Unsafe root symlink')
        self.root = policy.root.resolve(strict=True)
        self.state = policy.state.resolve(strict=True)
        if not self.root.is_dir() or not self.state.is_dir():
            raise Denied('Workspace/state directory missing')
        if self.root == self.state or self.root in self.state.parents or self.state in self.root.parents:
            raise Denied('Workspace and state must be separate')
        if self.root.is_symlink() or self.state.is_symlink():
            raise Denied('Unsafe root directory')
        if os.name == 'nt' and admin_mode() and not allow_admin:
            raise Denied('Administrator process forbidden')
        self.db = self.state / 'ledger.sqlite3'
        with self._db() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calls (
                  id INTEGER PRIMARY KEY, task TEXT NOT NULL, actor TEXT NOT NULL,
                  kind TEXT NOT NULL, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS plans (
                  id TEXT PRIMARY KEY, task TEXT NOT NULL, path TEXT NOT NULL,
                  expected TEXT NOT NULL, content BLOB NOT NULL,
                  created REAL NOT NULL, status TEXT NOT NULL,
                  receipt TEXT, idem TEXT);
                CREATE TABLE IF NOT EXISTS audits (
                  id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL,
                  object_hash TEXT NOT NULL, outcome TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ix_calls ON calls(actor, at);
            ''')
            c.execute("INSERT OR IGNORE INTO settings(name,value) VALUES ('emergency','0')")

    @contextmanager
    def _db(self):
        c = sqlite3.connect(self.db, timeout=3, isolation_level=None)
        try:
            c.execute('PRAGMA busy_timeout=3000')
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('PRAGMA synchronous=FULL')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    @staticmethod
    def _task_id(task: str) -> str:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', task):
            raise Denied('Invalid task id')
        return task

    def _audit(self, c, action: str, target: str, outcome: str):
        c.execute('INSERT INTO audits(at,action,object_hash,outcome) VALUES (?,?,?,?)',
                  (time.time(), action, sha(target.encode()), outcome))

    def _charge(self, task: str, kind: str):
        self._task_id(task)
        now = time.time()
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            emergency = c.execute("SELECT value FROM settings WHERE name='emergency'").fetchone()
            if not emergency or emergency[0] != '0':
                raise Denied('Emergency stop active')
            calls = c.execute('SELECT COUNT(*) FROM calls WHERE task=?', (task,)).fetchone()[0]
            hour = c.execute('SELECT COUNT(*) FROM calls WHERE actor=? AND at>?',
                             (self.p.actor, now-3600)).fetchone()[0]
            writes = c.execute("SELECT COUNT(*) FROM calls WHERE task=? AND kind='write'",(task,)).fetchone()[0]
            hour_writes = c.execute("SELECT COUNT(*) FROM calls WHERE actor=? AND kind='write' AND at>?",
                                    (self.p.actor, now-3600)).fetchone()[0]
            if calls >= self.p.max_calls_task or hour >= self.p.max_calls_hour:
                raise Denied('Call budget exhausted')
            if kind == 'write' and (writes >= self.p.max_writes_task or hour_writes >= self.p.max_writes_hour):
                raise Denied('Write budget exhausted')
            first = c.execute('SELECT MIN(at) FROM calls WHERE task=?',(task,)).fetchone()[0]
            if first is not None and now-first > 900:
                raise Denied('Task deadline exceeded')
            c.execute('INSERT INTO calls(task,actor,kind,at) VALUES(?,?,?,?)',
                      (task, self.p.actor, kind, now))
            c.commit()

    def _path(self, path: str, *, must_exist: bool = True) -> Path:
        if not isinstance(path, str) or not path or '\x00' in path:
            raise Denied('Invalid path')
        if path.startswith(('\\\\', '//', '\\\\?', '\\\\.', '/dev/')):
            raise Denied('Network/device paths are forbidden')
        p = Path(path)
        if not p.is_absolute() or '..' in p.parts:
            raise Denied('Absolute path inside workspace required; traversal forbidden')
        if any(part.casefold() in SENSITIVE_PARTS for part in p.parts):
            raise Denied('Sensitive path')
        if os.name == 'nt':
            if ':' in str(p)[2:]:
                raise Denied('Alternate streams are forbidden')
            if any(WINDOWS_RESERVED.match(x) or x.endswith(('.', ' ')) for x in p.parts[1:]):
                raise Denied('Windows special name')
        try:
            rel = p.relative_to(self.root)
        except ValueError:
            # Windows path matching must be case-insensitive.
            if os.name != 'nt' or os.path.commonpath([str(self.root), str(p)]).casefold() != str(self.root).casefold():
                raise Denied('Path outside workspace')
            rel = Path(os.path.relpath(p, self.root))
        cur = self.root
        for part in rel.parts:
            cur = cur / part
            try:
                st = cur.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(st.st_mode):
                raise Denied('Symbolic link forbidden')
            if os.name == 'nt' and bool(getattr(st, 'st_file_attributes', 0) & 0x400):
                raise Denied('NTFS reparse points forbidden')
        if must_exist and not p.exists():
            raise Denied('Path not found')
        resolved = p.resolve(strict=must_exist)
        if resolved != self.root and self.root not in resolved.parents:
            raise Denied('Resolved path escaped workspace')
        return p

    def status(self):
        with self._db() as c:
            e = c.execute("SELECT value FROM settings WHERE name='emergency'").fetchone()
        return {'service': 'JSC Local Commander', 'mode': 'local-stdio',
                'emergency_stop': bool(e and e[0] != '0'),
                'workspace': str(self.root), 'arbitrary_shell': False,
                'deletion': False, 'service_mutation': False}

    def list_workspace(self, task: str, path: str, max_results: int = 100):
        self._charge(task, 'read')
        p = self._path(path)
        if not p.is_dir():
            raise Denied('Not a directory')
        limit = max(1, min(int(max_results), 100))
        out = []
        with os.scandir(p) as entries:
            for entry in entries:
                if len(out) >= limit:
                    break
                try:
                    self._path(entry.path)
                except Denied:
                    continue
                out.append({'name':entry.name, 'directory':entry.is_dir(follow_symlinks=False)})
        return {'files':out, 'truncated':len(out) >= limit}

    def search_files(self, task: str, root: str, suffix: str = '.txt', max_results: int = 100):
        self._charge(task, 'read')
        start = time.monotonic()
        base = self._path(root)
        if not base.is_dir() or suffix not in SAFE_EXTENSIONS:
            raise Denied('Search requires a directory and allowed suffix')
        lim = max(1, min(int(max_results), 100))
        matches, scanned = [], 0
        stack = [base]
        while stack and len(matches) < lim and scanned < 3000 and time.monotonic()-start < 2:
            d = stack.pop()
            with os.scandir(d) as it:
                for f in it:
                    scanned += 1
                    if scanned > 3000:
                        break
                    try:
                        p = self._path(f.path)
                    except Denied:
                        continue
                    if f.is_dir(follow_symlinks=False):
                        stack.append(p)
                    elif f.is_file(follow_symlinks=False) and p.suffix.casefold()==suffix:
                        matches.append(str(p))
                        if len(matches) >= lim:
                            break
        return {'paths':matches, 'scanned':scanned, 'truncated':bool(stack) or len(matches)>=lim or scanned>=3000}

    def read_text(self, task: str, path: str, start_line: int=1, max_lines: int=200):
        self._charge(task, 'read')
        p = self._path(path)
        if not p.is_file() or p.suffix.casefold() not in SAFE_EXTENSIONS or p.stat().st_size>self.p.max_file_bytes:
            raise Denied('Only small ordinary text files are readable')
        lines = p.read_text(encoding='utf-8').splitlines()
        start = max(1,int(start_line))-1
        count = max(1,min(200,int(max_lines)))
        text='\n'.join(lines[start:start+count])
        return {'text':safe_text(text), 'line_count':len(lines), 'truncated':start+count<len(lines)}

    def get_file_info(self, task: str, path: str):
        self._charge(task, 'read')
        p = self._path(path)
        if not p.is_file() or p.suffix.casefold() not in SAFE_EXTENSIONS or p.stat().st_size>self.p.max_file_bytes:
            raise Denied('Unsupported file type or size')
        return {'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}

    def plan_edit(self, task: str, path: str, expected_sha256: str, replacement: str):
        self._charge(task, 'read')
        p = self._path(path)
        if not p.is_file() or p.suffix.casefold() not in SAFE_EXTENSIONS:
            raise Denied('Only existing safe text documents may be edited')
        if len(replacement.encode('utf-8')) > self.p.max_file_bytes:
            raise Denied('Replacement too large')
        old = p.read_bytes()
        if len(old)>self.p.max_file_bytes or sha(old) != expected_sha256:
            raise Denied('Expected hash does not match current file')
        updated = replacement.encode('utf-8')
        plan_id = str(uuid.uuid4())
        with self._db() as c:
            c.execute('INSERT INTO plans VALUES(?,?,?,?,?,?,?,?,?)',
                      (plan_id,task,str(p),sha(old),updated,time.time(),'pending',None,None))
            self._audit(c,'plan',str(p),'PENDING')
        diff = ''.join(list(difflib.unified_diff(
            old.decode('utf-8').splitlines(keepends=True),replacement.splitlines(keepends=True),
            fromfile='before',tofile='after'))[:100])[:6000]
        return {'plan_id':plan_id,'new_sha256':sha(updated),'diff':safe_text(diff),
                'expires_seconds':self.p.plan_ttl_seconds}

    def apply_edit(self, task: str, plan_id: str, idempotency_key: str):
        self._charge(task, 'write')
        if not re.fullmatch(r'[a-f0-9-]{36}', plan_id) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}',idempotency_key):
            raise Denied('Invalid plan or idempotency key')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT task,path,expected,content,created,status,receipt,idem FROM plans WHERE id=?',
                            (plan_id,)).fetchone()
            if not row or row[0] != task:
                raise Denied('Plan absent or task mismatch')
            old_task,path,expected,content,created,status,receipt,idem=row
            if status=='applied':
                if idem == idempotency_key:
                    return json.loads(receipt)
                raise Denied('Plan already executed; different key rejected')
            if status!='pending' or time.time()-created>self.p.plan_ttl_seconds:
                raise Denied('Plan expired or invalid')
            p=self._path(path)
            if not p.is_file() or p.suffix.casefold() not in SAFE_EXTENSIONS:
                raise Denied('File no longer safe')
            st=p.stat()
            if st.st_nlink != 1:
                raise Denied('Hardlinked files cannot be edited')
            data=p.read_bytes()
            if sha(data)!=expected:
                raise Denied('Concurrent file modification detected')
            if shutil.disk_usage(p.parent).free<self.p.min_free_disk_bytes:
                raise Denied('Disk free-space safety threshold not met')
            backups=self.state/'backups'
            backups.mkdir(exist_ok=True)
            backup=backups/(plan_id+'.bak')
            with open(backup,'xb') as f:
                f.write(data);f.flush();os.fsync(f.fileno())
            temp=None
            try:
                with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.jsc-',suffix='.tmp',delete=False) as f:
                    temp=Path(f.name); f.write(content);f.flush();os.fsync(f.fileno())
                os.chmod(temp,stat.S_IMODE(st.st_mode))
                # Revalidate before replacement; still requires dedicated OS ACL isolation for strong race protection.
                if self._path(path)!=p or sha(p.read_bytes())!=expected or p.stat().st_nlink!=1:
                    raise Denied('Target changed during write')
                os.replace(temp,p)
                if sha(p.read_bytes())!=sha(content):
                    raise Denied('Post-write verification failed; manual restore required')
            finally:
                if temp is not None and temp.exists():
                    temp.unlink()
            result={'status':'applied','path':str(p),'sha256':sha(content),'backup_id':plan_id}
            c.execute('UPDATE plans SET status=?,receipt=?,idem=? WHERE id=?',
                      ('applied',json.dumps(result),idempotency_key,plan_id))
            self._audit(c,'apply',str(p),'APPLIED')
            c.commit()
            return result

    def audits(self, task: str, limit: int=30):
        self._charge(task,'read')
        with self._db() as c:
            rows=c.execute('SELECT at,action,object_hash,outcome FROM audits ORDER BY id DESC LIMIT ?',
                           (max(1,min(50,int(limit))),)).fetchall()
        return [{'at':x[0], 'action':x[1], 'path_digest':x[2], 'result':x[3]} for x in rows]

    def emergency(self, stop: bool):
        # This method is for the out-of-band administrative CLI ONLY; never export as MCP tool.
        if os.name == 'nt' and not admin_mode():
            raise Denied('Administrator console required')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute("UPDATE settings SET value=? WHERE name='emergency'",('1' if stop else '0',))
            self._audit(c,'emergency','global','STOP' if stop else 'RESUME')
            c.commit()
