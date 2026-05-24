import os
from pathlib import Path


STAGES = [
    ("labgrid_accessible", "Labgrid is accessible"),
    ("target_acquired", "At least one target is acquired"),
    ("u_boot_booted", "U-Boot successfully booted"),
    ("linux_booted", "Linux successfully booted"),
    ("spi_flash_programmed", "SPI flash successfully programmed"),
]


class BootstrapReporter:
    def __init__(self):
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))
        self.summary_path = workspace / "bootstrap-flow-summary.md"
        self.step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        self.results = {
            stage_id: {"label": label, "status": "pending", "detail": ""}
            for stage_id, label in STAGES
        }
        self._write_summary()

    def pass_stage(self, stage_id, detail=""):
        self._set_stage(stage_id, "passed", detail)

    def fail_stage(self, stage_id, detail=""):
        self._set_stage(stage_id, "failed", detail)

    def note(self, message):
        print(f"[bootstrap] {message}", flush=True)

    def _set_stage(self, stage_id, status, detail):
        stage = self.results[stage_id]
        stage["status"] = status
        stage["detail"] = detail

        icon = "PASS" if status == "passed" else "FAIL"
        print(f"[bootstrap][{icon}] {stage['label']}: {detail}", flush=True)

        if os.environ.get("GITHUB_ACTIONS") == "true":
            command = "notice" if status == "passed" else "error"
            print(
                f"::{command} title=Bootstrap Flow::{stage['label']}: {detail}",
                flush=True,
            )

        self._write_summary()

    def _write_summary(self):
        def cell(value):
            return str(value).replace("\n", " ").replace("|", "\\|")

        lines = [
            "# Bootstrap Flow Summary",
            "",
            "| Stage | Status | Detail |",
            "| --- | --- | --- |",
        ]

        for stage_id, _ in STAGES:
            entry = self.results[stage_id]
            lines.append(
                f"| {cell(entry['label'])} | {cell(entry['status'])} | {cell(entry['detail'] or '-')} |"
            )

        content = "\n".join(lines) + "\n"
        self.summary_path.write_text(content, encoding="utf-8")

        if self.step_summary_path:
            Path(self.step_summary_path).write_text(content, encoding="utf-8")


_REPORTER = BootstrapReporter()


def get_reporter():
    return _REPORTER
