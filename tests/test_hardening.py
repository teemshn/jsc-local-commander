"""Adversarial tests; Linux runs the pure safety logic, Windows CI covers OS cases."""
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from jsc_local_commander.core import Commander, Denied, Policy
from jsc_local_commander.ipc import dispatch, TOOLS, BrokerClient, MAX_REQUEST_BYTES


def prepare(tmp_path):
    workspace = tmp_path/'work'; workspace.mkdir()
    state = tmp_path/'state'; state.mkdir()
    file = workspace/'notes.txt'; file.write_text('before\n', encoding='utf-8')
    return Commander(Policy(root=workspace,state=state,min_free_disk_bytes=0)), file


def digest(data): return hashlib.sha256(data).hexdigest()


def test_gateway_unknown_methods_denied(tmp_path):
    c,_=prepare(tmp_path)
    for method in ('emergency','reconcile_recovery','__getattribute__','execute_shell','getattr','__class__'):
        assert dispatch(c,method,[])['error']=='POLICY_DENIED'


def test_gateway_bad_argument_structure_denied(tmp_path):
    c,_=prepare(tmp_path)
    for data in ({'x': 1}, 'abc', None, [1,2,3,4,5]):
        assert dispatch(c,'read_text',data)['error']=='POLICY_DENIED'
    assert dispatch(c,'read_text',['task1',{'path':'x'}])['error']=='POLICY_DENIED'


def test_gateway_status_and_only_registered_tools(tmp_path):
    c,_=prepare(tmp_path)
    assert dispatch(c,'get_status',[])['deletion'] is False
    assert set(TOOLS).isdisjoint({'emergency','reconcile_recovery','run','shell','execute'})


def test_ipc_refuses_linux(tmp_path):
    if os.name != 'nt':
        with pytest.raises(Denied): BrokerClient(key=b'1'*32)


def test_sensitive_filename_patterns(tmp_path):
    c,p=prepare(tmp_path)
    for filename in ('backup_secret.txt','.env.local.txt','api_key.md','private-notes.csv','tokens_2026.txt'):
        candidate=p.parent/filename
        candidate.write_text('hidden',encoding='utf-8')
        with pytest.raises(Denied): c.read_text('names',str(candidate))


def test_growth_over_limit_is_refused(tmp_path):
    c,p=prepare(tmp_path)
    c.p=Policy(root=c.root,state=c.state,max_file_bytes=7,min_free_disk_bytes=0)
    with patch('jsc_local_commander.core.os.read',side_effect=[b'X'*8]):
        with pytest.raises(Denied,match='grew beyond'):
            c.get_file_info('growth',str(p))


def test_invalid_utf8_denied(tmp_path):
    c,p=prepare(tmp_path)
    p.write_bytes(b'\xff\xff')
    with pytest.raises(Denied,match='UTF-8'):
        c.read_text('unicode',str(p))


def test_crash_recovery_latches_emergency(tmp_path):
    c,p=prepare(tmp_path)
    plan=c.plan_edit('crash',str(p),digest(b'before\n'),'after\n')
    with c._db() as db:
        db.execute("UPDATE plans SET status='applying',idem='crash-key' WHERE id=?",(plan['plan_id'],))
    reopened=Commander(c.p)
    assert reopened.status()['emergency_stop']
    assert reopened.status()['unresolved_writes']==1
    with pytest.raises(Denied): reopened.read_text('another',str(p))
    with pytest.raises(Denied,match='Cannot resume'):
        reopened.emergency(False)


def test_recovery_rejects_unknown_state_and_mismatch(tmp_path):
    c,p=prepare(tmp_path)
    plan=c.plan_edit('crash2',str(p),digest(b'before\n'),'after\n')
    with c._db() as db:
        db.execute("UPDATE plans SET status='applying',idem='crash-key' WHERE id=?",(plan['plan_id'],))
    c.emergency(True)
    p.write_text('other\n')
    assert c.review_recovery(plan['plan_id'])['file_state']=='unknown'
    with pytest.raises(Denied): c.reconcile_recovery(plan['plan_id'],'original')
    with pytest.raises(Denied): c.reconcile_recovery(plan['plan_id'],'applied')


def test_recovery_original_acknowledgment_requires_stop(tmp_path):
    c,p=prepare(tmp_path)
    plan=c.plan_edit('crash3',str(p),digest(b'before\n'),'after\n')
    with c._db() as db:
        db.execute("UPDATE plans SET status='applying',idem='crash-key' WHERE id=?",(plan['plan_id'],))
    with pytest.raises(Denied,match='Emergency stop'):
        c.reconcile_recovery(plan['plan_id'],'original')
    c.emergency(True)
    assert c.reconcile_recovery(plan['plan_id'],'original')['status']=='aborted'
    c.emergency(False)
    assert not c.status()['emergency_stop']


def test_recovery_applied_requires_verified_backup(tmp_path):
    c,p=prepare(tmp_path)
    plan=c.plan_edit('crash4',str(p),digest(b'before\n'),'after\n')
    with c._db() as db:
        db.execute("UPDATE plans SET status='applying',idem='crash-key' WHERE id=?",(plan['plan_id'],))
    p.write_text('after\n')
    c.emergency(True)
    with pytest.raises(Denied,match='backup'):
        c.reconcile_recovery(plan['plan_id'],'applied')
    backup=c.state/'backups';backup.mkdir()
    (backup/(plan['plan_id']+'.bak')).write_bytes(b'before\n')
    assert c.reconcile_recovery(plan['plan_id'],'applied')['status']=='applied'
    c.emergency(False)
    assert c.status()['emergency_stop'] is False


def test_idempotency_key_unique_across_plans(tmp_path):
    c,p=prepare(tmp_path)
    one=c.plan_edit('samekey1',str(p),digest(b'before\n'),'after\n')
    c.apply_edit('samekey1',one['plan_id'],'global-idempotency-key')
    two=c.plan_edit('samekey2',str(p),digest(b'after\n'),'new\n')
    with pytest.raises(Denied,match='Idempotency key'):
        c.apply_edit('samekey2',two['plan_id'],'global-idempotency-key')
    assert p.read_text()=='after\n'


def test_unexpected_write_failure_latches(tmp_path):
    c,p=prepare(tmp_path)
    plan=c.plan_edit('writefail',str(p),digest(b'before\n'),'after\n')
    with patch('jsc_local_commander.core.tempfile.NamedTemporaryFile',side_effect=OSError('disk fail')):
        with pytest.raises(OSError):c.apply_edit('writefail',plan['plan_id'],'write-error-key1')
    assert c.status()['emergency_stop'] is True
    with pytest.raises(Denied):c.read_text('new',str(p))
    assert p.read_text()=='before\n'


def test_ordinary_edit_verified(tmp_path):
    c,p=prepare(tmp_path)
    plan=c.plan_edit('edit2',str(p),digest(b'before\n'),'after\n')
    receipt=c.apply_edit('edit2',plan['plan_id'],'unique-edit-key-1234')
    assert receipt['status']=='applied'
    assert c.status()['unresolved_writes']==0
    assert c.apply_edit('edit2',plan['plan_id'],'unique-edit-key-1234')==receipt


def test_cli_importable():
    from jsc_local_commander.__main__ import main
    assert callable(main)
