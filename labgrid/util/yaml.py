"""
This module contains the custom YAML load and dump functions and associated
loader and dumper
"""
from collections import OrderedDict, UserString
from string import Template
from ..exceptions import InvalidConfigError
import os
import yaml
import six

class Loader(yaml.SafeLoader):

    def __init__(self, stream):
        """Initialise Loader."""
        try:
            self._root = os.path.split(stream.name)[0]
        except AttributeError:
            self._root = os.path.curdir
        super().__init__(stream)

class Dumper(yaml.SafeDumper):
    pass

def _construct_include(loader: Loader, node: yaml.Node):
    """Include file referenced at node."""

    filename = os.path.abspath(os.path.join(loader._root, loader.construct_scalar(node)))
    extension = os.path.splitext(filename)[1].lstrip('.')

    with open(filename, 'r') as f:
        if extension in ('yaml', 'yml'):
            return yaml.load(f, Loader)
        elif extension in ('json', ):
            return json.load(f)
        else:
            return ''.join(f.readlines())

def _dict_constructor(loader, node):
    return OrderedDict(loader.construct_pairs(node))

Loader.add_constructor('!include', _construct_include)

Loader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
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


def dump(data, stream=None):
    """
    Wrapper for yaml dump function with custom dumper.
    """
    return yaml.dump(data, stream, Dumper=Dumper, default_flow_style=False)

def data_merge(a, b):
    """
    merges a yaml file into another
    """

    try:
        if isinstance(a, dict) and isinstance(b,dict):
            for key in b:
                if key in a:
                    a[key] = data_merge(a[key], b[key])
                else:
                    a[key] = b[key]
        elif isinstance(a, list):
            if isinstance(b, list):
                a.extend(b)
            else:
                a.append(b)
        elif a is None or isinstance(a, (six.string_types, float, six.integer_types)):
            a = b
        else:
            raise InvalidConfigError('Datatype not supported "%s" into "%s"' % (type(b), type(a)))
    except TypeError as e:
        raise InvalidConfigError('Error when merging type "%s" into "%s"' % (e, type(b), type(a)))
    return a

def resolve_includes(data):
    """
    Iterate recursively over the data and merge all includes
    """
    if isinstance(data, list):
        items = enumerate(data)
    elif isinstance(data, dict):
        items = data.items()
    for k, val in items:
        if k == 'includes':
            data.pop(k)
            for l in val:
                l = resolve_includes(l)
                data = data_merge(data, l)
    return data

def resolve_templates(data, mapping):
    """
    Iterate recursively over data and call substitute(mapping) on all
    Templates.
    """
    if isinstance(data, list):
        items = enumerate(data)
    elif isinstance(data, dict):
        items = data.items()
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
