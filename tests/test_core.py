from eiscp.core import iscp_to_command, command_to_iscp


class TestIscpToCommand:
    def test(self):
        assert iscp_to_command('MVL') == (('master-volume', 'volume'), '')


class TestCommandToIscp:
    def test(self):
        assert command_to_iscp('main.system-power=standby') == 'PWR00'