"""CLI entry point. Administrative stop control is intentionally not an MCP tool."""
import argparse
import json
import sys
from .core import Commander, Denied, Policy, admin_mode

def main():
    parser=argparse.ArgumentParser(description='JSC Local Commander restricted MCP')
    parser.add_argument('command',nargs='?',default='serve',choices=['serve','doctor','emergency-stop','resume'])
    args=parser.parse_args()
    try:
        if args.command=='serve':
            from .server import main as serve
            serve()
        elif args.command=='doctor':
            print(json.dumps(Commander(Policy.load()).status(),indent=2))
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
