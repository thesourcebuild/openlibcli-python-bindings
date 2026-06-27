"""
Serial (stdin/stdout) transport.

Reads from ``sys.stdin.buffer`` and writes to ``sys.stdout.buffer`` using
direct OS-level ``os.write()`` to bypass Python's I/O buffering.
Optionally sets raw terminal mode on POSIX (cbreak, no echo).

For interactive use, call ``raw_mode_enable()`` before ``session.start()``
and ``raw_mode_disable()`` after the session finishes.
"""

from __future__ import annotations

import os
import select
import sys
import platform
import time


from openlibcli.transports import BaseTransport, TRANSPORT_SERIAL
from openlibcli import _binding as _b

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    pass


class SerialTransport(BaseTransport):
    TRANSPORT_KIND = TRANSPORT_SERIAL

    # Extended-key scan code → CLI control character mapping (Windows)
    _EXT_KEY_MAP: dict[int, int] = {
        0x48: 0x10,  # Up    → Ctrl+P (history prev)
        0x50: 0x0E,  # Down  → Ctrl+N (history next)
        0x4B: 0x02,  # Left  → Ctrl+B (back char)
        0x4D: 0x06,  # Right → Ctrl+F (forward char)
        0x47: 0x01,  # Home  → Ctrl+A (beginning of line)
        0x4F: 0x05,  # End   → Ctrl+E (end of line)
        0x53: 0x04,  # Del   → Ctrl+D (delete char)
        0x49: 0x0C,  # PgUp  → Ctrl+L (clear screen)
        0x51: -1,    # PgDn  → ignore
        0x52: -1,    # Ins   → ignore
    }

    def __init__(self, timeout: float = 1.0) -> None:
        super().__init__()
        self._rfd = sys.stdin.fileno() if hasattr(sys.stdin, 'fileno') else 0
        self._wfd = sys.stdout.fileno() if hasattr(sys.stdout, 'fileno') else 1
        self.timeout = timeout
        if IS_WINDOWS:
            self._win_buffer = bytearray()

    def _available(self) -> int:
        if IS_WINDOWS:
            import msvcrt
            if self._win_buffer:
                return 1
            if msvcrt.kbhit():
                return 1
            start_time = time.time()
            while True:
                if msvcrt.kbhit():
                    return 1
                if self.timeout <= 0 or (time.time() - start_time) >= self.timeout:
                    break
                time.sleep(0.01)
            return 0
        else:
            try:
                r, _, _ = select.select([sys.stdin], [], [], self.timeout)
                return 1 if r else 0
            except OSError:
                return -1

    def _read_into(self, buf: bytearray) -> int:
        try:
            if IS_WINDOWS:
                import msvcrt
                if not self._win_buffer:
                    while msvcrt.kbhit():
                        ch = msvcrt.getch()
                        if ch in (b'\x00', b'\xe0'):
                            ext = msvcrt.getch()
                            val = ord(ext)
                            if val == 0x48:    # Up -> Esc [ A
                                self._win_buffer.extend(b'\x1b[A')
                            elif val == 0x50:  # Down -> Esc [ B
                                self._win_buffer.extend(b'\x1b[B')
                            elif val == 0x4D:  # Right -> Esc [ C
                                self._win_buffer.extend(b'\x1b[C')
                            elif val == 0x4B:  # Left -> Esc [ D
                                self._win_buffer.extend(b'\x1b[D')
                            elif val == 0x47:  # Home -> Ctrl+A (\x01)
                                self._win_buffer.extend(b'\x01')
                            elif val == 0x4F:  # End -> Ctrl+E (\x05)
                                self._win_buffer.extend(b'\x05')
                            elif val == 0x53:  # Del -> Ctrl+D (\x04)
                                self._win_buffer.extend(b'\x04')
                            else:
                                self._win_buffer.append(val)
                        else:
                            self._win_buffer.extend(ch)
                        if len(self._win_buffer) >= 1024:
                            break

                n = min(len(buf), len(self._win_buffer))
                if n > 0:
                    buf[:n] = self._win_buffer[:n]
                    del self._win_buffer[:n]
                else:
                    n = 0
            else:
                r, _, _ = select.select([sys.stdin], [], [], 0)
                n = 0
                if r:
                    data = os.read(self._rfd, len(buf))
                    if data:
                        buf[:len(data)] = data
                        n = len(data)
            
            # Check for ETX (0x03 - Ctrl+C) in raw terminal mode
            for i in range(n):
                if buf[i] == 0x03:
                    raise KeyboardInterrupt("Ctrl+C pressed")
            return n
        except (OSError, EOFError):
            return -1

    def _write(self, data: bytes) -> int:
        try:
            if IS_WINDOWS:
                written = _wt.DWORD(0)
                ok = _WriteFile(_stdout_handle, data, len(data), _wt.LPDWORD(written), None)
                if not ok:
                    return -1
                return written.value
            else:
                os.write(self._wfd, data)
                return len(data)
        except OSError:
            return -1

    def _flush(self) -> int:
        return 0

    @staticmethod
    def raw_mode_enable() -> None:
        """Set terminal to raw mode (cbreak, no echo)."""
        if IS_WINDOWS:
            _enable_win_raw()
        elif HAS_TERMIOS:
            _enable_posix_raw()

    @staticmethod
    def raw_mode_disable() -> None:
        """Restore terminal to normal mode."""
        if IS_WINDOWS:
            _disable_win_raw()
        elif HAS_TERMIOS:
            _disable_posix_raw()


