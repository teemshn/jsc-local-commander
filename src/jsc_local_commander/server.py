"""Unprivileged MCP stdio facade: all requests go through a separate pipe broker."""
from __future__ import annotations
import json
from mcp.server import MCPServer
from .core import Denied
from .ipc import BrokerClient

mcp = MCPServer('JSC Local Commander (split broker v0.2)')
_client = None

def get_client():
    global _client
    if _client is None:
        _client = BrokerClient()
    return _client

def invoke(name, *args):
    try:
        return get_client().call(name,*args)
    except Denied as exc:
        return {'error':'POLICY_DENIED','reason':str(exc)}
    except Exception:
        return {'error':'FAILED_CLOSED','reason':'Internal failure; operation not retried'}

@mcp.tool()
def get_status() -> dict:
    """Return security mode and emergency-stop state; no arbitrary execution."""
    return invoke('get_status')

@mcp.tool()
def get_system_info(task_id: str) -> dict:
    """Read-only CPU, RAM, OS and workspace disk capacity."""
    return invoke('get_system_info',task_id)

@mcp.tool()
def diagnose_processes(task_id: str, name_fragment: str='', max_results: int=30) -> dict:
    """Read-only process PID/name/status; never executes commands."""
    return invoke('diagnose_processes',task_id,name_fragment,max_results)

@mcp.tool()
def diagnose_services(task_id: str, name_fragment: str='', max_results: int=30) -> dict:
    """Read-only Windows service name/status (cannot stop services)."""
    return invoke('diagnose_services',task_id,name_fragment,max_results)

@mcp.tool()
def list_workspace(task_id: str, path: str, max_results: int=100) -> dict:
    """List a configured workspace directory; never follows links."""
    return invoke('list_workspace',task_id,path,max_results)

@mcp.tool()
def search_files(task_id: str, root: str, suffix: str='.txt', max_results: int=100) -> dict:
    """Bounded recursive search for safe text files only."""
    return invoke('search_files',task_id,root,suffix,max_results)

@mcp.tool()
def read_text(task_id: str, path: str, start_line: int=1, max_lines: int=200) -> dict:
    """Read a small safe workspace text file with basic secret masking."""
    return invoke('read_text',task_id,path,start_line,max_lines)

@mcp.tool()
def get_file_info(task_id: str, path: str) -> dict:
    """Retrieve size and SHA-256 digest for safe workspace text files."""
    return invoke('get_file_info',task_id,path)

@mcp.tool()
def plan_edit(task_id: str, path: str, expected_sha256: str, replacement: str) -> dict:
    """Prepare a bounded preview; does not modify the target."""
    return invoke('plan_edit',task_id,path,expected_sha256,replacement)

@mcp.tool()
def apply_edit(task_id: str, plan_id: str, idempotency_key: str) -> dict:
    """Apply one previewed safe text edit with hashes, local backup, and dedup."""
    return invoke('apply_edit',task_id,plan_id,idempotency_key)

@mcp.tool()
def get_audit_events(task_id: str, limit: int=30) -> dict:
    """Read a bounded digest-only audit log, not file contents."""
    result=invoke('audits',task_id,limit)
    return {'events':result} if isinstance(result,list) else result

def main():
    # Fail closed BEFORE stdio starts; no stdout logging.
    get_client()
    mcp.run(transport='stdio')
