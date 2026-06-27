"""
High-level Session wrapper around the openlibcli C engine.

Usage::

    import openlibcli as cli
    from openlibcli.transports import BaseTransport

    class MyTransport(BaseTransport):
        def _read_into(self, buf: bytearray) -> int:
            # Read input bytes into buf
            return 0
        def _write(self, data: bytes) -> int:
            # Write output bytes from data
            return len(data)

    transport = MyTransport()
    session = cli.Session("myhost", transport, cmd_pool_size=256)
    session.cli_add_builtin_commands()

    @session.cli_command("show", "version", privilege=cli.PRIV_USER,
                         mode=cli.MODE_ANY, help="Show version")
    def cmd_version(s, cmd, argc, argv):
        s.cli_println("Version 1.0")

    # Alternatively, without a decorator:
    # def cmd_version(s, cmd, argc, argv):
    #     s.cli_println("Version 1.0")
    # session.cli_add_command("show", "version", cmd_version, privilege=cli.PRIV_USER,
    #                         mode=cli.MODE_ANY, help="Show version")

    session.cli_start()
    session.cli_loop()
    session.cli_done()
"""

from __future__ import annotations

from .version import __version__
from .session import (
    Session,
    CLI_OK,
    CLI_ERR,
    CLI_ERR_QUIT,
    CLI_ERR_NOMEM,
    CLI_ERR_AUTH,
    CLI_ERR_AMBIG,
    CLI_CMD_INVALID,
    CLI_CMD_ROOT,
    PRIV_USER,
    PRIV_PRIVILEGED,
    PRIV_SUPERADMIN,
    MODE_ANY,
    MODE_EXEC,
    MODE_ENABLE,
    MODE_CONFIG,
    MODE_USER_BASE,
    TRANSPORT_UNKNOWN,
    TRANSPORT_TELNET,
    TRANSPORT_TCP,
    TRANSPORT_SERIAL,
    TRANSPORT_PIPE,
    TRANSPORT_UNIX_SOCKET,
    SESSION_INIT,
    SESSION_SHOW_BANNER,
    SESSION_AUTH_USERNAME,
    SESSION_AUTH_PASSWORD,
    SESSION_ENABLE_PASSWORD,
    SESSION_AUTH_LOCKOUT,
    SESSION_RUN,
    SESSION_STOP,
    AUTH_FAILURE_MODE_CLOSE,
    AUTH_FAILURE_MODE_LOCKOUT,
    EXIT_ROOT_POLICY_CLOSE_SESSION,
    EXIT_ROOT_POLICY_RESET_SESSION,
    EXIT_ROOT_POLICY_IGNORE,
    QUIT_POLICY_CLOSE_SESSION,
    QUIT_POLICY_RESET_SESSION,
    QUIT_POLICY_IGNORE,
    IDLE_TIMEOUT_MODE_CLOSE,
    IDLE_TIMEOUT_MODE_RESET_SESSION,
    IDLE_TIMEOUT_MODE_IGNORE,
    CLI_EXEC_REPLAY_INPUT,
    CLI_CMD_FLAG_HIDDEN,
    CLI_CMD_FLAG_IN_USE,
    PRINT_KIND_PRINT,
    PRINT_KIND_PRINTLN,
    PRINT_KIND_ERROR,
)

__all__ = [
    "Session",
    "CLI_OK",
    "CLI_ERR",
    "CLI_ERR_QUIT",
    "CLI_ERR_NOMEM",
    "CLI_ERR_AUTH",
    "CLI_ERR_AMBIG",
    "CLI_CMD_INVALID",
    "CLI_CMD_ROOT",
    "PRIV_USER",
    "PRIV_PRIVILEGED",
    "PRIV_SUPERADMIN",
    "MODE_ANY",
    "MODE_EXEC",
    "MODE_ENABLE",
    "MODE_CONFIG",
    "MODE_USER_BASE",
    "TRANSPORT_UNKNOWN",
    "TRANSPORT_TELNET",
    "TRANSPORT_TCP",
    "TRANSPORT_SERIAL",
    "TRANSPORT_PIPE",
    "TRANSPORT_UNIX_SOCKET",
    "SESSION_INIT",
    "SESSION_SHOW_BANNER",
    "SESSION_AUTH_USERNAME",
    "SESSION_AUTH_PASSWORD",
    "SESSION_ENABLE_PASSWORD",
    "SESSION_AUTH_LOCKOUT",
    "SESSION_RUN",
    "SESSION_STOP",
    "AUTH_FAILURE_MODE_CLOSE",
    "AUTH_FAILURE_MODE_LOCKOUT",
    "EXIT_ROOT_POLICY_CLOSE_SESSION",
    "EXIT_ROOT_POLICY_RESET_SESSION",
    "EXIT_ROOT_POLICY_IGNORE",
    "QUIT_POLICY_CLOSE_SESSION",
    "QUIT_POLICY_RESET_SESSION",
    "QUIT_POLICY_IGNORE",
    "IDLE_TIMEOUT_MODE_CLOSE",
    "IDLE_TIMEOUT_MODE_RESET_SESSION",
    "IDLE_TIMEOUT_MODE_IGNORE",
    "CLI_EXEC_REPLAY_INPUT",
    "CLI_CMD_FLAG_HIDDEN",
    "CLI_CMD_FLAG_IN_USE",
    "PRINT_KIND_PRINT",
    "PRINT_KIND_PRINTLN",
    "PRINT_KIND_ERROR",
    "__version__",
]
