#!/usr/bin/env python3
"""
Named Pipe CLI server and client example.

Usage:
    python examples/win_linux/pipe/cli_server_pipe.py [named|client] [pipe_name]
"""

from __future__ import annotations

import sys
import os
import time

# Set up paths to import local openlibcli and shared demo setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import openlibcli as cli
from cli_transport_pipe import PipeTransport
from shared.cli_demo_setup import demo_setup_session, demo_register_commands, DemoAppData

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    PIPE_ACCESS_DUPLEX = 0x00000003
    PIPE_TYPE_BYTE = 0x00000000
    PIPE_READMODE_BYTE = 0x00000000
    PIPE_WAIT = 0x00000000
    INVALID_HANDLE_VALUE = -1
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3


def run_windows_server(name: str) -> None:
    pipe_path = f"\\\\.\\pipe\\{name}"
    print(f"Creating Windows Named Pipe server: {pipe_path}")
    print("Type Ctrl+C to exit.\n")

    session_num = 0
    try:
        while True:
            h_pipe = kernel32.CreateNamedPipeW(
                pipe_path,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                1,
                4096,
                4096,
                0,
                None,
            )
            if h_pipe == INVALID_HANDLE_VALUE:
                print(f"Error creating named pipe: {kernel32.GetLastError()}", file=sys.stderr)
                sys.exit(1)

            print("Waiting for client connection...")
            connected = kernel32.ConnectNamedPipe(h_pipe, None)
            if not connected:
                if kernel32.GetLastError() != 535:  # ERROR_PIPE_CONNECTED
                    kernel32.CloseHandle(h_pipe)
                    continue

            session_num += 1
            print(f"Client connected (session {session_num})")

            transport = PipeTransport(h_pipe)
            session = cli.Session("router", transport, cmd_pool_size=256)

            banner = (
                "************************************************************\r\n"
                "*              OpenLibCLI  --  Pipe Transport              *\r\n"
                "*         Pure-C, 100% Static Allocation CLI Engine        *\r\n"
                "************************************************************"
            )
            app_data = DemoAppData(session_num, 4321, 3800)
            demo_setup_session(session, app_data, session_num, 4321, 3800, banner)
            demo_register_commands(session)

            try:
                session.cli_start()
                session.cli_loop()
            finally:
                print(f"Session {session_num} ended")
                session.cli_free()
                kernel32.CloseHandle(h_pipe)
    except KeyboardInterrupt:
        print("\nStopping pipe server.")


def run_windows_client(name: str) -> None:
    pipe_path = f"\\\\.\\pipe\\{name}"
    print(f"Connecting to Windows Named Pipe: {pipe_path}")

    h_pipe = kernel32.CreateFileW(
        pipe_path,
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if h_pipe == INVALID_HANDLE_VALUE:
        print(f"Error connecting to named pipe: {kernel32.GetLastError()}", file=sys.stderr)
        sys.exit(1)

    print("Connected. Type commands below (Press Ctrl+C to exit):\n")

    done = False

    def reader_thread() -> None:
        nonlocal done
        avail = wintypes.DWORD(0)
        read_bytes = wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(4096)
        while not done:
            success = kernel32.PeekNamedPipe(h_pipe, None, 0, None, ctypes.byref(avail), None)
            if not success:
                print("\nServer disconnected.")
                done = True
                break
            if avail.value > 0:
                ok = kernel32.ReadFile(h_pipe, buf, len(buf) - 1, ctypes.byref(read_bytes), None)
                if not ok or read_bytes.value == 0:
                    print("\nServer disconnected.")
                    done = True
                    break
                sys.stdout.buffer.write(buf.raw[:read_bytes.value])
                sys.stdout.buffer.flush()
            time.sleep(0.01)

    import threading
    t = threading.Thread(target=reader_thread, daemon=True)
    t.start()

    try:
        while not done:
            line = sys.stdin.readline()
            if not line:
                break
            data = line.encode("utf-8")
            written = wintypes.DWORD(0)
            ok = kernel32.WriteFile(h_pipe, data, len(data), ctypes.byref(written), None)
            if not ok:
                print("Failed to write to named pipe.")
                break
    except KeyboardInterrupt:
        pass
    finally:
        done = True
        kernel32.CloseHandle(h_pipe)


def run_posix_server(name: str) -> None:
    if not hasattr(os, "mkfifo"):
        print("POSIX Named Pipes (FIFOs) are not supported on this platform.", file=sys.stderr)
        sys.exit(1)

    fifo_in = f"{name}.in"
    fifo_out = f"{name}.out"

    for path in (fifo_in, fifo_out):
        if os.path.exists(path):
            os.remove(path)
        getattr(os, "mkfifo")(path)


    print(f"POSIX Named Pipe server listening on FIFOs: {fifo_in} / {fifo_out}")
    print("Type Ctrl+C to exit.\n")

    session_num = 0
    try:
        while True:
            print("Waiting for client connection...")
            fd_in = os.open(fifo_in, os.O_RDONLY)
            fd_out = os.open(fifo_out, os.O_WRONLY)

            session_num += 1
            print(f"Client connected (session {session_num})")

            transport = PipeTransport(fd_in, fd_out)
            session = cli.Session("router", transport, cmd_pool_size=256)

            banner = (
                "************************************************************\r\n"
                "*              OpenLibCLI  --  Pipe Transport              *\r\n"
                "*         Pure-C, 100% Static Allocation CLI Engine        *\r\n"
                "************************************************************"
            )
            app_data = DemoAppData(session_num, 4321, 3800)
            demo_setup_session(session, app_data, session_num, 4321, 3800, banner)
            demo_register_commands(session)

            try:
                session.cli_start()
                session.cli_loop()
            finally:
                print(f"Session {session_num} ended")
                session.cli_free()
                os.close(fd_in)
                os.close(fd_out)
    except KeyboardInterrupt:
        print("\nStopping pipe server.")
    finally:
        for path in (fifo_in, fifo_out):
            if os.path.exists(path):
                os.remove(path)


def run_posix_client(name: str) -> None:
    fifo_in = f"{name}.in"
    fifo_out = f"{name}.out"

    if not os.path.exists(fifo_in) or not os.path.exists(fifo_out):
        print(f"FIFOs {fifo_in} / {fifo_out} do not exist. Start the server first.", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to POSIX FIFOs: {fifo_in} / {fifo_out}")
    fd_write = os.open(fifo_in, os.O_WRONLY)
    fd_read = os.open(fifo_out, os.O_RDONLY)

    print("Connected. Type commands below (Press Ctrl+C to exit):\n")

    import select
    try:
        while True:
            r, _, _ = select.select([sys.stdin, fd_read], [], [])
            if sys.stdin in r:
                data = os.read(sys.stdin.fileno(), 1024)
                if not data:
                    break
                os.write(fd_write, data)
            if fd_read in r:
                data = os.read(fd_read, 1024)
                if not data:
                    print("\nServer disconnected.")
                    break
                os.write(sys.stdout.fileno(), data)
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd_write)
        os.close(fd_read)


def main() -> None:
    mode = "named"
    pipe_name = "OpenLibCLIPipe"

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    if len(sys.argv) > 2:
        pipe_name = sys.argv[2]

    if mode == "server" or mode == "named":
        if IS_WINDOWS:
            run_windows_server(pipe_name)
        else:
            run_posix_server(pipe_name)
    elif mode == "client":
        if IS_WINDOWS:
            run_windows_client(pipe_name)
        else:
            run_posix_client(pipe_name)
    else:
        print("Usage: python cli_server_pipe.py [named|client] [pipe_name]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
