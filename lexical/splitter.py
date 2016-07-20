#! /usr/bin/env python
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from .wordlists import load_set
from nltk.tokenize import punkt
import re


WHITESPACE = [' ', '\xA0']
ALL_DASHES = ['-', '–', '—', '\xAD']
EOS_PUNCTS = ['.', '!', '?']
CLS_PARENS = [')', ']', '}']
OPN_PARENS = ['(', '[', '{']
SNG_QUOTES = ['\'', '`', '‘', '’', '\x91', '\x92']
DBL_QUOTES = ['\"', '“', '”', '\x93', '\x94']


# Bad suffixes preceding a split boundary consist of common abbreviations
# which either start the sentence or are preceded by a non-word symbol.
abbrevs = load_set('abbreviations.lst', add_uppercased=True)
bad_suffixes_re = re.compile('^(?:.*\W)?({0})$'.format(
                             '|'.join(re.escape(abbrev)
                                      for abbrev in abbrevs)))

# Bad prefixes following a split boundary consist of common parenthetical-
# and sentence-ending symbols followed by quotes or spaces.
bad_prefixes_re = re.compile('^([{0}{1}{2}{3}]+s?)(?:[{4}].*)?$'.format(
                             ''.join(re.escape(x) for x in CLS_PARENS),
                             ''.join(re.escape(x) for x in SNG_QUOTES),
                             ''.join(re.escape(x) for x in DBL_QUOTES),
                             ''.join(re.escape(x) for x in EOS_PUNCTS),
                             ''.join(re.escape(x) for x in WHITESPACE)),
                             re.UNICODE)


class Splitter:
    """A sentence splitter that uses the Punkt tokenizer from NLTK but
    adds a bunch of fixes.
    """
    def __init__(self):
        """Initialize the bad prefixes and suffixes surrounding splits.
        """
        self.punkt_splitter = punkt.PunktSentenceTokenizer()
        self.whitespace = set(WHITESPACE)

    def split(self, text, fix=True):
        """Split text into sentences using the Punkt Sentence
        Tokenizer from NLTK with some post-processing.
        """
        sents = self.punkt_splitter.tokenize(text)

        if not fix:
            return sents
        return self.fix_boundaries(sents, text)

    def fix_boundaries(self, sents, text, debug=False):
        """Re-merge sentences which seem to have been incorrectly split based
        on their suffixes and move around new sentence prefixes.
        """
        fixed_sents = []
        prev_sent = ''
        prev_gap_len = 0
        i = 0  # offset in text where the next sentence would start
        for s, sent in enumerate(sents):
            i += len(sent)
            if debug:
                print(s, i, text[max(i-3, 0):min(i+3, len(text))])

            if len(prev_sent) > 0:
                # Merge entire sentence back
                gap = ' ' * prev_gap_len
                sent = gap.join((prev_sent, sent))

            elif len(fixed_sents) > 0:
                # Merge back bad prefixes and keep the rest of the sentence
                bad_prefix = self.check_prefix(sent)
                if bad_prefix is not None:
                    # Merge prefix back
                    gap = ' ' * prev_gap_len
                    fixed_sents[-1] += gap + bad_prefix

                    # Remove prefix from current sentence
                    j = len(bad_prefix)
                    j += self.consume_whitespace(text, j, self.whitespace)
                    sent = sent[j:]

            # Update i and determine the amount of trailing whitespace for
            # forthcoming merges
            prev_gap_len = 0
            if s < len(sents) - 1:
                prev_gap_len += self.consume_whitespace(text, i,
                                                        self.whitespace)
                i += prev_gap_len

            # Stripping the bad prefix may have resulted in a blank sentence
            if len(sent) == 0:
                prev_sent = ''
                continue

            if self.check_suffix(sent) is not None:
                # Awaiting future merge
                prev_sent = sent
            else:
                # Looks like a good split so far (may merge in a prefix later)
                prev_sent = ''
                fixed_sents.append(sent)

        if i != len(text) and not debug:
            # Rerun with debug
            print(i, "!=", len(text))
            print(sents)
            print(text)
            self.fix_boundaries(sents, text, debug=True)
        assert i == len(text)

        # Last sentence
        if len(prev_sent) > 0:
            fixed_sents.append(prev_sent)

        return fixed_sents

    @staticmethod
    def check_prefix(sent):
        """Check whether a sentence has a bad prefix.
        """
        # If the first alphanumeric character in the sentence is a lowercase
        # letter, the whole sentence is a bad prefix.
        for i in range(len(sent)):
            if not sent[i].isalnum():
                # Only alphanumerics
                continue

            if sent[i].isdigit() or (sent[i].isalpha() and sent[i].isupper()):
                # Starts with a number or uppercase letter
                break

            if sent[i].islower():
                # Starts with a lowercase letter
                return sent

        # No uncapitalized starting word so look for dangling parens, quotes
        # and sentence terminators, e.g., ''United States (U.S.)''.
        match = bad_prefixes_re.match(sent)
        if match is not None:
            return match.group(1)

        # Looks good
        return None

    @staticmethod
    def check_suffix(sent):
        """Check whether a sentence has a bad suffix, implying that perhaps
        we shouldn't have split on it.
        """
        # To quickly catch abbreviations like a.m., U.S., A.D., etc, check
        # whether a reverse find encounters a second period before a space.
        if sent.endswith('.'):
            i = -1

            while sent[i] != ' ':
                i -= 1
                if i < -len(sent):
                    break

                # Doesn't apply to digits, e.g., It costs 179.99.
                if sent[i].isdigit():
                    break

                if sent[i] == '.':
                    # Found a period before a space
                    return sent[sent.rfind(' ') + 1:]

        # No multi-period abbreviations, so check the dictionary of
        # single-period abbreviations.
        match = bad_suffixes_re.match(sent)
        if match is not None:
            return match.group(1)

        # Looks good
        return None

    @staticmethod
    def consume_whitespace(text, idx, whitespace):
        """Return the amount of whitespace at and following the given character
        index.
        """
        count = 0
        while idx < len(text) and text[idx] in whitespace:
            idx += 1
            count += 1
        return count


def split(string, splitter=Splitter(), **kwargs):
    return splitter.split(string, **kwargs)
