#! /usr/bin/env python
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from .sanitizer import Sanitizer
import html
import re
import sys


class Tokenizer(object):
    """A class to tokenize a sentence in a standard way.
    """
    def __init__(self, sanitizer=Sanitizer()):
        """Precompile regular expressions for tokenization. Since many regex
        operations will be performed consecutively, the inbuilt pattern object
        caching will be overwhelmed and patterns will be repeatedly recompiled.
        """
        # Default argument sanitizer will only be initialized once
        self.sanitizer = sanitizer

        # HTML non-breaking spaces and numeric references.
        self.nbsp_re = re.compile(r"&nbsp;|&#160;|&#xA0;", re.IGNORECASE)

        # Periods must not be separated out unless they terminate a sentence in
        # which case they are regarded as punctuation. Other uses of periods
        # (abbreviations, decimal points) should attach to the preceding word.
        # Ellipses should be normalized and separated from words.
        self.non_eos_period_re = re.compile(r"\s*\.(?!\s*[\.\"\'])(?=\.*\w)")
        self.eos_period_re = re.compile(r"(?<!\.)\.\s*([\"\']*)\s*$")
        self.ellipse_re = re.compile(r"\.{2,}")

        # ,:;/ are symbols that must be separated out as long as they aren't
        # in the middle of numbers.
        self.nonnumeric_punc_re = re.compile(r"(.?)([,:;/])(.?)")

        # !? are always standard punctuation and must be separated out in the
        # same manner as the above cases. Repeated ?! punctuation must also be
        # collapsed into the first symbol.
        self.punctuation_re = re.compile(r"([!?])[!?1]*")

        # Some punctuation can be found within words in place of unknown
        # characters eg. C?te D' Ivoire (from RTE). We try to replace these
        # with underscores.
        self.inner_punctuation_re = re.compile(r"(\w*)[!?]+(\w+)")

        # Normalize monetary amounts expressed in $ and USD
        self._init_money_re()

        # Some symbols are used in place of words
        # TODO: this doesn't handle twitter-like annotation (@person, #hashtag)
        self.replacement_re = re.compile(r"([+=@&#%])")
        self.replacement_map = {'+': ' and ',
                                '=': ' equals ',
                                '&': ' and ',
                                '@': ' at ',
                                '#': ' number ',
                                '%': ' percent '}

        # In some cases, entire words need to be replaced. For now, this just
        # includes the contraction-like 'cannot' which is split up to be
        # consistent with the treatment of 'can\'t'.
        self.lex_replacement_res = self.get_lex_res({'cannot': 'can not'})

        # Single hyphenations must remain unseparated if surrounded by word
        # characters. Double hyphens indicate long dashes and should always
        # be separated.
        # TODO: also handle em-dashes and en-dashes
        self.hyphen_re = re.compile(r"(.?)\-(\-*)(.?)")

        # Parentheses {}[]() should be separated out
        self.parens_re = re.compile(r"([\[\]\(\)\{\}])")

        # Double quotes should be normalized and separated
        # TODO: Handle cases in which quoted text includes
        # statement-terminating commas or periods, e.g. He said "I see."
        self.double_quotes_re = re.compile(r"\'\'|\`\`|\"+|“|”|\x93|\x94|"
                                           r"\u201e")

        # Single quotes should be separated out unless they indicate
        # contractions or possessives
        self._init_apostrophe_re()

        # _~^* are unexpected symbols and must be stripped
        # TODO: Should leftover symbols from earlier expressions also be
        # added here?
        self.unexpected_re = re.compile(r"[\\_~^*\`|]")

        # Basic spaces for final tokenization
        self.whitespace_re = re.compile(r" +")

    def tokenize(self, string, warnings=True):
        """Tokenize the string according to predetermined standard rules.
        """
        self.sanitizer.mask_all(string)

        # Strategy: add spaces around everything that needs to be tokenized
        # and then clean up the redundant spaces.

        # Replace HTML spaces with whitespace
        string = re.sub(self.nbsp_re, " ", string)

        # Replace named and numeric HTML character references with their
        # Unicode equivalents
        string = html.unescape(string)

        # Separate sentence-terminating periods and remove spaces before all
        # other periods in the sentence. Ellipses are normalized and separated
        # out. TODO: should quotes not be brought in before EOS periods?
        string = re.sub(self.non_eos_period_re, ".", string)
        string = re.sub(self.eos_period_re, "\\1 .", string)
        string = re.sub(self.ellipse_re, " ... ", string)

        # Separate out ,:;/ as long as they aren't in the middle of numbers
        string = re.sub(self.nonnumeric_punc_re, self.handle_nonnumeric_punc,
                        string)

        # Separate out ?! symbols, collapsing repeated symbols first
        string = re.sub(self.punctuation_re, " \\1", string)

        # Replce inner ?! symbols with underscores
        string = re.sub(self.inner_punctuation_re, " \\1_\\2", string)

        # Replace symbols that have a textual equivalent
        # Disabled for compatibility with OpenNLP
        # string = re.sub(self.replacement_re, self.handle_replacements,
        #                 string)

        # Replace entire words.
        # for lex_replacement_re, replacement in self.lex_replacement_res:
        #     string = re.sub(lex_replacement_re, replacement, string)

        # Normalize monetary amounts expressed in dollars
        # Disabled for compatibility with OpenNLP
        # string = re.sub(self.money_re, self.handle_money, string)

        # Separate out double-hyphenations and reduce to a single one
        string = re.sub(self.hyphen_re, self.handle_hyphens, string)

        # Separate out parentheses
        string = re.sub(self.parens_re, " \\1 ", string)

        # Normalize and separate out double quotes
        string = re.sub(self.double_quotes_re, " \" ", string)

        # Separate out single quotes that aren't possessives or contractions
        string = re.sub(self.apostrophe_re,
                        lambda x: self.handle_apostrophes(x,
                                                          warnings=warnings),
                        string)

        # Strip out unexpected symbols
        string = re.sub(self.unexpected_re, "", string)

        self.sanitizer.unmask_all(string)

        # Finally, tokenize the string by stripping leading and trailing spaces
        # and then splitting on consecutive whitespace (default split behavior)
        string.strip()
        tokens = string.split()

        return tokens

    def handle_nonnumeric_punc(self, match):
        """Handle punctuation symbols that should be separated out by spaces
        as long as they aren't within digits. For example:
         - periods as decimal points
         - commas/periods in large numbers (like 32,000)
         - colons in time patterns (like hh:mm:ss)
         - forward-slashes in date patterns (like dd/mm/yyyy)
        """
        (prev_char, symbol, foll_char) = match.groups()

        if prev_char.isdigit() and foll_char.isdigit():
            # Return original string
            return match.group(0)
        else:
            # Return
            return ''.join((prev_char, ' ', symbol, ' ', foll_char))

    def handle_replacements(self, match):
        """Handle punctuation symbols that should be replaced with words in an
        informal genre setting. For example:
         - + "and"
         - = "equals"
         - @ "at"
         - & "and"
         - # "number"
         - % "percent"
        """
        return self.replacement_map[match.group(1)]

    def _init_money_re(self):
        """Initialize a regular expression for detecting currency amounts
        expressed in US dollars.
        """
        # TODO: expand to GBP (unicode: \xc2\xa3)
        # TODO: incorporate word amounts?
        # TODO: steal RE_NUMERIC regex from NLTK Punkt?
        amount = r"\-?\d(?:\d|,\d)*(?:\.\d+)?"
        currency = "(?:%s)" % "|".join((r"\$",
                                        r"U\.?S\.?\s?\$",
                                        r"U\.?S\.?D\.?"))
        multipliers = "(?:%s)" % "|".join(("[kmbt]",
                                           "hundred",
                                           "thousand",
                                           "mil", "million",
                                           "bil", "billion",
                                           "trillion"))

        money = r"""
            %(currency)s            # Currency markers like $, USD, Us $ etc
            \s*
            (%(amount)s)            # Numerical amount, stored in \1
            (?:\s*
                (%(multiplier)s)    # Multiplier (K, million etc), stored in \2
            )?
            \b
            """ % {'amount': amount,
                   'currency': currency,
                   'multiplier': multipliers}

        self.money_re = re.compile(money, re.VERBOSE | re.IGNORECASE)

        # Add in transformations for the multipliers to keep things standard
        self.multiplier_map = {'k': 'thousand',
                               'm': 'million',
                               'mil': 'million',
                               'b': 'billion',
                               'bil': 'billion',
                               't': 'trillion'}

    def handle_money(self, match):
        """Process monetary amounts expressed in dollars such as $1, $33.5,
        USD 4.5 million etc and normalize them to a standard form.
        """
        (amount, multiplier) = match.groups()

        if multiplier is None:
            return ' '.join(("$", amount))
        else:
            # Normalize the multiplier to a standard form
            try:
                normalized_multiplier = self.multiplier_map[multiplier.lower()]
            except KeyError:
                normalized_multiplier = multiplier.lower()
            return ' '.join(("$", amount, normalized_multiplier))

