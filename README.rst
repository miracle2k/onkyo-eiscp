Onkyo eISCP Control
===================

Python library to control Onkyo receivers over Ethernet.

Originally based on `compbrain/Onkyo-TX-NR708-Control
<https://github.com/compbrain/Onkyo-TX-NR708-Control>`_.

Usage::

    import eiscp

    # Create a receiver object attached to the host 192.168.1.124
    receiver = eiscp.eISCP('192.168.1.125')

    # Turn the receiver on
    receiver.command('Power ON')

    # Select the PC input
    receiver.command('Computer/PC')

    # Done watching a movie, shut it off.
    receiver.command('Power OFF')

The ``command`` method supports different styles. These also work::

    receiver.command('internet-radio')
    receiver.command('volume_Down')

Specifically, case is ignored, and ``-``, ``_`` and a space all mean the
same thing.

You can also send the internal command names::

    receiver.command('SLI26')   # Selects the "Tuner" source.


Limitations
-----------

Receiving status information is not yet supported.
