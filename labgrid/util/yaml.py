from collections import OrderedDict, UserString
from string import Template

import yaml

def _dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))
yaml.SafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
)

def _dict_representer(dumper, data):
    return dumper.represent_dict(data.items())
yaml.SafeDumper.add_representer(OrderedDict, _dict_representer)


def _str_constructor(loader, node):
    # store location of multiline string
    if node.style != '|':
        return loader.construct_scalar(node)
    obj = UserString(loader.construct_scalar(node))
    obj.start_mark = node.start_mark
    obj.end_mark = node.end_mark
    return obj
yaml.SafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG, _str_constructor
)


def _template_constructor(loader, node):
    return Template(loader.construct_scalar(node))
yaml.SafeLoader.add_constructor(
    '!template', _template_constructor
)


# use SafeLoader
loader = yaml.SafeLoader
dumper = yaml.SafeDumper

def load(stream):
    return yaml.load(stream, Loader=loader)

def dump(data, stream=None):
    return yaml.dump(data, stream, Dumper=dumper, default_flow_style=False)

def resolve_templates(data, mapping):
    """
    Iterate recursively over data and call substitute(mapping) on all
    Templates.
    """
    if isinstance(data, list):
        items = enumerate(data)
    elif isinstance(data, dict):
        items = data.items()
    for k, v in items:
        if isinstance(v, Template):
            try:
                data[k] = v.substitute(mapping)
            except ValueError as e:
                raise ValueError(
                    "Invalid template string '{}'".format(v.template)
                ) from e

        elif isinstance(v, (list, dict)):
            resolve_templates(v, mapping)