#        if match.group(1) == '1':
#            return '1 dollar'
#        else:
#            return match.group(1) + ' dollars'

    def handle_hyphens(self, match):
        """Determine whether a hyphen symbol is a short dash between words or a
        long dash between clauses and separate accordingly.
        """
        (prev_char, repetition, foll_char) = match.groups()

        # If there are two or more hyphens, this is a long dash
        # TODO: Should this return one hyphen or two?
        if len(repetition) > 0:
            return ''.join((prev_char, " -- ", foll_char))

        # If there is a space on either side of the hyphen, this is a long dash
        elif prev_char == ' ' or foll_char == ' ':
            return ''.join((prev_char, " - ", foll_char))

        # Otherwise, it is in between two non-space characters and must be
        # a short dash
        else:
            return match.group(0)

    def _init_apostrophe_re(self):
        """Initialize a regular expression for picking up characters around
        single quotes that enable the identification of contractions and
        possessives.
        """
        single_quotes = '(?:%s)' % '|'.join(('\'', '‘', '’', '\x91', '\x92'))
        suffixes = '(?:%s)' % '|'.join(('s', 't', 'm', 'd', 're', 've', 'll'))

        apostrophe = r"""
            (.?)                    # Any character, stored in group \1
            (.?)                    # Any character, stored in group \2
            %(single_quote)s        # Apostrophe symbol
            (?:
                (%(suffix)s\b)      # Contraction suffix, stored in group \3
                |                   # or
                (.?)                # Any character, stored in group \4
            )
            """ % {'single_quote': single_quotes, 'suffix': suffixes}

        self.apostrophe_re = re.compile(apostrophe, re.VERBOSE | re.IGNORECASE)
        self.open_quote = False

    def handle_apostrophes(self, match, warnings=True):
        """Determine whether a particular apostrophe represents a single quote
        or a contraction/possessive and add spaces accordingly.
        """
        (prev_prev_char, prev_char, contraction, foll_char) = match.groups()

        # If apostrophe indicates a contraction
        if contraction:
            if contraction == 't':
                # Separate the entire negation suffix out
                if prev_char == 'n':
                    return ''.join((prev_prev_char, ' n\'t'))
                elif prev_prev_char == 'n' and prev_char == ' ':
                    return ' n\'t'
            elif contraction == 'T':
                # Separate the entire negation suffix out
                if prev_char == 'N':
                    return ''.join((prev_prev_char, ' N\'T'))
                elif prev_prev_char == 'N' and prev_char == ' ':
                    return ' N\'T'
            else:
                return ''.join((prev_prev_char, prev_char, " \'", contraction))

        # If apostrophe is preceded by a space
        elif prev_char.isspace() or prev_char == '':
            # Note that we've seen an open quote and separate it out
            self.open_quote = True
            return ''.join((prev_prev_char, prev_char, "\' ", foll_char))

        # If apostrophe is followed by a space
        elif foll_char.isspace() or foll_char == '':
            if self.open_quote:
                # If we have an unresolved open quote, expect a closing quote
                self.open_quote = False
                return ''.join((prev_prev_char, prev_char, " \'", foll_char))
            elif prev_char == 's':
                # We check if it might be a possessive on a word ending in s
                return ''.join((prev_prev_char, prev_char, '\'s', foll_char))
            elif prev_char == 'S':
                # Ditto for uppercase
                return ''.join((prev_prev_char, prev_char, '\'S', foll_char))
            elif prev_char == 'n' and prev_prev_char == 'i':
                # It might be an affected contraction of the suffix 'ing'
                return ''.join((prev_prev_char, prev_char, 'g', foll_char))
            elif prev_char == 'N' and prev_prev_char == 'I':
                # Ditto for uppercase
                return ''.join((prev_prev_char, prev_char, 'G', foll_char))
            else:
                # Or we might not be able to place it, in which case we don't
                # add or remove anything
                if warnings:
                    sys.stderr.write("WARNING: Unexpected apostrophe usage: "
                                     + match.group(0) + "\n")
                    sys.stderr.write(match.string + "\n")
                return match.group(0)

        # If apostrophe is in the middle of text but not a known contraction
        else:
            if foll_char.isupper():
                # Last names like O'Connor, O'Brien, D'Souza etc and brands
                # like L'Oreal.
                return match.group(0)
            elif foll_char.isnumeric():
                # Contractions of years like '97, '15, etc.
                return match.group(0)
            else:
                if warnings:
                    sys.stderr.write("WARNING: Non-contraction apostrophe "
                                     "usage: " + match.group(0) + "\n")
                    sys.stderr.write(match.string + "\n")
                return match.group(0)

    def normalize_contractions(self, sentence):
        """Normalize contractions in text through regular expressions.
        """
        pass
