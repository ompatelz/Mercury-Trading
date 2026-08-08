from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pybind11

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "backtesting" / "native" / "engine.cpp"
OUTPUT_DIR = ROOT / "app" / "backtesting" / "native"


def main() -> None:
    compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("c++")
    if compiler is None:
        raise SystemExit("No C++ compiler found. Install g++/c++ or set CXX.")

    extension_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not extension_suffix:
        extension_suffix = ".pyd" if sys.platform == "win32" else ".so"

    output = OUTPUT_DIR / f"_engine{extension_suffix}"
    include_dirs = [
        pybind11.get_include(),
        sysconfig.get_paths()["include"],
    ]
    command = [
        compiler,
        "-O3",
        "-std=c++17",
        "-shared",
        "-fPIC",
        str(SOURCE),
        "-o",
        str(output),
    ]
    for include_dir in include_dirs:
        command.extend(["-I", include_dir])

    if sys.platform == "win32":
        library_dir = sysconfig.get_config_var("LIBDIR") or str(Path(sys.base_prefix) / "libs")
        library = f"python{sys.version_info.major}{sys.version_info.minor}"
        command.extend(["-L", library_dir, f"-l{library}", "-static"])

    subprocess.run(command, cwd=ROOT, check=True)
    print(output)


if __name__ == "__main__":
    main()
