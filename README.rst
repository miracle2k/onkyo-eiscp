Onkyo eISCP Control
===================

Python library to control Onkyo receivers over Ethernet.

Installation
------------

Most recent released version::

    $ easy_install onkyo-eiscp

Latest development version::

    $ easy_install onkyo-eiscp==dev

__ http://github.com/miracle2k/onkyo-eiscp/tarball/master#egg=onkyo-eiscp-dev



Usage
-----

.. code:: python

    import eiscp

    # Create a receiver object, connecting to the host
    receiver = eiscp.eISCP('192.168.1.125')

    # Turn the receiver on, select PC input
    receiver.command('Power ON')
    receiver.command('Computer/PC')

    receiver.disconnect()

Don't forget to call ``disconnect()`` to close the socket. You can also use a
``with`` statement:

.. code:: python

    with eiscp.eISCP('192.168.1.125') as receiver:
        receiver.command('all-ch-stereo')


The ``command()`` method supports different styles. These also work:

.. code:: python

    receiver.command('internet-radio')
    receiver.command('volume_Down')

Specifically, case is ignored, and ``-``, ``_`` and `` `` (a space character)
all mean the same thing.

You can also send the internal command names:

.. code:: python

    receiver.command('SLI26')   # Selects the "Tuner" source.


Device discovery
~~~~~~~~~~~~~~~~

You can have it find the receivers on your local network:

.. code:: python

    for receiver in eiscp.eISCP.discover(timeout=5):
        receiver.command('power off')

This will turn off all the Onkyo receivers on your network.

A discovered device has an ``info`` attribute that gives you some data:

.. code:: python

    {'iscp_port': '60128', 'identifier': '0009B04448E0',
     'area_code': 'XX', 'model_name': 'TX-NR709', 'device_category': '1'}


Notes on Power On
~~~~~~~~~~~~~~~~~

For the ``power on`` command to work while the device is in standby, make
sure you turn on the ``Setup -> Hardware -> Network -> Network Control``.

Without it, you can only connect to your receiver while it is already
turned on.


Limitations
-----------

- Receiving status information is not yet supported.


Related Links
-------------

http://michael.elsdoerfer.name/onkyo/ISCP-V1.21_2011.xls
    Document from Onkyo describing the protocol, including a full list
    of supported commands.

https://github.com/compbrain/Onkyo-TX-NR708-Control
    Repository on which this was originally based.

https://github.com/beanz/device-onkyo-perl
    Perl implementation.

http://code.google.com/p/onkyo-eiscp-remote-windows/
    C# implementation.

https://github.com/janten/onkyo-eiscp-remote-mac
    Object-C implementation.

https://sites.google.com/a/webarts.ca/toms-blog/Blog/new-blog-items/javaeiscp-integraserialcontrolprotocol
    Some Java code. Also deserves credit for providing the official Onkyo
    protocol documentation linked above.
