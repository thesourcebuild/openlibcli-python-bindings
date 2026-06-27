"""
Shared session setup and command registration for openlibcli-python-bindings examples.
"""

from __future__ import annotations

import ctypes
import openlibcli as cli


class DemoAppData:
    """Per-session application data stored on the CLI session object."""
    def __init__(self, session_id: int, rx_packets: int, tx_packets: int) -> None:
        self.session_id = session_id
        self.rx_packets = rx_packets
        self.tx_packets = tx_packets


def demo_periodic_cb(session: cli.Session) -> int:
    app = session.cli_get_userdata()
    if app:
        app.rx_packets += 7
        app.tx_packets += 3
    return cli.CLI_OK


def demo_setup_session(
    session: cli.Session,
    app: DemoAppData,
    session_id: int,
    rx_packets: int,
    tx_packets: int,
    banner: str,
) -> None:
    app.session_id = session_id
    app.rx_packets = rx_packets
    app.tx_packets = tx_packets
    session.cli_set_userdata(app)

    session.cli_set_banner(banner)
    session.cli_set_idle_timeout(60)  # 1 minutes idle timeout
    session.cli_set_enable_secret("cisco")
    session.cli_set_mode_name(cli.MODE_CONFIG, "config")

    session.cli_add_user("admin", "admin", cli.PRIV_PRIVILEGED)
    session.cli_add_user("guest", "guest", cli.PRIV_USER)
    session.cli_require_authorization(True)

    session.cli_set_periodic_cb(demo_periodic_cb)
    session.cli_set_periodic_interval(5)


