# https://github.com/miracle2k/onkyo-eiscp/issues/49


import os
from os import path
import yaml


def construct_tuple(loader, node):
    return tuple(yaml.SafeLoader.construct_sequence(loader, node))
yaml.SafeLoader.add_constructor('tag:yaml.org,2002:seq', construct_tuple)


with open('eiscp-commands.yaml', 'r') as f:
  data = yaml.safe_load(f)


modelssets = data.pop('modelsets')


for zone, zone_data in data.items():
  for command, command_data in zone_data.items():
    output_dir = path.join('commands', zone)
    if not path.exists(output_dir):
      os.makedirs(output_dir)

    filename = path.join(output_dir, '%s.yaml' % command)

    for value_data in command_data['values'].values():
      if 'models'  in value_data:
        value_data['models'] = modelssets[value_data['models']]

    with open(filename, 'w') as f:
      yaml.safe_dump(command_data, f, default_flow_style=False)
