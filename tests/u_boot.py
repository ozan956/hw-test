from .boot_helpers import boot_into_uboot, run_uboot_command


def u_boot(labgrid_target):
    console, _ = boot_into_uboot(labgrid_target)
    output = run_uboot_command(console, "printenv")

    assert output.strip(), "printenv returned no output"
    print(output)
