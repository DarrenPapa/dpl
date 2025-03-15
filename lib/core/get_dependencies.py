import ast
import os
import sys
import importlib.util
from typing import Dict, Set
import importlib.metadata


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)


def is_standard_library(module_name: str) -> bool:
    if module_name.split(".")[0] in sys.builtin_module_names:
        return True
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None and spec.origin is None
    except (ValueError, ModuleNotFoundError):
        return False


def is_local_file(module_name: str) -> bool:
    try:
        module_path = module_name.replace(".", os.path.sep) + ".py"
        return os.path.isfile(module_path)
    except:
        return False


def find_imports(file_path: str) -> Set[str]:
    with open(file_path, "r") as file:
        tree = ast.parse(file.read(), filename=file_path)
    visitor = ImportVisitor()
    visitor.visit(tree)
    return visitor.imports


def build_dependency_graph(start_file: str) -> Dict[str, Dict[str, str]]:
    dependencies = {}
    to_process = [start_file]
    processed = set()

    while to_process:
        file = to_process.pop()
        if file in processed:
            continue
        processed.add(file)
        try:
            imports = find_imports(file)
        except:
            continue

        dependency_info = {}
        for imp in imports:
            if is_standard_library(imp):
                dependency_info[imp] = "builtin"
            elif imp.split(".")[0] in sys.stdlib_module_names:
                dependency_info[imp] = "stdlib "
            elif is_local_file(imp):
                imp_file = imp.replace(".", os.path.sep) + ".py"
                if imp_file not in processed:
                    to_process.append(imp_file)
                dependency_info[imp] = "local  "
            elif imp == "__main__":
                dependency_info[imp] = "self   "
            else:
                dependency_info[imp] = "extern "

        dependencies[file] = dependency_info

    return dependencies


def print_tree(
    file: str,
    dependencies: Dict[str, Dict[str, str]],
    indent: str = "",
    last: bool = True,
):
    if file not in dependencies:
        return
    connector = " \\-" if last else " |-"
    print(f"{indent}{connector} {os.path.basename(file)}")
    indent += "   " if last else " | "
    items = list(dependencies[file].items())
    for i, (imp, typ) in enumerate(items):
        imp_file = imp.replace(".", os.path.sep) + ".py"
        is_last = i == len(items) - 1
        if typ.strip() in ("local", "stdlib"):  # and os.path.isfile(imp_file):
            print_tree(imp_file, dependencies, indent, last=is_last)
        else:
            print(f"{indent}{' '+chr(92)+'-' if is_last else ' |-'} [ {typ} ] {imp}")


def generate_output(dependencies: Dict[str, Dict[str, str]]) -> str:
    lines = []
    for file, deps in dependencies.items():
        for imp, typ in deps.items():
            lines.append(f"[ {typ} ] {file}: {imp}")
    return "\n".join(lines)


def analyze(file):
    print(generate_output(build_dependency_graph(file)))


if __name__ == "__main__":
    analyze(__file__)
