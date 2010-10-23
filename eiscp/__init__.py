#!/usr/bin/python
"""Commands and control for the Onkyo TX-NR708 eISCP interface.

Model website:
  http://www.us.onkyo.com/model.cfm?m=TX-NR708&class=Receiver&p=i

Manual for the reciever:
  http://63.148.251.135/redirect_service.cfm?type=own_manuals
  &file=SN29400317_TX-NR708_En_web.pdf
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


class eISCP(object):
  def __init__(self, hostname, port=60128):
    self.hostname = hostname
    self.eiscp_port = port

    self.command_socket = None
    self.command_dict = None
    self.buildCommandDict()

  def buildCommandDict(self):
    if self.command_dict is None:
      self.command_dict = {}
      for x in commands.ALL:
        self.command_dict[x[0]] = x[1]

  def connectSocket(self):
    if self.command_socket is None:
      self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.command_socket.connect((self.hostname, self.eiscp_port))

  def disconnectSocket(self):
    if self.command_socket is not None:
      try:
        self.command_socket.close()
      except:
        logging.exception('Could not close serial port %s' % self.serial_port)
      self.command_socket = None

  def asciiCommandToHex(self, command):
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

  def verifyCommand(self, command):
    """Verify that a command is known and valid.

    Args:
       command: (string) ascii characters to be hexified for writing to serial
    """
    if command not in self.command_dict.values():
      raise InvalidCommandException("Specified command not in commands.py") 

  def writeCommand(self, command):
    """Write a command as an ascii string, will be converted to hex.

    Args:
       command: (string) ascii characters to be hexified for writing to serial
    """
    self.verifyCommand(command)
    hex_command = self.asciiCommandToHex(command)

    try:
      self.connectSocket()
      self.command_socket.send(hex_command)
    finally:
      self.disconnectSocket()

  def writeCommandFromName(self, command_name):
    """Write a command based on it's named entry in commands.py.

    Args:
       command: (string) command name from commands.py
    """
    if command_name not in self.command_dict:
      raise InvalidCommandException("Given command name not in commands.py")
    self.writeCommand(self.command_dict[command_name])

  def powerOn(self):
    """Turn the receiver power on."""
    self.writeCommandFromName('Power ON')

  def powerOff(self):
    """Turn the receiver power off."""
    self.writeCommandFromName('Power OFF')
