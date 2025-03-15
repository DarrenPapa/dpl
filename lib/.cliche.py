ext = dpl.extension("cliche")

ext.items["LIFE_ERROR"] = dpl.error.register_error("LIFE_ERROR")


@ext.add_func()
def alive(_, __):
    return (dpl.constants.true,)


@ext.add_func()
def sucess(_, __):
    return (dpl.constants.false,)


@ext.add_func()
def keep_trying(_, __):
    return f"err:{ext.items['LIFE_ERROR']}:Nope."


@ext.add_func()
def enjoy_life(_, __):
    raise Exception
