#! /usr/bin/env python
# Author: Kapil Thadani (kapil@cs.columbia.edu)

import re


class Sanitizer(object):
    """A class to identify structured elements within a string of text that
    involve special characters or punctuation symbols in predictable patterns.
    These tokens can then be tagged, removed, temporarily masked or
    replaced with canonical versions as required by downstream processing.
    """
    def __init__(self):
        """Initialize the regular expressions required for pattern-based
        expression identification.
        """
        # Set the prefix for the placeholder string used to replace tokens
        self.placeholder_prefix = 'InternalToken'

        # Initialize the dictionary that maps pattern names to compiled regexes
        self.patterns = {}

        # Generate a pattern for email addresses
        self._init_email_re()

        # Generate a pattern for URLs
        self._init_url_re()

        # TODO: Maybe add more web gunk like emoticons, hashtags etc
        # TODO: Add time and date expression tagging and normalization
        # TODO: Move currency identification here and extend normalization

        # Initialize attributes for storage and retrieval of tokens
        self.reset_stored_tokens()

    def reset_stored_tokens(self):
        """Initialize or reset the list of stored tokens and a dictionary to
        record tokens by their type.
        """
        self.tokens = []

        self.tokens_by_type = {name: [] for name in self.patterns.keys()}

    def mask_all(self, string):
        """Identify and mask tokens using all initialized patterns.
        """
        # Reset the masking so that tokens from different sentences aren't
        # combined
        self.reset_stored_tokens()

        for name, rexp in self.patterns.items():
            string = self.mask(string, rexp, name)

        return string

    def mask(self, string, pattern_re, pattern_name=''):
        """Identify and mask substrings that correspond to a particular regular
        expression, replacing them with a placeholder string.
        """
        self.current_pattern_name = pattern_name
        string = re.sub(pattern_re, self.store_token, string)

        return string

    def store_token(self, match):
        """Replace the matched token with an appropriate mask and store it for
        later retrieval.
        """
        # Save the token for later retrieval and record its index
        current_token_idx = len(self.tokens)
        self.tokens.append(match.group(1))

        # Add a link to the index of the stored token from the type-specific
        # dictionary
        self.tokens_by_type[self.current_pattern_name].append(
            current_token_idx)

        # Generate a placeholder string for the token. This consists of
        # a standard prefix + current pattern name + 5-digit integer index
        replacement_text = ''.join([self.placeholder_prefix,
                                    self.current_pattern_name,
                                    str(current_token_idx).zfill(5)])

        return replacement_text

    def unmask_all(self, string):
        """Replace all placeholders in the string with their corresponding
        token text. The list of stored tokens is not affected.
        """
        # Split the string into words on single spaces
        words = string.split(' ')

        # Replace the token markers with their stored values
        for w in range(len(words)):
            if words[w].startswith(self.placeholder_prefix):
                idx = int(words[w][-5:])
                words[w] = self.tokens[idx]

        # Rejoin the string and return it
        return ' '.join(words)

###############################################################################
# Patterns

    def _init_email_re(self):
        """Initialize a regular expression for detecting email addresses.
        """
        symbols = r'\.\-_'

        # Strategy: a string of word characters and permitted symbols
        # followed by an @ sign followed by more characters with at least one
        # interior period
        # NOTE: This is tuned for recall so we don't validate the top-level
        # domain of the email address
        email = r"""
            \b
            (                       # Begin \1
                [\w%(symbol)s]+     #   Characters or symbols
                \@                  #   @
                [\w%(symbol)s]+     #   More characters or symbols
                \.                  #   At least one period
                [\w%(symbol)s]+     #   More characters or symbols
            )                       # End \1
            (?=                     # Look-ahead non-consumptive assertion
                [:,\.]?             # Possible punctuation
                [^\w%(symbol)s]     # Non-email address character
                | $                 # Or the end of the string
            )
            """ % {'symbol': symbols}

        # Compile and store regular expression
        email_re = re.compile(email, re.VERBOSE)
        self.patterns['Email'] = email_re

    def _init_url_re(self):
        """Initialize a regular expression for detecting URLs (inspired by
        http://mail.python.org/pipermail/tutor/2002-February/012481.html).
        """
