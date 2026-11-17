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
import ntpath
import time
import uuid
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path

MAX_TEXT = 256 * 1024
MAX_BACKUPS = 512 * 1024 * 1024
SAFE_EXTENSIONS = frozenset({'.txt', '.md', '.csv'})
# Deny high-risk names even when their file extension looks innocuous.
SENSITIVE_NAME = re.compile(r'(?i)(?:^|[._-])(?:env|secret|secrets|token|tokens|password|passwd|credential|credentials|private|id_rsa|id_ed25519|npki|apikey|api_key)(?:[._-]|$)')
SENSITIVE_PARTS = frozenset({'.ssh', '.aws', '.gnupg', 'npki', 'appdata', 'programdata',
                             'windows', 'users', 'recovery', '$recycle.bin', 'boot', 'efi',
                             'perflogs', 'system32', 'syswow64', 'program files',
                             'program files (x86)', 'system volume information',
                             '.git', '.env', 'credentials', 'secrets', 'private'})
WINDOWS_RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)
SECRET_PATTERN = re.compile(r'(?im)^([ \t]*[+-]?[ \t]*(?:api[_-]?key|secret|password|token|authorization)[ \t]*[:=][ \t]*)[^\r\n]+')
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


def _require_windows_readonly(path: Path, *, directory: bool = False) -> None:
    """Conservative effective-access probe for the current token.

    An attempted combined mask is insufficient: an ACL may deny one bit but
    grant another. Probe each dangerous permission separately; fail on any
    unrecognised Win32 error. Still NOT a complete DACL/SID security audit.
    """
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    creator = kernel.CreateFileW
    creator.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    creator.restype = wintypes.HANDLE
    closer = kernel.CloseHandle
    closer.argtypes = [wintypes.HANDLE]
    closer.restype = wintypes.BOOL
    flags = 0x02000000 if directory else 0  # FILE_FLAG_BACKUP_SEMANTICS
    # WRITE_DATA/ADD_FILE, APPEND_DATA/ADD_SUBDIR, DELETE_CHILD,
    # WRITE_ATTRIBUTES, DELETE, WRITE_DAC, WRITE_OWNER.
    dangerous = [0x2, 0x4, 0x100, 0x10000, 0x40000, 0x80000]
    if directory:
        dangerous.append(0x40)
    for bit in dangerous:
        h = creator(str(path), bit, 0x7, None, 3, flags, None)
        raw = ctypes.cast(h, ctypes.c_void_p).value
        if raw is not None and raw != ctypes.c_void_p(-1).value:
            closer(h)
            raise Denied('Unsafe writable policy/code location')
        if ctypes.get_last_error() != 5:  # ERROR_ACCESS_DENIED
            raise Denied('Cannot prove policy/code path is protected')


def _require_windows_protected_ancestors(path: Path):
    """Reject rename/deletion or permission takeover on parent directories."""
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    f = kernel.CreateFileW
    f.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    f.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    for parent in path.parents:
        if not parent.exists():
            raise Denied('Unexpected missing protected ancestor')
        for bit in (0x40, 0x10000, 0x40000, 0x80000):
            h = f(str(parent),bit,0x7,None,3,0x02000000,None)
            raw = ctypes.cast(h,ctypes.c_void_p).value
            if raw is not None and raw != ctypes.c_void_p(-1).value:
                kernel.CloseHandle(h)
                raise Denied('Unsafe mutable ancestor of protected path')
            if ctypes.get_last_error() != 5:
                raise Denied('Cannot prove ancestor protections')



def validate_windows_policy_paths(workspace: str, state: str) -> None:
    """Lexical validation independent of platform; call again on resolved paths."""
    if not isinstance(workspace,str) or not isinstance(state,str):
        raise Denied('Invalid policy paths')
    for path in (workspace,state):
        if (not ntpath.isabs(path) or path.startswith(('\\\\','//')) or
                '/' in path or '..' in path.split('\\') or
                ntpath.normcase(ntpath.normpath(path)) != ntpath.normcase(path)):
            raise Denied('Policy must use a canonical local Windows path')
    drive,tail = ntpath.splitdrive(workspace)
    components = [part.casefold() for part in tail.split('\\') if part]
    if (not drive or len(components) < 1 or
            any(comp in SENSITIVE_PARTS or SENSITIVE_NAME.search(comp) for comp in components)):
        raise Denied('Workspace may not be a drive root or system/user directory')
    if ntpath.normcase(state) != ntpath.normcase(r'C:\ProgramData\JSCCommander\State'):
        raise Denied('State must use the protected administrator-defined location')
    if ntpath.normcase(workspace).startswith(ntpath.normcase(state)+'\\'):
        raise Denied('Workspace cannot be under state')


