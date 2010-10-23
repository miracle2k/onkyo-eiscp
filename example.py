#!/usr/bin/python
import eiscp


# Create a receiver object attached to the host 192.168.1.124
receiver = eiscp.eISCP('192.168.1.125')

# Turn the receiver on
receiver.writeCommandFromName('Power ON')

# Select the PC input
receiver.writeCommandFromName('Computer/PC')

# Done watching a movie, shut it off.
receiver.writeCommandFromName('Power OFF')

