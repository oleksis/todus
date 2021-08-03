import sys
from pathlib import Path

if __package__ is None and not hasattr(sys, "frozen"):
    # direct call of __main__.py
    PATH = Path(__file__).resolve().parent
    sys.path.insert(0, str(PATH))

from todus3.client import ToDusClient
from todus3.main import main
from todus3.util import ErrorCode


client = ToDusClient()

try:
    exit_code = main(client)
except KeyboardInterrupt:
    client.exit = True
    client.error_code = ErrorCode.MAIN
    exit_code = client.error_code
    print("Client has abruptly terminated.")

sys.exit(exit_code)