def demo_register_commands(session: cli.Session) -> int:
    session.cli_add_builtin_commands()

    # hostname
    def cmd_hostname(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        status = cli.CLI_OK
        if argc < 2:
            s.cli_println("Usage: hostname <name>")
            status = cli.CLI_ERR
        else:
            s.cli_set_hostname(argv[1])
            s.cli_println(f"Hostname set to: {argv[1]}")
        return status

    session.cli_add_command(
        parent=cli.CLI_CMD_ROOT,
        name="hostname",
        callback=cmd_hostname,
        privilege=cli.PRIV_PRIVILEGED,
        mode=cli.MODE_CONFIG,
        help="Set system hostname",
    )

    # show
    show_h = session.cli_add_command(
        parent=cli.CLI_CMD_ROOT,
        name="show",
        callback=lambda s, cmd, argc, argv: cli.CLI_OK,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Show system information",
    )

    # show version
    def cmd_show_version(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        s.cli_println(f"OpenLibCLI Library version: {cli.__version__}")
        s.cli_println("Platforms   : Linux / macOS / Windows / Embedded")
        s.cli_println("Transports  : Telnet, TCP, Serial (UART, stdin/stdout), pipe")
        s.cli_println("Python port : yes")
        return cli.CLI_OK

    session.cli_add_command(
        parent=show_h,
        name="version",
        callback=cmd_show_version,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Show software version",
    )

    # show counters
    def cmd_show_counters(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        app = s.cli_get_userdata()
        if app:
            s.cli_println(f"RX packets : {app.rx_packets}")
            s.cli_println(f"TX packets : {app.tx_packets}")
        return cli.CLI_OK

    session.cli_add_command(
        parent=show_h,
        name="counters",
        callback=cmd_show_counters,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Show packet counters",
    )

    # show interfaces
    def cmd_show_interfaces(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        s.cli_println("Interface GigE0/0  status up")
        s.cli_println("Interface GigE0/1  status down")
        s.cli_println("Interface GigE0/2  status up")
        return cli.CLI_OK

    session.cli_add_command(
        parent=show_h,
        name="interfaces",
        callback=cmd_show_interfaces,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Show interface status",
    )

    # network
    network_h = session.cli_add_command(
        parent=cli.CLI_CMD_ROOT,
        name="network",
        callback=lambda s, cmd, argc, argv: cli.CLI_OK,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Network commands",
    )

    # network ping
    def cmd_ping(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        status = cli.CLI_OK
        if argc < 2:
            s.cli_println("Usage: ping <host>")
            status = cli.CLI_ERR
        else:
            s.cli_println(f"Sending 5, 100-byte pings to {argv[1]}:")
            for _ in range(5):
                s.cli_println(f"Reply from {argv[1]}: bytes=100 time<1ms TTL=64")
            s.cli_println("Ping statistics: 5 sent, 5 received, 0% loss")
        return status

    session.cli_add_command(
        parent=network_h,
        name="ping",
        callback=cmd_ping,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Send ICMP echo requests",
    )

    # network traceroute
    def cmd_traceroute(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        status = cli.CLI_OK
        if argc < 2:
            s.cli_println("Usage: traceroute <host>")
            status = cli.CLI_ERR
        else:
            s.cli_println(f"Tracing route to {argv[1]}:")
            s.cli_println("  1  192.168.1.254   <1 ms")
            s.cli_println("  2  10.0.0.1        1 ms")
            s.cli_println(f"  3  {argv[1]}  2 ms")
        return status

    session.cli_add_command(
        parent=network_h,
        name="traceroute",
        callback=cmd_traceroute,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Trace route to host",
    )

    # reboot
    def cmd_reboot(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        s.cli_println("System reload scheduled.")
        s.cli_println("(Demo mode: no actual reload performed)")
        return cli.CLI_OK

    session.cli_add_command(
        parent=cli.CLI_CMD_ROOT,
        name="reboot",
        callback=cmd_reboot,
        privilege=cli.PRIV_PRIVILEGED,
        mode=cli.MODE_ENABLE,
        help="Reload / reboot the system",
    )

    # calc
    APP_MODE_CALCULATOR = cli.MODE_USER_BASE
    APP_MODE_ARITHMETIC = cli.MODE_USER_BASE + 1

    def cmd_calculator(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        s.cli_set_mode_name(APP_MODE_CALCULATOR, "")
        s.cli_set_mode_name(APP_MODE_ARITHMETIC, "")
        s.cli_set_mode(APP_MODE_CALCULATOR)
        return cli.CLI_OK

    calc_h = session.cli_add_command(
        parent=cli.CLI_CMD_ROOT,
        name="calc",
        callback=cmd_calculator,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_EXEC,
        help="Enter calc menu",
    )

    # calc arith
    def cmd_arithmetic(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        s.cli_set_mode(APP_MODE_ARITHMETIC)
        return cli.CLI_OK

    arith_h = session.cli_add_command(
        parent=calc_h,
        name="arith",
        callback=cmd_arithmetic,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Enter arithmetic submenu",
    )

    # calc arith add
    def cmd_add(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        status = cli.CLI_OK
        if argc < 3 or argc > 4:
            s.cli_println("Usage: add <a> <b>  or  add <a> + <b>")
            status = cli.CLI_ERR
        elif argc == 4 and argv[2] != "+":
            s.cli_println("Usage: add <a> + <b>")
            status = cli.CLI_ERR
        else:
            a = ctypes.c_int32(0)
            b = ctypes.c_int32(0)
            s.cli_sscanf(argv[1], "%u", a)
            s.cli_sscanf(argv[argc - 1], "%u", b)
            s.cli_println(f"{a.value + b.value}")
        return status

    session.cli_add_command(
        parent=arith_h,
        name="add",
        callback=cmd_add,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Add two numbers (add <a> <b>)",
    )

    # calc arith sub
    def cmd_sub(s: cli.Session, cmd: str, argc: int, argv: list[str]) -> int:
        status = cli.CLI_OK
        if argc < 3 or argc > 4:
            s.cli_println("Usage: sub <a> <b>  or  sub <a> - <b>")
            status = cli.CLI_ERR
        elif argc == 4 and argv[2] != "-":
            s.cli_println("Usage: sub <a> - <b>")
            status = cli.CLI_ERR
        else:
            a = ctypes.c_int32(0)
            b = ctypes.c_int32(0)
            s.cli_sscanf(argv[1], "%u", a)
            s.cli_sscanf(argv[argc - 1], "%u", b)
            s.cli_println(f"{a.value - b.value}")
        return status

    session.cli_add_command(
        parent=arith_h,
        name="sub",
        callback=cmd_sub,
        privilege=cli.PRIV_USER,
        mode=cli.MODE_ANY,
        help="Subtract two numbers (sub <a> <b>)",
    )

    return show_h
