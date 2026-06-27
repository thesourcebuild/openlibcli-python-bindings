#!/usr/bin/env python3
"""
Telnet CLI server — accepts connections then runs a CLI session.

Usage:
    python examples/win_linux/telnet/cli_server_telnet.py [port]
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
from cli_transport_telnet import TelnetTransport
from shared.cli_demo_setup import demo_setup_session, demo_register_commands, DemoAppData


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2323

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)

    print(f"OpenLibCLI Telnet CLI server listening on port {port} ...")
    print(f"Connect with: telnet localhost {port}\n")

    session_num = 0
    try:
        while True:
            r, _, _ = select.select([server], [], [], 0.5)
            if not r:
                continue
            client, addr = server.accept()
            session_num += 1
            print(f"Telnet client connected from {addr} (session {session_num})")

            transport = TelnetTransport(client)
            session = cli.Session("router", transport, cmd_pool_size=256)

            banner = (
                "************************************************************\r\n"
                "*             OpenLibCLI  --  Telnet Transport             *\r\n"
                "*         Pure-C, 100% Static Allocation CLI Engine        *\r\n"
                "************************************************************"
            )

            app_data = DemoAppData(session_num, 12345, 11000)
            demo_setup_session(session, app_data, session_num, 12345, 11000, banner)
            demo_register_commands(session)

            try:
                session.cli_start()
                session.cli_loop()
            finally:
                print(f"Telnet session {session_num} ended")
                session.cli_free()
                client.close()
    except KeyboardInterrupt:
        print("\nStopping Telnet server.")
    finally:
        server.close()


if __name__ == "__main__":
    main()
