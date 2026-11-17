"""Windows-only integration smoke: real authenticated named-pipe roundtrip."""
import os
import threading
import time
import uuid
from pathlib import Path

import pytest

from jsc_local_commander.core import Commander, Policy
from jsc_local_commander.ipc import BrokerClient, BrokerService

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows pipe backend')


def test_authenticated_pipe_is_only_an_allowlisted_gateway(tmp_path):
    root=tmp_path/'work';root.mkdir()
    state=tmp_path/'state';state.mkdir()
    c=Commander(Policy(root=root,state=state,min_free_disk_bytes=0),allow_admin=True)
    pipe=r'\\.\pipe\JSCCommander_Test_'+uuid.uuid4().hex
    key=b'x'*32
    service=BrokerService(c,key,address=pipe)
    thread=threading.Thread(target=service.serve_once,daemon=True)
    thread.start()
    for _ in range(30):
        try:
            response=BrokerClient(key,address=pipe).call('get_status')
            break
        except FileNotFoundError:
            time.sleep(0.02)
    else:
        pytest.fail('Broker pipe not listening')
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert response['arbitrary_shell'] is False
    assert response['emergency_stop'] is False


def test_production_rejects_elevated_windows_runner(tmp_path):
    from jsc_local_commander.core import admin_mode, Denied
    if not admin_mode():
        pytest.skip('Non-elevated Windows runner')
    workspace=tmp_path/'workspace';workspace.mkdir()
    state=tmp_path/'state';state.mkdir()
    with pytest.raises(Denied,match='Administrator process forbidden'):
        Commander(Policy(root=workspace,state=state))
