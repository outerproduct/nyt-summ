#! /usr/bin/env python
# Author: Kapil Thadani (kapil@cs.columbia.edu)

import logging
import re


class Untokenizer(object):
    """A class to untokenize a tokenized sentence. Currently just adjusts
    spacing so that the text appears natural to readers.
    """
    # Commas, periods, semicolons and other punctuation that shouldn't be
    # preceded by a space
    punc_re = re.compile(r"^[\,\.\;\:\%]$")

    # Parentheses
    open_paren_re = re.compile(r"^[\(\[\{\<]$")
    close_paren_re = re.compile(r"^[\)\]\}\>]$")
    close_to_open_parens = {')': '(',
                            ']': '[',
                            '}': '{',
                            '>': '<'}

    # Contractions
    contractions_re = re.compile(r"\'(?:s|t|m|d|re|ve|le)")

    @classmethod
    def untokenize(cls, words, warnings=True):
        """Convert a list of words into a string that reads like natural
        English.
        """
        # Don't add a space before the first word
        add_space_before = False
        add_space_after = True

        # Track paired punctuation symbols for error reporting
        # TODO: Allow branching to multiple stacks to recover from errors
        symbol_stack = []
        unexpected_symbols = []

        spaced_words = []
        for w, word in enumerate(words):

            # Determine spacing before and after the current word
            if re.match(cls.punc_re, word) is not None \
                or re.match(cls.contractions_re, word) is not None \
                    or word == 'n\'t':
                add_space_before = False

            elif word == '\'' or word == '\"':
                if len(symbol_stack) > 0 and symbol_stack[-1] == word:
                    add_space_before = False
                    symbol_stack.pop(-1)
                else:
                    add_space_after = False
                    symbol_stack.append(word)

            elif re.match(cls.open_paren_re, word) is not None:
                add_space_after = False
                symbol_stack.append(word)

            elif re.match(cls.close_paren_re, word) is not None:
                if len(symbol_stack) > 0 \
                        and symbol_stack[-1] == cls.close_to_open_parens[word]:
                    add_space_before = False
                    symbol_stack.pop(-1)
                else:
                    # Just note the erroneous symbol for reporting
                    unexpected_symbols.append(word)

            # Add the current word to the list with the necessary spacing
            if add_space_before:
                spaced_words.append(' ')
            spaced_words.append(word)

            # Set spacing before and after the next word
            add_space_before = add_space_after
            add_space_after = True

        # Construct the untokenized sentences
        string = ''.join(spaced_words)

        # Warn if we had errors in paired punctuation symbols
        if warnings and len(symbol_stack) > 0:
            logging.warn("WARNING: Lopsided punctuation symbols in "
                         + "string: " + string + "\n")
            logging.warn("Symbol stack: " + str(symbol_stack) + "\n")

        elif warnings and len(unexpected_symbols) > 0:
            logging.warn("WARNING: Unexpected closing symbols "
                         + str(unexpected_symbols) + " seen in string: "
                         + string + "\n")

        # Scrub out all erroneous symbols
        # NOTE: preserving unbalanced punctuation
        # error_symbols = symbol_stack + unexpected_symbols
        error_symbols = unexpected_symbols
        if len(error_symbols) > 0:
            scrubbed_words = []
            for word in spaced_words:
                if word not in error_symbols:
                    scrubbed_words.append(word)
            return ''.join(scrubbed_words)
        else:
            return string


def untokenize(tokens, **kwargs):
    return Untokenizer.untokenize(tokens, **kwargs)
