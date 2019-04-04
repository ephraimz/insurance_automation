def deep_get(dictionary, keys, default=None):
    v = dictionary
    for k in keys.split('.'):
        if isinstance(v, dict) and k in v:
            v = v[k]
        else:
            return default
    return v


def has_all_needed_keys(dictionary, keys):
    return all(map(lambda x: x in dictionary, keys))
