#!/usr/bin/python
"""Commands and control for the Onkyo eISCP interface.
"""

__author__ = 'Will Nowak <wan@ccs.neu.edu>'

import re
import struct
import socket, select
import logging

import commands


ALL_COMMANDS = commands.ALL


def CommandDictionary():
    outset = [('Power Control', commands.POWER),
        ('Basic Audio', commands.AUDIO),
        ('Source Selection', commands.SOURCE_SELECT),
        ('Sound Modes', commands.SOUND_MODES)]
    outdict = []

    for x in outset:
        a = {}
        for y in x[1]:
            a[y[0]] = y[1]
        outdict.append((x[0], a))
    return outdict


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
        self.command_dict = None
        self._build_command_dict()

    def __repr__(self):
        if getattr(self, 'info', False) and self.info.get('model_name'):
            model = self.info['model_name']
        else:
            model = 'unknown'
        string = "<%s(%s) %s:%s>" % (
            self.__class__.__name__, model, self.host, self.port)
        return string

    def _build_command_dict(self):
        if self.command_dict is None:
            self.command_dict = {}
            for readable, internal in commands.ALL:
                self.command_dict[normalize_command(readable)] = internal

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

    def command(self, command):
        """Write a command as an ascii string, will be converted to hex.

        Args:
           command: (string) ascii characters to be hexified for writing to serial
        """
        command = normalize_command(command)
        if command in self.command_dict:
            command = self.command_dict[command]

        if not command in self.command_dict.values():
            raise InvalidCommandException("Not a valid command %s" % command)

        self._ensure_socket_connected()
        self.command_socket.send(command_to_packet(command))

    def power_on(self):
        """Turn the receiver power on."""
        self.command('Power ON')

    def power_off(self):
        """Turn the receiver power off."""
        self.command('Power OFF')
