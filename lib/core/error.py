# Logging

import datetime
import os
from . import varproc

SYNTAX_ERROR = 1
RUNTIME_ERROR = 2
PYTHON_ERROR = 3
PANIC_ERROR = 4
IMPORT_ERROR = 5

STOP_RESULT = -1
SKIP_RESULT = -2

output = varproc.get_debug("debug_output_file")

if os.path.isfile(output):
    os.remove(output)

def my_print(text):
    if varproc.is_debug_enabled("log_events") and not os.path.isfile(output):
        with open(output, "w") as f:
            f.write(f"""[LOG FILE]
AUTOMATICALLY GENERATED LOG FILES BY THE INTERPRETER!
ANY LOG OUTPUT WAS REDIRECTED TO HERE!
Log file path: {output}
Date of initial logs: {datetime.datetime.now()}
Debug options:
""")
        with open(output, "a") as f:
            for name, enabled in varproc.debug.items():
                if isinstance(enabled, str):
                    f.write(f"  value: {enabled!r} - {name!r}\n")
                elif isinstance(enabled, int):
                    f.write(f"  {'on ' if enabled else 'off'} - {name!r}\n")
    if varproc.is_debug_enabled("log_events"):
        with open(output, "a") as f:
            f.write(f"{text}\n")
    else:
        print(text)

# pre_[name] is a preprocessing log

def pre_error(pos, file, cause=None):
    my_print(f"\n[Preprocessing Error]\nError in line {pos} file {file!r}")
    if cause is not None:
        my_print(f"Cause:\n{cause}")

def error(pos, file, cause=None):
    my_print(f"\nError in line {pos} file {file!r}")
    if cause is not None:
        my_print(f"Cause:\n{cause}")

def info(text, show_date=True):
    if show_date:
        my_print(f"   [INFO] {datetime.datetime.now()}: {text}")
    else:
        my_print(f"   [INFO]: {text}")

def warn(text, show_date=True):
    if show_date:
        my_print(f"[WARNING] {datetime.datetime.now()}: {text}")
    else:
        my_print(f"[WARNING]: {text}")

def pre_info(text, show_date=True):
    if show_date:
        my_print(f"   [INFO PRE] {datetime.datetime.now()}: {text}")
    else:
        my_print(f"   [INFO PRE]: {text}")

def pre_warn(text, show_date=True):
    if show_date:
        my_print(f"[WARNING PRE] {datetime.datetime.now()}: {text}")
    else:
        my_print(f"[WARNING PRE]: {text}")