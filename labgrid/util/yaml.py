"""
This module contains the custom YAML load and dump functions and associated
loader and dumper
"""

import warnings
from collections import OrderedDict, UserString
from string import Template

import yaml


class Loader(yaml.SafeLoader):
    pass


class Dumper(yaml.SafeDumper):
    pass


def _check_duplicate_dict_keys(loader, node):
    seen_keys = []
    for key_node, _ in node.value:
        key = loader.construct_scalar(key_node)
        if key in seen_keys:
            warnings.warn(
                f"{loader.name}: previous entry with duplicate YAML dictionary key '{key}' overwritten", UserWarning
            )
        seen_keys.append(key)


def _dict_constructor(loader, node):
    _check_duplicate_dict_keys(loader, node)
    return OrderedDict(loader.construct_pairs(node))


Loader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
)
Loader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    yaml.constructor.FullConstructor.construct_python_tuple,
)


def _dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


Dumper.add_representer(OrderedDict, _dict_representer)


def _str_constructor(loader, node):
    # store location of multiline string
    if node.style != '|':
        return loader.construct_scalar(node)
    obj = UserString(loader.construct_scalar(node))
    obj.start_mark = node.start_mark
    obj.end_mark = node.end_mark
    return obj


Loader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG, _str_constructor
)


def _template_constructor(loader, node):
    return Template(loader.construct_scalar(node))


Loader.add_constructor(
    '!template', _template_constructor
)


def load(stream):
    """
    Wrapper for yaml load function with custom loader.
    """
    return yaml.load(stream, Loader=Loader)


def dump(data, stream=None, **kwargs):
    """
    Wrapper for yaml dump function with custom dumper.
    """
    kwargs.pop("Dumper", None)
    return yaml.dump(data, stream, Dumper=Dumper, **kwargs)


def resolve_templates(data, mapping):
    """
    Iterate recursively over data and call substitute(mapping) on all
    Templates.
    """
    if isinstance(data, list):
        items = enumerate(data)
    elif isinstance(data, dict):
        items = data.items()
    else:
        raise TypeError(f"Expected list or dict, got {type(data)}")

    for k, val in items:
        if isinstance(val, Template):
            try:
                data[k] = val.substitute(mapping)
            except ValueError as error:
                raise ValueError(
                    f"Invalid template string '{val.template}'"
                ) from error

        elif isinstance(val, (list, dict)):
            resolve_templates(val, mapping)
