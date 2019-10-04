import re
import struct
import time
import socket, select
import threading
try:
    import queue as queue
except ImportError:
    import Queue as queue
import netifaces
from collections import namedtuple

from . import commands
from .utils import ValueRange


class ISCPMessage(object):
    """Deals with formatting and parsing data wrapped in an ISCP
    containers. The docs say:

        ISCP (Integra Serial Control Protocol) consists of three
        command characters and parameter character(s) of variable
        length.

    It seems this was the original protocol used for communicating
    via a serial cable.
    """

    def __init__(self, data):
        self.data = data

    def __str__(self):
        # ! = start character
        # 1 = destination unit type, 1 means receiver
        # End character may be CR, LF or CR+LF, according to doc
        return '!1{}\r'.format(self.data)

    @classmethod
    def parse(self, data):
        EOF = '\x1a'
        TERMINATORS = ['\n', '\r']
        assert data[:2] == '!1'
        eof_offset = -1
        # EOF can be followed by CR/LF/CR+LF
        if data[eof_offset] in TERMINATORS:
          eof_offset -= 1
          if data[eof_offset] in TERMINATORS:
            eof_offset -= 1
        assert data[eof_offset] == EOF
        return data[2:eof_offset]


class eISCPPacket(object):
    """For communicating over Ethernet, traditional ISCP messages are
    wrapped inside an eISCP package.
    """

    header = namedtuple('header', (
        'magic, header_size, data_size, version, reserved'))

    def __init__(self, iscp_message):
        iscp_message = str(iscp_message)
        # We attach data separately, because Python's struct module does
        # not support variable length strings,
        header = struct.pack(
            '! 4s I I b 3s',
            b'ISCP',            # magic
            16,                 # header size (16 bytes)
            len(iscp_message),  # data size
            0x01,               # version
            b'\x00\x00\x00'     #reserved
        )

        self._bytes = header + iscp_message.encode('utf-8')
        # __new__, string subclass?

    def __str__(self):
        return self._bytes.decode('utf-8')

    def get_raw(self):
        return self._bytes

    @classmethod
    def parse(cls, bytes):
        """Parse the eISCP package given by ``bytes``.
        """
        h = cls.parse_header(bytes[:16])
        data = bytes[h.header_size:h.header_size + h.data_size].decode()
        assert len(data) == h.data_size
        return data

    @classmethod
    def parse_header(self, bytes):
        """Parse the header of an eISCP package.

        This is useful when reading data in a streaming fashion,
        because you can subsequently know the number of bytes to
        expect in the packet.
        """
        # A header is always 16 bytes in length
        assert len(bytes) == 16

        # Parse the header
        magic, header_size, data_size, version, reserved = \
            struct.unpack('! 4s I I b 3s', bytes)

        magic = magic.decode()
        reserved = reserved.decode()

        # Strangly, the header contains a header_size field.
        assert magic == 'ISCP'
        assert header_size == 16

        return eISCPPacket.header(
            magic, header_size, data_size, version, reserved)


def command_to_packet(command):
    """Convert an ascii command like (PVR00) to the binary data we
    need to send to the receiver.
    """
    return eISCPPacket(ISCPMessage(command)).get_raw()


def normalize_command(command):
    """Ensures that various ways to refer to a command can be used."""
    command = command.lower()
    command = command.replace('_', ' ')
    command = command.replace('-', ' ')
    return command


