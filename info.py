# When ran shows the info of the dpl root dir

import os


def convert_bytes(byte):
    "Convert bytes to appropriate units"
    if byte < 1e3:
        return byte, "B"
    elif byte < 1e6:
        return byte * 1e-3, "KB"
    elif byte < 1e9:
        return byte * 1e-6, "MB"
    elif byte < 1e12:
        return byte * 1e-9, "GB"
    elif byte < 1e15:
        return byte * 1e-12, "TB"
    else:
        return byte * 1e-15, "PB"


def list_files_recursive(dir_path, remove=""):
    total_lines = 0
    total_size = 0
    t_files = 0
    for root, dirs, files in os.walk(dir_path):
        #        if os.path.relpath(root).startswith(".") or "__pycache__" in root:
        #            continue
        for file in files:
            if file.strip(os.path.sep).startswith("."):
                continue
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                file_size = convert_bytes(file_size)
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    if (EXT := file_path.rsplit(".", 1)[-1]) in {
                        "txt",
                        "py",
                        "dpl",
                        "cfg",
                        "c",
                        "yaml",
                        "toml",
                        "md",
                        "lua",
                    }:
                        head = "Head:\n"
                        while (temp := f.readline().lstrip()).startswith(
                            {
                                "py": "#",
                                "txt": "#",
                                "dpl": "#",
                                "cfg": "#",
                                "toml": "#",
                                "yaml": "#",
                                "md": "<--",
                                "c": "//",
                                "lua": "--",
                            }[EXT]
                        ):
                            head += "    " + temp
                        head = head.strip()
                        f.seek(0)
                        line_count = sum(1 for _ in f)
                        total_lines += line_count
                        line_count = f"{line_count:,}"
                    else:
                        head = "[Head Not Available]"
                        line_count = "[Line Count Not Available]"
                    t_files += 1
                if len(head.strip()) == 5:
                    head = "[Head Not Available]"
                print(
                    f"{file_path.replace(remove, '')}:\n  {head}\n  Size: {file_size[0]:,.4f} {file_size[1]}\n  Lines: {line_count}"
                )
            except (OSError, IOError) as e:
                print(f"Could not read file {file_path}: {e}")
    total_size = convert_bytes(total_size)
    print(
        f"\nFiles: {t_files:,}\nTotal Size ({total_size[1]}): {total_size[0]:,.2f}\nTotal Lines: {total_lines:,}"
    )


# Run the function on the current directory
list_files_recursive(os.getcwd(), os.getcwd())
