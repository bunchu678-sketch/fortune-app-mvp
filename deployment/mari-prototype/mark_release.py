"""Mark an isolated teacher release; never run in the shared doctor/admin source."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from mari_runtime import TEACHER_SURFACE

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',required=True,type=Path)
    args=parser.parse_args();target=args.release
    if not target.is_absolute() or target.resolve()!=ROOT.resolve():
        raise SystemExit('run_the_copy_in_the_dedicated_release')
    for directory in (target,target/'fortune-next-app'):
        with (directory/'.mari-reading-release').open('x',encoding='utf-8',newline='\n') as f:f.write(TEACHER_SURFACE+'\n')
