"""
Low-level ctypes bindings for the openlibcli C library.

This module loads the compiled ``openlibcli.dll`` / ``libopenlibcli.so``
and defines the ctypes types, function prototypes, and helper
functions used by the higher-level ``Session`` and transport classes.

You rarely need to touch this module directly.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import platform
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .transports import BaseTransport

# ── Load the shared library ──────────────────────────────────────────────────

_lib_path: str | None = None

import sysconfig
import glob

# 1) Try to find dynamically compiled setuptools extension in this directory
_this_dir = os.path.dirname(os.path.abspath(__file__))
_ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
if _ext_suffix:
    _pattern = os.path.join(_this_dir, f"*libopenlibcli*{_ext_suffix}")
    _matches = glob.glob(_pattern)
    if _matches:
        _lib_path = _matches[0]

# 2) Try standard static filenames (precompiled) next to this file
if _lib_path is None:
    for _candidate in ("openlibcli.dll", "libopenlibcli.so", "libopenlibcli.dylib"):
        _p = os.path.join(_this_dir, _candidate)
        if os.path.isfile(_p):
            _lib_path = _p
            break

# 3) Try generic pattern match fallback next to this file
if _lib_path is None:
    for _candidate_ext in (".so", ".pyd", ".dylib", ".dll"):
        _pattern = os.path.join(_this_dir, f"*libopenlibcli*{_candidate_ext}")
        _matches = glob.glob(_pattern)
        if _matches:
            _lib_path = _matches[0]
            break

# 4) Try system PATH / LD_LIBRARY_PATH
if _lib_path is None:
    _lib_path = ctypes.util.find_library("openlibcli")

if _lib_path is None:
    raise OSError(
        "Cannot locate openlibcli shared library. "
        "Place openlibcli.dll (or .so/.dylib) next to this file "
        "or in a system library path."
    )

_lib: ctypes.CDLL = ctypes.CDLL(_lib_path)

# ── Platform-dependent type aliases ──────────────────────────────────────────

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    TRANSPORT_RET = ctypes.c_int
    TRANSPORT_BUFLEN = ctypes.c_int
else:
    TRANSPORT_RET = ctypes.c_ssize_t
    TRANSPORT_BUFLEN = ctypes.c_size_t

# ── Helper: opaque cli_t allocation ──────────────────────────────────────────

_lib.cli_py_sizeof.restype = ctypes.c_size_t
_lib.cli_py_sizeof.argtypes = ()
_cli_sizeof: int = _lib.cli_py_sizeof()

_lib.cli_py_alloc.restype = ctypes.c_void_p
_lib.cli_py_alloc.argtypes = ()

_lib.cli_py_free.restype = None
_lib.cli_py_free.argtypes = (ctypes.c_void_p,)


def alloc_cli() -> int:
    """Return a raw pointer (int) to a zero-initialised cli_t."""
    return _lib.cli_py_alloc()


def free_cli(ptr: int) -> None:
    """Free a cli_t previously returned by alloc_cli()."""
    _lib.cli_py_free(ctypes.c_void_p(ptr))


# ── Helper: command pool allocation ──────────────────────────────────────────

_lib.cli_py_cmd_pool_alloc.restype = ctypes.c_void_p
_lib.cli_py_cmd_pool_alloc.argtypes = (ctypes.c_size_t,)


def alloc_cmd_pool(count: int) -> int:
    """Return a raw pointer to a zero-initialised command pool."""
    return _lib.cli_py_cmd_pool_alloc(ctypes.c_size_t(count))



# ── Transport vtable types ───────────────────────────────────────────────────

TRANSPORT_AVAILABLE_FN = ctypes.CFUNCTYPE(
    TRANSPORT_RET,
    ctypes.c_void_p,  # ctx
)

TRANSPORT_READ_FN = ctypes.CFUNCTYPE(
    TRANSPORT_RET,
    ctypes.c_void_p,  # ctx
)

TRANSPORT_WRITE_FN = ctypes.CFUNCTYPE(
    TRANSPORT_RET,
    ctypes.c_void_p,  # ctx
    ctypes.POINTER(ctypes.c_uint8),  # buf
    TRANSPORT_BUFLEN,  # len
)

TRANSPORT_FLUSH_FN = ctypes.CFUNCTYPE(
    TRANSPORT_RET,
    ctypes.c_void_p,  # ctx
)


class CliTransport(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_int),
        ("available", TRANSPORT_AVAILABLE_FN),
        ("read", TRANSPORT_READ_FN),
        ("write", TRANSPORT_WRITE_FN),
        ("flush", TRANSPORT_FLUSH_FN),
        ("ctx", ctypes.c_void_p),
    ]


class CliTickStats(ctypes.Structure):
    _fields_ = [
        ("min_us", ctypes.c_uint32),
        ("max_us", ctypes.c_uint32),
        ("avg_us", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
    ]


# ── Global mapping: ctx pointer -> Python Transport object ───────────────────
# This lets C callbacks find the Python transport instance.

_transport_map: dict[int, "BaseTransport"] = {}


def _register_transport(ctx_ptr: int, tp: "BaseTransport") -> None:
    _transport_map[ctx_ptr] = tp


def _unregister_transport(ctx_ptr: int) -> None:
    _transport_map.pop(ctx_ptr, None)


# ── Command handler callback type ────────────────────────────────────────────

CMD_FN = ctypes.CFUNCTYPE(
    ctypes.c_int8,  # return (CLI_OK / CLI_ERR)
    ctypes.c_void_p,  # cli_t*
    ctypes.c_char_p,  # cmd string
    ctypes.c_int,  # argc
    ctypes.POINTER(ctypes.c_char_p),  # argv[]
)

# ── Other callback types (auth, enable, mode-change, etc.) ───────────────────

AUTH_FN = ctypes.CFUNCTYPE(
    ctypes.c_int8,
    ctypes.c_char_p,  # username
    ctypes.c_char_p,  # password
)

ENABLE_FN = ctypes.CFUNCTYPE(
    ctypes.c_int8,
    ctypes.c_char_p,  # username
    ctypes.c_char_p,  # password
)

MODE_FN = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,  # cli_t*
    ctypes.c_int,  # new_mode
    ctypes.c_uint8,  # new_priv
)

TIME_FN = ctypes.CFUNCTYPE(
    ctypes.c_uint32,
    ctypes.c_void_p,  # ctx
)

MICROS_FN = ctypes.CFUNCTYPE(
    ctypes.c_uint32,
    ctypes.c_void_p,
)

IDLE_TIMEOUT_FN = ctypes.CFUNCTYPE(
    ctypes.c_int8,
    ctypes.c_void_p,
)

PERIODIC_FN = ctypes.CFUNCTYPE(
    ctypes.c_int8,
    ctypes.c_void_p,
)

SESSION_CMD_FN = ctypes.CFUNCTYPE(
    ctypes.c_int8,
    ctypes.c_void_p,
)

PRINT_TRANSPORT_FN = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,  # cli_t*
    ctypes.c_char_p,  # line
)

PRINT_FN = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,  # cli_t*
    ctypes.c_char_p,  # text
    ctypes.c_int,  # kind
)

PRINT_V_FN = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_char_p,  # fmt
    ctypes.c_void_p,  # va_list (opaque)
)

# ── Function prototypes ──────────────────────────────────────────────────────


def _fn(name: str, restype, *argtypes) -> Callable:
    f = getattr(_lib, name)
    f.restype = restype
    f.argtypes = argtypes
    return f


# Lifeycle
cli_lib_init: Callable = _fn("cli_lib_init", None)
cli_init: Callable = _fn("cli_init", None, ctypes.c_void_p, ctypes.c_char_p,
                          ctypes.POINTER(CliTransport), ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_int)
cli_done: Callable = _fn("cli_done", None, ctypes.c_void_p)
cli_get_session_state: Callable = _fn("cli_get_session_state", ctypes.c_int, ctypes.c_void_p)
cli_restart_session: Callable = _fn("cli_restart_session", None, ctypes.c_void_p)
cli_request_auth: Callable = _fn("cli_request_auth", None, ctypes.c_void_p)

# Configuration
cli_set_ansi_supported: Callable = _fn("cli_set_ansi_supported", None, ctypes.c_void_p, ctypes.c_bool)
cli_set_hostname: Callable = _fn("cli_set_hostname", None, ctypes.c_void_p, ctypes.c_char_p)
cli_set_banner: Callable = _fn("cli_set_banner", None, ctypes.c_void_p, ctypes.c_char_p)
cli_set_enable_secret: Callable = _fn("cli_set_enable_secret", None, ctypes.c_void_p, ctypes.c_char_p)
cli_set_enable_cb: Callable = _fn("cli_set_enable_privilege_cb", None, ctypes.c_void_p, ENABLE_FN)
cli_set_exit_cb: Callable = _fn("cli_set_exit_cb", None, ctypes.c_void_p, SESSION_CMD_FN)
cli_set_quit_cb: Callable = _fn("cli_set_quit_cb", None, ctypes.c_void_p, SESSION_CMD_FN)
cli_set_exit_root_policy: Callable = _fn("cli_set_exit_root_policy", None, ctypes.c_void_p, ctypes.c_int)
cli_set_quit_policy: Callable = _fn("cli_set_quit_policy", None, ctypes.c_void_p, ctypes.c_int)
cli_set_userdata: Callable = _fn("cli_set_userdata", None, ctypes.c_void_p, ctypes.c_void_p)
cli_get_userdata: Callable = _fn("cli_get_userdata", ctypes.c_void_p, ctypes.c_void_p)
cli_get_transport_kind: Callable = _fn("cli_get_transport_kind", ctypes.c_int, ctypes.c_void_p)
cli_set_mode_change_cb: Callable = _fn("cli_set_mode_change_cb", None, ctypes.c_void_p, MODE_FN)
cli_set_mode_name: Callable = _fn("cli_set_mode_name", None, ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p)
cli_set_time_source: Callable = _fn("cli_set_time_source", None, ctypes.c_void_p, TIME_FN, ctypes.c_void_p)
cli_set_idle_timeout: Callable = _fn("cli_set_idle_timeout", None, ctypes.c_void_p, ctypes.c_uint32)
cli_set_idle_timeout_cb: Callable = _fn("cli_set_idle_timeout_cb", None, ctypes.c_void_p, ctypes.c_uint32, IDLE_TIMEOUT_FN)
cli_set_idle_timeout_mode: Callable = _fn("cli_set_idle_timeout_mode", None, ctypes.c_void_p, ctypes.c_int)
cli_set_periodic_cb: Callable = _fn("cli_set_periodic_cb", None, ctypes.c_void_p, PERIODIC_FN)
cli_set_periodic_interval: Callable = _fn("cli_set_periodic_interval", None, ctypes.c_void_p, ctypes.c_uint32)
cli_touch_activity: Callable = _fn("cli_touch_activity", None, ctypes.c_void_p)
cli_clear_history: Callable = _fn("cli_clear_history", ctypes.c_int8, ctypes.c_void_p)
cli_check_idle_timeout: Callable = _fn("cli_check_idle_timeout", ctypes.c_int8, ctypes.c_void_p)

# Authentication
cli_add_user: Callable = _fn("cli_add_user", ctypes.c_int8, ctypes.c_void_p,
                              ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint8)
cli_set_authorization_cb: Callable = _fn("cli_set_authorization_cb", None, ctypes.c_void_p, AUTH_FN)
cli_require_authorization: Callable = _fn("cli_require_authorization", None, ctypes.c_void_p, ctypes.c_bool)
cli_set_auth_failure_mode: Callable = _fn("cli_set_auth_failure_mode", None, ctypes.c_void_p, ctypes.c_int)
cli_set_auth_lockout_duration: Callable = _fn("cli_set_auth_lockout_duration", None, ctypes.c_void_p, ctypes.c_uint32)

# Command registration
cli_add_command: Callable = _fn("cli_add_command", ctypes.c_int,
                                ctypes.c_void_p, ctypes.c_int,
                                ctypes.c_char_p, CMD_FN,
                                ctypes.c_uint8, ctypes.c_int,
                                ctypes.c_char_p)
cli_add_builtin_cmds: Callable = _fn("cli_add_builtin_cmds", None, ctypes.c_void_p)
cli_add_command_duplicate: Callable = _fn("cli_add_command_duplicate", ctypes.c_int,
                                           ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p)
cli_cmd_add_alias: Callable = _fn("cli_cmd_add_alias", ctypes.c_int8,
                                   ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p)
cli_remove_command: Callable = _fn("cli_remove_command", ctypes.c_int8, ctypes.c_void_p, ctypes.c_int)
cli_remove_command_recursive: Callable = _fn("cli_remove_command_recursive", ctypes.c_int8, ctypes.c_void_p, ctypes.c_int)
cli_hide_command: Callable = _fn("cli_hide_command", None, ctypes.c_void_p, ctypes.c_int)

# Running
cli_start: Callable = _fn("cli_start", None, ctypes.c_void_p)
cli_session_engine: Callable = _fn("cli_session_engine", ctypes.c_int8, ctypes.c_void_p)

# Output (non-variadic wrappers to avoid ctypes variadic issues)
cli_print: Callable = _fn("cli_py_print", ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p)
cli_println: Callable = _fn("cli_py_println", ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p)
cli_error: Callable = _fn("cli_py_error", ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p)
cli_print_flush: Callable = _fn("cli_print_flush", None, ctypes.c_void_p)
cli_set_print_transport_cb: Callable = _fn("cli_set_print_transport_cb", None, ctypes.c_void_p, PRINT_TRANSPORT_FN)
cli_set_print_cb: Callable = _fn("cli_set_print_cb", None, ctypes.c_void_p, PRINT_FN)
cli_set_print_cb_v: Callable = _fn("cli_set_print_cb_v", None, ctypes.c_void_p, PRINT_V_FN)

# Mode / Privilege
cli_set_mode: Callable = _fn("cli_set_mode", None, ctypes.c_void_p, ctypes.c_int)
cli_set_privilege: Callable = _fn("cli_set_privilege", None, ctypes.c_void_p, ctypes.c_uint8)
cli_get_mode: Callable = _fn("cli_get_mode", ctypes.c_int, ctypes.c_void_p)
cli_get_privilege: Callable = _fn("cli_get_privilege", ctypes.c_uint8, ctypes.c_void_p)

# Helper
cli_sscanf: Callable = _fn("cli_sscanf", ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p)

# Execution & Stats
cli_exec: Callable = _fn("cli_exec", ctypes.c_int8, ctypes.c_void_p, ctypes.c_char_p)
cli_exec_argv: Callable = _fn("cli_exec_argv", ctypes.c_int8, ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int)
cli_set_micros_source: Callable = _fn("cli_set_micros_source", None, ctypes.c_void_p, MICROS_FN, ctypes.c_void_p)
cli_tick_stats_get: Callable = _fn("cli_tick_stats_get", None, ctypes.c_void_p, ctypes.POINTER(CliTickStats))
cli_tick_stats_reset: Callable = _fn("cli_tick_stats_reset", None, ctypes.c_void_p)

# ── Transport builder ────────────────────────────────────────────────────────


def make_transport(
    kind: int,
    available_fn: TRANSPORT_AVAILABLE_FN | None,
    read_fn: TRANSPORT_READ_FN | None,
    write_fn: TRANSPORT_WRITE_FN | None,
    flush_fn: TRANSPORT_FLUSH_FN | None,
    ctx: int = 0,
) -> CliTransport:
    t = CliTransport()
    t.kind = kind
    t.available = available_fn
    t.read = read_fn
    t.write = write_fn
    t.flush = flush_fn
    t.ctx = ctypes.c_void_p(ctx)
    return t
