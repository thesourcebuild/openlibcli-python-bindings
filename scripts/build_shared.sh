#!/usr/bin/env bash
# Build openlibcli as a shared library for the Python ctypes binding.
# Run this from opencli-python/   e.g.  bash scripts/build_shared.sh
set -euo pipefail

CLI_SRC="src/openlibcli/openlibcli_c/cli.c"
CLI_INC="src/openlibcli/openlibcli_c"
CLI_CFG="src/openlibcli/openlibcli_c/config"

echo "Compiling openlibcli shared library ..."

gcc -std=c99 -O2 \
    -fPIC -DCLI_SHARED -DBUILD_LIB_SHARED \
    -DCLI_ENABLE_ALIASES=1 \
    -I"$CLI_INC" -I"$CLI_CFG" \
    -shared \
    -o src/openlibcli/libopenlibcli.so \
    "$CLI_SRC" src/openlibcli/openlibcli_c/cli_py_helper.c \
    -Wl,--export-all-symbols

echo "Shared library created at src/openlibcli/libopenlibcli.so"
