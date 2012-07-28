#!/usr/bin/env python
# coding: utf8
"""Script to extract the list of commands from the Onkyo protocol
documentation, which is an Excel file.

Since this Excel file is not designed to be read by machines, I don't
expect this to work for new versions of the file without adjustments.

Here's how the process is supposed to work:

    - This script takes the Excel document as a an input file, and
      converts it into a YAML.
    - This is checked into version control.
    - Adjustments to this file are required and made, via version control.
    - Subsequently, a new version of the Excel file can be parsed into YAML
      and merged with the manual changes.
    - The YAML file is used by the Python library for the final command list;
      potentially be further generating a Python file from it for speed.
"""

import sys
import re
import os
from datetime import datetime
import yaml
from collections import OrderedDict

# Currently requires this fork for Excel support:
# https://github.com/djv/tablib
# Can be installed via ``sudo pip install -e git+https://github.com/djv/tablib.git#egg=tablib``
#
# We could just as well skip tablib and work with the base libraries
# directly, though.
import tablib


def make_command(name):
    """Convert a string into a space-less command."""
    name = re.sub('[^\w]', ' ', name)   # Replace special characters with spaces
    name = name.strip().lower()
    while "  " in name: name = name.replace('  ', ' ') # Replace duplicate spaces
    name = name.replace(' ', '-')    # In the end, we want no whitespace
    return name


# Tained tuple that can have a non-standard YAML representation
class FlowStyleTuple(tuple):
    pass


def import_sheet(groupname, sheet, modelsets):
    data = OrderedDict()

    # First line has a list of models, ignore empty cols, and first two.
    modelcols = filter(lambda s: bool(s), sheet[0])[2:]
    # One model headers can continue multiple models. Split.
    modelcols = [m
                .replace('\n(Ether)', '(Ether)')
                .replace('\n(Ver2.0)', '(Ver2.0)')
                .replace('TX-NR5000ETX-NA1000', 'TX-NR5000\nETX-NA1000')
                .split('\n')
              for m in modelcols]

    # Because there is at least one floating standalone table next
    # to the main table, that we don't care about, and which in rows
    # further down below will bother us.
    max_model_column = len(filter(lambda s: bool(s), modelcols))

    prefix = prefix_desc = None
    for row in sheet[1:]:
        # Remove right-most columns that no longer belong to the main table
        row = row[:max_model_column]

        # Remove whitespace from all fields
        row = map(lambda s: unicode(s).strip(), row)

        # Ignore empty lines
        if not any(row):
            continue

        # This is a command prefix, e.g. "PWR" for power.
        # What follows are the different values that can be appended,
        # for example to make up the full command, e.g. "PWR01".
        #
        # The data looks something like ``"PWR" - System Power Command ``,
        # and we need to parse it.
        if not any(row[1:]):
            # Ignore a variety of text rows that are similar to a prefix header.
            # We need to grasp at straws here, since we can't look at the
            # row color, which would also tell us if it's a header.
            if row[0].startswith('*'):
                continue
            if 'when' in row[0] or 'Ex:' in row[0] or 'is shared' in row[0]:
                continue

            # operation command, command, brakets

            prefix, prefix_desc = re.match(r'"(.*?)" -\s?(.*)', row[0]).groups()

            # Auto-determine a possible command name
            name = re.sub(r'\(.*\)$', '', prefix_desc)  # Remove trailing brackets
            name = re.sub(r'(Operation\s*)?Command\s*$', '', name)  # Remove "Operation Command"
            name = re.sub(r'(?i)^%s' % re.escape(groupname), '', name)   # e.g. for zone2, remove any zone2 prefix.
            name = make_command(name)

            data.setdefault(prefix, OrderedDict())
            data[prefix]['name'] = name
            data[prefix]['description'] = prefix_desc
            data[prefix]['values'] = OrderedDict()

        # We can assume this row tells us a possible argument-suffix for
        # the command, and it's receiver support.
        else:
            value, desc = row[0], row[1]

            # Parse the value - sometimes ranges are given, split those first
            range = re.split(ur'(?<=["”“])-(?=["”“])', value)
            # Then, remove the quotes
            validate = lambda s: re.match(ur'^["”“](.*?)["”]$', s)
            range = [validate(r).groups()[0] for r in range]

            # If it's actually a single value, store as such
            # e.g. "UP" as opposed to "0 - 28".
            if len(range) == 1:
                range = range[0]
                # Replace `xx` to make it clearer it's a placeholder
                range = range.replace('xx', '{xx}')
                # If it's a number, it should always be hex. We could convert
                # to base-10, but why bother. They can just as well be treated
                # as string commands.
                #try:
                #    range = int(range, 16)
                #except ValueError:
                #    pass
            else:
                # If it's a range, output all as 10-base for simplicity.
                range = [int(i, 16) for i in range]
                # Make sure it's hashable
                range = tuple(range)

            # Model support
            support = [re.match(r'(Yes|No)(?:\(\*\))?', c).groups()[0]
                       for c in row[2:]
                       # Sometimes neither Yes or No is given. We assume No
                       # in those cases.
                       if c]
            # Validate we don't miss anything
            assert not any([m not in ('Yes','No') for m in support])

            # Get a final list of mnodel names
            supported_modelcols = [
                model for model, yesno in zip(modelcols, support)
                if yesno == 'Yes']
            supported_models = sum(supported_modelcols, [])  # flatten
            supported_models.sort()
            supported_models = tuple(supported_models)  # make hashable

            # Because the list of models is often so huge, including it
            # directly within the YAML file severely impacts editability and
            # readability. Since in post-processing the keys (command names)
            # are liable to change as well, we can't use those to associate
            # the models lists either.
            if not supported_models in model_sets.values():
                setname = 'set%d' % (len(modelsets)+1)
                model_sets[supported_models] = setname
            else:
                setname = model_sets[supported_models]

            # Fix up the description
            desc = re.sub(r'\*\d*$', '', desc)   # remove footnote refs
            if desc.startswith('sets'):
                # Multiple whitespace here is often used to indicate
                # multiple possible values, make it look nicer.
                desc = re.sub(r'\s\s\s+', ', ', desc)

            # Try to determine a readable name
            def remove_dups(name):
                # The description often repeats parts that are already part
                # of the command name, i.e. the system-power command would
                # have a value power-on, when really only "on" is needed.
                # Remove parts from name that are already in the command.
                command_parts = data[prefix]['name'].split('-')
                return '-'.join([p for p in name.split('-') if not p in command_parts])

            name = None
            if range == 'QSTN':
                name = 'query'
            elif 'nnn' in range or 'bbb' in range:
                # With these sorts of values, we already know we can't get
                # anything useful out of the long descriptions.
                name = None
            # When description tells us it sets something, use the what
            # as the value name. Except: For wrap-around commands it's better
            # to base off the internal name (e.g. up or down).
            elif desc.startswith('sets') and not 'Wrap-Around' in desc:
                name = desc.replace('sets', '')
                name = re.sub(r'\(.*\)$', '', name)  # Remove trailing brackets
                if ',' in name or '/' in name:
                    # Commas here (inserted above) indicate multiple values,
                    # so does /
                    names = re.split(r'[,/]', name)
                    name = [remove_dups(make_command(name)) for name in names]
                    name = FlowStyleTuple(filter(lambda s: bool(s), name))
                else:
                    name = make_command(name)
                    name = remove_dups(name)
            elif isinstance(range, basestring):
                if range == 'TG':
                    name = 'toggle'
                else:
                    # Use the internal command itself, if it's not a range
                    name = re.sub(r'\s*Key$', '', range)   # sometimes ends in key, remove
                    name = make_command(name)

            this = data[prefix]['values'][range] = OrderedDict()
            if name:
                this['name'] = name
            this['description'] = desc
            this['models'] = setname

    return data


