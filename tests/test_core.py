from eiscp.core import iscp_to_command, command_to_iscp


class TestIscpToCommand:
    def test(self):
        assert iscp_to_command('MVL') == ('master-volume', '')


class TestCommandToIscp:
    def test(self):
        assert command_to_iscp('main.system-power=standby') == 'PWR00'

    def test_argument_aliases(self):
        assert command_to_iscp('main.system-power=off') == 'PWR00'