#!/usr/bin/env python3

# DPL CLI
# We use match statements for te CLI
# To keep it lightweight, we dont need speed here.

import os
import sys
import subprocess
import shutil
import lib.core.info as info
import lib.core.error as error
import lib.core.cli_arguments as cli_args
import lib.core.extension_support as ext_s

try: # Try to use the .pyd or .so parser to get some kick
    import lib.core.parser as parser
except Exception as e: # fallback to normal python impl if it fails
    import lib.core.py_parser as parser
import lib.core.varproc as varproc
import lib.core.utils as utils

try:
    import dill as pickle
    has_dill = True
except ModuleNotFoundError:
    import pickle
    has_dill = False

ERRORS = {getattr(error, name):name for name in filter(lambda x: x.endswith("ERROR"), dir(error))}

def rec(this, ind=0):
    if not isinstance(this, (tuple, list)):
        print(f"{'  '*ind}Error Name: {ERRORS.get(this, f'ERROR NAME NOT FOUND <{this}>')}")
    else:
        for pos, i in enumerate(this):
            if isinstance(i, (tuple, list)):
                rec(i, ind+1)
            else:
                print(f"{'  '*ind}Error Name {'(original)' if pos == 0 else '(other)'}: {ERRORS.get(i, f'ERROR NAME NOT FOUND <{i}>')}")

def ez_run(code, process=True, file="???"):
    if process:
        code = parser.process(code)
    if (err:=parser.run(code)):
        print(f"\n[{file}]\nFinished with an error: {err}")
        rec(err)
    parser.IS_STILL_RUNNING.set()
    parser.clean_threads()
    if err:
        exit(1)

