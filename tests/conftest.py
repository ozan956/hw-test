import os
import pytest

from labgrid import Environment

from .reporting import get_reporter


@pytest.fixture
def labgrid_target(pytestconfig):
    reporter = get_reporter()
    config_file = pytestconfig.getoption("lg_env") or os.environ.get("LG_ENV")
    assert config_file, "missing Labgrid environment config"

    target_names = os.environ.get("LG_TARGETS", "").split()
    assert target_names, "missing LG_TARGETS"

    try:
        env = Environment(config_file)
    except Exception as exc:
        reporter.fail_stage("labgrid_accessible", str(exc))
        raise
    reporter.pass_stage("labgrid_accessible", f"Loaded environment from {config_file}")

    coordinator = pytestconfig.getoption("lg_coordinator")
    if coordinator:
        env.config.set_option("coordinator_address", coordinator)

    selected = None
    acquired_by_test = False

    try:
        for target_name in target_names:
            try:
                target = env.get_target(target_name)
                assert target is not None

                target.acquire()
                selected = target
                acquired_by_test = True
                reporter.pass_stage("target_acquired", f"Acquired target {target_name}")
                break

            except Exception as exc:
                reporter.note(f"Could not acquire {target_name}: {exc}")

        if selected is None:
            reporter.fail_stage(
                "target_acquired",
                f"Could not acquire any target from: {target_names}",
            )
        assert selected is not None, f"Could not acquire any target from: {target_names}"

        yield selected

    finally:
        if selected is not None and acquired_by_test:
            try:
                selected.release()
            except Exception:
                pass

        env.cleanup()
