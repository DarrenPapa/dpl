#!/usr/bin/env python3

# DPL CLI
# We use match statements for the CLI
# To keep it lightweight, we dont need speed here.

import subprocess
import shutil
import time
import pstats
import lib.core.info as info
import lib.core.utils as utils
import lib.core.error as error
import lib.core.cli_arguments as cli_args
import lib.core.extension_support as ext_s
import lib.core.get_dependencies as get_dep
from dfpm import dfpm
from documenter import docs
import cProfile

try:  # Try to use the .pyd or .so parser to get some kick
    import lib.core.parser as parser
except Exception as e:  # fallback to normal python impl if it fails
    import lib.core.py_parser as parser
import lib.core.varproc as varproc
import lib.core.utils as utils
import lib.core.suggestions as suggest

import os
import sys

# DANGEROUS
sys.setrecursionlimit(10**6)
sys.set_int_max_str_digits(10**6)

try:
    import dill as pickle

    has_dill = True
except ModuleNotFoundError:
    import pickle

    has_dill = False


def rec(this, ind=0):
    if not isinstance(this, (tuple, list)):
        print(
            f"{'  '*ind}Error Name: {error.ERRORS_DICT.get(this, f'ERROR NAME NOT FOUND <{this}>')}"
        )
    else:
        for pos, i in enumerate(this):
            if isinstance(i, (tuple, list)):
                rec(i, ind + 1)
            else:
                print(
                    f"{'  '*ind}Error Name {'(original)' if pos == 0 else '(other)'}: {error.ERRORS_DICT.get(i, f'ERROR NAME NOT FOUND <{i}>')}"
                )


def ez_run(code, process=True, file="???", profile=False):
    "Run a DPL script in an easier way, hence ez_run"
    if process:
        code = parser.process(code)
    if profile:
        stime = time.perf_counter()
    if err := parser.run(code):
        print(f"\n[{file}]\nFinished with an error: {err}")
        rec(err)
    if profile:
        delta = time.perf_counter() - stime
    parser.IS_STILL_RUNNING.set()
    parser.clean_threads()
    if profile:
        s, u = utils.convert_sec(delta)
        print(f"\nProgram Time: {s:,.2f}{u}")
    if err:
        exit(1)


