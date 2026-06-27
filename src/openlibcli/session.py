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

import ctypes
from typing import Any, Callable, ClassVar

from . import _binding as _b
from .transports import BaseTransport


# Re-export constants from the C header as Python module-level names.

CLI_OK = 0
CLI_ERR = -1
CLI_ERR_QUIT = -2
CLI_ERR_NOMEM = -3
CLI_ERR_AUTH = -4
CLI_ERR_AMBIG = -5
CLI_EXEC_REPLAY_INPUT = 1

CLI_CMD_INVALID = -1
CLI_CMD_ROOT = -2
CLI_CMD_FLAG_HIDDEN = 0x01
CLI_CMD_FLAG_IN_USE = 0x02

PRIV_USER = 0
PRIV_PRIVILEGED = 10
PRIV_SUPERADMIN = 15

MODE_ANY = 0
MODE_EXEC = 1
MODE_ENABLE = 2
MODE_CONFIG = 3
MODE_USER_BASE = 20

TRANSPORT_UNKNOWN = 0
TRANSPORT_TELNET = 1
TRANSPORT_TCP = 2
TRANSPORT_SERIAL = 3
TRANSPORT_PIPE = 4
TRANSPORT_UNIX_SOCKET = 5

PRINT_KIND_PRINT = 0
PRINT_KIND_PRINTLN = 1
PRINT_KIND_ERROR = 2

SESSION_INIT = 0
SESSION_SHOW_BANNER = 1
SESSION_AUTH_USERNAME = 2
SESSION_AUTH_PASSWORD = 3
SESSION_ENABLE_PASSWORD = 4
SESSION_AUTH_LOCKOUT = 5
SESSION_RUN = 6
SESSION_STOP = 7

AUTH_FAILURE_MODE_CLOSE = 0
AUTH_FAILURE_MODE_LOCKOUT = 1

EXIT_ROOT_POLICY_CLOSE_SESSION = 0
EXIT_ROOT_POLICY_RESET_SESSION = 1
EXIT_ROOT_POLICY_IGNORE = 2

QUIT_POLICY_CLOSE_SESSION = 0
QUIT_POLICY_RESET_SESSION = 1
QUIT_POLICY_IGNORE = 2

IDLE_TIMEOUT_MODE_CLOSE = 0
IDLE_TIMEOUT_MODE_RESET_SESSION = 1
IDLE_TIMEOUT_MODE_IGNORE = 2


