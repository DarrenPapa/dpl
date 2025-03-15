# Used to handle arguments and expressions
# NOT FOR THE CLI

from ast import expr, parse
from platform import processor
from sys import flags

from requests.models import parse_header_links
from . import state
from . import constants
from . import error
from . import varproc
from io import TextIOWrapper
from .info import *
from . import py_argument_handler as pah

run_code = None  # to be set by py_parser


def nest_args(tokens):
    stack = [[]]
    for token in tokens:
        if not isinstance(token, str):
            stack[-1].append(token)
            continue
        if token in OPEN_P:
            new_list = []
            stack[-1].append(new_list)
            stack.append(new_list)
        elif token in CLOSE_P:
            if len(stack) == 1:
                raise ValueError("Mismatched parentheses")
            stack.pop()
        else:
            stack[-1].append(token)
    if len(stack) > 1:
        raise ValueError("Mismatched parentheses")
    return stack[0]


def get_block(code, current_p):
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
            k -= INC[ins]
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


# Functions in utils that couldnt be imported


def parse_match(frame, body, value):
    name = None
    np = 0
    ft = False
    for p, [pos, file, ins, args] in enumerate(body):
        if ins == "as":
            varproc.rset(frame[-1], process_args(frame, args)[0], value)
        elif ft == True and ins in {"case", "with"}:
            ft = False
            temp = get_block(body, p)
            if temp is None:
                error.error(pos, file, "Expected a case block!")
                return error.SYNTAX_ERROR
            if name:
                frame[-1][name] = value
            res = run_code(temp[1], frame=frame)
            if res != error.FALLTHROUGH:
                return res
            ft = True
        elif ins == "case":
            if (v := process_args(frame, args))[0]:
                temp = get_block(body, p)
                if temp is None:
                    error.error(pos, file, "Expected a case block!")
                    return error.SYNTAX_ERROR
                if name:
                    frame[-1][name] = value
                res = run_code(temp[1], frame=frame)
                if res != error.FALLTHROUGH:
                    return res
                ft = True
        elif ins == "with":
            if (v := process_args(frame, args))[0] == value:
                temp = get_block(body, p)
                if temp is None:
                    error.error(pos, file, "Expected a case block!")
                    return error.SYNTAX_ERROR
                if name:
                    frame[-1][name] = value
                res = run_code(temp[1], frame=frame)
                if res != error.FALLTHROUGH:
                    return res
                ft = True
        elif ins == "default":
            temp = get_block(body, p)
            if temp is None:
                error.error(pos, file, "Expected a case block!")
                return error.SYNTAX_ERROR
            if name:
                frame[-1][name] = value
            res = run_code(temp[1], frame=frame)
            return res


def parse_template(frame, temp_name, body):
    data = {}
    for p, [pos, file, ins, args] in enumerate(body):
        args = process_args(frame, args)
        argc = len(args)
        if ins == "define" and argc == 3 and args[1] == "as":
            name, _, type_ = args
            data[name] = type_
        elif ins == "define" and argc == 5 and args[1] == "as" and args[3] == "=":
            name, _, type_, _, value = args
            data[name] = type_
            data[f"value:{name}"] = value
        else:
            error.error(pos, file, f"Invalid statement!")
            return 1
    varproc.rset(frame[-1], temp_name, data)


def flatten_dict(d, parent_key="", sep=".", seen=None):
    if seen is None:
        seen = set()
    items = {}
    dict_id = id(d)
    if dict_id in seen:
        return d
    seen.add(dict_id)
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key, sep, seen))
        elif isinstance(value, list):
            items[f"{new_key}"] = value
            for i, item in enumerate(value):
                items[f"{new_key}[{i}]"] = item
        else:
            items[new_key] = value
    seen.remove(dict_id)
    return items


methods = {}


# Need I explain?
def is_int(arg):
    arg = arg.replace("_", "")
    return arg.replace("-", "").replace(",", "").isdigit()


def is_hex(arg):
    if not arg.startswith("0x"):
        return False
    try:
        int(arg[2:], 16)
        return True
    except:
        return False


def is_bin(arg):
    if not arg.startswith("0b"):
        return False
    try:
        int(arg[2:], 2)
        return True
    except:
        return False


def is_float(arg):
    arg = arg.replace("_", "")
    return arg.replace("-", "").replace(",", "").replace(".", "").isdigit()


