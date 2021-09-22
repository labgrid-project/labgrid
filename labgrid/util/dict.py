"""
This module contains helper functions for working with dictionaries.
"""
import warnings

import attr


def diff_dict(old, new):
    """
    Compares old and new dictionaries, yielding for each difference (key,
    old_value, new_value).
    None is used for missing values.
    """
    for key in sorted(old.keys() | new.keys()):
        v_old = old.get(key)
        v_new = new.get(key)
        if v_old != v_new:
            yield key, v_old, v_new


def flat_dict(d):
    def flatten(d, prefix=()):
        for key, value in d.items():
            key = prefix + (key,)
            if isinstance(value, dict):
                yield from flatten(value, prefix=key)
            else:
                yield '.'.join(key), value
    return dict(flatten(d))


def filter_dict(d, cls, warn=False):
    """
    Returns a copy a dictionary which only contains the attributes defined on
    an attrs class.
    """
    assert attr.has(cls)
    fields = set(a.name for a in attr.fields(cls))
    if warn:
        remove = set(d) - fields
        for k in sorted(remove):
            warnings.warn(
                f"unsupported attribute '{k}' with value '{d[k]}' for class '{cls.__name__}'",
                stacklevel=2
            )
    return {k: v for k, v in d.items() if k in fields}

def find_dict(d, key):
    """
    Recursively search for a key in a dictionary

    Args:
        d (dict): The dictionary to recursively search through
        key (str): The key to search for
    """
    if key in d:
        return d[key]
    for v in d.values():
        if isinstance(v, dict):
            value = find_dict(v, key)
            if value is not None:
                return value
