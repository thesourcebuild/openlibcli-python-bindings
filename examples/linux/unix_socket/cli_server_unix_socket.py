#!/usr/bin/env python3
"""
UNIX Domain Socket CLI server and client example.

Usage:
    python examples/linux/unix_socket/cli_server_unix_socket.py [server|client] [socket_path]
"""

from __future__ import annotations

import sys
import os
import socket
import select

# Set up paths to import local openlibcli and shared demo setup
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import openlibcli as cli
from cli_transport_unix_socket import UnixSocketTransport
from shared.cli_demo_setup import demo_setup_session, demo_register_commands, DemoAppData

# Check if AF_UNIX is available
if not hasattr(socket, "AF_UNIX"):
    print("Error: UNIX domain sockets are not supported on this platform.", file=sys.stderr)
    sys.exit(1)


def run_client(path: str) -> None:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(path)
    except OSError as e:
        print(f"Error connecting to socket: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to {path}. Press Ctrl+C to exit.\n")
    
    # Save original terminal settings for raw mode on POSIX if stdout is a TTY
    fd = sys.stdin.fileno()
    is_tty = os.isatty(fd)
    if is_tty and sys.platform != "win32":
        import termios
        import atexit
        orig_term = termios.tcgetattr(fd)
        new_term = termios.tcgetattr(fd)
        new_term[termios.LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.ISIG)
        new_term[termios.CC][termios.VMIN] = 1
        new_term[termios.CC][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSAFLUSH, new_term)
        atexit.register(lambda: termios.tcsetattr(fd, termios.TCSAFLUSH, orig_term))

    try:
        while True:
            r, _, _ = select.select([sys.stdin, sock], [], [])
            if sys.stdin in r:
                data = os.read(sys.stdin.fileno(), 1024)
                if not data:
                    break
                sock.sendall(data)
            if sock in r:
                data = sock.recv(1024)
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("\nDisconnected.")


def run_server(path: str) -> None:
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError as e:
            print(f"Could not remove old socket file: {e}", file=sys.stderr)
            sys.exit(1)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(5)

    print(f"UNIX domain socket CLI server listening on {path} ...")
    print(f"Connect using: nc -U {path}")
    print(f"Or run client: python {sys.argv[0]} client {path}\n")

    session_num = 0
    try:
        while True:
            client, addr = server.accept()
            session_num += 1
            print(f"Client connected (session {session_num})")

            transport = UnixSocketTransport(client)
            session = cli.Session("router", transport, cmd_pool_size=256)

            banner = (
                "************************************************************\r\n"
                "*         OpenLibCLI  --  UNIX Domain Socket (Python)       *\r\n"
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
                client.close()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.close()
        if os.path.exists(path):
            os.remove(path)


def main() -> None:
    mode = "server"
    path = "/tmp/OpenLibCLI.sock"

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    if len(sys.argv) > 2:
        path = sys.argv[2]

    if mode == "client":
        run_client(path)
    elif mode == "server":
        run_server(path)
    else:
        print("Usage: python cli_server_unix_socket.py [server|client] [socket_path]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
