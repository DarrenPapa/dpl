# Parser and Preprocessor
# The heart, the interpreter of DPL

import os
import time
import sys
import itertools
import traceback
import threading
import pickle
from copy import deepcopy as copy
from . import arguments as argproc
from . import info
from . import state
from . import error
from . import utils
from . import varproc
from . import objects
from . import constants
from . import extension_support as ext_s

IS_STILL_RUNNING = threading.Event()

dpl_func_attr = [
    "name", "body", "args", "docs", "defs",
]

threads = []
thread_events = [] # Thread events, so any threads can be killed manually or automatically

def clean_threads(): # kill all threads and wait for them to terminate
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
        return utils.convert_bytes(memory_usage),
    varproc.meta["internal"]["HasGetMemory"] = 1
    varproc.meta["internal"]["GetMemory"] = get_memory
except ModuleNotFoundError as e:
    varproc.meta["internal"]["HasGetMemory"] = 0
    varproc.meta["internal"]["GetMemory"] = lambda _, __: (state.bstate("nil"),)

varproc.meta["internal"].update({
    "SetEnv":lambda _, __, name, value:os.putenv(name, value),
    "GetEnv":lambda _, __, name, default=None:os.getenv(name, default)
})

varproc.meta["internal"]["os"] = {
    "uname":info.SYS_MACH_INFO,        # uname
    "architecture":info.SYS_ARCH,      # system architecture (commonly x86 or ARMv7 or whatever arm proc)
    "executable_format":info.EXE_FORM, # name is self explanatory
    "machine":info.SYS_MACH,           # machine information
    "information":info.SYS_INFO,       # basically the tripple
    "processor":info.SYS_PROC,         # processor (intel and such)
    "threads":os.cpu_count()           # physical thread count,
}

def get_size_of(_, __, object):
    return utils.convert_bytes(sys.getsizeof(object)),

try:
    get_size_of(0, 0, 0)
    varproc.meta["internal"]["SizeOf"] = get_size_of
except:
    def temp(_, __, ___):
        return f"err:{error.PYTHON_ERROR}:Cannot get memory usage of an object!\nIf you are using pypy, pypy does not support this feature."
    varproc.meta["internal"]["SizeOf"] = temp

varproc.meta["threading"] = {
    "runtime_event":IS_STILL_RUNNING,
    "is_still_running":lambda _, __: IS_STILL_RUNNING.is_set()
}
    
def get_block(code, current_p):
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

def process(code, name="__main__"):
    "Preprocess a file"
    res = []
    nframe = varproc.new_frame()
    for lpos, line in filter(lambda x: (
        True if x[1] and not x[1].startswith("#") else False
    ),enumerate(map(str.strip, code.split("\n")), 1)):
        if line.startswith("&"):
            ins, *args = line[1:].lstrip().split()
            args = argproc.bs_thing(nframe, args)
            argc = len(args)
            if ins == "include" and argc == 1:
                if args[0].startswith("<") and args[0].endswith(">"):
                    file = os.path.join(info.LIBDIR, args[0][1:-1])
                elif args[0].startswith('"') and args[0].endswith('"'):
                    file = os.path.join(os.path.dirname(name), args[0][1:-1])
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), file)
                if not os.path.isfile(file):
                    print("File not found:", file)
                    break
                with open(file, "r") as f:
                    res.extend(process(f.read(), name=file))
                varproc.meta["dependencies"]["dpl"].add(file)
            elif ins == "set_name" and argc == 1:
                name = str(args[0])
            elif ins == "define" and argc == 0:
                includes.add(name)
            elif ins == "includec" and argc == 1:
                if args[0].startswith("<") and args[0].endswith(">"):
                    file = os.path.join(info.LIBDIR, args[0][1:-1])
                elif args[0].startswith('"') and args[0].endswith('"'):
                    file = os.path.join(os.path.dirname(name), args[0][1:-1])
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), file)
                else:
                    assert False, "This is not reachable!"
                if not os.path.isfile(file):
                    print("File not found:", file)
                    break
                with open(file, "rb") as f:
                    res.extend(pickle.loads(f.read()))
                varproc.meta["dependencies"]["dpl"].add(file)
            elif ins == "extend" and argc == 1:
                if args[0].startswith("<") and args[0].endswith(">"):
                    file = os.path.join(info.LIBDIR, args[0][1:-1])
                elif args[0].startswith('"') and args[0].endswith('"'):
                    file = os.path.join(os.path.dirname(name), args[0][1:-1])
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), file)
                else:
                    assert False, "This is not reachable!"
                if not os.path.isfile(file):
                    print("File not found:", file)
                    break
                with open(file, "r") as f:
                    res.extend(process(f.read(), name=name))
                varproc.meta["dependencies"]["dpl"].add(file)
            elif ins == "use" and argc == 1:
                if args[0].startswith("<") and args[0].endswith(">"):
                    file = os.path.join(info.LIBDIR, (ofile:=args[0][1:-1]))
                    search_path = "_std"
                elif args[0].startswith('"') and args[0].endswith('"'):
                    file = os.path.join(os.path.dirname(name), (ofile:=args[0][1:-1]))
                    if name != "__main__":
                        file = os.path.join(os.path.dirname(name), file)
                    search_path = "_loc"
                else:
                    assert False, "This is not reachable!"
                if not os.path.isfile(file):
                    print("File not found:", file)
                    break
                if ext_s.py_import(nframe, file, search_path, loc="."):
                    print(f"Something wrong happened...")
                    return error.PREPROCESSING_ERROR
                if search_path in varproc.meta["dependencies"]["python"]:
                    varproc.meta["dependencies"]["python"][search_path].add(ofile)
                else:
                    varproc.meta["dependencies"]["python"][search_path] = {ofile}
            elif ins == "version" and argc == 1:
                if (err:=info.VERSION.getDiff(args[0])):
                    error.pre_error(lpos, name, f"{name!r}:{lpos}: {err}")
                    return error.COMPAT_ERROR
            else:
                error.pre_error(lpos, name, f"{name!r}:{lpos}: Invalid directive {ins!r}")
                break
        else:
            ins, *args = line.split()
            args = argproc.exprs_preruntime(args)
            res.append((lpos, name, ins, args))
    else:
        return {"code":res, "frame":nframe or None}
    return error.PREPROCESSING_ERROR

