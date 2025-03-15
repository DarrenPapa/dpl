# Parser and Preprocessor
# The heart, the interpreter of DPL

import os
import time
import sys
import itertools
import traceback
import threading
import pickle
import gc
from copy import deepcopy as copy
from cffi import FFI

try:
    from . import arguments as argproc
    from . import info
    from . import state
    from . import error
    from . import utils
    from . import varproc
    from . import objects
    from . import constants
    from . import extension_support as ext_s
except ImportError:
    print(f"Please do not run it from here.")
    sys.exit(1)


ext_s.dpl.ffi = FFI()

IS_STILL_RUNNING = threading.Event()

dpl_func_attr = [
    "name",
    "body",
    "args",
    "docs",
    "defs",
]

threads = []
thread_events = (
    []
)  # Thread events, so any threads can be killed manually or automatically


def clean_threads():  # kill all threads and wait for them to terminate
    for i in thread_events:
        i.set()
    for i in threads:
        i.join()


def my_exit(code=0):
    IS_STILL_RUNNING.set()
    clean_threads()
    raise SystemExit(code)


sys.exit = my_exit
exit = my_exit

# setup runtime stuff. And yes on import.
try:
    import psutil

    CUR_PROCESS = psutil.Process()

    def get_memory(_, __):
        memory_usage = CUR_PROCESS.memory_info().rss
        return (utils.convert_bytes(memory_usage),)

    varproc.meta["internal"]["HasGetMemory"] = 1
    varproc.meta["internal"]["GetMemory"] = get_memory
except ModuleNotFoundError as e:
    varproc.meta["internal"]["HasGetMemory"] = 0
    varproc.meta["internal"]["GetMemory"] = lambda _, __: (state.bstate("nil"),)

varproc.meta["internal"].update(
    {
        "SetEnv": lambda _, __, name, value: os.putenv(name, value),
        "GetEnv": lambda _, __, name, default=None: os.getenv(name, default),
    }
)

varproc.meta["internal"]["os"] = {
    "uname": info.SYS_MACH_INFO,  # uname
    "architecture": info.SYS_ARCH,  # system architecture (commonly x86 or ARMv7 or whatever arm proc)
    "executable_format": info.EXE_FORM,  # name is self explanatory
    "machine": info.SYS_MACH,  # machine information
    "information": info.SYS_INFO,  # basically the tripple
    "processor": info.SYS_PROC,  # processor (intel and such)
    "threads": os.cpu_count(),  # physical thread count,
    "os_name": info.SYS_OS_NAME.lower(),
}


def get_size_of(_, __, object):
    return (utils.convert_bytes(sys.getsizeof(object)),)


try:
    get_size_of(0, 0, 0)
    varproc.meta["internal"]["SizeOf"] = get_size_of
except:

    def temp(_, __, ___):
        return f"err:{error.PYTHON_ERROR}:Cannot get memory usage of an object!\nIf you are using pypy, pypy does not support this feature."

    varproc.meta["internal"]["SizeOf"] = temp

varproc.meta["threading"] = {
    "runtime_event": IS_STILL_RUNNING,
    "is_still_running": lambda _, __: IS_STILL_RUNNING.is_set(),
}

varproc.meta["str_intern"] = lambda _, __, string: sys.intern(string)


def get_block(code, current_p, supress=False):
    "Get a code block"
    pos, file, _, _ = code[current_p]
    p = current_p + 1
    k = 1
    res = []
    while p < len(code):
        _, _, ins, _ = code[p]
        if ins in info.INC_EXT:
            k += 1
        elif ins in info.INC:
            k -= info.INC[ins]
        elif ins in info.DEC:
            k -= 1
        if k == 0:
            break
        else:
            res.append(code[p])
        p += 1
    else:
        if not supress:
            print(f"Error in line {pos} file {file!r}\nCause: Block wasnt closed!")
        return None
    return p, res


def get_cust(code, current_p, INC, INC_EXT, DEC):
    "Get a code block"
    pos, file, _, _ = code[current_p]
    p = current_p + 1
    k = 1
    res = []
    while p < len(code):
        _, _, ins, _ = code[p]
        if ins in INC_EXT:
            k += 1
        elif ins in INC:
            k -= info.INC[ins]
        elif ins in DEC:
            k -= 1
        if k == 0:
            break
        else:
            res.append(code[p])
        p += 1
    else:
        print(f"Error in line {pos} file {file!r}\nCause: Block wasnt closed!")
        return None
    return p, res


def has(attrs, dct):
    return True if False not in map(lambda x: x in dct, attrs) else False


def pprint(d, l=0, seen=None):
    if seen is None:
        seen = set()
    if id(d) in seen:
        print("  " * l + "...")
        return
    seen.add(id(d))
    if isinstance(d, list):
        for i in d:
            if isinstance(i, list):
                print("  " * l + f"[")
                pprint(i, l + 1, seen)
                print("  " * l + "]")
            else:
                print("  " * l + repr(i))
        return
    for name, value in d.items():
        if name.startswith("_"):
            ...
        elif isinstance(value, dict):
            print("  " * l + f"{name!r} => {{")
            pprint(value, l + 1, seen)
            print("  " * l + "}")
        elif isinstance(value, list):
            print("  " * l + f"{name!r} => [")
            pprint(value, l + 1, seen)
            print("  " * l + "]")
        else:
            print("  " * l + f"{name!r} = {value!r}")