def is_id(arg):
    return arg.replace(".", "").replace("_", "a").isalnum()


def is_var(arg):
    return arg.startswith("%") and is_id(arg[1:])


def is_fvar(arg):
    return arg.startswith(":") and is_id(arg[1:])


def expr_preruntime(arg):
    "Process arguments at preprocessing"
    if not isinstance(arg, str):
        return arg
    elif is_int(arg):
        return int(arg.replace(",", ""))
    elif is_float(arg.replace(",", "")):
        return float(arg)
    elif is_bin(arg):
        return int(arg, 2)
    elif is_hex(arg):
        return int(arg, 16)
    elif arg == "true":
        return constants.true
    elif arg == "false":
        return constants.false
    elif arg == "none":
        return constants.none
    elif arg == "nil":
        return constants.nil
    elif arg == "...":
        return constants.elipsis
    elif arg == "!tuple":  # really?
        return tuple()
    return arg


def expr_runtime(frame, arg):
    "Process an argument at runtime"
    if isinstance(arg, list):
        return evaluate(frame, arg)
    elif not isinstance(arg, str):
        return arg
    if is_id(arg):
        return arg
    elif is_var(arg):
        if varproc.debug["allow_automatic_global_name_resolution"]:
            return varproc.rget(
                frame[-1], arg[1:], default=varproc.rget(frame[0], arg[1:])
            )
        else:
            return varproc.rget(frame[-1], arg[1:])
    elif is_fvar(arg):
        if varproc.debug["allow_automatic_global_name_resolution"]:
            return varproc.rget(
                frame[-1],
                arg[1:],
                default=varproc.rget(frame[0], arg[1:], meta=False),
                meta=False,
            )
        else:
            return varproc.rget(frame[-1], arg[1:], meta=False)
    elif arg == "!dict":
        return {}
    elif arg == "!list":
        return []
    elif arg.startswith('"') and arg.endswith('"'):
        return arg[1:-1]
    elif arg.startswith("'") and arg.endswith("'"):
        text = arg[1:-1]
        for name, value in flatten_dict(frame[-1]).items():
            text = text.replace(f"${{{name}}}", str(value))
        return text
    else:
        return expr_preruntime(arg)


def add_method(name=None, from_func=False, process=True):
    def wrapper(func):
        fname = name if name is not None else getattr(func, "__name__", "_dump")
        methods[fname] = (
            lambda *arg: func(None, None, *arg) if from_func else func,
            process,
        )
        return func

    return wrapper


def my_range(start, end):
    def pos(start, end):
        while start < end:
            yield start
            start += 1

    def neg(start, end):
        while start > end:
            yield start
            start -= 1

    return pos(start, end) if start < end else neg(start, end)


def is_static(code):
    for i in code:
        if isinstance(i, list):
            if not is_static(i):
                return False
        elif not isinstance(i, str):
            continue
        elif is_var(i) or is_fvar(i):
            return False
        elif is_id(i):
            return False
    return True


def to_static(code):
    for pos, i in enumerate(code):
        if isinstance(i, list):
            if is_static(i):
                code[pos] = evaluate(None, i)
            else:
                code[pos] = to_static(i)
    return code