def run(code, frame=None, thread_event=IS_STILL_RUNNING):
    "Run code generated by 'process'"
    p = 0
    end_time = start_time = 0
    if isinstance(code, dict):
        code, nframe = code["code"], code["frame"]
    elif isinstance(code, int):
        return code
    else:
        nframe = {}
    sys.stdout.flush()
    frame = nframe if frame is None else frame
    while p < len(code) and not IS_STILL_RUNNING.is_set():
        pos, file, ins, args = code[p]
        if ins not in { # Lazy evaluation
            "while",
        }:
            try:
                args = argproc.exprs_runtime(frame, args)
            except Exception as e:
                error.error(pos, file, f"Something went wrong when arguments were processed:\n{traceback.format_exc()}\n> {args!r}")
                return error.PYTHON_ERROR
        if varproc.is_debug_enabled("show_instructions"):
            error.info(f"Executing: {code[p]}")
        argc = len(args)
        if ins == "fn" and argc >= 1:
            name, *params = args
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            varproc.rset(frame[-1], name, objects.make_function(name, body, params))
        elif ins == "for" and argc == 3 and args[1] == "in":
            name, _, iter = args
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                for i in iter:
                    varproc.rset(frame[-1], name, i)
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
        elif ins == "while" and argc != 0:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            if body:
                while not thread_event.is_set():
                    try:
                        res, = argproc.exprs_runtime(frame, args)
                        if not res:
                            break
                    except Exception as e:
                        error.error(pos, file, f"Something went wrong when arguments were processed:\n{e}\n> {args!r}")
                        return error.RUNTIME_ERROR
                    err = run(body, frame)
                    if err:
                        if err == error.STOP_RESULT:
                            break
                        elif err == error.SKIP_RESULT:
                            continue
                        return err
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
        elif ins == "if_else" and argc == 1:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, true = temp
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, false = temp
            if args[0]:
                err = run(true, frame=frame)
                if err:
                    return err
            else:
                err = run(false, frame=frame)
                if err:
                    return err
        elif ins == "set" and argc == 2:
            if varproc.rset(frame[-1], args[0], args[1]):
                error.error(pos, file, "Tried to set a constant variable!\nPlease use fset instead!")
                return error.NAME_ERROR
        elif ins == "const" and argc == 2:
            name = args[0]
            if varproc.rset(frame[-1], name, args[1]):
                error.error(pos, file, "Tried to set a constant variable!\nPlease use fset instead!")
                return error.RUNTIME_ERROR
            consts = varproc.rget(frame[-1], "[const]", default=None)
            if consts:
                consts.append(name)
            else:
                varproc.rset(frame[-1], "[const]", [name], meta=False)
        elif ins == "fset" and argc == 2:
            varproc.rset(frame[-1], args[0], args[1], meta=False)
        elif ins == "del" and argc == 1:
            varproc.rpop(frame[-1], args[0])
            consts = varproc.rget(frame[-1], "[const]", default=None)
            name = args[0] if "." not in args[0] else args[0].rsplit(".", 1)[-1]
            if consts and name in consts:
                consts.remove(name)
        elif ins == "expect" and argc == 1:
            vname = args[0]
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            err = run(body, frame)
            err_name = error.ERRORS_DICT.get(err, err)
            if isinstance(err_name, int):
                ...
            else:
                err = (err_name, err)
            varproc.rset(frame[-1], vname, err)
        elif ins == "raise" and argc == 1 and isinstance(args[0], int):
            return args[0]
        elif ins == "module" and argc == 1:
            name = args[0]
            temp = [frame[-1]]
            varproc.nscope(temp)
            btemp = get_block(code, p)
            if btemp == None:
                break
            else:
                p, body = btemp
            err = run(body, temp)
            if err:
                return err
            varproc.rset(frame[-1], name, temp[1])
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
                error.error(pos, file, "Cannot bind a method to a value that isnt a context!")
                return error.RUNTIME_ERROR
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            varproc.rset(self, name, objects.make_method(name, body, params, self))
        elif ins == "import" and argc == 1:
            if ext_s.py_import(frame, args[0], "_std"):
                return error.IMPORT_ERROR
        elif ins == "import" and argc == 2:
            if ext_s.py_import(frame, args[0], args[1], loc=os.path.dirname(file)):
                return error.IMPORT_ERROR
        elif ins == "import*" and argc == 0:
            for ext_file in varproc.meta["internal"]["libs"]["std_libs"]:
                ext_s.py_import(frame, ext_file, "_std")
        elif ins == "START_TIME" and argc == 0:
            start_time = time.perf_counter()
        elif ins == "STOP_TIME" and argc == 0:
            end_time = time.perf_counter() - start_time
        elif ins == "LOG_TIME" and argc == 0:
            ct, unit = utils.convert_sec(end_time)
            error.info(f"Elapsed time: {ct:,.8f}{unit}")
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
                if (err:=run(body, frame, thread_event)):
                    raise RuntimeError(f"Thread returned an error: {err}")
            th_obj = threading.Thread(target=th)
            threads.append(th_obj)
            th_obj.start()
        elif ins == "new_thread_event" and argc == 1:
            varproc.rset(frame[-1], args[0], (temp:=threading.Event()))
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
                if (err:=run(body, frame, args[0])):
                    raise RuntimeError(f"Thread returned an error: {err}")
            th_obj = threading.Thread(target=th)
            threads.append(th_obj)
            th_obj.start()
        elif ins == "exit" and argc == 0:
            my_exit()
        elif ins == "return" and (temp:=varproc.rget(frame[-1], "_returns")) != state.bstate("nil"): # Return to the latched names
            for name, value in zip(temp, args):
                varproc.rset(frame[-1], f"_nonlocal.{name}", value)
            return 0
        elif ins == "help" and argc == 1:
            if not isinstance(args[0], dict) and hasattr(args[0], "__doc__"):
                doc = getattr(args[0], "__doc__")
                if doc:
                    print(f"\nHelp on {getattr(args[0], '__name__', '???')}, line [{pos}]:\n{doc}")
                else:
                    help(args[0])
            elif not isinstance(args[0], dict):
                return error.TYPE_ERROR
            else:
                temp = varproc.rget(args[0], "docs",
                    default=varproc.rget(args[0], "_internal.docs")
                )
                if temp == state.bstate("nil"):
                    print(f"\nHelp, line [{pos}]: No documentation was found!")
                else:
                    print(f"\nHelp, line [{pos}]:\n{temp}")
        elif ins == "wait_for_threads" and argc == 0:
            for i in threads:
                i.join()
            threads.clear()
        elif ins == "catch" and argc >= 2: # catch return value of a function
            rets, func_name, *args = args
            if (temp:=varproc.rget(frame[-1], func_name)) == state.bstate("nil") or not isinstance(temp, dict):
                error.error(pos, file, f"Invalid function {func_name!r}!")
                break
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        varproc.rset(frame[-1], name, temp["defs"].get(name, state.bstate("nil")))
                    else:
                        varproc.rset(frame[-1], name, value)
            else:
                if len(args) != len(temp["args"]):
                    error.error(pos, file, f"Function {func_name!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.")
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            varproc.rset(frame[-1], "_returns", rets)
            if temp["self"] != state.bstate("nil"):
                varproc.rset(frame[-1], "self", temp["self"])
            err = run(temp["body"], frame)
            if err:
                return err
            varproc.pscope(frame)
        elif ins == "body" and argc >= 1: # give a code block to a python function
            name, *args = args
            if (temp:=varproc.rget(frame[-1], name)) == state.bstate("nil") or not hasattr(temp, "__call__"):
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
                    res = ext_s.call_w_body(temp, frame, varproc.meta["internal"]["main_path"], body, pa, args[0])
                else:
                    res = ext_s.call_w_body(temp, frame, varproc.meta["internal"]["main_path"], body, args)
                if isinstance(res, tuple):
                    for name, value in zip(rets, res):
                        varproc.rset(frame[-1], name, value)
                elif isinstance(res, int) and res:
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
        elif ins == "raise" and argc in (0, 1, 2):
            if argc == 0:
                return error.RUNTIME_ERROR
            elif argc == 1:
                return args[0]
            elif argc == 2:
                error.error(file, pos, args[1])
                return args[0]
            else:
                error.error(file, pos, "Invalid raise statement!")
                break
        elif ins == "pycatch" and argc >= 2: # catch return value of a python function
            rets, name, *args = args
            if (temp:=varproc.rget(frame[-1], name)) == state.bstate("nil") or not hasattr(temp, "__call__"):
                error.error(pos, file, f"Invalid function {name!r}!")
                return error.NAME_ERROR
            try:
                if argc == 3 and isinstance(args[0], dict) and args[0].get("[KWARGS]"):
                    args[0].pop("[KWARGS]")
                    pa = args[0].pop("[PARGS]", tuple())
                    res = ext_s.call(temp, frame, varproc.meta["internal"]["main_path"], pa, args[0])
                else:
                    res = ext_s.call(temp, frame, varproc.meta["internal"]["main_path"], args)
                if isinstance(res, tuple):
                    if res is not None:
                        for name, value in zip(rets, res):
                            varproc.rset(frame[-1], name, value)
                elif isinstance(res, int) and res:
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
        elif ins == "template" and argc == 1:
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            dct = {}
            for _, _, vname, vtype in body:
                if not vtype:
                    dct[vname] = state.bstate("types:any")
                else:
                    dct[vname], = argproc.bs_thing(frame, vtype)
            varproc.rset(frame[-1], args[0], dct)
        elif ins == "from_template" and argc == 2:
            template = args[0]; tname = args[0]
            temp = get_block(code, p)
            if temp is None:
                break
            else:
                p, body = temp
            dct = {}
            if template != constants.none:
                for pos, _, vname, vitem in body:
                    if vname in dct:
                        error.error(pos, file, f"Attribute {vname!r} is already defined!")
                        return error.NAME_ERROR
                    if vitem == ["$name"]:
                        value = args[1]
                    else:
                        value, = argproc.bs_thing(frame, vitem)
                    if vname not in template:
                        error.error(pos, file, f"Attribute {vname!r} is not in the defined template.")
                        return error.NAME_ERROR
                    if template[vname] != state.bstate("types:any") and not isinstance(value, template[vname]):
                        error.error(pos, file, f"Attribute {vname!r} must be type {template[vname]!r}! Not {value!r} of {type(value)!r}")
                        return error.TYPE_ERROR
                    dct[vname] = value
                for i in template.keys():
                    if i not in dct:
                        dct[i] = constants.none
            else:
                for pos, _, vname, vitem in body:
                    dct[vname], = argproc.bs_thing(frame, vitem)
            varproc.rset(frame[-1], args[1], dct)
        elif (temp:=varproc.rget(frame[-1], ins, default=varproc.rget(frame[0], ins))) != state.bstate("nil") and isinstance(temp, dict) and has(dpl_func_attr, temp): # Call a function
            varproc.nscope(frame)
            if temp["defs"]:
                for name, value in itertools.zip_longest(temp["args"], args):
                    if value is None:
                        varproc.rset(frame[-1], name, temp["defs"].get(name, state.bstate("nil")))
                    else:
                        varproc.rset(frame[-1], name, value)
            else:
                if len(args) != len(temp["args"]):
                    error.error(pos, file, f"Function {ins!r} has a parameter mismatch!\nGot {'more' if len(args) > len(temp['args']) else 'less'} than expected.")
                    break
                for name, value in itertools.zip_longest(temp["args"], args):
                    varproc.rset(frame[-1], name, value)
            if temp["self"] != state.bstate("nil"):
                varproc.rset(frame[-1], "self", temp["self"])
            err = run(temp["body"], frame)
            if err:
                return err
            varproc.pscope(frame)
        elif (temp:=varproc.rget(frame[-1], ins, default=varproc.rget(frame[0], ins))) != state.bstate("nil") and hasattr(temp, "__call__"): # call a python function
            try:
                if argc == 1 and isinstance(args[0], dict) and args[0].get("[KWARGS]"):
                    args[0].pop("[KWARGS]")
                    pa = args[0].pop("[PARGS]", tuple())
                    res = ext_s.call(temp, frame, varproc.meta["internal"]["main_path"], pa, args[0])
                else:
                    res = ext_s.call(temp, frame, varproc.meta["internal"]["main_path"], args)
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
        else:
            error.error(pos, file, f"Invalid instruction {ins}")
            return error.RUNTIME_ERROR
        p += 1
    else:
        return 0
    error.error(pos, file, "Error was raised!")
    return error.SYNTAX_ERROR

ext_s.register_run(run)
ext_s.register_process(process)