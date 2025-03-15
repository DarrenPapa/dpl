if __name__ != "__dpl__":
    raise Exception

if not dpl.info.VERSION.isLater((1, 4, None)):
    raise Exception("This is for version 1.4.x!")

ext = dpl.extension(meta_name="tests", alias=__alias__)

ext.items["ASSERT_ERROR"] = dpl.register_error("ASSERT_ERROR")


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
            print("  " * l + "{name!r} => {{")
            pprint(value, l + 1, seen)
            print("  " * l + "}")
        elif isinstance(value, list):
            print("  " * l + f"{name!r} => [")
            pprint(value, l + 1, seen)
            print("  " * l + "]")
        else:
            print(f"{name!r} = {value!r}")


@ext.add_func("assert")
def _(frame, _, condition, message):
    "Raises an error"
    if not condition:
        print("\n-- LOCAL VARIABLES DUMP --")
        pprint(frame[-1])
        return f"err:{ext.items['ASSERT_ERROR']}:{message}"


@ext.add_func()
def quiet_assert(frame, _, condition, message):
    "Does not raise an error"
    if not condition:
        print("\n-- LOCAL VARIABLES DUMP --")
        pprint(frame[-1])
        print("Assert Failed:", message)
