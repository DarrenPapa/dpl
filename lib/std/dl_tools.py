ext = dpl.extension("dl_tools")

if dpl.ffi is None:
    raise Exception("The ffi api isnt fully initiated!")


@ext.add_method(from_func=True)
@ext.add_func()
def convert_c_string(_, __, string, protocol="utf-8"):
    return dpl.ffi.string(string).decode(protocol)
