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
