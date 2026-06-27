# OpenLibCLI — Python Bindings

Thin [ctypes](https://docs.python.org/3/library/ctypes.html) wrapper around the
[OpenLibCLI](https://github.com/thesourcebuild/OpenLibCLI) C library.

**OpenLibCLI** — A command-line interface library written in pure C99 with 100 % static memory allocation. Runs on Windows, Linux/macOS, and MCUs (AVR, ARM, RISC-V) with any byte-stream transport (Telnet, TCP, serial, pipes, UNIX sockets, or custom).

## Prerequisites

- Python 3.10+
- A C compiler (MSVC / MinGW-w64 for Windows, GCC/Clang for Linux/macOS)

## Build the C Extension

Since the C library source code is embedded directly in this repository under `src/openlibcli/openlibcli_c/`, you can compile the shared library in-place using `setuptools`:

```bash
python setup.py build_ext --inplace
```


## Usage

Below is a basic example of how to implement a TCP socket transport and host a CLI session over telnet:

```python
import socket
import openlibcli as cli
from openlibcli.transports import BaseTransport

# Define a custom transport to communicate over a TCP socket
class SocketTransport(BaseTransport):
    def __init__(self, client_socket: socket.socket) -> None:
        super().__init__()
        self.sock = client_socket
        self.sock.setblocking(False)

    def _read_into(self, buf: bytearray) -> int:
        try:
            data = self.sock.recv(len(buf))
            if not data:
                return 0  # Connection closed (EOF)
            buf[:len(data)] = data
            return len(data)
        except BlockingIOError:
            return 0  # No data available right now

    def _write(self, data: bytes) -> int:
        return self.sock.send(data)

# Start a basic TCP server on port 2323
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 2323))
server.listen(1)

print("Telnet/TCP CLI Server listening on port 2323...")
print("Connect with: telnet localhost 2323")
client, addr = server.accept()
print(f"Connection from {addr}")

# Initialize the transport and session
transport = SocketTransport(client)
session = cli.Session("router", transport, cmd_pool_size=256)
session.cli_add_builtin_commands()

# Register a custom command
@session.cli_command("show", "version", help="Show version")
def cmd_version(s, cmd, argc, argv):
    s.cli_println("OpenLibCLI Library version: 0.1.0")

session.cli_set_enable_secret("cisco")
session.cli_set_banner("Welcome to OpenLibCLI (Python)\r\n")

# Start the session loop
session.cli_start()
try:
    session.cli_loop()
finally:
    session.cli_free()
    client.close()
    server.close()
```

For the complete, robust telnet server implementation featuring full Telnet protocol negotiation (echo control, character suppression, window sizes, etc.), check out the [examples/](examples) directory:
- **Telnet Server Transport (Full Negotiation):** [examples/win_linux/telnet](examples/win_linux/telnet)
- **Serial Transport (stdin/stdout with raw mode):** [examples/win_linux/serial](examples/win_linux/serial)
- **POSIX Pipe/UNIX Socket Transports:** [examples/win_linux/pipe](examples/win_linux/pipe)



## Project Layout

```
openlibcli-python-bindings/
├── Docs/                      Documentation files
├── examples/                  Example scripts demonstrating usage
│   ├── linux/                 Linux-specific examples
│   ├── shared/                Shared resources/utilities
│   └── win_linux/             Cross-platform examples (serial, telnet, pipe)
├── scripts/                   Build helper scripts
│   ├── build_shared.bat       Build shared library (Windows)
│   ├── build_shared.sh        Build shared library (POSIX)
│   └── cli_py_helper.c        Helper C functions for the binding
├── src/openlibcli/            Python library package
│   ├── __init__.py            Public API exports
│   ├── _binding.py            Low-level ctypes glue
│   ├── session.py             Session wrapper
│   ├── version.py             Dynamic version wrapper
│   ├── openlibcli_c/          Embedded C engine source code
│   └── transports/            Transport implementations
│       └── __init__.py        Transport base class and logic
├── pyproject.toml             Build system configuration
├── setup.py                   Package build & extension setup script
└── README.md                  Project documentation
```

## Contributions

Contributions of all sizes are warmly welcome!. Please feel free to:

- Report issues using [the issue guide](Docs/create_a_issue.md)
- Submit pull requests
- Improve documentation
- Suggest new features
- Start a discussion

Let's make the library better for everyone.

---

## License

MIT License — see ['LICENSE'](LICENSE) file and source file headers.

---

## Author

Muhammad Hassaan Shah

- GitHub: [@thesourcebuild](https://github.com/thesourcebuild)
- Project: [github.com/thesourcebuild/openlibcli-python-bindings](https://github.com/thesourcebuild/openlibcli-python-bindings)