class Session:
    """A single CLI session backed by a C ``cli_t`` instance.

    Manages the lifecycle: alloc, init, run, done, free.
    """

    _userdata_slot: ClassVar[list[Any]] = []

    def __init__(
        self,
        hostname: str,
        transport: BaseTransport,
        cmd_pool_size: int = 64,
        banner: str | None = None,
    ):
        if not isinstance(hostname, str):
            raise TypeError("hostname must be a string")
        if not isinstance(transport, BaseTransport):
            raise TypeError("transport must be an instance of BaseTransport")
        if not isinstance(cmd_pool_size, int) or cmd_pool_size <= 0:
            raise ValueError("cmd_pool_size must be a positive integer")
        if banner is not None and not isinstance(banner, str):
            raise TypeError("banner must be a string or None")

        self._ptr: int = _b.alloc_cli()
        self._pool_ptr: int = _b.alloc_cmd_pool(cmd_pool_size)
        self._transport = transport
        self._handlers: dict[int, tuple[Callable, _b.CMD_FN, str]] = {}
        self._callback_wrappers: dict[str, Any] = {}

        # Build the C transport vtable from the Python transport
        c_transport = transport._build_c_transport()

        _b.cli_lib_init()
        _b.cli_init(
            self._ptr,
            hostname.encode("utf-8"),
            c_transport,
            None,  # platform (use host OS defaults)
            ctypes.c_void_p(self._pool_ptr),
            ctypes.c_int(cmd_pool_size),
        )

        if banner:
            self.cli_set_banner(banner)

    # ── Lifecycle ───────────────────  
    def cli_done(self) -> None:
        """Release the C session (does NOT free the inner struct)."""
        if self._ptr:
            _b.cli_done(self._ptr)

    def cli_free(self) -> None:
        """Free the wrapped C struct entirely."""
        if self._ptr:
            _b.cli_done(self._ptr)
            if self._pool_ptr:
                _b.free_cli(self._pool_ptr)
                self._pool_ptr = 0
            _b.free_cli(self._ptr)
            self._ptr = 0

    def cli_start(self) -> None:
        _b.cli_start(self._ptr)

    def cli_session_engine(self) -> int:
        rc = _b.cli_session_engine(self._ptr)
        if self._transport and self._transport.exception is not None:
            exc = self._transport.exception
            self._transport.exception = None
            raise exc
        return rc

    def cli_loop(self) -> None:
        """Run the session engine until it returns a negative code."""
        while True:
            rc = self.cli_session_engine()
            if rc < 0:
                break


    def cli_get_session_state(self) -> int:
        return _b.cli_get_session_state(self._ptr)

    def cli_restart_session(self) -> None:
        _b.cli_restart_session(self._ptr)

    def cli_request_auth(self) -> None:
        _b.cli_request_auth(self._ptr)

    # ── Configuration ────────────────────────────────────────────────────────

    def cli_set_ansi_supported(self, enabled: bool) -> None:
        _b.cli_set_ansi_supported(self._ptr, enabled)

    def cli_set_hostname(self, hostname: str) -> None:
        _b.cli_set_hostname(self._ptr, hostname.encode("utf-8"))

    def cli_set_banner(self, banner: str) -> None:
        _b.cli_set_banner(self._ptr, banner.encode("utf-8"))

    def cli_set_enable_secret(self, secret: str) -> None:
        _b.cli_set_enable_secret(self._ptr, secret.encode("utf-8"))

    def cli_set_exit_root_policy(self, policy: int) -> None:
        _b.cli_set_exit_root_policy(self._ptr, policy)

    def cli_set_quit_policy(self, policy: int) -> None:
        _b.cli_set_quit_policy(self._ptr, policy)

    def cli_set_enable_cb(self, cb: Callable | None) -> None:
        """cb(username: str, password: str) -> int (CLI_OK / CLI_ERR_AUTH)"""
        if cb is None:
            self._callback_wrappers.pop("enable", None)
            _b.cli_set_enable_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.ENABLE_FN
        def _cb(user_c, pass_c):
            return cb(user_c.decode("utf-8") if user_c else "",
                      pass_c.decode("utf-8") if pass_c else "")
        self._callback_wrappers["enable"] = _cb
        _b.cli_set_enable_cb(self._ptr, _cb)

    def cli_set_exit_cb(self, cb: Callable | None) -> None:
        """cb(session) -> int"""
        if cb is None:
            self._callback_wrappers.pop("exit", None)
            _b.cli_set_exit_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.SESSION_CMD_FN
        def _cb(cli_ptr):
            return cb(self)
        self._callback_wrappers["exit"] = _cb
        _b.cli_set_exit_cb(self._ptr, _cb)

    def cli_set_quit_cb(self, cb: Callable | None) -> None:
        """cb(session) -> int"""
        if cb is None:
            self._callback_wrappers.pop("quit", None)
            _b.cli_set_quit_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.SESSION_CMD_FN
        def _cb(cli_ptr):
            return cb(self)
        self._callback_wrappers["quit"] = _cb
        _b.cli_set_quit_cb(self._ptr, _cb)

    def cli_set_userdata(self, data: Any) -> None:
        """Store an arbitrary Python object reference (kept alive via a thread)."""
        # Store via a module-level list to prevent GC
        Session._userdata_slot.append(data)
        _b.cli_set_userdata(self._ptr, id(data))

    def cli_get_userdata(self) -> Any | None:
        ptr = _b.cli_get_userdata(self._ptr)
        if not ptr:
            return None
        return ctypes.cast(ptr, ctypes.py_object).value

    def cli_get_transport_kind(self) -> int:
        return _b.cli_get_transport_kind(self._ptr)

    def cli_set_mode_change_cb(self, cb: Callable | None) -> None:
        """cb(session, new_mode: int, new_priv: int) -> None"""
        if cb is None:
            self._callback_wrappers.pop("mode_change", None)
            _b.cli_set_mode_change_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.MODE_FN
        def _cb(cli_ptr, mode, priv):
            cb(self, mode, priv)
        self._callback_wrappers["mode_change"] = _cb
        _b.cli_set_mode_change_cb(self._ptr, _cb)

    def cli_set_mode_name(self, mode: int, name: str) -> None:
        _b.cli_set_mode_name(self._ptr, mode, name.encode("utf-8"))

    def cli_set_time_source(self, fn: Callable | None, ctx: Any = None) -> None:
        if fn is None:
            self._callback_wrappers.pop("time_source", None)
            _b.cli_set_time_source(self._ptr, None, 0)
            return
        if not callable(fn):
            raise TypeError("time source function must be callable or None")
        @_b.TIME_FN
        def _cb(c_ctx):
            return fn(ctx)
        self._callback_wrappers["time_source"] = _cb
        _b.cli_set_time_source(self._ptr, _cb, id(ctx) if ctx is not None else 0)

    def cli_set_idle_timeout(self, seconds: int) -> None:
        _b.cli_set_idle_timeout(self._ptr, seconds)

    def cli_set_idle_timeout_cb(self, seconds: int, cb: Callable | None) -> None:
        if cb is None:
            self._callback_wrappers.pop("idle_timeout", None)
            _b.cli_set_idle_timeout_cb(self._ptr, seconds, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.IDLE_TIMEOUT_FN
        def _cb(cli_ptr):
            return cb(self)
        self._callback_wrappers["idle_timeout"] = _cb
        _b.cli_set_idle_timeout_cb(self._ptr, seconds, _cb)

    def cli_set_idle_timeout_mode(self, mode: int) -> None:
        _b.cli_set_idle_timeout_mode(self._ptr, mode)

    def cli_set_periodic_cb(self, cb: Callable | None) -> None:
        if cb is None:
            self._callback_wrappers.pop("periodic", None)
            _b.cli_set_periodic_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.PERIODIC_FN
        def _cb(cli_ptr):
            return cb(self)
        self._callback_wrappers["periodic"] = _cb
        _b.cli_set_periodic_cb(self._ptr, _cb)

    def cli_set_periodic_interval(self, seconds: int) -> None:
        _b.cli_set_periodic_interval(self._ptr, seconds)

    def cli_touch_activity(self) -> None:
        _b.cli_touch_activity(self._ptr)

    def cli_clear_history(self) -> int:
        return _b.cli_clear_history(self._ptr)

    def cli_check_idle_timeout(self) -> int:
        return _b.cli_check_idle_timeout(self._ptr)

    # ── Authentication ───────────────────────────────────────────────────────

    def cli_add_user(self, username: str, password: str, privilege: int = PRIV_USER) -> int:
        return _b.cli_add_user(
            self._ptr,
            username.encode("utf-8"),
            password.encode("utf-8"),
            privilege,
        )

    def cli_set_authorization_cb(self, cb: Callable | None) -> None:
        """cb(username: str, password: str) -> int (CLI_OK / CLI_ERR_AUTH)"""
        if cb is None:
            self._callback_wrappers.pop("authorization", None)
            _b.cli_set_authorization_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.AUTH_FN
        def _cb(user_c, pass_c):
            return cb(user_c.decode("utf-8") if user_c else "",
                      pass_c.decode("utf-8") if pass_c else "")
        self._callback_wrappers["authorization"] = _cb
        _b.cli_set_authorization_cb(self._ptr, _cb)

    def cli_require_authorization(self, require: bool) -> None:
        _b.cli_require_authorization(self._ptr, require)

    def cli_set_auth_failure_mode(self, mode: int) -> None:
        _b.cli_set_auth_failure_mode(self._ptr, mode)

    def cli_set_auth_lockout_duration(self, seconds: int) -> None:
        _b.cli_set_auth_lockout_duration(self._ptr, seconds)

    # ── Command Registration ─────────────────────────────────────────────────

    def cli_add_builtin_commands(self) -> None:
        _b.cli_add_builtin_cmds(self._ptr)

    def cli_command(
        self,
        parent: int | str = CLI_CMD_ROOT,
        name: str = "",
        privilege: int = PRIV_USER,
        mode: int = MODE_ANY,
        help: str = "",
    ) -> Callable:
        """Decorator to register a command handler.

        Can be used with a string parent name for sub-commands.
        """
        def decorator(fn: Callable) -> Callable:
            self.cli_add_command(parent, name, fn, privilege, mode, help)
            return fn
        return decorator

    def cli_add_command(
        self,
        parent: int | str,
        name: str,
        callback: Callable,
        privilege: int = PRIV_USER,
        mode: int = MODE_ANY,
        help: str = "",
    ) -> int:
        """Register a command.

        ``callback`` signature: ``(session, cmd: str, argc: int, argv: list[str]) -> int``
        """
        if not callable(callback):
            raise TypeError("callback must be callable")
        parent_h = self._resolve_parent(parent)

        @_b.CMD_FN
        def _cb(cli_ptr, cmd_c, argc, argv_c):
            cmd_str = cmd_c.decode("utf-8") if cmd_c else ""
            argv_list = []
            for i in range(argc):
                argv_list.append(argv_c[i].decode("utf-8") if argv_c[i] else "")
            result = callback(self, cmd_str, argc, argv_list)
            return CLI_OK if result is None else result

        handle = _b.cli_add_command(
            self._ptr,
            parent_h,
            name.encode("utf-8"),
            _cb,
            privilege,
            mode,
            help.encode("utf-8") if help else None,
        )
        if handle != CLI_CMD_INVALID:
            self._handlers[handle] = (callback, _cb, name)
        return handle

    def _resolve_parent(self, parent: int | str) -> int:
        if isinstance(parent, int):
            return parent
        # String parent — search registered commands by name
        for handle, (_, _, name) in self._handlers.items():
            if name == parent:
                return handle
        return CLI_CMD_ROOT

    def cli_add_command_duplicate(self, original: int, alias_name: str) -> int:
        return _b.cli_add_command_duplicate(self._ptr, original, alias_name.encode("utf-8"))

    def cli_cmd_add_alias(self, handle: int, alias_name: str) -> int:
        return _b.cli_cmd_add_alias(self._ptr, handle, alias_name.encode("utf-8"))

    def cli_remove_command(self, handle: int) -> int:
        self._handlers.pop(handle, None)
        return _b.cli_remove_command(self._ptr, handle)

    def cli_remove_command_recursive(self, handle: int) -> int:
        self._handlers.pop(handle, None)
        return _b.cli_remove_command_recursive(self._ptr, handle)

    def cli_hide_command(self, handle: int) -> None:
        _b.cli_hide_command(self._ptr, handle)

    # ── Output ───────────────────────────────────────────────────────────────

    def cli_println(self, fmt: str, *args) -> int:
        msg = (fmt % args) if args else fmt
        return _b.cli_println(self._ptr, msg.encode("utf-8"))

    def cli_print(self, fmt: str, *args) -> int:
        msg = (fmt % args) if args else fmt
        return _b.cli_print(self._ptr, msg.encode("utf-8"))

    def cli_error(self, fmt: str, *args) -> int:
        msg = (fmt % args) if args else fmt
        return _b.cli_error(self._ptr, msg.encode("utf-8"))

    def cli_print_flush(self) -> None:
        _b.cli_print_flush(self._ptr)

    def cli_set_print_transport_cb(self, cb: Callable | None) -> None:
        if cb is None:
            self._callback_wrappers.pop("print_transport", None)
            _b.cli_set_print_transport_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.PRINT_TRANSPORT_FN
        def _cb(cli_ptr, line_c):
            cb(self, line_c.decode("utf-8") if line_c else "")
        self._callback_wrappers["print_transport"] = _cb
        _b.cli_set_print_transport_cb(self._ptr, _cb)

    def cli_set_print_cb(self, cb: Callable | None) -> None:
        """cb(session, text: str, kind: int) -> None"""
        if cb is None:
            self._callback_wrappers.pop("print", None)
            _b.cli_set_print_cb(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.PRINT_FN
        def _cb(cli_ptr, text_c, kind):
            cb(self, text_c.decode("utf-8") if text_c else "", kind)
        self._callback_wrappers["print"] = _cb
        _b.cli_set_print_cb(self._ptr, _cb)

    def cli_set_print_cb_v(self, cb: Callable | None) -> None:
        """cb(session, fmt: str, ap: int) -> None"""
        if cb is None:
            self._callback_wrappers.pop("print_v", None)
            _b.cli_set_print_cb_v(self._ptr, None)
            return
        if not callable(cb):
            raise TypeError("callback must be callable or None")
        @_b.PRINT_V_FN
        def _cb(cli_ptr, fmt_c, ap):
            cb(self, fmt_c.decode("utf-8") if fmt_c else "", ap)
        self._callback_wrappers["print_v"] = _cb
        _b.cli_set_print_cb_v(self._ptr, _cb)

    # ── Mode / Privilege ─────────────────────────────────────────────────────

    def cli_set_mode(self, mode: int) -> None:
        _b.cli_set_mode(self._ptr, mode)

    def cli_set_privilege(self, privilege: int) -> None:
        _b.cli_set_privilege(self._ptr, privilege)

    def cli_get_mode(self) -> int:
        return _b.cli_get_mode(self._ptr)

    def cli_get_privilege(self) -> int:
        return _b.cli_get_privilege(self._ptr)

    def cli_sscanf(self, s: str, fmt: str, out: Any) -> int:
        return _b.cli_sscanf(s.encode("utf-8"), fmt.encode("utf-8"), ctypes.byref(out))

    def cli_exec(self, cmd: str) -> int:
        return _b.cli_exec(self._ptr, cmd.encode("utf-8"))

    def cli_exec_argv(self, argv: list[str]) -> int:
        argc = len(argv)
        c_argv = (ctypes.c_char_p * argc)()
        for i, arg in enumerate(argv):
            c_argv[i] = arg.encode("utf-8")
        return _b.cli_exec_argv(self._ptr, c_argv, argc)

    def cli_set_micros_source(self, fn: Callable, ctx: Any = None) -> None:
        @_b.MICROS_FN
        def _cb(c_ctx):
            return fn(ctx)
        self._callback_wrappers["micros_source"] = _cb
        _b.cli_set_micros_source(self._ptr, _cb, id(ctx) if ctx is not None else 0)

    def cli_tick_stats_get(self) -> dict[str, int]:
        stats = _b.CliTickStats()
        _b.cli_tick_stats_get(self._ptr, ctypes.byref(stats))
        return {
            "min_us": stats.min_us,
            "max_us": stats.max_us,
            "avg_us": stats.avg_us,
            "count": stats.count,
        }

    def cli_tick_stats_reset(self) -> None:
        _b.cli_tick_stats_reset(self._ptr)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.cli_free()
