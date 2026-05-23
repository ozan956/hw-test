from unittest.mock import Mock


def test_mock_labgrid_target_flow():
    target = Mock()
    power = target.get_driver.return_value

    target.get_driver("PowerProtocol").cycle()

    target.get_driver.assert_called_with("PowerProtocol")
    power.cycle.assert_called_once()