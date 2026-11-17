import hashlib
import json
import os
from pathlib import Path

import pytest
from jsc_local_commander.core import Commander, Denied, Policy

@pytest.fixture
def env(tmp_path):
    root=tmp_path/'workspace'; state=tmp_path/'state'
    root.mkdir(); state.mkdir()
    target=root/'notes.txt';target.write_text('before\n',encoding='utf-8')
    return Commander(Policy(root=root,state=state,min_free_disk_bytes=0)), target

def digest(content):return hashlib.sha256(content).hexdigest()

def test_status_and_safe_read(env):
    c,p=env
    assert c.status()['arbitrary_shell'] is False
    assert c.read_text('task01',str(p))['text']=='before'
    assert c.get_file_info('task01',str(p))['sha256']==digest(b'before\n')
    assert 'notes.txt' in [x['name'] for x in c.list_workspace('task01',str(p.parent))['files']]

def test_path_outside_and_traversal_denied(env,tmp_path):
    c,p=env
    extra=tmp_path/'bad.txt';extra.write_text('bad')
    for bad in [str(extra),str(p.parent/'..'/'bad.txt'),'../bad.txt','file.txt','//srv/host.txt']:
        with pytest.raises(Denied): c.read_text('task02',bad)

def test_sensitive_and_script_denied(env):
    c,p=env
    (p.parent/'.env').write_text('SECRET=yes')
    (p.parent/'run.ps1').write_text('bad')
    for name in ('.env','run.ps1'):
        with pytest.raises(Denied): c.read_text('task03',str(p.parent/name))

def test_symlink_denied(env,tmp_path):
    c,p=env
    outside=tmp_path/'external.txt';outside.write_text('outside')
    link=p.parent/'external.txt'
    try: link.symlink_to(outside)
    except OSError: pytest.skip('symlinks need elevated privilege here')
    with pytest.raises(Denied): c.read_text('task04',str(link))

def test_backup_dedup_and_hash_mismatch(env):
    c,p=env
    plan=c.plan_edit('task05',str(p),digest(b'before\n'),'after\n')
    assert p.read_text()=='before\n'
    result=c.apply_edit('task05',plan['plan_id'],'unique-key-0001')
    assert result['status']=='applied'
    assert p.read_text()=='after\n'
    assert (c.state/'backups'/(plan['plan_id']+'.bak')).read_text()=='before\n'
    assert c.apply_edit('task05',plan['plan_id'],'unique-key-0001') == result
    with pytest.raises(Denied): c.apply_edit('task05',plan['plan_id'],'different-key-0002')
    with pytest.raises(Denied): c.plan_edit('task05',str(p),digest(b'before\n'),'invalid')

def test_concurrent_change_refused(env):
    c,p=env
    plan=c.plan_edit('task06',str(p),digest(b'before\n'),'after\n')
    p.write_text('someone else changed this')
    with pytest.raises(Denied): c.apply_edit('task06',plan['plan_id'],'another-key-1234')
    assert p.read_text()=='someone else changed this'

def test_repeated_new_tasks_hit_actor_hourly_budget(env):
    c,p=env
    for n in range(120):c.status() if False else c.read_text(f'request{n}',str(p))
    with pytest.raises(Denied):c.read_text('request121',str(p))

def test_task_budget_and_emergency(env):
    c,p=env
    for n in range(40): c.read_text('same-task',str(p))
    with pytest.raises(Denied):c.read_text('same-task',str(p))
    c.emergency(True)
    with pytest.raises(Denied):c.read_text('other-task',str(p))
    assert c.status()['emergency_stop'] is True
    c.emergency(False)
    assert c.read_text('other-task',str(p))['text']=='before'

def test_hardlink_refuses_write(env):
    c,p=env
    hard=p.parent/'hard.txt'
    try:os.link(p,hard)
    except OSError: pytest.skip('hardlinks not supported')
    plan=c.plan_edit('task-hard',str(p),digest(b'before\n'),'after\n')
    with pytest.raises(Denied):c.apply_edit('task-hard',plan['plan_id'],'unique-key-hard1')

def test_plan_expiry(env):
    c,p=env
    plan=c.plan_edit('task-expiry',str(p),digest(b'before\n'),'after\n')
    with c._db() as db:
        db.execute('UPDATE plans SET created=? WHERE id=?',(0,plan['plan_id']))
    with pytest.raises(Denied):c.apply_edit('task-expiry',plan['plan_id'],'key-expire-1234')

def test_disk_limit_blocks_write(env):
    c,p=env
    object.__setattr__(c,'p',Policy(root=c.root,state=c.state,min_free_disk_bytes=10**18))
    plan=c.plan_edit('task-disk',str(p),digest(b'before\n'),'after\n')
    with pytest.raises(Denied):c.apply_edit('task-disk',plan['plan_id'],'disk-space-key1')

def test_secret_masking(env):
    c,p=env
    p.write_text('PASSWORD=abc123\nordinary text\n')
    content=c.read_text('task-secret',str(p))['text']
    assert 'abc123' not in content
    assert '[REDACTED]' in content

def test_search_is_bounded(env):
    c,p=env
    for i in range(102):(p.parent/f'{i}.txt').write_text('x')
    r=c.search_files('task-search',str(p.parent),'.txt',100)
    assert len(r['paths'])<=100
    assert r['truncated']

def test_no_unsafe_code_edit(env):
    c,p=env
    script=p.parent/'deploy.sh';script.write_text('echo danger')
    with pytest.raises(Denied):c.plan_edit('task-code',str(script),digest(b'echo danger'),'new')