def command_to_iscp(command, arguments=None, zone=None):
    """Transform the given given high-level command to a
    low-level ISCP message.

    Raises :class:`ValueError` if `command` is not valid.

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
        raise ValueError('"{}" is not a valid zone'.format(zone))

    prefix = commands.COMMAND_MAPPINGS[group].get(command, command)
    if not prefix in commands.COMMANDS[group]:
        raise ValueError('"{}" is not a valid command in zone "{}"'.format(
                command, zone))

    # Resolve the argument to the command. This is a bit more involved,
    # because some commands support ranges (volume) or patterns
    # (setting tuning frequency). In some cases, we might imagine
    # providing the user an API with multiple arguments (TODO: not
    # currently supported).
    argument = arguments[0]

    # 1. Consider if there is a alias, e.g. level-up for UP.
    try:
        value = commands.VALUE_MAPPINGS[group][prefix][argument]
    except KeyError:
        # 2. See if we can match a range or pattern
        for possible_arg in commands.VALUE_MAPPINGS[group][prefix]:
            if argument.isdigit():
                if isinstance(possible_arg, ValueRange):
                    if int(argument) in possible_arg:
                        # We need to send the format "FF", hex() gives us 0xff
                        value = hex(int(argument))[2:].zfill(2).upper()
                        break

            # TODO: patterns not yet supported
        else:
            raise ValueError('"{}" is not a valid argument for command '
                             '"{}" in zone "{}"'.format(argument, command, zone))

    return '{}{}'.format(prefix, value)


def iscp_to_command(iscp_message):
    for zone, zone_cmds in commands.COMMANDS.items():
        # For now, ISCP commands are always three characters, which
        # makes this easy.
        command, args = iscp_message[:3], iscp_message[3:]
        if command in zone_cmds:
            if args in zone_cmds[command]['values']:
                return zone_cmds[command]['name'], \
                       zone_cmds[command]['values'][args]['name']
            else:
                match = re.match('[+-]?[0-9a-f]+$', args, re.IGNORECASE)
                if match:
                    return zone_cmds[command]['name'], \
                             int(args, 16)
                else:
                    return zone_cmds[command]['name'], args

    else:
        raise ValueError(
            'Cannot convert ISCP message to command: {}'.format(iscp_message))


def filter_for_message(getter_func, msg):
    """Helper that calls ``getter_func`` until a matching message
    is found, or the timeout occurs. Matching means the same commands
    group, i.e. for sent message MVLUP we would accept MVL13
    in response."""
    start = time.time()
    while True:
        candidate = getter_func(0.05)
        # It seems ISCP commands are always three characters.
        if candidate and candidate[:3] == msg[:3]:
            return candidate
        # The protocol docs claim that a response  should arrive
        # within *50ms or the communication has failed*. In my tests,
        # however, the interval needed to be at least 200ms before
        # I managed to see any response, and only after 300ms
        # reproducably, so use a generous timeout.
        if time.time() - start > 5.0:
            raise ValueError('Timeout waiting for response.')


def parse_info(data):
    response = eISCPPacket.parse(data)
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
    return info

class eISCP(object):
    """Implements the eISCP interface to Onkyo receivers.

    This uses a blocking interface. The remote end will regularily
    send unsolicited status updates. You need to manually call
    ``get_message`` to query those.

    You may want to look at the :meth:`Receiver` class instead, which
    uses a background thread.
    """
    ONKYO_PORT = 60128
    CONNECT_TIMEOUT = 5

    @classmethod
    def discover(cls, timeout=5, clazz=None):
        """Try to find ISCP devices on network.

        Waits for ``timeout`` seconds, then returns all devices found,
        in form of a list of dicts.
        """
        onkyo_magic = eISCPPacket('!xECNQSTN').get_raw()
        pioneer_magic = eISCPPacket('!pECNQSTN').get_raw()
        # Since due to interface aliasing we may see the same Onkyo device
        # multiple times, we build the list as a dict keyed by the
        # unique identifier code
        found_receivers = {}

        # We do this on all network interfaces
        # which have an AF_INET address and broadcast address
        for interface in netifaces.interfaces():
            ifaddrs=netifaces.ifaddresses(interface)
            if not netifaces.AF_INET in ifaddrs:
                continue
            for ifaddr in ifaddrs[netifaces.AF_INET]:
                if not "addr" in ifaddr or not "broadcast" in ifaddr:
                    continue
                # Broadcast magic
                sock = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setblocking(0)   # So we can use select()
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((ifaddr["addr"], 0))
                sock.sendto(onkyo_magic, (ifaddr["broadcast"], eISCP.ONKYO_PORT))
                sock.sendto(pioneer_magic, (ifaddr["broadcast"], eISCP.ONKYO_PORT))
        
                while True:
                    ready = select.select([sock], [], [], timeout)
                    if not ready[0]:
                        break
                    data, addr = sock.recvfrom(1024)

                    info = parse_info(data)
        
                    # Give the user a ready-made receiver instance. It will only
                    # connect on demand, when actually used.
                    receiver = (clazz or eISCP)(addr[0], int(info['iscp_port']))
                    receiver.info = info
                    found_receivers[info["identifier"]]=receiver
        
                sock.close()
        return list(found_receivers.values())

    def __init__(self, host, port=60128):
        self.host = host
        self.port = port
        self._info = None

        self.command_socket = None

    @property
    def model_name(self):
        if self.info and self.info.get('model_name'):
            return self.info['model_name']
        else:
            return 'unknown-model'

    @property
    def identifier(self):
        if self.info and self.info.get('identifier'):
            return self.info['identifier']
        else:
            return 'no-id'

    def __repr__(self):
        if self.info and self.info.get('model_name'):
            model = self.info['model_name']
        else:
            model = 'unknown'
        string = "<{}({}) {}:{}>".format(
            self.__class__.__name__, model, self.host, self.port)
        return string

    @property
    def info(self):
        if not self._info:
            sock = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setblocking(0)
            sock.bind(('0.0.0.0', 0))
            sock.sendto(eISCPPacket('!xECNQSTN').get_raw(), (self.host, self.port))

            ready = select.select([sock], [], [], 0.1)
            if ready[0]:
                data = sock.recv(1024)
                self._info = parse_info(data)
            sock.close()
        return self._info

    @info.setter
    def info(self, value):
        self._info = value

    def _ensure_socket_connected(self):
        if self.command_socket is None:
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.settimeout(self.CONNECT_TIMEOUT)
            self.command_socket.connect((self.host, self.port))
            self.command_socket.setblocking(0)

    def disconnect(self):
        try:
            self.command_socket.close()
        except:
            pass
        self.command_socket = None

    def __enter__(self):
        self._ensure_socket_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def send(self, iscp_message):
        """Send a low-level ISCP message, like ``MVL50``.

        This does not return anything, nor does it wait for a response
        from the receiver. You can query responses via :meth:`get`,
        or use :meth:`raw` to send a message and waiting for one.
        """
        self._ensure_socket_connected()
        self.command_socket.send(command_to_packet(iscp_message))

    def get(self, timeout=0.1):
        """Return the next message sent by the receiver, or, after
        ``timeout`` has passed, return ``None``.
        """
        self._ensure_socket_connected()

        ready = select.select([self.command_socket], [], [], timeout or 0)
        if ready[0]:
            header_bytes = self.command_socket.recv(16)
            header = eISCPPacket.parse_header(header_bytes)
            body = b''
            while len(body) < header.data_size:
                ready = select.select([self.command_socket], [], [], timeout or 0)
                if not ready[0]:
                    return None
                body += self.command_socket.recv(header.data_size - len(body))
            return ISCPMessage.parse(body.decode())

    def raw(self, iscp_message):
        """Send a low-level ISCP message, like ``MVL50``, and wait
        for a response.

        While the protocol is designed to acknowledge each message with
        a response, there is no fool-proof way to differentiate those
        from unsolicited status updates, though we'll do our best to
        try. Generally, this won't be an issue, though in theory the
        response this function returns to you sending ``SLI05`` may be
        an ``SLI06`` update from another controller.

        It'd be preferable to design your app in a way where you are
        processing all incoming messages the same way, regardless of
        their origin.
        """
        while self.get(False):
            # Clear all incoming messages. If not yet queried,
            # they are lost. This is so that we can find the real
            # response to our sent command later.
            pass
        self.send(iscp_message)
        return filter_for_message(self.get, iscp_message)

    def command(self, command, arguments=None, zone=None):
        """Send a high-level command to the receiver, return the
        receiver's response formatted has a command.

        This is basically a helper that combines :meth:`raw`,
        :func:`command_to_iscp` and :func:`iscp_to_command`.
        """
        iscp_message = command_to_iscp(command, arguments, zone)
        response = self.raw(iscp_message)
        if response:
            return iscp_to_command(response)

    def power_on(self):
        """Turn the receiver power on."""
        return self.command('power', 'on')

    def power_off(self):
        """Turn the receiver power off."""
        return self.command('power', 'off')


class Receiver(eISCP):
    """Changes the behaviour of :class:`eISCP` to use a background
    thread for network operations. This allows receiving messages
    from the receiver via a callback::


        def message_received(message):
            print message

        receiver = Receiver('...')
        receiver.on_message = message_received

    The argument ``message`` is
    """

    @classmethod
    def discover(cls, timeout=5, clazz=None):
        return eISCP.discover(timeout, clazz or Receiver)

    def _ensure_thread_running(self):
        if not getattr(self, '_thread', False):
            self._stop = False
            self._queue = queue.Queue()
            self._thread = threading.Thread(target=self._thread_loop)
            self._thread.start()

    def disconnect(self):
        self._stop = True
        self._thread.join()
        self._thread = None

    def send(self, iscp_message):
        """Like :meth:`eISCP.send`, but sends asynchronously via the
        background thread.
        """
        self._ensure_thread_running()
        self._queue.put((iscp_message, None, None))

    def get(self, *a, **kw):
        """Not supported by this class. Use the :attr:`on_message``
        hook to handle incoming messages.
        """
        raise NotImplementedError()

    def raw(self, iscp_message):
        """Like :meth:`eISCP.raw`.
        """
        self._ensure_thread_running()
        event = threading.Event()
        result = []
        self._queue.put((iscp_message, event, result))
        event.wait()
        if isinstance(result[0], Exception):
            raise result[0]
        return result[0]

    def _thread_loop(self):
        def trigger(message):
            if self.on_message:
                self.on_message(message)

        eISCP._ensure_socket_connected(self)
        try:
            while not self._stop:
                # Clear all incoming message first.
                while True:
                    msg = eISCP.get(self, False)
                    if not msg:
                        break
                    trigger(msg)

                # Send next message
                try:
                    item = self._queue.get(timeout=0.01)
                except queue.Empty:
                    continue
                if item:
                    message, event, result = item
                    eISCP.send(self, message)

                    # Wait for a response, if the caller so desires
                    if event:
                        try:
                            # XXX We are losing messages here, since
                            # those are not triggering the callback!
                            # eISCP.raw() really has the same problem,
                            # messages being dropped without a chance
                            # to get() them. Maybe use a queue after all.
                            response = filter_for_message(
                                super(Receiver, self).get, message)
                        except ValueError as e:
                            # No response received within timeout
                            result.append(e)
                        else:
                            result.append(response)
                        # Mark as processed
                        event.set()

        finally:
            eISCP.disconnect(self)
