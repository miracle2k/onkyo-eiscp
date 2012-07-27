"""Control Onkyo A/V receivers.

Usage:
  onkyo [options] <command>...
  onkyo --discover
  onkyo --list-commands
  onkyo -h | --help


Selecting the receiver:

  --host <host>         Connect to this host
  --port, -p <port>     Connect to this port [default: 60128]
  --all                 Discover receivers, send to all found
  --name, -n <name>     Discover receivers, send to those matching name.

If none of these options is given, the program searches for receivers,
and uses the first one found.

  --discover            List all discoverable receivers
  --list-commands       List available commands.

Examples:
  onkyo "power on" "source pc", "volume 75"
    Turn receiver on, select "PC" source, set volume to 75.
  onkyo muting off
    If only a single command is sent, it is not necessary to wrap it in
    quotes.
"""

import sys
import docopt

from core import eISCP
from commands import ALL as ALL_COMMANDS


def main(argv=sys.argv):
    options = docopt.docopt(__doc__, help=True)

    # List commands
    if options['--discover']:
        for receiver in eISCP.discover(timeout=1):
            print "%s %s:%s" % (
                receiver.info['model_name'], receiver.host, receiver.port)
        return

    # List available commands
    if options['--list-commands']:
        for command, _ in ALL_COMMANDS:
            print command
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
            print "No receivers found."
            return 1

    # List of commands to execute - deal with special shortcut case
    commands = options['<command>']
    if len(commands) == 2 and not any([c for c in commands if not ' ' in c]):
        commands = ["%s %s" % tuple(commands)]

    # Execute commands
    for receiver in receivers:
        with receiver:
            for command in commands:
                print '%s: %s' % (receiver, command)
                receiver.command(command)




if __name__ == '__main__':
    sys.exit(main() or 0)
