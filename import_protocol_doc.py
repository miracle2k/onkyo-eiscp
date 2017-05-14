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


def is_known_footer(string):
    """Sometimes the excel has a footer for a command section and
    we cannot very reliably differentiate it from a command value
    (actually, it might be possible, but this appraoch is easier).
    """

    if not string:
        return False

    lines = [
        'If Jacket Art is disable from one',
        'Please refer to sheets of popup xml,',
        'Line Separator : " ・ "（0x20, 0xC2, 0xB7, 0x20'
    ]

    for line in lines:
        if line in string:
            return True

    return False


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
    max_model_column = len([s for s in modelcols if bool(s)]) + 2


    def loop_rows(data):
        it = iter(data)

        while True:
            row = next(it)

            # Special case with many many rows we have to skip
            # (the NRI query command)
            if row[0] and 'ex.)XML data' in row[0]:
                while True:
                    row = next(it)
                    if row[0] and 'NET Custom Popup' in row[0]:
                        break

            else:
                yield row


    prefix = prefix_desc = None
    for row in loop_rows(sheet[1:]):
        # Remove right-most columns that no longer belong to the main table
        row = row[:max_model_column]

        # Remove whitespace from all fields
        row = [str(s).strip() if s else s for s in row]

        #print row

        # Ignore empty lines
        if not any(row):
            continue

        # Excel format is as such:
        # First, there is a row that defines the command prefix,
        # e.g. "PWR" for power. We can recognize that by the fact that
        # the model colums are all empty.
        #
        # What follows in subsequent rows are the different values that
        # can be appended to the prefix, to make up the full command,
        # e.g. "PWR01".
        #
        # One exception are footer lines below all the values which
        # contain extra information about the command. These are difficult
        # to recognize.

        # Try to recognize command footers. Footnotes often start with *.
        if (row[0].strip().startswith('*') and not row[1]) or is_known_footer(row[0]):
            continue

        # Let's recognize command prefix headers. The data in
        # those rows looks something like
        # ``"PWR" - System Power Command ``, and we need to parse it.
        elif not any(row[1:]):
            # Ignore a variety of text rows that are similar to a prefix header.
            # We need to grasp at straws here, since we can't look at the
            # row color, which would also tell us if it's a header.
            if row[0].strip().startswith('*'):
                continue
            if 'when' in row[0] or 'Ex:' in row[0] or 'is shared' in row[0]:
                continue

            # operation command, command, brakets
            prefix, prefix_desc = re.match(r'"?(.*?)"? -\s?(.*)', row[0]).groups()

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

            if not re.search(r'["”“]', value):
                range = value
            else:
                # Parse the value - sometimes ranges are given, split those first
                range = re.split(r'(?<=["”“])-(?=["”“])', value)
                # Then, remove the quotes
                validate = lambda s: re.match(r'^["”“](.*?)["”]$', s)
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

                    # TODO: This will fail in a number of cases where
                    # values given as in -10...0...+10
                    # Beginning from now we want to rewrite this
                    # to -10 to 10, with a default of 0. The default
                    # seems to be always 0. I am not sure if this is
                    # a true default either, or some kind of strange
                    # range notation Onkyo uses. In any case, the logic
                    # to parse these ranges into simple pairs is still
                    # missing. I add this check as a reminder to myself.
                    # The YAML already has been manually adjusted.
                    assert len(range) == 2

            # Model support
            def parse_support(s):
                # Sometimes neither Yes or No is given. We
                # assume No in those cases.
                if not s:
                    return False

                m = re.match(r'(Yes|No)(?:\(\*\))?', c)
                if not m:
                    # Sometimes it doesn't say Yes or No, but as string
                    # such as RS232C. It seems that this notes always
                    # imply YES. We log yes and ignore the extra
                    # information.
                    return "Yes"
                return m.groups()[0]

            support = ['Yes' if parse_support(c) else 'No' for c in row[2:]]
            # Validate we don't miss anything
            assert len(support) == len(modelcols) == len(row[2:])
            assert not any([m not in ('Yes','No') for m in support])

            # Get a final list of model names
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
            if not supported_models in model_sets:
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
                return '-'.join(
                    [p for p in name.split('-')
                     if not p in command_parts and not p == groupname.lower()])

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
                    name = FlowStyleTuple([s for s in name if bool(s)])
                else:
                    name = make_command(name)
                    name = remove_dups(name)
            elif isinstance(range, str):
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
    try:
        book = tablib.Databook().load('xlsx', f.read())
    except Exception as e:
        raise


# Model sets collect unique combinations of supported models.
model_sets = OrderedDict()
data = OrderedDict((
    ('main', import_sheet('main', book.sheets()[4], model_sets)),
    ('zone2', import_sheet('zone2', book.sheets()[5], model_sets)),
    ('zone3', import_sheet('zone3', book.sheets()[6], model_sets)),
    ('zone4', import_sheet('zone4', book.sheets()[7], model_sets)),
    ('dock', import_sheet('dock', book.sheets()[8], model_sets)),
))
data['modelsets'] = OrderedDict(list(zip(list(model_sets.values()), list(model_sets.keys()))))



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
        mapping = list(mapping.items())
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
    lambda dumper, value: represent_odict(dumper, 'tag:yaml.org,2002:map', value))
# Be sure to not use flow style, since this makes merging in changes harder.,
# except for special tuples, so we have a way to display small multi-value
# sequences in one line.
yaml.SafeDumper.add_representer(FlowStyleTuple,
    lambda dumper, value: yaml.SafeDumper.represent_sequence(dumper, 'tag:yaml.org,2002:seq', value, flow_style=True))


print("""# Last generated
#   by %s
#   from %s
#   at %s
#
# This file can and should be manually changed to fix things the
# automatic import didn't and often can't do right. These changes
# should be tracked in source control, so they can be merged with
# new generated versions of the file.
""" % (os.path.basename(sys.argv[0]), os.path.basename(sys.argv[1]), datetime.now()))
print(yaml.safe_dump(data, default_flow_style=False))
