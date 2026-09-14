#!/usr/bin/env python

"""Helpers for displaying and navigating nested context data."""

import json


def normalize_json_values(value):
    """Recursively decode strings containing JSON objects or arrays.

    JSON scalar strings are deliberately preserved so ordinary values such as
    ``"true"`` or ``"42"`` do not unexpectedly change type.
    """
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return value

        if isinstance(decoded, (dict, list)):
            return normalize_json_values(decoded)
        return value

    if isinstance(value, dict):
        return {
            key: normalize_json_values(nested_value)
            for key, nested_value in value.items()
        }

    if isinstance(value, list):
        return [normalize_json_values(item) for item in value]

    return value


def resolve_data_path(data, path):
    """Return ``(found, value)`` for a dot-separated dict/list path."""
    if not path:
        return False, None

    current = data
    for segment in path.split('.'):
        if not segment:
            return False, None

        if isinstance(current, dict):
            if segment not in current:
                return False, None
            current = current[segment]
        elif isinstance(current, list):
            if not segment.isdigit():
                return False, None
            index = int(segment)
            if index >= len(current):
                return False, None
            current = current[index]
        else:
            return False, None

    return True, current


def complete_data_path(data, prefix):
    """Return context-aware completions for a partially entered data path."""
    found, exact_value = resolve_data_path(data, prefix)
    if found and isinstance(exact_value, (dict, list)):
        parent_path = prefix
        partial = ''
        parent = exact_value
    elif '.' in prefix:
        parent_path, partial = prefix.rsplit('.', 1)
        found, parent = resolve_data_path(data, parent_path)
        if not found:
            return []
    else:
        parent_path = ''
        partial = prefix
        parent = data

    if isinstance(parent, dict):
        children = [str(key) for key in parent]
    elif isinstance(parent, list):
        children = [str(index) for index in range(len(parent))]
    else:
        return []

    matches = sorted(child for child in children if child.startswith(partial))
    if not parent_path:
        return matches
    return [f"{parent_path}.{child}" for child in matches]
