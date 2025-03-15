# Logging

import datetime
import os
from . import varproc

ERRORS = (
    "PREPROCESSING_ERROR",
    "SYNTAX_ERROR",
    "RUNTIME_ERROR",
    "PYTHON_ERROR",
    "PANIC_ERROR",
    "IMPORT_ERROR",
    "THREAD_ERROR",
    "TYPE_ERROR",
    "NAME_ERROR",
    "COMPAT_ERROR",
    "FILE_NOT_FOUND_ERROR",
)

META_ERR = varproc.meta["err"] = {"builtins": ERRORS, "defined_errors": list(ERRORS)}


def register_error(name, value=None):
    if name in META_ERR:
        return META_ERR[name]
    META_ERR["defined_errors"].append(name)
    META_ERR[name] = (
        err_id := len(META_ERR["defined_errors"]) if value is None else value
    )
    META_ERR[err_id] = name
    ERRORS_DICT[err_id] = name
    return err_id


for pos, name in enumerate(ERRORS, 1):
    globals()[name] = pos
    META_ERR[name] = pos
    META_ERR[pos] = name

STOP_RESULT = -1
SKIP_RESULT = -2
FALLTHROUGH = -3

ERRORS_DICT = {
    globals().get(name): name for name in filter(lambda x: x.endswith("ERROR"), dir())
}

output = varproc.get_debug("debug_output_file")

if os.path.isfile(output):
    os.remove(output)


def my_print(text):
    if varproc.is_debug_enabled("log_events") and not os.path.isfile(output):
        with open(output, "w") as f:
            f.write(
                f"""[LOG FILE]
AUTOMATICALLY GENERATED LOG FILES BY THE INTERPRETER!
ANY LOG OUTPUT WAS REDIRECTED TO HERE!
Log file path: {output}
Date of initial logs: {datetime.datetime.now()}
Debug options:
"""
            )
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


og_error = error  # Use this to always call an error even when silent


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


def silent():
    global error
    error = lambda *x, **y: ...


def active():
    global error
    error = og_error
