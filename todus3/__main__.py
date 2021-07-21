import sys
from pathlib import Path

if __package__ is None and not hasattr(sys, "frozen"):
    # direct call of __main__.py
    PATH = Path(__file__).resolve().parent
    sys.path.insert(0, str(PATH))

from todus3.main import main

main()