def _windows_require_fixed_drive(path: Path) -> None:
    if os.name != 'nt':
        return
    import ctypes
    # DRIVE_FIXED = 3. A mapped/network or removable drive may hang or be
    # substituted by remote actors, and is not a supported safe workspace.
    root = str(path.drive) + '\\'
    if ctypes.windll.kernel32.GetDriveTypeW(root) != 3:
        raise Denied('Policy directories must reside on local fixed drives')


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
        # This rejects commonly unsafe ACL setups, but is not a complete DACL audit.
        if not (allow_admin and admin_mode()):
            _require_windows_readonly(cfg)
            _require_windows_readonly(cfg.parent, directory=True)
            _require_windows_readonly(Path(__file__).resolve())
            _require_windows_readonly(Path(__file__).resolve().parent, directory=True)
            _require_windows_protected_ancestors(cfg)
            _require_windows_protected_ancestors(Path(__file__).resolve())
        data = json.loads(cfg.read_text(encoding='utf-8'))
        if set(data) != {'workspace', 'state'}:
            raise Denied('Unexpected policy keys')
        validate_windows_policy_paths(data['workspace'],data['state'])
        root = Path(data['workspace'])
        state = Path(data['state'])
        if not root.is_absolute() or not state.is_absolute() or not root.is_dir():
            raise Denied('Invalid workspace or state configuration')
        _windows_require_fixed_drive(root)
        _windows_require_fixed_drive(state)
        validate_windows_policy_paths(str(root.resolve(strict=True)), str(state.resolve(strict=True)))
        if any(part.casefold() in SENSITIVE_PARTS for part in root.parts):
            raise Denied('Workspace cannot be placed under a protected system location')
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
        for d in (self.root, self.state):
            if d.is_symlink() or (os.name == 'nt' and (getattr(d.lstat(), 'st_file_attributes', 0) & 0x400)):
                raise Denied('Unsafe reparse root directory')
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
                CREATE UNIQUE INDEX IF NOT EXISTS ix_plans_idem ON plans(idem) WHERE idem IS NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS ix_plans_active_target ON plans(path) WHERE status='applying';
            ''')
            c.execute("INSERT OR IGNORE INTO settings(name,value) VALUES ('emergency','0')")
            # Crash-safe fail closed: if a prior write died mid-flight, no new work
            # may start until an operator investigates and explicitly reconciles.
            stuck = c.execute("SELECT COUNT(*) FROM plans WHERE status='applying'").fetchone()[0]
            if stuck:
                c.execute("UPDATE settings SET value='1' WHERE name='emergency'")

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
        if any(part.casefold() in SENSITIVE_PARTS or SENSITIVE_NAME.search(part) for part in rel.parts):
            raise Denied('Sensitive path')
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
        with self._db() as c:
            unresolved = c.execute("SELECT COUNT(*) FROM plans WHERE status='applying'").fetchone()[0]
        return {'service': 'JSC Local Commander', 'mode': 'isolated-local-broker',
                'unresolved_writes': unresolved,
                'emergency_stop': bool(e and e[0] != '0'),
                'workspace': str(self.root), 'arbitrary_shell': False,
                'deletion': False, 'service_mutation': False}

    def system_info(self, task: str):
        """Read-only host health snapshot; never exposes environment variables or secrets."""
        self._charge(task, 'read')
        import platform
        import psutil
        ram = psutil.virtual_memory()
        disk = shutil.disk_usage(self.root)
        return {'os': platform.system(), 'release': platform.release(),
                'cpu_cores': os.cpu_count(), 'memory_total': ram.total,
                'memory_available': ram.available, 'workspace_disk_free': disk.free}

    def diagnose_processes(self, task: str, name_fragment: str = '', max_results: int = 30):
        """Read-only PID/name/status; no command line or arguments disclosure."""
        self._charge(task, 'read')
        import psutil
        term = name_fragment.strip().casefold()
        if len(term)>32: raise Denied('Filter too long')
        limit = max(1, min(int(max_results), 50))
        items=[]
        deadline = time.monotonic()+2
        for proc in psutil.process_iter(attrs=['pid','name','status'],ad_value=None):
            if len(items)>=limit or time.monotonic()>deadline:break
            try:
                data=proc.info
                name=data.get('name') or ''
                if term and term not in name.casefold(): continue
                items.append({'pid':data['pid'],'name':name[:100],'status':data.get('status')})
            except (psutil.NoSuchProcess,psutil.AccessDenied,psutil.ZombieProcess):
                continue
        return {'processes':items,'truncated':len(items)>=limit}

    def diagnose_services(self, task: str, name_fragment: str = '', max_results: int = 30):
        """Windows services status only; this code cannot start or stop a service."""
        self._charge(task, 'read')
        if os.name!='nt':raise Denied('Windows-only service diagnostics')
        import psutil
        term=name_fragment.strip().casefold()
        if len(term)>32:raise Denied('Filter too long')
        limit=max(1,min(int(max_results),50))
        items=[]
        deadline=time.monotonic()+2
        for service in psutil.win_service_iter():
            if len(items)>=limit or time.monotonic()>deadline:break
            try:
                name=service.name()
                if term and term not in name.casefold():continue
                items.append({'name':name[:100],'status':service.status()})
            except (OSError,psutil.AccessDenied):
                continue
        return {'services':items,'truncated':len(items)>=limit}

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

    def _read_bounded(self, p: Path, *, for_write: bool = False) -> bytes:
        """Open and inspect an ordinary file; reject file swaps and oversize reads.

        This is defense in depth, NOT a complete Windows TOCTOU or ACL boundary.
        Protected NTFS ACLs and a dedicated OS identity are still mandatory.
        """
        self._path(str(p))
        before = p.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise Denied('Not an ordinary file')
        if before.st_size > self.p.max_file_bytes:
            raise Denied('File too large')
        if for_write and (before.st_nlink != 1 or before.st_mode & stat.S_IWUSR == 0):
            raise Denied('Hardlinked/read-only target refused')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(p, flags)
        try:
            actual = os.fstat(fd)
            if (not stat.S_ISREG(actual.st_mode) or
                actual.st_size > self.p.max_file_bytes or
                (for_write and actual.st_nlink != 1) or
                (actual.st_dev, actual.st_ino) != (before.st_dev, before.st_ino)):
                raise Denied('File changed or unsafe after opening')
            data = bytearray()
            while len(data) <= self.p.max_file_bytes:
                block = os.read(fd, min(65536, self.p.max_file_bytes + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
            if len(data) > self.p.max_file_bytes:
                raise Denied('File grew beyond size limit')
            after = p.lstat()
            if ((after.st_dev, after.st_ino) != (actual.st_dev, actual.st_ino) or
                not stat.S_ISREG(after.st_mode) or
                (for_write and after.st_nlink != 1)):
                raise Denied('File replaced during inspection')
            self._path(str(p))
            return bytes(data)
        finally:
            os.close(fd)

    def read_text(self, task: str, path: str, start_line: int=1, max_lines: int=200):
        self._charge(task, 'read')
        p = self._path(path)
        if p.suffix.casefold() not in SAFE_EXTENSIONS:
            raise Denied('Only approved text extensions are readable')
        try:
            lines = self._read_bounded(p).decode('utf-8').splitlines()
        except UnicodeError as exc:
            raise Denied('Invalid UTF-8 text') from exc
        start = max(1,int(start_line))-1
        count = max(1,min(200,int(max_lines)))
        text='\n'.join(lines[start:start+count])
        return {'text':safe_text(text), 'line_count':len(lines), 'truncated':start+count<len(lines)}

    def get_file_info(self, task: str, path: str):
        self._charge(task, 'read')
        p = self._path(path)
        if p.suffix.casefold() not in SAFE_EXTENSIONS:
            raise Denied('Unsupported extension')
        data = self._read_bounded(p)
        return {'bytes':len(data),'sha256':sha(data)}

    def plan_edit(self, task: str, path: str, expected_sha256: str, replacement: str):
        self._charge(task, 'read')
        p = self._path(path)
        if p.suffix.casefold() not in SAFE_EXTENSIONS:
            raise Denied('Only safe text documents may be edited')
        if not isinstance(replacement, str):
            raise Denied('Replacement must be text')
        if len(replacement.encode('utf-8')) > self.p.max_file_bytes:
            raise Denied('Replacement too large')
        old = self._read_bounded(p, for_write=True)
        if sha(old) != expected_sha256:
            raise Denied('Expected hash does not match current file')
        updated = replacement.encode('utf-8')
        plan_id = str(uuid.uuid4())
        with self._db() as c:
            c.execute('DELETE FROM plans WHERE created<?', (time.time()-86400,))
            pending_count=c.execute("SELECT COUNT(*) FROM plans WHERE status='pending'").fetchone()[0]
            if pending_count>=50:
                raise Denied('Too many pending plans')
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
        if not re.fullmatch(r'[a-f0-9-]{36}', plan_id) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', idempotency_key):
            raise Denied('Invalid plan or idempotency key')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT task,path,expected,content,created,status,receipt,idem FROM plans WHERE id=?',
                            (plan_id,)).fetchone()
            if not row or row[0] != task:
                raise Denied('Plan absent or task mismatch')
            _, path, expected, content, created, status, receipt, idem = row
            if status == 'applied':
                if idem == idempotency_key:
                    return json.loads(receipt)
                raise Denied('Plan already executed; different key rejected')
            if status != 'pending' or time.time() - created > self.p.plan_ttl_seconds:
                raise Denied('Plan expired or invalid')
            if c.execute("SELECT 1 FROM plans WHERE idem=? AND id<>?", (idempotency_key, plan_id)).fetchone():
                raise Denied('Idempotency key already assigned to another plan')
            if c.execute("SELECT 1 FROM plans WHERE status='applying' LIMIT 1").fetchone():
                raise Denied('Another write is active or unreconciled')
            p = self._path(path)
            if p.suffix.casefold() not in SAFE_EXTENSIONS:
                raise Denied('File extension no longer safe')
            if sha(self._read_bounded(p, for_write=True)) != expected:
                raise Denied('Concurrent file modification detected')
            if shutil.disk_usage(p.parent).free < self.p.min_free_disk_bytes:
                raise Denied('Disk free-space safety threshold not met')
            backups = self.state / 'backups'
            backups.mkdir(exist_ok=True)
            if backups.is_symlink():
                raise Denied('Backup directory unsafe')
            # Phase 1: commit a durable intent. Crash after this point latches
            # emergency mode on next start rather than silently retrying.
            c.execute("UPDATE plans SET status='applying',idem=? WHERE id=?", (idempotency_key, plan_id))
            self._audit(c, 'apply_intent', path, 'PREPARED')
            c.commit()
        # There is intentionally NO automatic retry after this point.
        backup = backups / (plan_id + '.bak')
        temp = None
        try:
            data = self._read_bounded(p, for_write=True)
            if sha(data) != expected:
                raise Denied('Target changed after durable intent')
            backup_total = 0
            for old_backup in backups.glob('*.bak'):
                if old_backup.is_symlink():
                    raise Denied('Backup link refused')
                backup_total += old_backup.stat().st_size
                if backup_total + len(data) > MAX_BACKUPS:
                    raise Denied('Protected backup quota exhausted')
            with open(backup, 'xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            with tempfile.NamedTemporaryFile(dir=p.parent, prefix='.jsc-', suffix='.tmp', delete=False) as f:
                temp = Path(f.name)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            # Revalidate the path and content as close to replacement as possible.
            if sha(self._read_bounded(p, for_write=True)) != expected:
                raise Denied('Target changed before replacement')
            with self._db() as c:
                c.execute('BEGIN IMMEDIATE')
                emergency = c.execute("SELECT value FROM settings WHERE name='emergency'").fetchone()
                if not emergency or emergency[0] != '0':
                    raise Denied('Emergency stop active immediately before replacement')
                st = p.stat()
                os.chmod(temp, stat.S_IMODE(st.st_mode))
                if os.name == 'nt':
                    import ctypes
                    from ctypes import wintypes
                    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                    replace = kernel.ReplaceFileW
                    replace.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                        wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
                    replace.restype = wintypes.BOOL
                    if not replace(str(p), str(temp), None, 0, None, None):
                        raise Denied('Windows atomic replacement failed; investigate pending intent')
                else:
                    os.replace(temp, p)
                if sha(self._read_bounded(p)) != sha(content):
                    raise Denied('Post-write verification failed; operator recovery required')
                result = {'status':'applied', 'path':str(p), 'sha256':sha(content), 'backup_id':plan_id}
                c.execute('UPDATE plans SET status=?,receipt=? WHERE id=?',
                          ('applied', json.dumps(result), plan_id))
                self._audit(c, 'apply', path, 'APPLIED')
                c.commit()
                return result
        except BaseException:
            # Do not permit more work if the filesystem/ledger is indeterminate.
            with self._db() as c:
                c.execute("UPDATE settings SET value='1' WHERE name='emergency'")
                self._audit(c, 'apply', path, 'NEEDS_RECONCILIATION')
            raise
        finally:
            if temp is not None and temp.exists():
                temp.unlink()

    def audits(self, task: str, limit: int=30):
        self._charge(task,'read')
        with self._db() as c:
            rows=c.execute('SELECT at,action,object_hash,outcome FROM audits ORDER BY id DESC LIMIT ?',
                           (max(1,min(50,int(limit))),)).fetchall()
        return [{'at':x[0], 'action':x[1], 'path_digest':x[2], 'result':x[3]} for x in rows]

    def review_recovery(self, plan_id: str) -> dict:
        """Offline operator inspection. Never a model-callable MCP tool."""
        if os.name == 'nt' and not admin_mode():
            raise Denied('Administrator console required')
        with self._db() as c:
            row = c.execute('SELECT path,expected,content,status FROM plans WHERE id=?',
                            (plan_id,)).fetchone()
        if not row or row[3] != 'applying':
            raise Denied('No unresolved plan with this ID')
        path, expected, content, _ = row
        current = sha(self._read_bounded(self._path(path)))
        backup = self.state / 'backups' / (plan_id + '.bak')
        backup_valid = bool(backup.is_file() and not backup.is_symlink() and
                            sha(backup.read_bytes()) == expected)
        result = 'original' if current == expected else 'applied' if current == sha(content) else 'unknown'
        return {'plan_id': plan_id, 'file_state': result, 'backup_valid': backup_valid,
                'requires_operator': True}

    def reconcile_recovery(self, plan_id: str, observed_state: str) -> dict:
        """Mark an unchanged or verified-replaced file; no file data is overwritten.

        The broker MUST be stopped by the operator while reconciling to avoid
        accepting a simultaneously running write; documented operational rule.
        """
        if os.name == 'nt' and not admin_mode():
            raise Denied('Administrator console required')
        if observed_state not in ('original', 'applied'):
            raise Denied('Explicit expected state required')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT value FROM settings WHERE name='emergency'").fetchone() != ('1',):
                raise Denied('Emergency stop must be set before recovery')
            row = c.execute('SELECT path,expected,content,idem,status FROM plans WHERE id=?',
                            (plan_id,)).fetchone()
            if not row or row[4] != 'applying':
                raise Denied('No pending recovery')
            path, expected, content, idem, _ = row
            actual = sha(self._read_bounded(self._path(path)))
            if observed_state == 'original' and actual == expected:
                c.execute("UPDATE plans SET status='aborted' WHERE id=?", (plan_id,))
                result = {'status':'aborted','file_state':'original'}
            elif observed_state == 'applied' and actual == sha(content):
                backup = self.state / 'backups' / (plan_id + '.bak')
                if not backup.is_file() or backup.is_symlink() or sha(backup.read_bytes()) != expected:
                    raise Denied('Cannot verify original backup')
                receipt = {'status':'applied','path':path,'sha256':actual,'backup_id':plan_id}
                c.execute('UPDATE plans SET status=?,receipt=? WHERE id=?',
                          ('applied', json.dumps(receipt), plan_id))
                result = {'status':'applied','file_state':'applied'}
            else:
                raise Denied('File state does not match operator decision')
            self._audit(c, 'operator_reconcile', path, result['status'].upper())
            c.commit()
            return result

    def emergency(self, stop: bool):
        # This method is for the out-of-band administrative CLI ONLY; never export as MCP tool.
        if os.name == 'nt' and not admin_mode():
            raise Denied('Administrator console required')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not stop and c.execute("SELECT 1 FROM plans WHERE status='applying' LIMIT 1").fetchone():
                raise Denied('Cannot resume with unresolved writes; investigate and reconcile offline')
            c.execute("UPDATE settings SET value=? WHERE name='emergency'",('1' if stop else '0',))
            self._audit(c,'emergency','global','STOP' if stop else 'RESUME')
            c.commit()
