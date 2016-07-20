#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

import os


def load_set(list_path):
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
    return item_set


def load_list(list_path):
    """Read the lines of a file into an ordered list.
    """
    dir_path = os.path.dirname(__file__)
    file_path = os.path.join(dir_path, list_path)
    item_list = []
    with open(file_path) as f:
        for line in f:
            # NOTE: only stripping newlines here
            line = line.rstrip('\n')
            if len(line) == 0 or line.startswith('#'):
                continue
            item_list.append(line)
    return item_list


def load_dict(tsv_path, flip=False):
    """Read a file of tab-separated strings into a dictionary.
    """
    dir_path = os.path.dirname(__file__)
    file_path = os.path.join(dir_path, tsv_path)
    item_map = {}
    num_values = None
    with open(file_path) as f:
        for line in f:
            line = line.rstrip()
            if len(line) == 0 or line.startswith('#'):
                continue

            # Ensure unique keys and a consistent number of values
            if flip:
                # Key is the second field
                all_fields = line.split('\t')
                key = all_fields[1]
                values = [all_fields[0]] + all_fields[2:]
            else:
                key, *values = line.split('\t')

            assert key not in item_map
            if num_values is None:
                assert len(values) > 0
                num_values = len(values)
            else:
                assert len(values) == num_values

            if num_values == 1:
                item_map[key] = values[0]
            else:
                item_map[key] = tuple(values)
    return item_map


# Type descriptors of structured or out-of-domain articles
BAD_DESCRIPTORS = load_set('descriptors.type.lst')

# Indicators of templated or structured articles
BAD_TITLES = load_set('repeated.title.lst')
BAD_LEADS = load_set('repeated.lead.lst')
BAD_SUMMLEADS = load_set('repeated.summlead.lst')
BAD_SUMMS = load_set('repeated.fullsummary.lst')

# Prefixes to be removed from article summaries
BAD_PREFIXES = load_list('prefixes.summlead.lst')

# Resources for identifying stitched words
AMBIGUOUS_STITCHES_SUMM = load_dict('stitches.ambiguous.map')
STITCHES_SUMM = load_dict('stitches.summ.map')
SPLITS_DOC = load_dict('stitches.doc.map', flip=True)
