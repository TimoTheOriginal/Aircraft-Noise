import argparse
import json
from pathlib import Path
from .core import build_aircraft_basis
from .packages import export_aircraft_basis, validate_package

def main():
    parser=argparse.ArgumentParser(description='Project 1 · Aircraft Noise Terminal')
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run');run.add_argument('--input',required=True,type=Path);run.add_argument('--output',required=True,type=Path)
    check=sub.add_parser('validate-package');check.add_argument('path',type=Path)
    ui=sub.add_parser('serve');ui.add_argument('--port',type=int,default=8793)
    args=parser.parse_args()
    try:
        if args.command=='run':print(export_aircraft_basis(build_aircraft_basis(json.loads(args.input.read_text(encoding='utf-8'))),args.output))
        elif args.command=='validate-package':print(json.dumps(validate_package(args.path),indent=2))
        else:
            from .server import serve
            serve(args.port)
    except (ValueError,OSError) as e:parser.exit(2,str(e)+'\n')
if __name__=='__main__':main()