def process(fcode, name="__main__"):
    "Preprocess a file"
    res = []
    nframe = varproc.new_frame()
    nframe[-1].update(
        {"__file__": name, "__path__": os.path.dirname(name) or constants.none}
    )
    dead_code = True
    warnings = True
    define_func = False
    multiline = False
    last_comment = 0
    offset = 0
    for lpos, line in filter(
        lambda x: (
            True
            if x[1] and not x[1].startswith("#") and not x[1].startswith("...")
            else False
        ),
        enumerate(map(str.strip, fcode.split("\n")), 1),
    ):
        if multiline:
            if line.endswith("--"):
                multiline = False
            continue
        elif len(line) >= 4 and line.startswith("--") and line.endswith("--"):
            continue
        elif line.startswith("--"):
            last_comment = lpos
            multiline = True
        elif line.startswith("&"):
            ins, *args = line[1:].lstrip().split()
            args = argproc.process_args(nframe, args)
            argc = len(args)
            if ins == "include" and argc == 1:
                if args[0].startswith("{") and args[0].endswith("}"):
                    file = os.path.abspath(info.get_path_with_lib(args[0][1:-1]))
                else:
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), args[0])
                if not os.path.exists(file):
                    print("Not found:", file, f"\nLine {lpos}\nFile {name}")
                    break
                if os.path.isdir(file):
                    if not os.path.isfile(
                        files := os.path.join(file, "include-dpl.txt")
                    ):
                        with open(files) as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("#:"):
                                    print(
                                        "{name} [{lpos}] {line}:", line[2:]
                                    )  # for messages like deprecation warnings
                                    continue
                                elif line.startswith("#?"):
                                    print(
                                        line[2:]
                                    )  # for messages like deprecation warnings
                                    continue
                                elif line.startswith("#") or not line:
                                    continue
                                with open(line, "r") as f:
                                    if isinstance(
                                        err := process(f.read(), name=line), int
                                    ):
                                        return err
                                    res.extend(err["code"])
                                    if not err["frame"] is None:
                                        nframe[0].update(err["frame"][0])
                                varproc.meta["dependencies"]["dpl"].add(
                                    os.path.realpath(line)
                                )
                else:
                    with open(file, "r") as f:
                        if isinstance(err := process(f.read(), name=file), int):
                            return err
                        res.extend(err["code"])
                        if not err["frame"] is None:
                            nframe[0].update(err["frame"][0])
                    file = os.path.realpath(file)
                    varproc.meta["dependencies"]["dpl"].add(file)
            elif ins == "set_name" and argc == 1:
                name = str(args[0])
            elif ins == "includec" and argc == 1:
                if args[0].startswith("{") and args[0].endswith("}"):
                    file = os.path.abspath(info.get_path_with_lib(args[0][1:-1]))
                else:
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), args[0])
                if not os.path.exists(file):
                    print("Not found:", file)
                    break
                if os.path.isdir(file):
                    if not os.path.isfile(
                        files := os.path.join(file, "include-cdpl.txt")
                    ):
                        with open(files) as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("#:"):
                                    print(
                                        "{name} [{lpos}] {line}:", line[2:]
                                    )  # for messages like deprecation warnings
                                    continue
                                elif line.startswith("#?"):
                                    print(
                                        line[2:]
                                    )  # for messages like deprecation warnings
                                    continue
                                elif line.startswith("#") or not line:
                                    continue
                                with open(line, "rb") as f:
                                    if isinstance(
                                        err := process(
                                            pickle.loads(f.read()), name=line
                                        ),
                                        int,
                                    ):
                                        return err
                                    res.extend(err["code"])
                                    if not err["frame"] is None:
                                        nframe[0].update(err["frame"][0])
                                varproc.meta["dependencies"]["dpl"].add(
                                    os.path.realpath(line)
                                )
                else:
                    with open(file, "rb") as f:
                        if isinstance(
                            err := process(pickle.loads(f.read()), name=file), int
                        ):
                            return err
                        res.extend(err["code"])
                        if not err["frame"] is None:
                            nframe[0].update(err["frame"][0])
                    file = os.path.realpath(file)
                    varproc.meta["dependencies"]["dpl"].add(file)
            elif ins == "extend" and argc == 1:
                if args[0].startswith("{") and args[0].endswith("}"):
                    file = os.path.abspath(info.get_path_with_lib(args[0][1:-1]))
                else:
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), args[0])
                if not os.path.isfile(file):
                    print("File not found:", file)
                    break
                with open(file, "r") as f:
                    res.extend(process(f.read(), name=name))
                file = os.path.realpath(file)
                varproc.meta["dependencies"]["dpl"].add(file)
            elif ins == "use" and argc == 1:
                if args[0].startswith("{") and args[0].endswith("}"):
                    file = os.path.abspath(
                        info.get_path_with_lib(ofile := args[0][1:-1])
                    )
                    search_path = "_std"
                else:
                    file = os.path.join(os.path.dirname(name), (ofile := args[0]))
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), file)
                    search_path = "_loc"
                if ext_s.py_import(
                    nframe, file, search_path, loc=os.path.dirname(name)
                ):
                    print(
                        f"pytho: Something wrong happened...\nLine {lpos}\nFile {name}"
                    )
                    return error.PREPROCESSING_ERROR
            elif ins == "use" and argc == 3 and args[1] == "as":
                if args[0].startswith("{") and args[0].endswith("}"):
                    file = os.path.abspath(
                        info.get_path_with_lib(ofile := args[0][1:-1])
                    )
                    search_path = "_std"
                else:
                    file = os.path.join(os.path.dirname(name), (ofile := args[0]))
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), file)
                    search_path = "_loc"
                if ext_s.py_import(
                    nframe, file, search_path, loc=os.path.dirname(name), alias=args[2]
                ):
                    print(
                        f"pytho: Something wrong happened...\nLine {lpos}\nFile {name}"
                    )
                    return error.PREPROCESSING_ERROR
            elif ins == "use:luaj" and argc == 1:
                if args[0].startswith("{") and args[0].endswith("}"):
                    file = os.path.abspath(
                        info.get_path_with_lib(ofile := args[0][1:-1])
                    )
                    search_path = "_std"
                else:
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), args[0])
                    search_path = "_loc"
                if ext_s.luaj_import(nframe, file, search_path, loc="."):
                    print(
                        f"luaj: Something wrong happened...\nLine {lpos}\nFile {name}"
                    )
                    return error.PREPROCESSING_ERROR
            elif ins == "file" and argc == 1:
                name = args[0]
                offset = lpos
            elif ins == "version" and argc == 1:
                if err := info.VERSION.getDiff(args[0]):
                    error.pre_error(lpos, name, f"{name!r}:{lpos}: {err}")
                    return error.COMPAT_ERROR
            elif ins == "embed" and argc == 3 and args[1] == "as":
                if args[0] == name:
                    nframe[-1][args[2]] = fcode
                    continue
                file = os.path.join(os.path.dirname(name), args[0])
                if os.path.isfile(file):
                    with open(file) as f:
                        nframe[-1][args[2]] = f.read()
                else:
                    print("File not found:", file)
                    return error.PREPROCESSING_ERROR
            elif ins == "embed_binary" and argc == 3 and args[1] == "as":
                if args[0] == name:
                    nframe[-1][args[2]] = bytes(fcode)
                    continue
                file = os.path.join(os.path.dirname(name), args[0])
                if os.path.isfile(file):
                    with open(file, "rb") as f:
                        nframe[-1][args[2]] = f.read()
                else:
                    print("File not found:", file)
                    return error.PREPROCESSING_ERROR
            elif ins == "dead_code_disable" and argc == 0:
                dead_code = False
            elif ins == "dead_code_enable" and argc == 0:
                dead_code = True
            elif ins == "warn_code_disable" and argc == 0:
                warnings = False
            elif ins == "warn_code_enable" and argc == 0:
                warnings = True
            elif ins == "def_fn_disable" and argc == 0:
                define_func = False
            elif ins == "def_fn_enable" and argc == 0:
                define_func = True
            elif ins == "set" and argc == 2:
                varproc.rset(nframe[-1], args[0], args[1])
            else:
                error.pre_error(
                    lpos, name, f"{name!r}:{lpos}: Invalid directive {ins!r}"
                )
                break
        else:
            if " " in line:
                ins, arg = line.strip().split(maxsplit=1)
                args = argproc.nest_args(argproc.exprs_preruntime(argproc.group(arg)))
            else:
                ins = line
                args = []
            args = argproc.to_static(
                args
            )  # If there are static parts in the arguments run them before runtime.
            res.append((lpos - offset, name, ins, args))
    else:
        if multiline:
            error.pre_error(
                last_comment,
                name,
                f"{name!r}:{last_comment}: Unclosed multiline comment!",
            )
            return error.PREPROCESSING_ERROR
        if dead_code and info.DEAD_CODE_OPT:
            p = 0
            warn_num = 0
            nres = []
            while p < len(res):
                line = pos, file, ins, args = res[p]
                if (
                    ins in {"for", "loop", "while", "thread"}
                    and p + 1 < len(res)
                    and res[p + 1][2] in {"end", "stop", "skip"}
                ):
                    if warnings and info.WARNINGS:
                        error.warn(
                            f"Warning: {ins!r} statement is empty!\nLine {pos}\nIn file {file!r}"
                        )
                    temp = get_block(res, p)
                    if temp:
                        p, _ = temp
                    else:
                        return []
                    warn_num += 1
                elif (
                    ins in {"if", "module", "body"}
                    and p + 1 < len(res)
                    and res[p + 1][2] == "end"
                ):
                    if warnings and info.WARNINGS:
                        error.warn(
                            f"Warning: {ins!r} statement is empty!\nLine {pos}\nIn file {file!r}"
                        )
                    temp = get_block(res, p)
                    if temp:
                        p, _ = temp
                    else:
                        return []
                    warn_num += 1
                elif (
                    ins in {"case", "match", "with", "default"}
                    and p + 1 < len(res)
                    and res[p + 1][2] in {"end", "return"}
                ):
                    if ins != "default" and len(args) == 0:
                        error.warn(
                            f"Error: Malformed {ins!r} statement/sub-statements!\nLine {pos}\nIn file {file!r}"
                        )
                        return error.PREPROCESSING_ERROR
                    if warnings and info.WARNINGS:
                        error.warn(
                            f"Warning: {ins!r} statement/sub-statements is empty!\nLine {pos}\nIn file {file!r}"
                        )
                    temp = get_block(res, p)
                    if temp:
                        p, _ = temp
                    else:
                        return []
                    warn_num += 1
                elif (
                    ins in {"fn", "method"}
                    and p + 1 < len(res)
                    and res[p + 1][2] in {"end", "return"}
                ):
                    if res[p + 1][2] == "return" and len(res[p + 1][3]) != 0:
                        nres.append(line)
                        p += 1
                        continue
                    if len(args) == 0:
                        error.warn(
                            f"Error: Malformed function definition!\nLine {pos}\nIn file {file!r}"
                        )
                        return error.PREPROCESSING_ERROR
                    if warnings and info.WARNINGS:
                        error.warn(
                            f"Warning: Function {line[3][0]!r} is empty!\nLine {pos}\nIn file {file!r}"
                        )
                    temp = get_block(res, p)
                    if temp:
                        p, _ = temp
                    else:
                        return []
                    if define_func:
                        if warnings and info.WARNINGS:
                            print(
                                f'Warning: set "{line[3][0]}" none\nLine {pos}\nIn file {file!r}'
                            )
                        nres.append(
                            (pos, file, "set", [f'"{line[3][0]}"', constants.none])
                        )
                        warn_num += 1
                    warn_num += 1
                else:
                    nres.append(line)
                p += 1
            if warnings and info.WARNINGS and warn_num:
                print(f"Warning Info: {warn_num:,} Total warnings.")
        # Try to catch syntax errors earlier
        np = 0
        for p, [pos, file, ins, args] in enumerate(nres):
            if ins in info.INC_EXT:
                temp = get_block(nres, p, True)
                if not temp:
                    error.error(pos, file, f"{ins!r} statement is unclosed!")
                    return error.PREPROCESSING_ERROR
            if ins == "match":
                temp = get_block(nres, p, True)
                for [pos, file, ins, _] in temp[1]:
                    if ins in {"as", "end"}:
                        ...
                    elif ins in {"with", "case", "default"}:
                        _, body = get_block(nres, p)
                        np = pos + len(body)
                    elif pos > np:
                        error.error(
                            pos,
                            file,
                            f"Only 'case', 'with', 'default' and 'as' statements are allowed in match blocks!\nGot: {ins}",
                        )
                        return error.PREPROCESSING_ERROR
                np = 0
        return {
            "code": nres if dead_code and info.DEAD_CODE_OPT else res,
            "frame": nframe or None,
        }
    return error.PREPROCESSING_ERROR