#        protocols = '(?:%s)' % '|'.join(('http', 'telnet', 'gopher', 'file',
#                                         'wais','ftp'))
        tlds = '(?:%s)' % '|'.join(('aero', 'asia', 'biz', 'cat', 'com',
                                    'coop', 'edu', 'gov', 'info', 'int',
                                    'jobs', 'mil', 'mobi', 'museum', 'name',
                                    'net', 'org', 'pro', 'tel', 'travel',
                                    'ac', 'ad', 'ae',
                                    'af', 'ag', 'ai', 'al', 'am', 'an', 'ao',
                                    'aq', 'ar', 'as', 'at', 'au', 'aw', 'ax',
                                    'az', 'ba', 'bb', 'bd', 'be', 'bf', 'bg',
                                    'bh', 'bi', 'bj', 'bm', 'bn', 'bo', 'br',
                                    'bs', 'bt', 'bv', 'bw', 'by', 'bz', 'ca',
                                    'cc', 'cd', 'cf', 'cg', 'ch', 'ci', 'ck',
                                    'cl', 'cm', 'cn', 'co', 'cr', 'cu', 'cv',
                                    'cx', 'cy', 'cz', 'de', 'dj', 'dk', 'dm',
                                    'do', 'dz', 'ec', 'ee', 'eg', 'eh', 'er',
                                    'es', 'et', 'eu', 'fi', 'fj', 'fk', 'fm',
                                    'fo', 'fr', 'ga', 'gb', 'gd', 'ge', 'gf',
                                    'gg', 'gh', 'gi', 'gl', 'gm', 'gn', 'gp',
                                    'gq', 'gr', 'gs', 'gt', 'gu', 'gw', 'gy',
                                    'hk', 'hm', 'hn', 'hr', 'ht', 'hu', 'id',
                                    'ie', 'il', 'im', 'in', 'io', 'iq', 'ir',
                                    'is', 'it', 'je', 'jm', 'jo', 'jp', 'ke',
                                    'kg', 'kh', 'ki', 'km', 'kn', 'kp', 'kr',
                                    'kw', 'ky', 'kz', 'la', 'lb', 'lc', 'li',
                                    'lk', 'lr', 'ls', 'lt', 'lu', 'lv', 'ly',
                                    'ma', 'mc', 'md', 'me', 'mg', 'mh', 'mk',
                                    'ml', 'mm', 'mn', 'mo', 'mp', 'mq', 'mr',
                                    'ms', 'mt', 'mu', 'mv', 'mw', 'mx', 'my',
                                    'mz', 'na', 'nc', 'ne', 'nf', 'ng', 'ni',
                                    'nl', 'no', 'np', 'nr', 'nu', 'nz', 'om',
                                    'pa', 'pe', 'pf', 'pg', 'ph', 'pk', 'pl',
                                    'pm', 'pn', 'pr', 'ps', 'pt', 'pw', 'py',
                                    'qa', 're', 'ro', 'rs', 'ru', 'rw', 'sa',
                                    'sb', 'sc', 'sd', 'se', 'sg', 'sh', 'si',
                                    'sj', 'sk', 'sl', 'sm', 'sn', 'so', 'sr',
                                    'st', 'su', 'sv', 'sy', 'sz', 'tc', 'td',
                                    'tf', 'tg', 'th', 'tj', 'tk', 'tl', 'tm',
                                    'tn', 'to', 'tp', 'tr', 'tt', 'tv', 'tw',
                                    'tz', 'ua', 'ug', 'uk', 'us', 'uy', 'uz',
                                    'va', 'vc', 've', 'vg', 'vi', 'vn', 'vu',
                                    'wf', 'ws', 'ye', 'yt', 'za', 'zm', 'zw'))
        symbols = r'/#~:\.?+=&%@!\-;$'

        # Strategy: a string of word characters and permitted symbols with at
        # least one interior period followed by a top-level domain from above.
        # NOTE: This is tuned for recall; for precision we could check for
        # the leading protocol and "www" but stand to risk missing things like
        # "google.com"
        # TODO: new TLDs, oh lord
        url = r"""
            \b
            (                       # Begin \1
                [\w%(symbol)s]*     #   Characters or symbols
                \.%(tld)s           #   A period followed by a top-level domain
                [\w%(symbol)s]*     #   More characters or symbols
            )                       # End \1
            (?=                     # Look-ahead non-consumptive assertion
                [:,\.]?             # Possible punctuation
                [^\w%(symbol)s]     # Non-URL character
                | $                 # Or the end of the string
            )
            """ % {'tld': tlds,
                   'symbol': symbols}

        # Compile and store regular expression
        url_re = re.compile(url, re.VERBOSE)
        self.patterns['URL'] = url_re
