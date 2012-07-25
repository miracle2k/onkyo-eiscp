Onkyo eISCP Control
===================

Python library to control Onkyo receivers over Ethernet.

Originally based on `compbrain/Onkyo-TX-NR708-Control
<https://github.com/compbrain/Onkyo-TX-NR708-Control>`_.

Usage
-----

::

    import eiscp

    # Create a receiver object, connecting to the host
    receiver = eiscp.eISCP('192.168.1.125')

    # Turn the receiver on, select PC input
    receiver.command('Power ON')
    receiver.command('Computer/PC')

    receiver.disconnect()

Don't forget to call ``disconnect()`` to close the socket. You can also use a
``with`` statement::

    with eiscp.eISCP('192.168.1.125') as receiver:
        receiver.command('all-ch-stereo')


The ``command()`` method supports different styles. These also work::

    receiver.command('internet-radio')
    receiver.command('volume_Down')

Specifically, case is ignored, and ``-``, ``_`` and `` `` (a space character)
all mean the same thing.

You can also send the internal command names::

    receiver.command('SLI26')   # Selects the "Tuner" source.


Device discovery
~~~~~~~~~~~~~~~~

You can have it find the receivers on your local network::

    for receiver in eiscp.eISCP.discover(timeout=5):
        receiver.command('power off')

This will turn off all the Onkyo receivers on your network.

A discovered device has an ``info`` attribute that gives you some data::

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