def run(code, frame=None, thread_event=IS_STILL_RUNNING):
    "Run code generated by 'process'"
    p = 0
    end_time = start_time = 0
    if isinstance(code, str):
        code = process(code)
    if isinstance(code, dict):
        code, nframe = code["code"], code["frame"]
    elif isinstance(code, int):
        return code
    else:
        nframe = varproc.new_frame()
    sys.stdout.flush()
    if frame is not None:
        frame[0].update(nframe[0])
    else:
        frame = nframe
    while p < len(code) and not IS_STILL_RUNNING.is_set():
        pos, file, ins, oargs = code[p]
        if ins not in {"while", "lazy"}:  # Lazy evaluation
            try:
                args = argproc.process_args(frame, oargs)
            except Exception as e:
                error.error(
                    pos,
                    file,
                    f"Something went wrong when arguments were processed:\n{traceback.format_exc()}\n> {oargs!r}",
                )
                return error.PYTHON_ERROR
            argc = len(args)
        else:
            args = oargs
        argc = len(args)
        if ins == "fn" and argc >= 1:
            name, *params = args
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            varproc.rset(frame[-1], name, objects.make_function(name, body, params))
        elif ins == "lazy" and argc == 2:
            frame[-1][args[0]] = args[1]
        elif ins == "get_time" and argc == 1:
            frame[-1][args[0]] = time.time()
        elif ins == "pub" and argc >= 2 and args[0] == "fn":
            _, name, *params = args
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            varproc.rset(
                frame[-1],
                "_export." + name,
                (temp := objects.make_function(name, body, params)),
            )
            varproc.rset(frame[-1], name, temp)
        elif ins == "export" and argc == 3 and args[0] == "set":
            _, name, value = args
            varproc.rset(frame[-1], "_export." + name, value)
            varproc.rset(frame[-1], name, value)
        elif ins == "for" and argc == 3 and args[1] == "in":
            name, _, iter = args
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                for i in iter:
                    frame[-1][name] = i
                    err = run(body, frame)
                    if err:
                        if err == error.STOP_RESULT:
                            break
                        elif err == error.SKIP_RESULT:
                            continue
                        return err
        elif ins == "for" and argc == 4 and args[2] == "in":
            pos_name, name, _, iter = args
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                for posv, i in enumerate(iter):
                    frame[-1][name] = i
                    frame[-1][pos_name] = posv
                    err = run(body, frame)
                    if err:
                        if err == error.STOP_RESULT:
                            break
                        elif err == error.SKIP_RESULT:
                            continue
                        return err
        elif ins == "loop" and argc == 0:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                while not thread_event.is_set():
                    err = run(body, frame)
                    if err:
                        if err == error.STOP_RESULT:
                            break
                        elif err == error.SKIP_RESULT:
                            continue
                        return err
        elif ins == "dump_scope" and argc == 0:
            pprint(frame[-1])
        elif ins == "loop" and argc == 1:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                for _ in range(args[0]):
                    err = run(body, frame)
                    if err:
                        if err == error.STOP_RESULT:
                            break
                        elif err == error.SKIP_RESULT:
                            continue
                        return err
        elif ins == "while" and argc > 0:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                while not thread_event.is_set():
                    try:
                        (res,) = argproc.process_args(frame, args)
                        if not res:
                            break
                    except Exception as e:
                        error.error(
                            pos,
                            file,
                            f"Something went wrong when arguments were processed:\n{e}\n> {args!r}",
                        )
                        return error.RUNTIME_ERROR
                    err = run(body, frame)
                    if err:
                        if err == error.STOP_RESULT:
                            break
                        elif err == error.SKIP_RESULT:
                            continue
                        return err
        elif ins == "dlopen" and argc == 2:
            if args[1].startswith("{") and args[1].endswith("}"):
                file = info.get_path_with_lib(args[1][1:-1])
            else:
                file = args[1]
            if not os.path.isfile(file):
                error.error(pos, file, f"File {file!r} coundlt be loaded!")
                return error.FILE_NOT_FOUND_ERROR
            frame[-1][args[0]] = ext_s.dpl.ffi.dlopen(file)
        elif ins == "dlclose" and argc == 1:
            ext_s.dpl.ffi.dlclose(args[0])
        elif ins == "getc" and argc == 2:
            frame[-1][args[0]] = getattr(args[1], args[0], constants.none)
        elif ins == "cdef" and argc == 1:
            ext_s.dpl.ffi.cdef(args[0])
        elif ins == "stop" and argc == 0:
            return error.STOP_RESULT
        elif ins == "skip" and argc == 0:
            return error.SKIP_RESULT
        elif ins == "if" and argc == 1:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if args[0]:
                err = run(body, frame=frame)
                if err:
                    return err
        elif ins == "match" and argc == 1:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if (err := argproc.parse_match(frame, body, args[0])) > 0:
                return err
        elif ins == "exec" and argc == 3:
            if err := run(process(args[0], name=args[1]), frame=args[2]):
                return err
        elif ins == "sexec" and argc == 4:
            error.silent()
            frame[-1][args[0]] = run(process(args[1], name=args[2]), frame=args[3])
            error.active()
        elif ins == "fallthrough" and argc == 0:
            return error.FALLTHROUGH
        elif ins == "set" and argc == 2:
            if t := varproc.rset(frame[-1], args[0], args[1]):
                error.error(
                    pos,
                    file,
                    f"Tried to set a constant variable!\nPlease use fset instead!\nLine {pos}\nFile {file}",
                )
                return error.NAME_ERROR
        elif ins == "const" and argc == 2:
            name = args[0]
            if varproc.rset(frame[-1], name, args[1]):
                error.error(
                    pos,
                    file,
                    "Tried to set a constant variable!\nPlease use fset instead!\nLine {pos}\nFile {file}",
                )
                return error.RUNTIME_ERROR
            consts = frame[-1].get("_const")
            if consts:
                consts.append(name)
            else:
                frame[-1]["_const"] = [name]
        elif ins == "fset" and argc == 2:
            varproc.rset(frame[-1], args[0], args[1], meta=False)
        elif ins == "del" and argc >= 1:
            consts = frame[-1].get("_const")
            for name in args:
                varproc.rpop(frame[-1], name)
                if consts and name in consts:
                    consts.remove(name)
        elif ins == "module" and argc == 1:
            name = args[0]
            temp = [frame[-1]]
            varproc.nscope(temp)
            temp[-1]["_export"] = {}
            btemp = get_block(code, p)
            if btemp is None:
                break
            else:
                p, body = btemp
            err = run(body, temp)
            if err:
                return err
            varproc.rset(frame[-1], name, temp[1]["_export"])
            del temp
        elif ins == "object" and argc == 1:
            varproc.rset(frame[-1], args[0], objects.make_object(args[0]))
        elif ins == "new" and argc == 2:
            obj = args[0]
            if obj == state.bstate("nil"):
                error.error(pos, file, f"Unknown object")
                break
            varproc.rset(obj, "_internal.name", args[1])
            varproc.rset(frame[-1], args[1], copy(obj))
        elif ins == "method" and argc >= 2:
            self, name, *params = args
            if self == state.bstate("nil"):
                error.error(
                    pos, file, "Cannot bind a method to a value that isnt a context!"
                )
                return error.RUNTIME_ERROR
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            varproc.rset(self, name, objects.make_method(name, body, params, self))
        elif ins == "START_TIME" and argc == 0:
            start_time = time.perf_counter()
        elif ins == "STOP_TIME" and argc == 0:
            end_time = time.perf_counter() - start_time
        elif ins == "LOG_TIME" and argc == 0:
            ct, unit = utils.convert_sec(time.perf_counter() - start_time)
            error.info(f"Elapsed time: {ct:,.8f}{unit}")
        elif ins == "LOG_TIME" and argc == 1:
            ct, unit = utils.convert_sec(time.perf_counter() - start_time)
            error.info(f"Elapsed time: {args[0]} {ct:,.8f}{unit}")
        elif ins == "cmd" and argc == 1:
            os.system(args[0])
        elif ins == "pass":
            ...
        elif ins == "thread" and argc == 0:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp

            def th():
                if err := run(body, frame, thread_event):
                    raise RuntimeError(f"Thread returned an error: {err}")

            th_obj = threading.Thread(target=th)
            threads.append(th_obj)
            th_obj.start()
        elif ins == "new_thread_event" and argc == 1:
            varproc.rset(frame[-1], args[0], (temp := threading.Event()))
            thread_events.append(temp)
        elif ins == "thread" and argc == 1:
            if not isinstance(args[0], threading.Event):
                error.error(pos, file, "The given thread event was invalid!")
                return error.THREAD_ERROR
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp

            def th():
                if err := run(body, frame, args[0]):
                    raise RuntimeError(f"Thread returned an error: {err}")

            th_obj = threading.Thread(target=th)
            threads.append(th_obj)
            th_obj.start()
        elif ins == "exit" and argc == 0:
            my_exit()
        elif ins == "return":  # Return to the latched names
            if not (temp := varproc.rget(frame[-1], "_returns")) != state.bstate("nil"):
                ...
            else:
                if (
                    "_safe_call" in frame[-1]
                    and frame[-1]["_safe_call"] == constants.true
                ):
                    args = (0, args)
                for name, value in zip(temp, args):
                    varproc.rset(frame[-1], f"_nonlocal.{name}", value)
                if (tmp := frame[-1].get("_memoize")) not in constants.constants_false:
                    tmp[0][tmp[1]] = tuple(
                        map(
                            lambda x: (
                                x
                                if isinstance(x, (str, int, float, tuple, complex))
                                else f"{type(x)}:{id(x)}"
                            ),
                            args,
                        )
                    )
            return error.STOP_RESULT
        elif (
            ins == "freturn"
        ):  # Return to the latched names with no memoization detection (faster)
            if not (temp := varproc.rget(frame[-1], "_returns")) != state.bstate("nil"):
                ...
            else:
                if (
                    "_safe_call" in frame[-1]
                    and frame[-1]["_safe_call"] == constants.true
                ):
                    args = (0, args)
                for name, value in zip(temp, args):
                    varproc.rset(frame[-1], f"_nonlocal.{name}", value)
            return error.STOP_RESULT
        elif ins == "help" and argc == 1:
            if not isinstance(args[0], dict) and hasattr(args[0], "__doc__"):
                doc = getattr(args[0], "__doc__")
                if doc:
                    print(
                        f"\nHelp on {getattr(args[0], '__name__', '???')}, line [{pos}]:\n{doc}"
                    )
                else:
                    help(args[0])
            elif not isinstance(args[0], dict):
                return error.TYPE_ERROR
            else:
                temp = varproc.rget(
                    args[0], "docs", default=varproc.rget(args[0], "_internal.docs")
                )
                if temp == state.bstate("nil"):
                    print(f"\nHelp, line [{pos}]: No documentation was found!")
                else:
                    print(f"\nHelp, line [{pos}]:\n{temp}")
        elif ins == "wait_for_threads" and argc == 0:
            for i in threads:
                i.join()
            threads.clear()
        elif ins == "catch" and argc >= 2:  # catch return value of a function
            rets, func_name, *args = args
            if (temp := varproc.rget(frame[-1], func_name)) == state.bstate(
                "nil"
            ) or not isinstance(temp, dict):
                error.error(pos, file, f"Invalid function {func_name!r}!")
                break
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        frame[-1][name] = temp["defs"].get(name, state.bstate("nil"))
                    else:
                        frame[-1][name] = value
            else:
                if len(args) != len(temp["args"]):
                    error.error(
                        pos,
                        file,
                        f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.",
                    )
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != constants.nil:
                frame[-1]["self"] = temp["self"]
            if temp["capture"] != constants.nil:
                frame[-1]["_capture"] = temp["capture"]
            frame[-1]["_returns"] = rets
            err = run(temp["body"], frame)
            if err > 0:
                return err
            varproc.pscope(frame)
        elif ins == "DEFINE_ERROR" and 0 < argc < 3:
            error.register_error(*args)
        elif ins == "mcatch" and argc >= 2:  # catch return value of a function
            rets, func_name, *args = args
            mem_args = tuple(
                map(
                    lambda x: (
                        x
                        if isinstance(x, (str, int, float, tuple, complex))
                        else f"{type(x)}:{id(x)}"
                    ),
                    args,
                )
            )
            if (
                (temp := varproc.rget(frame[-1], func_name)) == state.bstate("nil")
                and isinstance(temp, dict)
                and mem_args in temp
            ):
                error.error(pos, file, f"Invalid function {func_name!r}!")
                break
            if mem_args in temp["memoize"]:
                for name, value in zip(rets, temp["memoize"][mem_args]):
                    varproc.rset(frame[-1], name, value)
                p += 1
                continue
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        frame[-1][name] = temp["defs"].get(name, state.bstate("nil"))
                    else:
                        frame[-1][name] = value
            else:
                if len(args) != len(temp["args"]):
                    error.error(
                        pos,
                        file,
                        f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.",
                    )
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != constants.nil:
                frame[-1]["self"] = temp["self"]
            if temp["capture"] != constants.nil:
                frame[-1]["_capture"] = temp["capture"]
            frame[-1]["_returns"] = rets
            frame[-1]["_memoize"] = (temp["memoize"], mem_args)
            err = run(temp["body"], frame)
            if err > 0:
                return err
            varproc.pscope(frame)
        elif ins == "smcatch" and argc >= 2:  # safe catch return value of a function
            rets, func_name, *args = args
            mem_args = tuple(
                map(
                    lambda x: (
                        x
                        if isinstance(x, (str, int, float, tuple, complex))
                        else f"{type(x)}:{id(x)}"
                    ),
                    args,
                )
            )
            if (
                (temp := varproc.rget(frame[-1], func_name)) == state.bstate("nil")
                and isinstance(temp, dict)
                and mem_args in temp
            ):
                error.error(pos, file, f"Invalid function {func_name!r}!")
                break
            if mem_args in temp["memoize"]:
                for name, value in zip(rets, temp["memoize"][mem_args]):
                    varproc.rset(frame[-1], name, value)
                p += 1
                continue
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        frame[-1][name] = temp["defs"].get(name, state.bstate("nil"))
                    else:
                        frame[-1][name] = value
            else:
                if len(args) != len(temp["args"]):
                    error.error(
                        pos,
                        file,
                        f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.",
                    )
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != constants.nil:
                frame[-1]["self"] = temp["self"]
            if temp["capture"] != constants.nil:
                frame[-1]["_capture"] = temp["capture"]
            frame[-1]["_returns"] = rets
            frame[-1]["_safe_call"] = constants.true
            frame[-1]["_memoize"] = (temp["memoize"], mem_args)
            error.silent()
            run(temp["body"], frame)
            error.active()
            varproc.pscope(frame)
        elif ins == "scatch" and argc >= 2:  # catch return value of a function
            rets, func_name, *args = args
            if (temp := varproc.rget(frame[-1], func_name)) == state.bstate(
                "nil"
            ) or not isinstance(temp, dict):
                error.error(pos, file, f"Invalid function {func_name!r}!")
                break
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        frame[-1][name] = temp["defs"].get(name, state.bstate("nil"))
                    else:
                        frame[-1][name] = value
            else:
                if len(args) != len(temp["args"]):
                    error.error(
                        pos,
                        file,
                        f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.",
                    )
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != constants.nil:
                frame[-1]["self"] = temp["self"]
            if temp["capture"] != constants.nil:
                frame[-1]["_capture"] = temp["capture"]
            frame[-1]["_returns"] = rets
            frame[-1]["_safe_call"] = constants.true
            error.silent()
            err = run(temp["body"], frame)
            error.active()
            varproc.pscope(frame)
        elif ins == "body" and argc >= 1:  # give a code block to a python function
            name, *args = args
            if (temp := varproc.rget(frame[-1], name)) == state.bstate(
                "nil"
            ) or not hasattr(temp, "__call__"):
                error.error(pos, file, f"Invalid function {name!r}!")
                break
            try:
                btemp = get_block(code, p)
                if btemp is None:
                    break
                else:
                    p, body = btemp
                if argc == 2 and isinstance(args[0], dict) and args[0].get("[KWARGS]"):
                    args[0].pop("[KWARGS]")
                    pa = args[0].pop("[PARGS]", tuple())
                    res = ext_s.call_w_body(
                        temp,
                        frame,
                        varproc.meta["internal"]["main_path"],
                        body,
                        pa,
                        args[0],
                    )
                else:
                    res = ext_s.call_w_body(
                        temp, frame, varproc.meta["internal"]["main_path"], body, args
                    )
                if isinstance(res, tuple):
                    for name, value in zip(rets, res):
                        varproc.rset(frame[-1], name, value)
                elif isinstance(res, int) and res:
                    return res
                elif isinstance(res, str):
                    if res == "err":
                        break
                    elif res == "stop":
                        return error.STOP_RESULT
                    elif res == "skip":
                        return error.SKIP_RESULT
                    elif res.startswith("err:"):
                        _, ecode, message = res.split(":", 2)
                        error.error(pos, file, message)
                        return int(ecode)
            except:
                error.error(pos, file, traceback.format_exc()[:-1])
                return error.PYTHON_ERROR
        elif ins == "pause" and argc == 0:
            input()
        elif ins == "pycatch" and argc >= 2:  # catch return value of a python function
            rets, name, *args = args
            if (temp := varproc.rget(frame[-1], name)) == state.bstate(
                "nil"
            ) or not hasattr(temp, "__call__"):
                error.error(pos, file, f"Invalid function {name!r}!")
                return error.NAME_ERROR
            try:
                if argc == 3 and isinstance(args[0], dict) and args[0].get("[KWARGS]"):
                    args[0].pop("[KWARGS]")
                    pa = args[0].pop("[PARGS]", tuple())
                    res = ext_s.call(
                        temp, frame, varproc.meta["internal"]["main_path"], pa, args[0]
                    )
                else:
                    res = ext_s.call(
                        temp, frame, varproc.meta["internal"]["main_path"], args
                    )
                if (
                    res is None
                    and info.WARNINGS
                    and varproc.is_debug_enabled("warn_no_return")
                ):
                    error.warn(
                        "Function doesnt return anything. To reduce overhead please dont use pycatch.\nLine {pos}\nFile {file}"
                    )
                if isinstance(res, tuple):
                    for name, value in zip(rets, res):
                        varproc.rset(frame[-1], name, value)
                elif isinstance(res, int) and res:
                    return res
                elif isinstance(res, str):
                    if res == "err":
                        break
                    elif res == "stop":
                        return error.STOP_RESULT
                    elif res == "skip":
                        return error.SKIP_RESULT
                    elif res.startswith("err:"):
                        _, ecode, message = res.split(":", 2)
                        error.error(pos, file, message)
                        return int(ecode)
            except:
                error.error(pos, file, traceback.format_exc()[:-1])
                return error.PYTHON_ERROR
        elif ins == "ccall" and argc >= 1:
            name, *args = args
            if not name:
                error.error(pos, file, "Function not defined!")
                break
            try:
                name(*args)
            except:
                error.error(pos, file, traceback.format_exc()[:-1])
                return error.PYTHON_ERROR
        elif ins == "ccatch" and argc >= 1:
            ret, name, *args = args
            if not name:
                error.error(pos, file, "Function not defined!")
                break
            try:
                frame[-1][ret] = name(*args)
            except:
                error.error(pos, file, traceback.format_exc()[:-1])
                return error.PYTHON_ERROR
        elif ins == "template" and argc == 1:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if argproc.parse_template(frame, args[0], body):
                break
        elif ins == "from_template" and argc == 2:
            template = args[0]
            tname = args[1]
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            dct = {}
            if template != constants.none:
                for pos, _, vname, vitem in body:
                    if vname not in template:
                        error.error(
                            pos,
                            file,
                            f"Attribute {vname!r} is not defined in template!",
                        )
                        return error.NAME_ERROR
                    if vname in dct:
                        error.error(
                            pos, file, f"Attribute {vname!r} is already defined!"
                        )
                        return error.NAME_ERROR
                    (value,) = argproc.process_args(frame, vitem)
                    if value == "$default":
                        dct[vname] = template[f"value:{vname}"]
                    elif value == "$name":
                        dct[vname] = tname
                    elif template[vname] == constants.any:
                        dct[vname] = value
                    elif not isinstance(value, template[vname]):
                        error.error(
                            pos,
                            file,
                            f"Invalid type!\nItem {vname!r} should be type {template[vname]!r} but got {type(vitem)!r}",
                        )
                        return error.TYPE_ERROR
                    else:
                        dct[vname] = value
                for i, value in template.items():
                    if not i.startswith("value:"):
                        continue
                    i = i.removeprefix("value:")
                    if i not in dct:
                        dct[i] = value
            else:
                for pos, _, vname, vitem in body:
                    (dct[vname],) = argproc.process_args(frame, vitem)
            varproc.rset(frame[-1], args[1], dct)
        elif ins == "raise" and isinstance(args[0], int) and argc == 2:
            error.error(pos, file, args[1])
            if (
                (temp := frame[-1].get("_returns"))
                and "_safe_call" in frame[-1]
                and frame[-1]["_safe_call"] == constants.true
            ):
                args = (args[0], constants.nil)
                for name, value in zip(temp, args):
                    varproc.rset(frame[-1], f"_nonlocal.{name}", value)
            return args[0]
        elif ins == "raise" and argc == 1 and isinstance(args[0], int):
            error.error(pos, file, "Raised an error.")
            if (
                (temp := frame[-1].get("_returns"))
                and "_safe_call" in frame[-1]
                and frame[-1]["_safe_call"] == constants.true
            ):
                args = (args[0], constants.nil)
                for name, value in zip(temp, args):
                    varproc.rset(frame[-1], f"_nonlocal.{name}", value)
            return args[0]
        elif (
            ins == "safe"
            and (
                temp := varproc.rget(
                    frame[-1], args[0], default=varproc.rget(frame[0], args[0])
                )
            )
            != state.bstate("nil")
            and isinstance(temp, dict)
            and has(dpl_func_attr, temp)
        ):  # Call a function
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args[1:]):
                    if value is None:
                        frame[-1][name] = temp["defs"].get(name, state.bstate("nil"))
                    else:
                        frame[-1][name] = value
            else:
                if len(args) - 1 != len(temp["args"]):
                    error.error(
                        pos,
                        file,
                        f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.",
                    )
                    break
                for name, value in itertools.zip_longest(temp["args"], args[1:]):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != constants.nil:
                frame[-1]["self"] = temp["self"]
            error.silent()
            run(temp["body"], frame)
            error.active()
            varproc.pscope(frame)
        elif (
            (temp := varproc.rget(frame[-1], ins, default=varproc.rget(frame[0], ins)))
            != state.bstate("nil")
            and isinstance(temp, dict)
            and has(dpl_func_attr, temp)
        ):  # Call a function
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        frame[-1][name] = temp["defs"].get(name, state.bstate("nil"))
                    else:
                        frame[-1][name] = value
            else:
                if len(args) != len(temp["args"]):
                    error.error(
                        pos,
                        file,
                        f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.",
                    )
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != constants.nil:
                frame[-1]["self"] = temp["self"]
            if temp["capture"] != constants.nil:
                frame[-1]["_capture"] = temp["capture"]
            err = run(temp["body"], frame)
            if err:
                return err
            varproc.pscope(frame)
        elif (
            temp := varproc.rget(frame[-1], ins, default=varproc.rget(frame[0], ins))
        ) != state.bstate("nil") and hasattr(
            temp, "__call__"
        ):  # call a python function
            try:
                if argc == 1 and isinstance(args[0], dict) and args[0].get("[KWARGS]"):
                    args[0].pop("[KWARGS]")
                    pa = args[0].pop("[PARGS]", tuple())
                    res = ext_s.call(
                        temp, frame, varproc.meta["internal"]["main_path"], pa, args[0]
                    )
                else:
                    res = ext_s.call(
                        temp, frame, varproc.meta["internal"]["main_path"], args
                    )
                if isinstance(res, int) and res:
                    return res
                elif isinstance(res, str):
                    if res == "break":
                        break
                    elif res.startswith("err:"):
                        _, ecode, message = res.split(":", 2)
                        error.error(pos, file, message)
                        return int(ecode)
            except:
                error.error(pos, file, traceback.format_exc()[:-1])
                return error.PYTHON_ERROR
        elif ins == "end":
            error.error(pos, file, "Lingering end statement!")
            return error.SYNTAX_ERROR
        else:
            if not isinstance((obj := varproc.rget(frame[-1], ins)), dict) and obj in (
                None,
                constants.none,
            ):
                print(
                    "\nAdditional Info: User may have called a partially defined function!",
                    end="",
                )
            error.error(pos, file, f"Invalid instruction {ins}\n{args}")
            return error.RUNTIME_ERROR
        p += 1
    else:
        return 0
    error.error(pos, file, "Error was raised!")
    return error.SYNTAX_ERROR


# to avoid circular imports
ext_s.register_run(run)
ext_s.register_process(process)
argproc.run_code = run
