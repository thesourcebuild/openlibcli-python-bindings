#!/usr/bin/env python3
"""
Serial CLI demo — interactive session on stdin/stdout.

Usage:
    python examples/win_linux/serial/cli_server_serial.py
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
from cli_transport_serial import SerialTransport
from shared.cli_demo_setup import demo_setup_session, demo_register_commands, DemoAppData


def main() -> None:
    transport = SerialTransport()
    session = cli.Session("serial", transport, cmd_pool_size=256)

    banner = (
        "************************************************************\r\n"
        "*             OpenLibCLI  --  Serial (stdin stdout)        *\r\n"
        "*         Pure-C Wrapper | Pure Python Transport           *\r\n"
        "************************************************************"
    )

    app_data = DemoAppData(1, 4321, 3800)
    demo_setup_session(session, app_data, 1, 4321, 3800, banner)
    demo_register_commands(session)

    print("Starting Serial CLI server (stdin/stdout)")
    print("Connect with: (Interactive terminal)")
    print("Type 'exit' to quit.\n")

    transport.raw_mode_enable()
    try:
        session.cli_start()
        while True:
            rc = session.cli_session_engine()
            if rc < 0:
                break
    finally:
        transport.raw_mode_disable()
        session.cli_free()


if __name__ == "__main__":
    main()
