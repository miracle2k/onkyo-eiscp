#!/usr/bin/python
import sys

f = open(sys.argv[1])


print '#!/usr/bin/python'
print
print '"""Command set for the Onkyo TX-NR708.'
print
print 'This file was automatically created by %s' % sys.argv[0]
print 'from the source file: %s' % sys.argv[1]
print 'Each command group in the documentation has a seperate list,'
print 'and all commands are available in ALL."""'
print
print


sections = []
for x in f:
  x = x.strip()
  if not x:
    continue
  if x[0] == '#':
    continue
  elif x[0] == '=':
    x = x.replace('=', '')
    x = x.strip()
    if sections:
      print ']'
    print '######################'
    print '### %s' % x
    print '######################'
    n = x.upper().replace(' ', '_')
    sections.append(n)
    print '%s = [' % n
  else:
    name, command = x.split(':')
    name = name.strip()
    command = command.strip().replace(' ', '')
    print '  ("%s", "%s"),' % (name, command)
print ']'
print
print 'ALL = %s' % ' + '.join(sections)
