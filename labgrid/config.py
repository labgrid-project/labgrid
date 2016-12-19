from collections import OrderedDict

import yaml


def _dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


def _dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))


yaml.add_representer(OrderedDict, _dict_representer)
yaml.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
)


def load_config(filename):
    try:
        with open(filename) as file:
            return yaml.load(file)
    except FileNotFoundError:
        raise NoConfigFoundError(
            "{} could not be found".format(self.config_file)
        )