# ── POSIX raw mode helpers ───────────────────────────────────────────────────

HAS_TERMIOS = False
if not IS_WINDOWS:
    try:
        import termios
        import atexit
        HAS_TERMIOS = hasattr(termios, 'tcgetattr')
    except ImportError:
        pass

if HAS_TERMIOS:
    _saved_termios: list = []

    def _enable_posix_raw() -> None:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        _saved_termios.append(old)
        new = termios.tcgetattr(fd)
        new[termios.IFLAG] &= ~(termios.BRKINT | termios.ICRNL | termios.INPCK | termios.ISTRIP | termios.IXON)
        new[termios.OFLAG] &= ~termios.OPOST
        new[termios.CFLAG] &= ~(termios.CSIZE | termios.PARENB)
        new[termios.CFLAG] |= termios.CS8
        new[termios.LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.IEXTEN | termios.ISIG)
        new[termios.CC][termios.VMIN] = 0
        new[termios.CC][termios.VTIME] = 1
        termios.tcsetattr(fd, termios.TCSAFLUSH, new)
        atexit.register(_disable_posix_raw)

    def _disable_posix_raw() -> None:
        if _saved_termios:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, _saved_termios.pop())

if IS_WINDOWS:
    import ctypes as _ct
    from ctypes import wintypes as _wt

    _kernel32 = _ct.windll.kernel32
    _stdin_handle = _kernel32.GetStdHandle(-10)
    _stdout_handle = _kernel32.GetStdHandle(-11)
    _saved_console_mode = _wt.DWORD(0)
    _saved_stdout_mode = _wt.DWORD(0)

    _GetNumberOfConsoleInputEvents = _kernel32.GetNumberOfConsoleInputEvents
    _GetNumberOfConsoleInputEvents.argtypes = [
        _wt.HANDLE,
        _wt.LPDWORD,
    ]
    _GetNumberOfConsoleInputEvents.restype = _wt.BOOL

    _ReadFile = _kernel32.ReadFile
    _ReadFile.argtypes = [
        _wt.HANDLE,
        _ct.c_void_p,
        _wt.DWORD,
        _wt.LPDWORD,
        _ct.c_void_p,
    ]
    _ReadFile.restype = _wt.BOOL

    _WriteFile = _kernel32.WriteFile
    _WriteFile.argtypes = [
        _wt.HANDLE,
        _ct.c_void_p,
        _wt.DWORD,
        _wt.LPDWORD,
        _ct.c_void_p,
    ]
    _WriteFile.restype = _wt.BOOL


    def _enable_win_raw() -> None:
        _kernel32.GetConsoleMode(_stdin_handle, _ct.byref(_saved_console_mode))
        # Disable line input, echo, and processed input
        new_mode = _saved_console_mode.value & ~0x0004  # ENABLE_LINE_INPUT
        new_mode = new_mode & ~0x0001  # ENABLE_ECHO_INPUT
        new_mode = new_mode & ~0x0002  # ENABLE_PROCESSED_INPUT
        new_mode = new_mode | 0x0200  # ENABLE_VIRTUAL_TERMINAL_INPUT
        _kernel32.SetConsoleMode(_stdin_handle, new_mode)

        # Enable virtual terminal processing on stdout
        _kernel32.GetConsoleMode(_stdout_handle, _ct.byref(_saved_stdout_mode))
        _kernel32.SetConsoleMode(_stdout_handle, _saved_stdout_mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING

    def _disable_win_raw() -> None:
        if _saved_console_mode.value:
            _kernel32.SetConsoleMode(_stdin_handle, _saved_console_mode.value)
        if _saved_stdout_mode.value:
            _kernel32.SetConsoleMode(_stdout_handle, _saved_stdout_mode.value)
