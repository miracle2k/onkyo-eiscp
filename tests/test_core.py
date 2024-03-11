from eiscp.core import iscp_to_command, command_to_iscp
from unittest import TestCase

class TestIscpToCommand(TestCase):
    def test(self):
        self.assertEqual(('master-volume', ''), iscp_to_command('MVL'))

    def test_with_zone(self):
        self.assertEqual(('main', 'audio-muting', ''), iscp_to_command('AMT', True))
        self.assertEqual(('zone2', 'muting', ''), iscp_to_command('ZMT', True))
        self.assertEqual(('zone3', 'muting', ''), iscp_to_command('MT3', True))
        self.assertEqual(('zone4', 'muting', ''), iscp_to_command('MT4', True))

class TestCommandToIscp(TestCase):
    def test(self):
        self.assertEqual('PWR00', command_to_iscp('main.system-power=standby'))

    def test_argument_aliases(self):
        self.assertEqual('PWR00', command_to_iscp('main.system-power=off'))