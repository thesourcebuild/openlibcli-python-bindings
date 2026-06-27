from setuptools import setup, Extension, find_packages
import sys
import os
import subprocess

PACKAGE_NAME = "openlibcli"

def read_version():
    version_file = os.path.join(os.path.dirname(__file__), "version")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.1.0"

# ── Dynamic versioning from Git ──────────────────────────────────────────────
root_version = read_version()
version_parts = root_version.split(".")
VER_MAJOR = int(version_parts[0]) if len(version_parts) > 0 else 0
VER_MINOR = int(version_parts[1]) if len(version_parts) > 1 else 1
VER_MAINT = int(version_parts[2]) if len(version_parts) > 2 else 0
VER_PREREL = version_parts[3] if len(version_parts) > 3 else ""

VER_LOCAL = ""
try:
    # Check if we are in a git repository and git is installed
    if subprocess.call(["git", "status"], stderr=subprocess.STDOUT, stdout=open(os.devnull, 'w')) == 0:
        p = subprocess.Popen(
            "git log -1 --format=%cd --date=format:%Y%m%d.%H%M%S",
            shell=True, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )
        (outstr, __) = p.communicate()
        (VER_CDATE, VER_CTIME) = outstr.strip().decode("utf-8").split('.')

        p = subprocess.Popen(
            "git rev-parse --short HEAD",
            shell=True, stdin=subprocess.PIPE, stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )
        (outstr, __) = p.communicate()
        VER_CHASH = outstr.strip().decode("utf-8")

        VER_LOCAL = f"+{VER_CDATE}.{VER_CTIME}.{VER_CHASH}"
except Exception:
    pass

version = f"{VER_MAJOR}.{VER_MINOR}.{VER_MAINT}"
if VER_PREREL:
    version += f".{VER_PREREL}"
if VER_LOCAL:
    version += VER_LOCAL
# The version is now resolved dynamically in src/openlibcli/version.py


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname), encoding="utf-8").read()


define_macros: list[tuple[str, str | None]] = [
    ("CLI_SHARED", "1"),
    ("CLI_ENABLE_ALIASES", "1"),
]

if sys.platform == "win32":
    define_macros.append(("BUILD_LIB_SHARED", "1"))

libraries = []
if sys.platform == "win32":
    libraries.append("ws2_32")

ext = Extension(
    "openlibcli.libopenlibcli",
    sources=[
        "src/openlibcli/openlibcli_c/cli.c",
        "src/openlibcli/openlibcli_c/cli_py_helper.c",
    ],
    include_dirs=[
        "src/openlibcli/openlibcli_c",
        "src/openlibcli/openlibcli_c/config",
    ],
    define_macros=define_macros,
    libraries=libraries,
)

setup(
    version=version,
    ext_modules=[ext],
)
