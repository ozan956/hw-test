import os
import time
from pathlib import Path

from labgrid.util.ssh import sshmanager
from pexpect import TIMEOUT


def u_boot(labgrid_target):
    target = labgrid_target

    prompt = "=> "

    spl = Path(os.environ["UBOOT_SPL"]).expanduser().resolve()
    uboot = Path(os.environ["UBOOT"]).expanduser().resolve()

    assert spl.is_file(), f"missing SPL file: {spl}"
    assert uboot.is_file(), f"missing U-Boot file: {uboot}"

    target.get_driver("PowerProtocol").cycle()

    openocd = target.get_driver("OpenOCDDriver", activate=False)
    interface = openocd.interface

    ssh = sshmanager.open(interface.host)
    ssh.put_file(str(spl), "u-boot-spl")
    ssh.put_file(str(uboot), "u-boot")

    target.activate(openocd)
    openocd.execute(openocd.load_commands)

    console = target.get_driver("ConsoleProtocol")
    deadline = time.monotonic() + 30
    captured = bytearray()

    while time.monotonic() < deadline:
        index, before, _, _ = console.expect([prompt, "U-Boot", TIMEOUT], timeout=2)
        captured.extend(before)

        if index == 0:
            break

        console.sendline("")
    else:
        assert False, (
            f"U-Boot prompt {prompt!r} not found. Captured console output:\n"
            + captured.decode("utf-8", "replace")
        )

    console.sendline("printenv")
    _, before, _, _ = console.expect(prompt, timeout=30)
    output = before.decode("utf-8", "replace")

    assert output.strip(), "printenv returned no output"
    print(output)