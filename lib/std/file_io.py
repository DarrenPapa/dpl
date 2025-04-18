if __name__ != "__dpl__":
    raise Exception("This must be included by a DuProL script!")

if not dpl.info.VERSION.isLater((1, 4, None)):
    raise Exception("This is for version 1.4.x!")

ext = dpl.extension(meta_name="io", alias=__alias__)


@ext.add_func("open")
def myOpen(_, local, file_name, mode="r"):
    try:
        if modules.os.path.isabs(file_name):
            file = file_name
        else:
            file = modules.os.path.join(local, file_name)
        return (open(file),)
    except Exception as e:
        return dpl.error.get_error_string("PYTHON_ERROR", repr(e))


@ext.add_func()
def with_file(frame, local, body, name, _eq_, file_name, mode="r"):
    if _eq_ != "=":
        return dpl.error.get_error_string("SYNTAX_ERROR", f"Expected it to be `body io:with_file {name} **=** {file_name!r} {mode!r}`") 
    try:
        if modules.os.path.isabs(file_name):
            file = file_name
        else:
            file = modules.os.path.join(local, file_name)
        with open(file, mode) as f:
            frame[-1][name] = f
            return dpl.run_code(body, frame=frame)
    except Exception as e:
        return dpl.error.get_error_string("PYTHON_ERROR", repr(e))

@ext.add_func()
def seek(_, __, file_object, position, whence=0):
    file_object.seek(position, whence)


@ext.add_func()
def read(_, __, file_object):
    try:
        return (file_object.read(),)
    except Exception as e:
        file_object.close()
        return (e,)


@ext.add_func()
def write(_, __, file_object, content):
    try:
        file_object.write(content)
    except Exception as e:
        file_object.close()
        return f"err:{dpl.error.PYTHON_ERROR}:{repr(e)}"


@ext.add_func()
def append(_, __, file_object, content):
    try:
        if (mode := file_object.mode) == "a":
            file_object.append(content)
        else:
            raise Exception(
                f'Invalid operation on a file! Expected the mode to be "a" but got "{mode}"'
            )
    except Exception as e:
        file_object.close()
        return f"err:{dpl.error.PYTHON_ERROR}:{repr(e)}"


@ext.add_func()
def close(_, __, file_object):
    file_object.close()
