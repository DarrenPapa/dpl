if __name__ != "__dpl__":
    raise Exception("This must be included by a DuProL script!")


if not dpl.info.VERSION.isLater((1, 4, None)):
    raise Exception("This is for version 1.4.x!")

helper = dpl.require(["dpl_helpers", "func_helper.py"])

if helper is None:
    raise Exception("Helper func_helper.py doesnt exist!")

ext = dpl.extension(meta_name="io", alias=__alias__)
ext.items["output"] = modules.sys.stdout


@ext.add_func("print")
def myPrint(_, __, *args, end="", sep=" "):
    args = list(args)
    for pos, arg in enumerate(args):
        if isinstance(arg, dict) and helper.has_repr(arg):
            arg[pos] = helper.get_repr(arg["_im_repr"])
    print(*args, end=end, sep=sep, file=ext.items["output"], flush=True)

@ext.add_func()
def println(_, __, *args, sep=" "):
    args = list(args)
    for pos, arg in enumerate(args):
        if isinstance(arg, dict) and helper.has_repr(arg):
            args[pos] = helper.get_repr(arg["_im_repr"])
    print(*args, sep=sep, file=ext.items["output"], flush=True)


@ext.add_func()
def rawprint(_, __, *args, sep=" ", end=""):
    print(*args, sep=sep, file=ext.items["output"], end=end, flush=True)


@ext.add_func()
def rawprintln(_, __, *args, sep=" "):
    print(*args, sep=sep, file=ext.items["output"], flush=True)


@ext.add_func("input")
def myInput(frame, __, prompt=None, name=None):
    res = input(prompt if prompt not in dpl.falsy else "")
    if name is not None:
        dpl.varproc.rset(frame[-1], name, res)


@ext.add_func()
def setOutputFile(_, __, file):

    ext.items["output"] = file


@ext.add_func()
def rawoutput(_, __, *values):
    s = []
    for i in values:
        if isinstance(i, int):
            try:
                s.append(chr(i))
            except:
                s.append(str(i))
        elif isinstance(i, bytes):
            s.append(i.decode("utf-8"))
        else:
            s.append(str(i))
    modules.sys.stdout.write("".join(s))
    modules.sys.stdout.flush()


@ext.add_func()
def flush(_, __):
    modules.sys.stdout.flush()


# misc


@ext.add_func()
def printf(_, __, fmt, *values, sep=" ", end=""):
    for pos, value in enumerate(values):
        fmt = fmt.replace(f"%{pos}", str(value))
    print(fmt, sep=sep, end=end)
