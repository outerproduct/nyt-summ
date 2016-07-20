#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from collections import defaultdict
from functools import partial
from lexical import stemmer
import logging
import numpy as np
import os
import pickle
from utils.timer import Timer


def idf_smoothing(num_docs, alpha):
    """Smoothing by add-alpha for OOV words. This is a module-level function
    because a defaultdict can't be pickled if we define it with a lambda
    directly. Note that this doesn't serialize the function, however.
    """
    return np.log(num_docs/alpha)


class IDFTable:
    """A class to calculate and serve IDF values for words.
    """
    # Special key for number of docs
    nkey = '__numdocs__'

    def __init__(self, name, base_path, stemming=False, alpha=1):
        """Load stored document frequencies if they exist; otherwise wait
        for input.
        """
        # Path where the idf file should be stored
        self.name = name
        self.base_path = base_path
        self.stemming = stemming
        self.alpha = alpha

        self.freq_path = self.get_filepath(suffix='.freqs')
        self.idf_path = self.get_filepath(suffix='.{0:0>3d}.idf'
                                                 .format(int(alpha * 100)))
        self.loaded = False

        if os.path.exists(self.idf_path):
            self.idf = self.load(self.idf_path, description="idf values")
            self.loaded = True

        elif os.path.exists(self.freq_path):
            self.doc_freqs = self.load(self.freq_path)
            self.idf = self.compute_idf(self.doc_freqs, self.alpha)
            self.save(self.idf, self.idf_path, description="idf values")
            self.loaded = True

        else:
            logging.info("Storing new token frequency table at {0}"
                         .format(self.freq_path))

    def __getitem__(self, token):
        """Return the IDF for a given token.
        """
        return self.idf[self.stem(token)]

    def stem(self, token):
        """A pass-through function for the stemmer so that term
        frequencies can be computed in the same way as the IDF counts.
        """
        return stemmer.stem(token) if self.stemming else token.lower()

    def add_doc(self, token_list):
        """Add a document represented by a list of tokens.
        """
        if not hasattr(self, 'doc_freqs'):
            self.doc_freqs = defaultdict(int)

        # Keep track of the number of documents with a special key
        self.doc_freqs[self.nkey] += 1

        seen_tokens = set()
        for token in token_list:
            token = self.stem(token)

            if token not in seen_tokens:
                # Count each token/stem in the document only once
                self.doc_freqs[token] += 1
                seen_tokens.add(token)

    def done_adding_docs(self):
        """Save the token frequencies to disk and compute IDF values.
        """
        # Save token frequencies to disk
        assert self.nkey in self.doc_freqs
        self.save(self.doc_freqs, self.freq_path,
                  description="token frequencies")

        # Compute IDF values
        self.idf = self.compute_idf(self.doc_freqs, self.alpha)
        self.save(self.idf, self.idf_path,
                  description="idf values")
        self.loaded = True

    def get_filepath(self, suffix='.freqs'):
        """Get a consistent filename for this frequency or idf table on disk.
        """
        return os.path.join(self.base_path,
                            ''.join((self.name,
                                     '.stem' if self.stemming else '',
                                     suffix)))

    @classmethod
    def compute_idf(cls, doc_freqs, alpha):
        """Compute IDF values from the stored document frequencies.
        """
        num_tokens = len(doc_freqs)
        num_docs = doc_freqs[cls.nkey]

        # Smoothed IDF table
        idf = defaultdict(partial(idf_smoothing, num_docs, alpha))

        i = 0
        with Timer(num_tokens) as t:
            for token, freq in doc_freqs.items():
                i += 1
                if token != cls.nkey:
                    idf[token] = np.log(num_docs / (freq + alpha))
                    t.status("Computing idf for token {0}/{1}: {2}"
                             .format(i, num_tokens, token))
        return idf

    @staticmethod
    def load(path, description="something"):
        """Load a picked dictionary on disk.
        """
        with Timer() as t:
            t.status("Loading {0} from {1}".format(description, path))
            # Reminder: always open pickle files in binary mode
            with open(path, 'rb') as f:
                return pickle.load(f)

    @staticmethod
    def save(freqs, path, description="something"):
        """Save a pickled dictionary to disk.
        """
        with Timer() as t:
            t.status("Saving {0} to {1}".format(description, path))
            with open(path, 'wb') as f:
                pickle.dump(freqs, f)
