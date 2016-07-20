#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

import os


def load_set(list_path, add_lowercased=False, add_uppercased=False,
             add_capitalized=False):
    """Read the lines of a file into a set.
    """
    dir_path = os.path.dirname(__file__)
    file_path = os.path.join(dir_path, list_path)
    item_set = set()
    with open(file_path) as f:
        for line in f:
            line = line.rstrip()
            if len(line) == 0 or line.startswith('#'):
                continue
            item_set.add(line)
            if add_lowercased:
                item_set.add(line.upper())
            if add_uppercased:
                item_set.add(line.upper())
            if add_capitalized:
                item_set.add(line.capitalize())
    return item_set