#    	# TODO Expand contractions [THIS NEEDS POS TAGS]
# 	    $sentence =~ s/(\w+)n\'t/$1 not/gi;
# 	    $sentence =~ s/(\w+)\'m/$1 am/gi;
# 	    $sentence =~ s/(\w+)\'re/$1 are/gi;
# 	    $sentence =~ s/(\w+)\'ll/$1 will/gi;
# 	    $sentence =~ s/(\w+)\'d/$1 would/gi;    # OR had,
#                                               # based on tense of next verb?
# 	    $sentence =~ s/(\w+)\'ve/$1 have/gi;
#
# 	    #Expand 's contractions (ambiguous because of possessives)
# 	    $sentence =~ s/(there|here|that|it|he|she)\'s/$1 is/gi;
# 	    $sentence =~ s/(who|what|when|where|why|how)\'s/$1 is/gi;
# 	    $sentence =~ s/let\'s/let us/gi;

    @classmethod
    def get_lex_res(self, lex_map):
        """Return a list of pairs of compiled regular expressions
        and their target substitutions for each lexical replacement,
        including variants for capitalized and uppercased words.
        """
        lex_replacement_res = []
        for word, replacement in lex_map.items():
            lex_re = re.compile(r"\b" + re.escape(word) + r"\b")
            lex_replacement_res.append((lex_re, replacement))

            capitalized_word = word.capitalize()
            if capitalized_word not in lex_map:
                lex_re = re.compile(
                    r"\b" + re.escape(capitalized_word) + r"\b")
                lex_replacement_res.append((lex_re, replacement.capitalize()))

            uppercased_word = word.upper()
            if len(word) > 1 and uppercased_word not in lex_map:
                lex_re = re.compile(
                    r"\b" + re.escape(uppercased_word) + r"\b")
                lex_replacement_res.append((lex_re, replacement.upper()))

        return lex_replacement_res


def tokenize(string, tokenizer=Tokenizer(), **kwargs):
    return tokenizer.tokenize(string, **kwargs)
