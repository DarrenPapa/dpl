# Give better suggestions for the REPL

from . import varproc
from . import info
from re import compile as rcomp

pattern = rcomp(r"[&\w\.\:_\%\!]+")
import os

SUGGEST = info.KEYWORDS + [
    "pub fn",
    "export set",
]
SUGGEST.remove("pub")


def listdir(path=info.LIBDIR):
    directory_contents = {}

    for root, dirs, files in os.walk(path):
        # Only include immediate subdirectories
        if root == path:
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                directory_contents[dir_name] = list(
                    filter(
                        lambda x: (t := x.rsplit(".", 1))[-1]
                        in ("py", "dpl", "cdpl", "lua")
                        or t[0]
                        in ("include-dpl", "include-cdpl", "include-py", "include-lua"),
                        os.listdir(dir_path),
                    )
                )
            break  # Stop after processing the top-level directory
    return directory_contents


k = listdir()
k.pop("core")
k.pop("dpl_helpers")
directive = "use"
for lib, files in k.items():
    if "include-py.txt" in files:
        SUGGEST.append(f"&use {{{lib}}}")
        directive = "use"
    elif "include-dpl.txt" in files:
        SUGGEST.append(f"&include {{{lib}}}")
        directive = "include"
    elif "include-cdpl.txt" in files:
        SUGGEST.append(f"&includec {{{lib}}}")
        directive = "includec"
    elif "include-lua.txt" in files:
        SUGGEST.append(f"&use:luaj {{{lib}}}")
        directive = "use:luaj"
    for file in files:
        if file.endswith(".lua"):
            SUGGEST.append(f"&use:luaj {{{lib}{os.sep}{file}}}")
        elif file.endswith(".py"):
            SUGGEST.append(f"&use {{{lib}{os.sep}{file}}}")
        elif file.endswith(".dpl"):
            SUGGEST.append(f"&include {{{lib}{os.sep}{file}}}")
        elif file.endswith(".cdpl"):
            SUGGEST.append(f"&includec {{{lib}{os.sep}{file}}}")
        else:
            SUGGEST.append(f"&{directive} {{{lib}{os.sep}{file}}}")
