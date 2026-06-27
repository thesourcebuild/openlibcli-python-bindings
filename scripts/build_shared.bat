@echo off
REM Build openlibcli as a shared library for the Python ctypes binding
REM Run this from opencli-python/   e.g. scripts\build_shared.bat

setlocal
set CLI_SRC=src\openlibcli\openlibcli_c\cli.c
set CLI_INC=src\openlibcli\openlibcli_c
set CLI_CFG=src\openlibcli\openlibcli_c\config

echo Compiling openlibcli DLL ...
gcc -std=c99 -O2 ^
    -DCLI_SHARED -DBUILD_LIB_SHARED ^
    -DCLI_ENABLE_ALIASES=1 ^
    -I"%CLI_INC%" -I"%CLI_CFG%" ^
    -shared ^
    -o src\openlibcli\openlibcli.dll ^
    "%CLI_SRC%" src\openlibcli\openlibcli_c\cli_py_helper.c ^
    -lws2_32 ^
    -Wl,--out-implib,src\openlibcli\libopenlibcli.dll.a ^
    -Wl,--export-all-symbols

if %ERRORLEVEL% equ 0 (
    echo DLL created at src\openlibcli\openlibcli.dll
) else (
    echo Build FAILED
    exit /b 1
)