def handle_args():
    flags = cli_args.flags(info.ARGV, True)
    if "arg-test" in flags:
        print(flags)
        return
    match (info.ARGV):
        case ["run", file, *args]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            if os.path.isfile("meta_config.cfg"):
                with open("meta_config.cfg", "r") as f:
                    varproc.meta = utils.parse_config(f.read(), {"meta":varproc.meta})["meta"]
            info.ARGV.clear()
            info.ARGV.extend([file, *args])
            info.ARGC = len(info.ARGV)
            varproc.meta["argc"] = info.ARGC
            with open(file, "r") as f:
                varproc.meta["internal"]["main_path"] = os.path.dirname(os.path.abspath(file))+os.sep
                ez_run(f.read(), file=file)
        case ["rc", file, *args]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            if os.path.isfile("meta_config.cfg"):
                with open("meta_config.cfg", "r") as f:
                    varproc.meta = utils.parse_config(f.read(), {"meta":varproc.meta})["meta"]
            info.ARGV.clear()
            info.ARGV.extend([file, *args])
            info.ARGC = len(info.ARGV)
            varproc.meta["argc"] = info.ARGC
            try:
                with open(file, "rb") as f:
                    code = pickle.loads(f.read())
                    varproc.meta["internal"]["main_path"] = os.path.dirname(os.path.abspath(file))+os.sep
                    ez_run(code, False, file)
            except Exception as e:
                print("Something went wrong:", file)
                print("Error:", repr(e))
                exit(1)
        case ["compile", file]:
            if not os.path.isfile(file):
                print("Invalid file path:", file)
                exit(1)
            output = file.rsplit(".", 1)[0]+".cdpl"
            try:
                with open(file, "r") as in_file:
                    with open(output, "wb") as f:
                        f.write(pickle.dumps(parser.process(in_file.read())))
            except Exception as e:
                print("Something went wrong:", file)
                print("Error:", repr(e))
                exit(1)
        case ["build"]:
            print(f"This will build a compiled parser for your system.\nThis does not necessarily mean that the parser will be faster!\nThis will build for Python {info.PYTHON_VER}\nCython does not like loading functions from exec, please be careful.")
            if input("Proceed? [y/N] ").strip().lower() in {"y", "yes"}:
                import lib.core.build # This will run the code so no need to do stuff
        case ["build", "clean"]:
            print("Removing any files generated by cython (including the built parser) in the `./lib/core` directory")
            stuff = set()
            for i in os.listdir(info.CORE_DIR):
                stuff.add(os.path.join(os.getcwd(), info.CORE_DIR, i))
            if os.path.isdir(temp:=os.path.join(info.CORE_DIR, "build")):
                print("Removed build directory made by cython.")
                shutil.rmtree(temp)
            stuff = *filter(
                lambda x: x.rsplit(".", 1)[-1] in {"so", "pyd", "dll"},
                stuff
            ),
            for pos,i in enumerate(stuff):
                print(f"[{((pos+1)/len(stuff))*100:,.2f}] Removing:",i)
                try:
                    os.remove(i)
                except:
                    print("Failed. Another process may be using it! Terminate it.")
        case ["install", python_exec, *flags]:
            print(f"Installing requirements for `{sys.platform}`")
            tmp_dir = os.getcwd()
            if info.BINDIR:
                os.chdir(info.BINDIR)
            with open("requirements.txt", "r") as f:
                while (line:=f.readline().strip()) != "end":
                    if "#" in line:
                        line = line[:line.index("#")].strip()
                    if not line:
                        continue
                    if line.startswith("?"):
                        if "verbose" in flags:
                            print(f"Conditional install [for {(temp:=line[1:line.index(' ')])}{' (match)' if temp == sys.platform or temp == 'any' else ' (mismatch)'}]: {line[len(sys.platform)+2:]}")
                        if line[1:].startswith(sys.platform) or line[1:line.index(' ')] == "any":
                            line = line[len(sys.platform)+1:].strip()
                        else:
                            continue
                    elif line.startswith("!"):
                        if "verbose" in flags:
                            print(f"Conditional command [for {(temp:=line[1:line.index(' ')])}{' (match)' if temp == sys.platform or temp == 'any' else ' (mismatch)'}]: {line[len(sys.platform)+2:]}")
                        if line[1:].startswith(sys.platform) or line[1:line.index(' ')] == "any":
                            line = line[len(sys.platform)+2:].strip()
                            if "verbose" in flags:
                                print(f"Running: {line}")
                            if (err:=os.system(line)):
                                print(f"Error code: {err}")
                            continue
                        else:
                            continue
                    with open(os.devnull, "w") as devnull:
                        print("Installing:", line)
                        try:
                            if subprocess.run([python_exec, "-m", "pip", "install", "--ignore-installed", line], stdout=devnull, stderr=devnull).returncode:
                                print(f"Error while installing: {line}")
                        except Exception as e:
                            print(f"Failed to install [{line}]: {repr(e)}\nPlease check the usage of `dpl.py install`")
            print('Done!')
            os.chdir(tmp_dir)
        case ["repr"] | []:
            if os.path.isfile(os.path.join(info.BINDIR, 'start_prompt.txt')):
                start_text = open(os.path.join(info.BINDIR, 'start_prompt.txt')).read()
            else:
                start_text = ""
            frame = varproc.new_frame()
            if "import-all" in flags:
                if "verbose" in flags:
                    print("Importing all standard modules...")
                for pos, file in enumerate(temp:=varproc.meta["internal"]["libs"]["std_libs"], 1):
                    if "verbose" in flags:
                        print(f"[{(pos/len(temp))*100:7.2f}% ] Importing: {file}")
                    ext_s.py_import(frame, file, "@std")
                if "verbose" in flags:
                    print("Done importing!")
            PROMPT_CTL = frame[-1]["_meta"]["internal"]["prompt_ctl"] = {}
            PROMPT_CTL["ps1"] = ">>> "
            PROMPT_CTL["ps2"] = "... "
            print(f"DPL REPL for DPL {varproc.meta['internal']['version']}\nPython {info.PYTHON_VER}{(chr(10)+start_text) if start_text else ''}")
            START_FILE = os.path.join(info.BINDIR, "start_script.dpl")
            if os.path.isfile(START_FILE):
                try:
                    with open(START_FILE, "r") as f:
                        parser.run(parser.process(f.read(), name="dpl_repl-startup"))
                except:
                    print("something went wrong while running start up script!")
            while True:
                try:
                    act = input(PROMPT_CTL["ps1"]).strip()
                except KeyboardInterrupt:
                    exit()
                if act and ((temp:=act.split(maxsplit=1)[0]) in info.INC or temp in info.INC_EXT) or act == "#multiline":
                    while True:
                        try:
                            aa = input(PROMPT_CTL["ps2"])
                        except KeyboardInterrupt:
                            exit()
                        if not aa:
                            break
                        act += "\n"+aa
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
                                parser.run(parser.process(f.read(), name="dpl_repl-startup"))
                        except:
                            print("something went wrong while running start up script!")
                    continue
                try:
                    if (err:=parser.run(parser.process(act), frame=frame)):
                        print(f"Error Code: {err}")
                except Exception as e:
                    print(f"Python Exception was raised while running:\n{repr(e)}")
        case ["help"] | ["--help"]:
            print(f"""Help for DPL [v{varproc.meta['internal']['version']}]

dpl run [file] args...
    Runs the given DPL script.
dpl rc [file] args..
    Runs the given compiled DPL script.
dpl compile [file]
    Compiles the given DPL script.
    Outputs to [file].cdpl
dpl install [python_exec] [flags: verbose]
    Installs runtime requirements.
    See the requirements.txt file.
dpl build
    Builds the parser and cythonizes it.
    The interpreter chooses which to run automatically.
    Although it might be changeable in the configs soon!
dpl build clean
    Removes the cythonized components.
dpl repr ALSO JUST `dpl`
    Invokes the REPL""")
        case _:
            print("Invalid invokation!")
            exit(1)
    if "pause" in flags:
        input("\n[Press Enter To Finish]")

if __name__ == "__main__":
    handle_args()