with open(sys.argv[1], 'r') as f:
    book = tablib.import_book(f.read())


# Model sets collect unique combinations of supported models.
model_sets = OrderedDict()
data = OrderedDict((
    ('main', import_sheet('main', book.sheets()[4], model_sets)),
    ('zone2', import_sheet('zone2', book.sheets()[5], model_sets)),
    ('zone3', import_sheet('zone3', book.sheets()[6], model_sets)),
    ('zone4', import_sheet('zone4', book.sheets()[7], model_sets)),
    ('dock', import_sheet('dock', book.sheets()[8], model_sets)),
))
data['modelsets'] = OrderedDict(zip(model_sets.values(), model_sets.keys()))



# The following is what it takes to output proper OrderedDicts with PyYAML.

def represent_odict(dump, tag, mapping, flow_style=None):
    """Like BaseRepresenter.represent_mapping, but does not issue the sort().
    """
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if dump.alias_key is not None:
        dump.represented_objects[dump.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = mapping.items()
    for item_key, item_value in mapping:
        node_key = dump.represent_data(item_key)
        node_value = dump.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if dump.default_flow_style is not None:
            node.flow_style = dump.default_flow_style
        else:
            node.flow_style = best_style
    return node

yaml.SafeDumper.add_representer(OrderedDict,
    lambda dumper, value: represent_odict(dumper, u'tag:yaml.org,2002:map', value))
# Be sure to not use flow style, since this makes merging in changes harder.,
# except for special tuples, so we have a way to display small multi-value
# sequences in one line.
yaml.SafeDumper.add_representer(FlowStyleTuple,
    lambda dumper, value: yaml.SafeDumper.represent_sequence(dumper, u'tag:yaml.org,2002:seq', value, flow_style=True))


print """# Last generated
#   by %s
#   from %s
#   at %s
#
# This file can and should be manually changed to fix things the
# automatic import didn't and often can't do right. These changes
# should be tracked in source control, so they can be merged with
# new generated versions of the file.
""" % (os.path.basename(sys.argv[0]), os.path.basename(sys.argv[1]), datetime.now())
print yaml.safe_dump(data, default_flow_style=False)