def evaluate(frame, expression):
    "Evaluate an expression"
    match (process_args(frame, expression)):
        # operations
        case [val1, "+", val2]:
            return val1 + val2
        case [val1, "-", val2]:
            return val1 - val2
        case [val1, "*", val2]:
            return val1 * val2
        case [val1, "/", val2]:
            return val1 / val2
        # conditionals
        case [val1, "=", "=", val2]:
            return val1 == val2
        case [val1, "!", "=", val2]:
            return val1 != val2
        case [val1, "and", val2]:
            return val1 and val2
        case [val1, "or", val2]:
            return val1 or val2
        case ["not", val2]:
            return not val2
        case ["!", val2]:
            return not val2
        case [val1, ">", "=", val2]:
            return val1 >= val2
        case [val1, "<", "=", val2]:
            return val1 <= val2
        case [val1, "<", val2]:
            return val1 < val2
        case [val1, ">", val2]:
            return val1 > val2
        case ["?list", *lst]:
            return lst
        case ["?tuple", *lst]:
            return tuple(lst)
        case ["?dict", *lst]:
            return dict(lst)
        case ["?string", item]:
            return str(item)
        case ["?bytes", item]:
            try:
                return bytes(item)
            except:
                return constants.nil
        case ["?int", item]:
            try:
                return int(item)
            except:
                return constants.nil
        case ["?float", item]:
            try:
                return float(item)
            except:
                return constants.nil
        case ["dict", *args]:
            temp = {}
            for i in args:
                temp.update(i)
            return temp
        case ["nil?", value]:
            return value == constants.nil
        case ["none?", value]:
            return value == constants.none
        case ["Type", item]:
            return getattr(type(item), "__name__", constants.nil)
        case ["Sum", *args]:
            t = type(args[0])
            start = args[0]
            for i in args[1:]:
                start += t(i)
            return start
        case [val1, "in", val2]:
            return val1 in val2
        case [val1, "/", "/", val2]:
            return val1 // val2
        case [val1, "mod", val2]:
            return val1 % val2
        case [val1, "^", val2]:
            return val1**val2
        case ["RawRange", num]:
            return range(num)
        case ["Range", num]:
            return tuple(range(num))
        case ["dRange", num]:
            return tuple(my_range(0, num))
        case ["dRawRange", num]:
            return my_range(0, num)
        case ["dRange", num, end]:
            return tuple(my_range(num, end))
        case ["dRawRange", num, end]:
            return my_range(num, end)
        case ["LenOf", item]:
            try:
                return len(item)
            except:
                return 0
        case ["Eval", expr]:
            return process_arg(frame, expr)
        case ["@", ins, *args] if ins in methods:
            return methods[ins](frame, *args)
        case ["#", ins, *args] if ins in methods:
            return ins(frame, "_", *args)[0]
        case [obj, "@", method, *args] if hasattr(
            obj, method
        ):  # direct python method calling
            getattr(obj, method)(*args)
        case ["?args", *args]:
            temp = pah.arguments_handler(None, None)
            temp.parse(args)
            return temp
        case [name, "=", value]:
            return {name: value}
        case [obj, "-", ">", index]:
            if not isinstance(obj, (tuple, list, str)):
                return constants.nil
            if isinstance(obj, (tuple, list, str)) and index >= len(obj):
                return constants.nil
            elif isinstance(obj, dict) and index not in obj:
                return constants.nil
            else:
                return obj[index]
    return expression


sep = " ,"
special_sep = "@()+/*[]<>="


def group(text):
    res = []
    str_tmp = []
    id_tmp = []
    this = False
    rq = False
    quotes = {"str": '"', "pre": "}", "str1": "'"}
    str_type = "str"
    for i in text:
        if str_tmp:
            if this:
                if i == "n":
                    str_tmp.append("\n")
                elif i == "r":
                    str_tmp.append("\r")
                elif i == "t":
                    str_tmp.append("\t")
                elif i == "b":
                    str_tmp.append("\b")
                elif i == "f":
                    str_tmp.append("\f")
                elif i == "a":
                    str_tmp.append("\a")
                elif i == "v":
                    str_tmp.append("\v")
                else:
                    str_tmp.append(i)
                this = False
                continue
            if i == "\\":
                this = True
            elif i == quotes[str_type]:
                text = "".join(str_tmp) + quotes[str_type]
                res.append(text)
                str_tmp.clear()
            else:
                str_tmp.append(i)
            continue
        elif i in sep:
            if id_tmp:
                res.append("".join(id_tmp))
                id_tmp.clear()
        elif i in special_sep:
            if id_tmp:
                res.append("".join(id_tmp))
                id_tmp.clear()
            res.append(i)
        elif i in "\"{'":
            if id_tmp:
                res.append("".join(id_tmp))
                id_tmp.clear()
            str_tmp.append(i)
            if i == '"':
                str_type = "str"
            elif i == "{":
                str_type = "pre"
            elif i == "'":
                str_type = "str1"
            else:
                str_type = "str"
        else:
            id_tmp.append(i)
    if id_tmp:
        res.append("".join(id_tmp))
    return res


def exprs_preruntime(args):
    return [*map(expr_preruntime, args)]


def process_arg(frame, e):
    return expr_runtime(frame, e)


def process_args(frame, e):
    return list(map(lambda x: expr_runtime(frame, x), e))
