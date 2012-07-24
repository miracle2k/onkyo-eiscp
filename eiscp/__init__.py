#!/usr/bin/python
"""Commands and control for the Onkyo eISCP interface.
"""

__author__ = 'Will Nowak <wan@ccs.neu.edu>'

import socket
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


def ascii_command_to_hex(command):
    """Convert an ascii command to it's hex equivalent.

    Args:
       command: (string) ascii characters to be hexified for writing to serial
    """
    if '!1' != command[:2]:
        command = '!1%s' % command
    command_length = len(command)
    pad = chr(command_length + 1 + 16)
    cmd = ('ISCP\x00\x00\x00\x10\x00\x00\x00%s\x01\x00\x00\x00%s\x0D'
           % (pad, command))
    return cmd


class eISCP(object):

    def __init__(self, hostname, port=60128):
        self.hostname = hostname
        self.port = port

        self.command_socket = None
        self.command_dict = None
        self._build_command_dict()

    def _build_command_dict(self):
        if self.command_dict is None:
            self.command_dict = {}
            for x in commands.ALL:
                self.command_dict[x[0].lower()] = x[1]

    def _connect_socket(self):
        if self.command_socket is None:
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.connect((self.hostname, self.port))

    def _disconnect_socket(self):
        if self.command_socket is not None:
            try:
                self.command_socket.close()
            except:
                logging.exception('Could not close serial port %s' % self.port)
            self.command_socket = None

    def command(self, command):
        """Write a command as an ascii string, will be converted to hex.

        Args:
           command: (string) ascii characters to be hexified for writing to serial
        """
        if command in self.command_dict:
            command = self.command_dict[command]

        if not command in self.command_dict.values():
            raise InvalidCommandException("Not a valid command %s" % command)

        try:
            self._connect_socket()
            self.command_socket.send(ascii_command_to_hex(command))
        finally:
            self._disconnect_socket()

    def power_on(self):
        """Turn the receiver power on."""
        self.command('Power ON')

    def power_off(self):
        """Turn the receiver power off."""
        self.command('Power OFF')
