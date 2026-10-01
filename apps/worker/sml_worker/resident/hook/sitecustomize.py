"""Hands a launch of a resident detector script to its server (sml_worker/resident/server.py).

The worker puts this directory on PYTHONPATH and lists the resident scripts in SML_RESIDENT
({real script path: socket}). Any Python process started for the task - by the worker, a bash
wrapper or a Python wrapper - runs this first. When its script is one of them and the server answers,
the run happens in the server (model already loaded) and this process just relays the output and
exit code; otherwise the script runs here as usual, loading its model. Standard library only.
"""

import os
import sys


def _sml_resident():
    table = os.environ.get("SML_RESIDENT")
    if not table or not sys.argv or not sys.argv[0] or sys.argv[0] in ("-", "-c", "-m"):
        return
    import json
    import socket

    try:
        sock_path = json.loads(table).get(os.path.realpath(sys.argv[0]))
    except ValueError:
        return
    if not sock_path:
        return
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        conn.connect(sock_path)
    except OSError:
        conn.close()
        return  # server not running: load the model here, as before
    env = {k: v for k, v in os.environ.items() if k not in ("SML_RESIDENT", "PYTHONPATH")}
    request = {"argv": [os.path.realpath(sys.argv[0]), *sys.argv[1:]], "cwd": os.getcwd(), "env": env}
    conn.sendall((json.dumps(request) + "\n").encode())
    code = 1
    with conn.makefile("rb") as replies:
        for line in replies:
            message = json.loads(line)
            if "out" in message:
                sys.stdout.write(message["out"])
                sys.stdout.flush()
            elif "err" in message:
                sys.stderr.write(message["err"])
                sys.stderr.flush()
            elif "exit" in message:
                code = int(message["exit"])
                break
        else:
            sys.stderr.write("resident model server closed the connection before finishing\n")
    conn.close()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


_sml_resident()
