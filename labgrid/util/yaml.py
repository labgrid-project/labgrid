from collections import OrderedDict

import yaml

def _dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))
yaml.SafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
)

def _dict_representer(dumper, data):
    return dumper.represent_dict(data.items())
yaml.SafeDumper.add_representer(OrderedDict, _dict_representer)


# use SafeLoader
loader = yaml.SafeLoader
dumper = yaml.SafeDumper

def load(stream):
    return yaml.load(stream, Loader=loader)

def dump(data, stream=None):
    return yaml.dump(data, stream, Dumper=dumper, default_flow_style=False)
