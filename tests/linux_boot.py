import pytest

from .boot_helpers import (
    artifact_path,
    boot_into_uboot,
    resolve_image_server_ip,
    run_uboot_command,
    start_remote_http_server,
    stop_remote_http_server,
    wait_for_console_text,
)
from .reporting import get_reporter


@pytest.mark.linux
def linux_boot(labgrid_target):
    reporter = get_reporter()
    kernel = artifact_path("KERNEL_IMAGE")
    devicetree = artifact_path("DEVICETREE")

    server_port = 8000
    boot_command = "booti ${kernel_addr_r} - ${fdt_addr_r}"
    boot_banner_patterns = [
        "======== Installer Environment ========",
        "Please press Enter to activate this console",
        "login:",
    ]
    continue_prompt = "Continue? [y/N]:"
    flash_success_patterns = [
        "SPI install complete",
        "",
        "Set the switch S1 to position 1 (SPI boot).",
        "Waiting for switch...",
    ]

    console, host = boot_into_uboot(labgrid_target)
    server_ip = resolve_image_server_ip(host)

    remote_dir = ""
    server_pid = ""

    try:
        remote_dir, server_pid = start_remote_http_server(
            host,
            {
                kernel: kernel.name,
                devicetree: devicetree.name,
            },
            server_port,
        )

        run_uboot_command(console, "setenv autoload no")
        dhcp_output = run_uboot_command(console, "dhcp", timeout=60)
        assert "DHCP" in dhcp_output or "bound to address" in dhcp_output, dhcp_output

        if server_port != 80:
            run_uboot_command(console, f"setenv httpdstp {server_port}")

        kernel_output = run_uboot_command(
            console,
            f"wget ${{kernel_addr_r}} {server_ip}:/{kernel.name}",
            timeout=120,
        )
        assert "Transfer Successful" in kernel_output or "Bytes transferred =" in kernel_output, (
            kernel_output
        )

        dtb_output = run_uboot_command(
            console,
            f"wget ${{fdt_addr_r}} {server_ip}:/{devicetree.name}",
            timeout=120,
        )
        assert "Transfer Successful" in dtb_output or "Bytes transferred =" in dtb_output, (
            dtb_output
        )

        try:
            reporter.note("Booting the bootstrap Linux image")
            console.sendline(boot_command)

            matched, output = wait_for_console_text(console, boot_banner_patterns, timeout=180)
            reporter.note(f"Observed Linux boot marker: {matched}")

            matched, output = wait_for_console_text(console, [continue_prompt], timeout=180)
            reporter.pass_stage("linux_booted", f"Bootstrap image reached prompt: {matched}")
        except Exception as exc:
            reporter.fail_stage("linux_booted", str(exc))
            raise

        try:
            reporter.note("Confirming SPI flash programming from bootstrap image")
            console.sendline("y")

            matched, output = wait_for_console_text(console, flash_success_patterns, timeout=300)
            reporter.pass_stage(
                "spi_flash_programmed",
                f"Bootstrap image reported: {matched}",
            )
            print(output, flush=True)
        except Exception as exc:
            reporter.fail_stage("spi_flash_programmed", str(exc))
            raise

    finally:
        stop_remote_http_server(host, remote_dir, server_pid)
