import re
import struct
import socket, select
import logging

import commands


class InvalidCommandException(Exception):
    """Raised when an invalid command is provided."""


def eiscp_packet(data):
    """Convert ``data`` into an eISCP packet as expected by
    Onkyo receivers.
    """
    # We attach data separately, because Python's struct module does
    # not support variable length strings,
    header = struct.pack(
        '! 4s I I b 3b',
        'ISCP',           # magic
        16,                # header size (16 bytes)
        len(data),      # data size
        0x01,              # version
        0x00, 0x00, 0x00   # reserved
    )

    return "%s%s" % (header, data)


def parse_packet(bytes):
    """Reverse of :meth:`eiscp_packet`.
    """
    magic, header_size, data_size, version, reserved = \
        struct.unpack('! 4s I I b 3s', bytes[:16])
    assert magic == 'ISCP'
    assert header_size == 16

    data = bytes[header_size:header_size+data_size]
    assert len(data) == data_size
    return data


def command_to_packet(command):
    """Convert an ascii command like (PVR00) to the binary data we need
    to send to the receiver.
    """
    # ! = start character
    # 1 = destination unit type, 1 means receiver
    if '!1' != command[:2]:
        command = '!1%s' % command
    command = '%s\r' % command
    return eiscp_packet(command)


def normalize_command(command):
    """Ensures that various ways to refer to a command can be used."""
    command = command.lower()
    command = command.replace('_', ' ')
    command = command.replace('-', ' ')
    return command


class eISCP(object):

    @classmethod
    def discover(cls, timeout=5):
        """Try to find ISCP devices on network.

        Waits for ``timeout`` seconds, then returns all devices found,
        in form of a list of dicts.
        """
        onkyo_port = 60128
        onkyo_magic = eiscp_packet('!xECNQSTN')

        # Broadcast magic
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setblocking(0)   # So we can use select()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('0.0.0.0', 0))
        sock.sendto(onkyo_magic, ('255.255.255.255', onkyo_port))

        found_receivers = []
        while True:
            ready = select.select([sock], [], [], timeout)
            if not ready[0]:
                break
            data, addr = sock.recvfrom(1024)

            response = parse_packet(data)
            # Return string looks something like this:
            # !1ECNTX-NR609/60128/DX
            info = re.match(r'''
                !
                (?P<device_category>\d)
                ECN
                (?P<model_name>[^/]*)/
                (?P<iscp_port>\d{5})/
                (?P<area_code>\w{2})/
                (?P<identifier>.{0,12})
            ''', response.strip(), re.VERBOSE).groupdict()

            # Give the user a ready-made receiver instance. It will only
            # connect on demand, when actually used.
            receiver = eISCP(addr[0], int(info['iscp_port']))
            receiver.info = info
            found_receivers.append(receiver)

        sock.close()
        return found_receivers

    def __init__(self, host, port=60128):
        self.host = host
        self.port = port

        self.command_socket = None

    def __repr__(self):
        if getattr(self, 'info', False) and self.info.get('model_name'):
            model = self.info['model_name']
        else:
            model = 'unknown'
        string = "<%s(%s) %s:%s>" % (
            self.__class__.__name__, model, self.host, self.port)
        return string

    def _ensure_socket_connected(self):
        if self.command_socket is None:
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.connect((self.host, self.port))

    def disconnect(self):
        try:
            self.command_socket.close()
        except:
            logging.exception('Could not close serial port %s' % self.port)
        self.command_socket = None

    def __enter__(self):
        self._ensure_socket_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def command(self, command, arguments=None, zone=None):
        """Execute a command.

        This exposes a system of human-readable, "pretty"
        commands, which is organized into three parts: the zone, the
        command, and arguments. For example::

            command('power', 'on')
            command('power', 'on', zone='main')
            command('volume', 66, zone='zone2')

        As you can see, if no zone is given, the main zone is assumed.

        Instead of passing three different parameters, you may put the
        whole thing in a single string, which is helpful when taking
        input from users::

            command('power on')
            command('zone2 volume 66')

        To further simplify things, for example when taking user input
        from a command line, where whitespace needs escaping, the
        following is also supported:

            command('power=on')
            command('zone2.volume=66')

        """
        default_zone = 'main'
        command_sep = r'[. ]'
        norm = lambda s: s.strip().lower()

        # If parts are not explicitly given, parse the command
        if arguments is None and zone is None:
            # Separating command and args with colon allows multiple args
            if ':' in command or '=' in command:
                base, arguments = re.split(r'[:=]', command, 1)
                parts = [norm(c) for c in re.split(command_sep, base)]
                if len(parts) == 2:
                    zone, command = parts
                else:
                    zone = default_zone
                    command = parts[0]
                # Split arguments by comma or space
                arguments = [norm(a) for a in re.split(r'[ ,]', arguments)]
            else:
                # Split command part by space or dot
                parts = [norm(c) for c in re.split(command_sep, command)]
                if len(parts) >= 3:
                    zone, command = parts[:2]
                    arguments = parts[3:]
                elif len(parts) == 2:
                    zone = default_zone
                    command = parts[0]
                    arguments = parts[1:]
                else:
                    raise ValueError('Need at least command and argument')

        # Find the command in our database, resolve to internal eISCP command
        group = commands.ZONE_MAPPINGS.get(zone, zone)
        if not zone in commands.COMMANDS:
            raise ValueError('"%s" is not a valid zone' % zone)

        prefix = commands.COMMAND_MAPPINGS[group].get(command, command)
        if not prefix in commands.COMMANDS[group]:
            raise ValueError('"%s" is not a valid command in zone "%s"'
                    % (command, zone))

        # TODO: For now, only support one; though some rare commands would
        # need multiple.
        argument = arguments[0]
        value = commands.VALUE_MAPPINGS[group][prefix].get(argument, argument)
        if not value in commands.COMMANDS[group][prefix]['values']:
            raise ValueError('"%s" is not a valid argument for command '
                             '"%s" in zone "%s"' % (argument, command, zone))

        eiscp_command = '%s%s' % (prefix, value)
        return self.raw(eiscp_command)

    def raw(self, eiscp_command):
        """Send a low-level ISCP command directly, like ``MVL50``.
        """
        self._ensure_socket_connected()
        self.command_socket.send(command_to_packet(eiscp_command))

    def power_on(self):
        """Turn the receiver power on."""
        self.command('power', 'on')

    def power_off(self):
        """Turn the receiver power off."""
        self.command('power', 'off')
