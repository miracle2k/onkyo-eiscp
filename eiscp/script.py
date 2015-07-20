'''Control Onkyo A/V receivers.

Usage:
  %(program_name)s [--host <host>] [--port <port>] [--all] [--name <name>]
                   <command>...
  %(program_name)s --discover
  %(program_name)s --help-commands [<zone> <command>]
  %(program_name)s -h | --help

Selecting the receiver:

  --host, -t <host>     Connect to this host
  --port, -p <port>     Connect to this port [default: 60128]
  --all, -a             Discover receivers, send to all found
  --name, -n <name>     Discover receivers, send to those matching name.

If none of these options is given, the program searches for receivers,
and uses the first one found.

  --discover            List all discoverable receivers
  --help-commands       List available commands.

Examples:
  onkyo power:on source:pc volume:75
    Turn receiver on, select "PC" source, set volume to 75.
  onkyo zone2.power:standby
    To execute a command for zone that isn't the main one.
'''

import sys
import os
import docopt

from .core import eISCP, command_to_iscp, iscp_to_command
from . import commands

# Automatically replace %(program_name)s with the current program name in the
# documentation.
__doc__ %= dict(program_name=sys.argv[0])


def main(argv=sys.argv):
    basename = os.path.basename(argv[0])
    options = docopt.docopt(__doc__, help=True)

    # List commands
    if options['--discover']:
        for receiver in eISCP.discover(timeout=1):
            print('%s %s:%s' % (
                receiver.info['model_name'], receiver.host, receiver.port))
        return

    # List available commands
    if options['--help-commands']:
        # List the zones
        if not options['<zone>']:
            print('Available zones:')
            for zone in commands.COMMANDS:
                print('  %s' % zone)
            print('Use %s --help-commands <zone> to see a list of '\
                  'commands for that zone.' % basename)
            return
        # List the commands
        selected_zone = options['<zone>']
        if not selected_zone in commands.COMMANDS:
            print('No such zone: %s' % selected_zone)
            return 1
        if not options['<command>']:
            print('Available commands for this zone:')
            for _, command in list(commands.COMMANDS[selected_zone].items()):
                print('  %s - %s' % (command['name'], command['description']))
            print('Use %s --help-commands %s <command> to see a list '\
                  'of possible values.' % (basename, selected_zone))
            return
        # List values
        selected_command = options['<command>'][0]
        selected_command = commands.COMMAND_MAPPINGS[selected_zone].get(
            selected_command, selected_command)
        if not selected_command in commands.COMMANDS[selected_zone]:
            print('No such command in zone: %s' % selected_command)
            return 1
        print('Possible values for this command:')
        cmddata = commands.COMMANDS[selected_zone][selected_command]
        for range, value in list(cmddata['values'].items()):
            print('  %s - %s' % (value['name'], value['description']))
        return

    # Determine the receivers the command should run on
    if options['--host']:
        receivers = [eISCP(options['--host'], int(options['--port']))]
    else:
        receivers = eISCP.discover(timeout=1)
        if not options['--all']:
            if options['--name']:
                receivers = [r for r in receivers
                             if options['--name'] in r.info['model_name']]
            else:
                receivers = receivers[:1]
        if not receivers:
            print('No receivers found.')
            return 1

    # List of commands to execute - deal with special shortcut case
    to_execute = options['<command>']

    # Execute commands
    for receiver in receivers:
        with receiver:
            for command in to_execute:
                if command.isupper() and command.isalnum():
                    iscp_command = command
                    raw_response = True
                else:
                    try:
                        iscp_command = command_to_iscp(command)
                    except ValueError as e:
                        print('Error:', e)
                        return 2
                    raw_response = False

                print('%s: %s' % (receiver, iscp_command))
                response = receiver.raw(iscp_command)
                if not raw_response:
                    response = iscp_to_command(response)
                print(response)


def run():
    sys.exit(main() or 0)

if __name__ == '__main__':
    run()
