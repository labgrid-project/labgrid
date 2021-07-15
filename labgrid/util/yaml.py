"""
This module contains the custom YAML load and dump functions and associated
loader and dumper
"""
from collections import OrderedDict, UserString
from string import Template

import yaml
import os
import re

class Loader(yaml.SafeLoader):
    pass
class Dumper(yaml.SafeDumper):
    pass

# TODO: Is this constructor below important? `<<: *ref` does not work with `OrderedDict`. Produces the following error, though the yaml is valid:
# INTERNALERROR>   File "<attrs generated init labgrid.config.Config>", line 5, in __init__
# INTERNALERROR>     self.__attrs_post_init__()
# INTERNALERROR>   File "/home/test/work/labgrid/labgrid/config.py", line 28, in __attrs_post_init__
# INTERNALERROR>     raise InvalidConfigError("Error in configuration file: {}".format(err))
# INTERNALERROR> labgrid.exceptions.InvalidConfigError: Error in configuration file: could not determine a constructor for the tag 'tag:yaml.org,2002:merge'
# INTERNALERROR>   in "<unicode string>", line 37, column 9:
# INTERNALERROR>             <<: *pdu_resource
# INTERNALERROR>             ^
#
# def _dict_constructor(loader, node):
#     return OrderedDict(loader.construct_pairs(node))


# Loader.add_constructor(
#     yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
# )


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



def _include_block(content: str, remove: bool) -> str:
    ret = ""
    lines = content.splitlines()
    found = False

    for line in lines:
        if not found and re.match("^includes:\\s*(#.*)?$", line):
            found = True
            if not remove:
                ret = ret + line + '\n'
        elif found and re.match("^\\s+\\-\\s[\"'].*[\"']\\s*(#.*)?$", line):
            if not remove:
                ret = ret + line + '\n'
        elif found and re.match("^\\s*$", line):
            # just ignore blank lines in the include block
            pass
        else:
            # this is no longer in the include block
            found = False
            if remove:
                ret = ret + line + '\n'

    return ret


def _get_include_block(content: str) -> str:
    return _include_block(content, remove=False)


def _remove_include_block(content: str) -> str:
    return _include_block(content, remove=True)


def _load_from_content(content: str, base: str) -> str:
    """
    Load a configuration yaml and copy/paste included files.
    """
    include_block = _get_include_block(content)
    ret = _remove_include_block(content)

    if not include_block:
        return ret

    _includes = yaml.load(include_block, Loader=Loader)
    for _include in _includes['includes']:
        print(_include)
        _filename = os.path.join(base, _include)
        _base = os.path.dirname(os.path.abspath(_filename))

        with open(_filename) as _f:
            _content = _f.read()
            ret = _load_from_content(ret + _content, _base)

    return ret


def load(stream, base):
    """
    Wrapper for yaml load function with custom loader.
    """
    mergen_content = _load_from_content(stream.read(), base)
    ret = yaml.load(mergen_content, Loader=Loader)

    return ret


def dump(data, stream=None):
    """
    Wrapper for yaml dump function with custom dumper.
    """
    return yaml.dump(data, stream, Dumper=Dumper, default_flow_style=False)


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
                    "Invalid template string '{}'".format(val.template)
                ) from error

        elif isinstance(val, (list, dict)):
            resolve_templates(val, mapping)
