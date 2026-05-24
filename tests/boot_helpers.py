import os
import shlex
import socket
import subprocess
import time
from pathlib import Path

from labgrid.util.ssh import sshmanager
from pexpect import TIMEOUT

from .reporting import get_reporter

UBOOT_PROMPT = "=> "


def artifact_path(env_name):
    path = Path(os.environ[env_name]).expanduser().resolve()
    assert path.is_file(), f"missing artifact for {env_name}: {path}"
    return path


def wait_for_uboot_prompt(console, timeout=30, prompt=UBOOT_PROMPT):
    deadline = time.monotonic() + timeout
    captured = bytearray()

    while time.monotonic() < deadline:
        index, before, _, _ = console.expect([prompt, "U-Boot", TIMEOUT], timeout=2)
        captured.extend(before)

        if index == 0:
            return captured.decode("utf-8", "replace")

        console.sendline("")

    raise AssertionError(
        f"U-Boot prompt {prompt!r} not found. Captured console output:\n"
        + captured.decode("utf-8", "replace")
    )


def run_uboot_command(console, command, timeout=30, prompt=UBOOT_PROMPT):
    console.sendline(command)
    _, before, _, _ = console.expect(prompt, timeout=timeout)
    return before.decode("utf-8", "replace")


def boot_into_uboot(target):
    reporter = get_reporter()
    try:
        spl = artifact_path("UBOOT_SPL")
        uboot = artifact_path("UBOOT")

        target.get_driver("PowerProtocol").cycle()

        openocd = target.get_driver("OpenOCDDriver", activate=False)
        interface = openocd.interface

        ssh = sshmanager.open(interface.host)
        ssh.put_file(str(spl), "u-boot-spl")
        ssh.put_file(str(uboot), "u-boot")

        target.activate(openocd)
        openocd.execute(openocd.load_commands)

        console = target.get_driver("ConsoleProtocol")
        wait_for_uboot_prompt(console)
    except Exception as exc:
        reporter.fail_stage("u_boot_booted", str(exc))
        raise

    reporter.pass_stage("u_boot_booted", f"Reached U-Boot prompt on {interface.host}")
    return console, interface.host


def remote_shell(host, command):
    result = subprocess.run(
        ["ssh", host, "sh", "-lc", command],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def start_remote_http_server(host, files, port):
    remote_dir = remote_shell(host, "mktemp -d")

    ssh = sshmanager.open(host)
    for local_path, remote_name in files.items():
        ssh.put_file(str(local_path), f"{remote_dir}/{remote_name}")

    command = (
        f"cd {shlex.quote(remote_dir)} && "
        f"nohup python3 -m http.server {port} >/tmp/labgrid-http-server.log 2>&1 "
        f"</dev/null & echo $!"
    )
    pid = remote_shell(host, command)

    return remote_dir, pid


def stop_remote_http_server(host, remote_dir, pid):
    if pid:
        subprocess.run(
            ["ssh", host, "sh", "-lc", f"kill {shlex.quote(pid)} >/dev/null 2>&1 || true"],
            check=False,
            capture_output=True,
            text=True,
        )

    if remote_dir:
        subprocess.run(
            ["ssh", host, "sh", "-lc", f"rm -rf {shlex.quote(remote_dir)}"],
            check=False,
            capture_output=True,
            text=True,
        )


def resolve_image_server_ip(host):
    return socket.gethostbyname(host)


def wait_for_console_text(console, patterns, timeout):
    deadline = time.monotonic() + timeout
    captured = bytearray()

    while time.monotonic() < deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        index, before, _, _ = console.expect(patterns + [TIMEOUT], timeout=min(10, remaining))
        captured.extend(before)

        if index < len(patterns):
            return patterns[index], captured.decode("utf-8", "replace")

    raise AssertionError(
        "Expected console text not found. Captured console output:\n"
        + captured.decode("utf-8", "replace")
    )
