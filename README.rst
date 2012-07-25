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


Limitations
-----------

Receiving status information is not yet supported.
