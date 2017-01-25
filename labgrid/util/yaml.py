from collections import OrderedDict

import yaml

def _dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))
yaml.SafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
)

# use SafeLoader
loader = yaml.SafeLoader

def load(file):
    return yaml.load(file, loader)
