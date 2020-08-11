#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from lexical.tokenizer import tokenize
from lexical.untokenizer import untokenize
import re
import spacy
from utils.timer import Timer


# Initialize spaCy with the largest available model
models = ['en_core_web_lg', 'en_core_web_md', 'en_core_web_sm']
with Timer() as t:
    for model in models:
        t.status("Loading spaCy {0}".format(model))
        try:
            nlp = spacy.load(model)
            break
        except OSError:
            if model == models[-1]:
                raise


# A regexp to strip non-alphanumeric characters from a Unicode string
alnum_re = re.compile(r"[\W_ ]+", re.UNICODE)


class Sentence:
    """A single sentence for use in summarization.
    """
    __slots__ = ['tokens', 'raw', 'sentid', 'par_id', 'rel_id',
                 'annotations', 'features']

    def __init__(self, tokens=None, raw=None, sentid=None, par_id=None,
                 rel_id=None, warnings=False):
        """Initialize with either text or tokens.
        """
        self.sentid = sentid    # Presumed unique
        self.par_id = par_id    # ID of the paragraph
        self.rel_id = rel_id    # ID within the paragraph

        if tokens is None and raw is None:
            self.tokens = []
            self.raw = ''
        elif tokens is None:
            self.tokens = tokenize(raw, warnings=warnings)
            self.raw = raw
        elif raw is None:
            self.tokens = tokens
            self.raw = untokenize(tokens, warnings=warnings)
        else:
            self.tokens = tokens
            self.raw = raw

        # For caching annotations and features
        self.annotations = {}
        self.features = {}

        # For quick comparisons, store a version of the sentence without
        # case, punctuation or spacing
        self.annotations['stripped'] = alnum_re.sub('', self.raw.lower())

        # Store POS annotations using spaCy
        if len(self.raw) > 0:
            pos_tokens, pos_tags = zip(*self.extract_pos_tags(self.raw))
            self.annotations['pos_tags'] = pos_tags
            self.annotations['pos_tokens'] = pos_tokens

    def is_identical_to(self, other):
        """Return whether the two sentences match exactly when case,
        punctuation and spacing is ignored.
        """
        return self.annotations['stripped'] == other.annotations['stripped']

    def is_contained_in(self, other):
        """Return whether the sentence is contained within another sentence
        when case, punctuation and spacing is ignored.
        """
        return self.annotations['stripped'] in other.annotations['stripped']

    def is_subseq_of(self, other):
        """Return whether the sentence is a subsequence of another sentence
        when case and punctuation is ignored.
        """
        # The iterator ensures that tokens are matched in order
        other_tokens_iter = iter(other.tokens)
        return all(any(token.lower() == other_token.lower()
                       for other_token in other_tokens_iter)
                   for token in self.tokens
                   if token[-1].isalnum() or token[0].isalnum())

    def display(self):
        """Print the sentence with its sentence ID.
        """
        if self.sentid is not None:
            print("[{0}] {1}".format(self.sentid, self.raw))
        else:
            print(self.raw)

    def get_parsed(self):
        """Parse the sentence and return a spaCy Doc object.
        """
        if 'parsed' not in self.annotations:
            self.annotations['parsed'] = nlp(self.raw)
        return self.annotations['parsed']

    def get_noun_phrases(self):
        """Return noun phrase chunks in the sentence.
        """
        # TODO: adverbs may need to be dropped
        return list(self.get_parsed().noun_chunks)

    def get_entities(self):
        """Return named entities.
        """
        return list(self.get_parsed().ents)

    def get_stripped(self):
        """Return a version of the sentence without non-alphanumeric
        characters for string comparison.
        """
        return self.annotations['stripped']

    def get_words(self):
        """Return the non-punctuation words in the sentence.
        """
        # Assume words start with alphanumeric characters
        return [token for token in self.tokens if token[0].isalnum()]

    def has_eos_punct(self):
        """Return whether the sentence contains valid sentence-terminating
        punctuation.
        """
        # Note that the tokenizer moves sentence-terminating punctuation
        # outside quotes.
        return len(self.tokens) > 0 and self.tokens[-1] in ('.', '!', '?')

    def has_verb(self):
        """Return whether the sentence contains a verb.
        """
        for pos_tag in self.annotations['pos_tags']:
            if pos_tag.upper().startswith('V'):
                return True
        return False

    def truncate(self, budget, cost_type='char'):
        """Return a truncated version of the sentence.
        """
        word_cost = 0
        char_cost = 0
        new_tokens = []
        for t, token in enumerate(self.tokens):
            word_cost += int(token[0].isalnum())
            char_cost += 1 + len(token)
            if (cost_type == 'word' and word_cost > budget) or \
                    (cost_type == 'char' and char_cost > budget - 4):
                break
            new_tokens.append(token)

        new_sent = Sentence(tokens=new_tokens,
                            raw=' '.join(new_tokens) + ' ...',
                            sentid=self.sentid,
                            par_id=self.par_id,
                            rel_id=self.rel_id)
        new_sent.annotations.update(self.annotations)
        new_sent.features.update(self.features)
        return new_sent

    @staticmethod
    def extract_pos_tags(text):
        """Derive a POS tag sequence for the given sentence. This may not
        synchronize with tokens so we also return spaCy's tokenization.
        """
        return [(token.orth_, token.tag_) for token in nlp(text,
                                                           disable=['parser'])]
