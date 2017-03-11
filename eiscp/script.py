'''Control Onkyo A/V receivers.

Usage:
  %(program_name)s [--host <host>] [--port <port>]
  %(prog_n_space)s [--all] [--name <name>] [--id <identifier>]
  %(prog_n_space)s [--verbose | -v]... [--quiet | -q]... <command>...
  %(program_name)s --discover
  %(program_name)s --help-commands [<zone> <command>]
  %(program_name)s -h | --help

Selecting the receiver:

  --host, -t <host>     Connect to this host
  --port, -p <port>     Connect to this port
  --all, -a             Discover receivers, send to all found
  --name, -n <name>     Discover receivers, send to those matching name.
  --id, -i <id>         Discover receivers, send to those matching identifier.
  --verbose, -v         Show commands sent and additional info
                        (specify multiple times to show parsed raw commands)
  --quiet, -q           Don't include receiver name in response
                        (specify multiple times to hide even the command name)

If none of these options is given, the program searches for receivers,
and uses the first one found.

  --discover            List all discoverable receivers
  --help-commands       List available commands.

Examples:
  %(program_name)s power=on source=pc volume=75
    Turn receiver on, select "PC" source, set volume to 75.
  %(program_name)s zone2.power=standby
    To execute a command for zone that isn't the main one.
'''

import sys
import os
import docopt

from .core import eISCP, command_to_iscp, iscp_to_command
from . import commands

# Automatically replace %(program_name)s with the current program name in the
# documentation.
program_name = os.path.basename(sys.argv[0])
__doc__ %= {'program_name': program_name, 'prog_n_space': ' ' * len(program_name)}


def main(argv=sys.argv):
    basename = os.path.basename(argv[0])
    options = docopt.docopt(__doc__, help=True)

    # List commands
    if options['--discover']:
        for receiver in eISCP.discover(timeout=1):
            print('%s\t%s:%s\t%s' % (receiver.model_name, receiver.host, receiver.port, receiver.identifier))
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
    host = options.get('--host') or os.environ.get('ONKYO_HOST', None)
    port = int(options.get('--port') or os.environ.get('ONKYO_PORT', eISCP.ONKYO_PORT))
    if host:
        receivers = [eISCP(host, port)]
    else:
        receivers = eISCP.discover(timeout=1)
        if not options['--all']:
            if options['--name']:
                receivers = [r for r in receivers
                             if options['--name'] in r.model_name]
            elif options['--id']:
                receivers = [r for r in receivers
                             if options['--id'] in r.identifier]
            else:
                receivers = list(receivers)[:1]
        if not receivers:
            print('No receivers found.')
            return 1

    # List of commands to execute - deal with special shortcut case
    to_execute = options['<command>']

    # Execute commands
    model_names = [r.model_name for r in receivers]
    for receiver in receivers:
        with receiver:
            name = receiver.model_name
            if model_names.count(receiver.model_name) > 1:
                name += '@' + receiver.host
            for command in to_execute:
                raw = command.isupper() and command.isalnum()
                log = Log(name, options, raw)
                log.log_command(command)
                if raw:
                    iscp_message = command
                else:
                    try:
                        iscp_message = command_to_iscp(command)
                    except ValueError as e:
                        print('Error:', e)
                        return 2
                response = receiver.raw(iscp_message)
                log.log_response(response)

class Log():
    def __init__(self, name, options, raw):
        self.name = name
        self.verbose = options['--verbose']
        self.quiet = options['--quiet']
        self.raw = raw
    def log_command(self, command):
        if self.verbose >= 1:
            if self.verbose >= 2:
                if self.raw:
                    command_str = '%s (%s)' % (command, iscp_to_command(command))
                else:
                    command_str = '%s (%s)' % (command, command_to_iscp(command))
            else:
                command_str = command
            print('sending to %s: %s' % (self.name, command_str))
    def log_response(self, response):
        if self.raw and self.verbose < 2:
            response_str = response
        else:
            cmd_name, args = iscp_to_command(response)
            if isinstance(cmd_name, tuple):
                cmd_name = min(cmd_name, key=len)
            if isinstance(args, tuple):
                args = ','.join(args)
            if self.quiet >= 2:
                response_str = args
            else:
                if self.verbose >= 2:
                    response_str = '%s = %s (%s)' % (cmd_name, args, response)
                else:
                    response_str = '%s = %s' % (cmd_name, args)
            if self.raw:
                response_str = '%s (%s)' % (response, response_str)
        if self.quiet >= 1:
            print(response_str)
        else:
            print('%s: %s' % (self.name, response_str))

def run():
    sys.exit(main() or 0)

if __name__ == '__main__':
    run()