def handle_args():
    if "arg-test" in varproc.flags:
        print("Flags:", varproc.flags)
        return
    if "info" in varproc.flags:
        info.print_info()
        return
    if "version" in varproc.flags or "v" in varproc.flags:
        print(
            f"DPL v{info.VERSION}\nUsing Python {info.PYTHON_VER}\n© Darren Chase Papa 2024\nMIT License (see LICENSE)"
        )
        return
    match (info.ARGV):
        case ["run", file, *args]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            if os.path.isfile("meta_config.cfg"):
                with open("meta_config.cfg", "r") as f:
                    varproc.meta = utils.parse_config(f.read(), {"meta": varproc.meta})[
                        "meta"
                    ]
            info.ARGV.clear()
            info.ARGV.extend([file, *args])
            varproc.meta["argc"] = info.ARGC = len(info.ARGV)
            with open(file, "r") as f:
                varproc.meta["internal"]["main_path"] = (
                    os.path.dirname(os.path.abspath(file)) + os.sep
                )
                varproc.meta["internal"]["main_file"] = file
                ez_run(
                    f.read(),
                    file=file,
                    profile="profile" in varproc.flags or "p" in varproc.flags,
                )
        case ["rc", file, *args]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            if os.path.isfile("meta_config.cfg"):
                with open("meta_config.cfg", "r") as f:
                    varproc.meta = utils.parse_config(f.read(), {"meta": varproc.meta})[
                        "meta"
                    ]
            info.ARGV.clear()
            info.ARGV.extend([file, *args])
            varproc.meta["argc"] = info.ARGC = len(info.ARGV)
            try:
                with open(file, "rb") as f:
                    code = pickle.loads(f.read())
                    varproc.meta["internal"]["main_file"] = file
                    varproc.meta["internal"]["main_path"] = (
                        os.path.dirname(os.path.abspath(file)) + os.sep
                    )
                    ez_run(
                        code,
                        False,
                        file,
                        profile="profile" in varproc.flags or "p" in varproc.flags,
                    )
            except Exception as e:
                print("Something went wrong:", file)
                print("Error:", repr(e))
                exit(1)
        case ["compile", file]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            output = file.rsplit(".", 1)[0] + ".cdpl"
            try:
                with open(file, "r") as in_file:
                    with open(output, "wb") as f:
                        f.write(pickle.dumps(parser.process(in_file.read())))
            except Exception as e:
                print("Something went wrong:", file)
                print("Error:", repr(e))
                exit(1)
        case ["dump-comp", file]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            try:
                with open(file, "r") as in_file:
                    print(parser.process(in_file.read()))
            except Exception as e:
                print("Something went wrong:", file)
                print("Error:", repr(e))
                exit(1)
        case ["docs", name]:
            docs.from_lib(name)
        case ["docu", name]:
            docs.from_local(name)
        case ["build", python_bin]:
            print(
                f"This will build a compiled parser for your system.\nThis does not necessarily mean that the parser will be faster!\nThis will build for {python_bin}\nCython does not like loading functions from exec, please be careful."
            )
            if input("Proceed? [y/N] ").strip().lower() in {"y", "yes"}:
                import lib.core.build as bld

                bld.run(python_bin)
        case ["build-clean"]:
            print(
                "Removing any files generated by cython (including the built parser) in the `./lib/core` directory"
            )
            stuff = set()
            for i in os.listdir(info.CORE_DIR):
                stuff.add(os.path.join(os.getcwd(), info.CORE_DIR, i))
            if os.path.isdir(temp := os.path.join(info.CORE_DIR, "build")):
                print("Removed build directory made by cython.")
                shutil.rmtree(temp)
            stuff = (
                *filter(
                    lambda x: x.rsplit(".", 1)[-1] in {"so", "pyd", "c", "pyi", "dll"},
                    stuff,
                ),
            )
            for pos, i in enumerate(stuff):
                print(f"[{((pos+1)/len(stuff))*100:,.2f}] Removing:", i)
                try:
                    os.remove(i)
                except:
                    print("Failed. Another process may be using it! Terminate it.")
        case ["package", *args]:
            match args:
                case ["install", user, repo]:
                    dfpm.dl_repo(user, repo, location=info.LIBDIR)
                case ["install", user, repo, branch]:
                    dfpm.dl_repo(user, repo, branch, location=info.LIBDIR)
                case ["installto:", ipath, user, repo]:
                    dfpm.dl_repo(user, repo, location=ipath)
                case ["installto:", ipath, user, repo, branch]:
                    dfpm.dl_repo(user, repo, branch, location=ipath)
                case ["install", user, repo, branch, use]:
                    dfpm.dl_repo(
                        user,
                        repo,
                        branch,
                        location=info.LIBDIR,
                        use_branch_name=use == "true",
                    )
                case ["installto:", ipath, user, repo, branch, use]:
                    dfpm.dl_repo(
                        user,
                        repo,
                        branch,
                        location=ipath,
                        use_branch_name=use == "true",
                    )
                case ["remove", pack_name]:
                    if not os.path.isdir(
                        pack_path := os.path.join(info.LIBDIR, pack_name)
                    ):
                        print("Package doesnt exist!")
                        return
                    print(pack_path, "Is going to be removed.")
                    if input("Enter y to continue: ").lower() in {"y", "yes"}:
                        dfpm.delete(pack_path)
                    print("Done!")
                case _:
                    print("Invalid command!")
                    return
        case ["get-docs", file]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            res = []
            get = False
            with open(file) as file:
                for line_pos, oline in enumerate(file, 1):
                    line = oline.strip()
                    if get:
                        if line == "--":
                            get = False
                        else:
                            if not oline.startswith("  "):
                                print(
                                    f"{file.name} [line {line_pos}]: Expected a 2-space indent!"
                                )
                                exit(1)
                            res.append(oline.rstrip()[2:])
                        continue
                    if line == "--doc":
                        get = True
                    elif line.startswith("#:"):
                        res.append(line[2:])
            print("\n".join(res))
        case ["repr"] | []:
            from prompt_toolkit.history import InMemoryHistory
            from prompt_toolkit import prompt
            from prompt_toolkit.completion import WordCompleter

            if os.path.isfile(os.path.join(info.BINDIR, "start_prompt.txt")):
                start_text = open(os.path.join(info.BINDIR, "start_prompt.txt")).read()
            else:
                start_text = ""
            frame = varproc.new_frame()
            cmd_hist = InMemoryHistory()
            acc = []
            if not "-disable-auto-complete" in flags:
                for f in frame:
                    acc.extend(utils.flatten_dict(f).keys())
                    acc.extend(map(lambda x: ":" + x, utils.flatten_dict(f).keys()))
                    acc.extend(map(lambda x: "%" + x, utils.flatten_dict(f).keys()))
            if "import-all" in varproc.flags:
                if "verbose" in varproc.flags:
                    print("Importing all standard modules...")
                for pos, file in enumerate(
                    temp := varproc.meta["internal"]["libs"]["std_libs"], 1
                ):
                    if "verbose" in varproc.flags:
                        print(f"[{(pos/len(temp))*100:7.2f}% ] Importing: {file}")
                    ext_s.py_import(frame, file, "@std")
                if "verbose" in varproc.flags:
                    print("Done importing!")
            PROMPT_CTL = frame[-1]["_meta"]["internal"]["prompt_ctl"] = {}
            PROMPT_CTL["ps1"] = ">>> "
            PROMPT_CTL["ps2"] = "... "
            print(
                f"DPL REPL for DPL {varproc.meta['internal']['version']}\nPython {info.PYTHON_VER}{(chr(10)+start_text) if start_text else ''}"
            )
            START_FILE = os.path.join(info.BINDIR, "start_script.dpl")
            if os.path.isfile(START_FILE):
                try:
                    with open(START_FILE, "r") as f:
                        parser.run(parser.process(f.read(), name="dpl_repl-startup"))
                except:
                    print("something went wrong while running start up script!")
            while True:
                try:
                    act = prompt(
                        PROMPT_CTL["ps1"],
                        completer=WordCompleter(
                            acc + suggest.SUGGEST, pattern=suggest.pattern
                        ),
                        history=cmd_hist,
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    exit()
                if (
                    act
                    and (
                        (temp := act.split(maxsplit=1)[0]) in info.INC
                        or temp in info.INC_EXT
                    )
                    or act == "#multiline"
                ):
                    while True:
                        try:
                            aa = prompt(
                                PROMPT_CTL["ps2"],
                                completer=WordCompleter(
                                    acc + suggest.SUGGEST, pattern=suggest.pattern
                                ),
                                history=cmd_hist,
                            ).strip()
                        except (KeyboardInterrupt, EOFError):
                            exit()
                        if not aa:
                            break
                        act += "\n" + aa
                elif act == ".paste":
                    act = ""
                    while True:
                        act += (this := input())
                        if not this:
                            break
                elif act == "exit":
                    break
                elif act.startswith("$"):
                    try:
                        err = os.system(act[1:])
                    except BaseException as e:
                        err = f"Error Raised: {repr(e)}"
                    finally:
                        print("\nDone!")
                    if err:
                        print(f"Error Code: {err}")
                    else:
                        print("Success")
                    continue
                elif act == ".reload":
                    if os.path.isfile(START_FILE):
                        try:
                            with open(START_FILE, "r") as f:
                                parser.run(
                                    parser.process(f.read(), name="dpl_repl-startup")
                                )
                        except:
                            print("something went wrong while running start up script!")
                    continue
                try:
                    if err := parser.run(
                        parser.process(act, "./repr.dpl-instance"), frame=frame
                    ):
                        rec(err)
                    if not "-disable-auto-complete" in flags:
                        acc = []
                        for f in frame:
                            acc.extend(utils.flatten_dict(f).keys())
                            acc.extend(
                                map(lambda x: ":" + x, utils.flatten_dict(f).keys())
                            )
                            acc.extend(
                                map(lambda x: "%" + x, utils.flatten_dict(f).keys())
                            )
                except Exception as e:
                    print(f"Python Exception was raised while running:\n{repr(e)}")
        case ["deps"]:
            get_dep.analyze(__file__)
        case ["help"]:
            print(
                f"""Help for DPL [v{varproc.meta['internal']['version']}]

dpl run [file] args...
    Runs the given DPL script.
dpl rc [file] args...
    Runs the given compiled DPL script.
dpl compile [file]
    Compiles the given DPL script.
    Outputs to [file].cdpl
dpl build [python executable]
    Builds the parser and cythonizes it.
    The interpreter chooses which to run automatically.
    Although it might be changeable in the configs soon!
dpl build-clean
    Removes the cythonized components.
dpl repr ALSO JUST `dpl`
    Invokes the REPL
dpl package install <user> <repo> <branch> <include_branch_name?>
    Install a package hosted on github.
    Default branch is 'master'
dpl package installto: <path_to_dest> <user> <repo> <branch> <include_branch_name?>
    Install a package hosted on github.
    Default branch is 'master'
dpl package remove <package_name>
    Delete that package.
dpl docs doc_name.mmu
dpl docu doc_name.mmu
dpl dump-comp file
    Dump the compile data of the file (unpickled)
dpl get-docs file
    Get the doc comments.
dpl deps
    Lists the dependencies for DPL. (not accurate)
    Only recognizes "import x" and not "from y import x"
dpl -info
    Prints info.
dpl -arg-test
    Tests flag handling.
'dpl -version' or 'dpl -v'
    Prints version and some info.
'dpl -profile ...' or 'dpl -p ...'
    Profiles the code using 'time.perf_counter' for inaccurate but fast execution.
dpl -cprofile ...
    Profiles the code using cProfile for more accurate but slower execution.
dpl -disable-auto-complete ...
    Disable the auto complete.
"""
            )
        case _:
            print("Invalid invokation!")
            print("See 'dpl help' for more")
            exit(1)
    if "pause" in varproc.flags:
        input("\n[Press Enter To Finish]")


if __name__ == "__main__":
    flags = cli_args.flags(info.ARGV, True)
    varproc.flags.update(flags)
    info.ARGC = len(info.ARGV)
    if "cprofile" in flags:
        profiler = cProfile.Profile()
        profiler.enable()
    handle_args()
    if "cprofile" in flags:
        profiler.disable()
        default = "tottime"
        order_by = None
        for i in flags:
            if i.startswith("order_profile="):
                order_by = i[14:]
        print("\nProfile Result")
        stats = pstats.Stats(profiler)
        stats.sort_stats(order_by or default).print_stats()
