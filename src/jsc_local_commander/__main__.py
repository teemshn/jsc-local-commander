"""CLI entry point. Administrative stop control is intentionally not an MCP tool."""
import argparse
import json
import sys
from .core import Commander, Denied, Policy, admin_mode

def main():
    parser=argparse.ArgumentParser(description='JSC Local Commander restricted MCP')
    parser.add_argument('command',nargs='?',default='serve',choices=['serve','broker','doctor','emergency-stop','resume','review-recovery','reconcile-recovery'])
    parser.add_argument('--plan-id', default='')
    parser.add_argument('--observed-state', choices=['original','applied'])
    args=parser.parse_args()
    try:
        if args.command=='serve':
            from .server import main as serve
            serve()
        elif args.command=='broker':
            from .ipc import BrokerService
            BrokerService().serve_forever()
        elif args.command=='doctor':
            print(json.dumps(Commander(Policy.load()).status(),indent=2))
        elif args.command in ('review-recovery','reconcile-recovery'):
            if not admin_mode():
                raise Denied('Administrator CLI required')
            if not args.plan_id:
                raise Denied('Supply --plan-id')
            commander = Commander(Policy.load(allow_admin=True), allow_admin=True)
            result = (commander.review_recovery(args.plan_id) if args.command == 'review-recovery'
                      else commander.reconcile_recovery(args.plan_id, args.observed_state))
            print(json.dumps(result, indent=2))
        else:
            if not admin_mode():
                raise Denied('Administrator CLI required')
            Commander(Policy.load(allow_admin=True), allow_admin=True).emergency(args.command=='emergency-stop')
            print(args.command+' complete')
    except Denied as exc:
        print('DENIED: '+str(exc),file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':
    sys.exit(main())
