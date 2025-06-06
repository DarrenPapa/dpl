if __name__ != "__dpl__":
    raise Exception("This must be included by a DuProL script!")

ext = dpl.extension(meta_name="cli")

@ext.add_func()
def flags(_, __):
    return modules.cli_arguments.flags(
        dpl.info.ARGV.copy(),
        remove_first=True
    )