#! /usr/bin/env python
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from nltk.stem import snowball


def stem(word, stemmer=snowball.EnglishStemmer()):
    """Stem a word using Snowball by default.
    """
    return stemmer.stem(word)
