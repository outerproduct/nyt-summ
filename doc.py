#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from lexical.tokenizer import tokenize
from lexical.splitter import split
import logging
import os
import re
import sentence
from xml.etree import ElementTree

from resources import (BAD_DESCRIPTORS, BAD_TITLES, BAD_LEADS,
                       BAD_SUMMLEADS, BAD_SUMMS, BAD_PREFIXES,
                       STITCHES_SUMM, AMBIGUOUS_STITCHES_SUMM,
                       SPLITS_DOC)

# A regex to fix spaces preceding .com in URLs
dotcom_fix_re = re.compile(r"(at +[^ ]+) (?=\.com|\.org|\.net)")

# A regex to identify roundup articles by their lead sentence
roundup_pt_re = re.compile(r"[A-Z\.\- ]+\-\-")

# A regex to identify page markers like [Page A1] or unexpected markers
# like [?][?][?]Author Name
pagemarker_re = re.compile(r" *\[(?:Page )?[A-Z]?[0-9]{1,2}\][\. ]*$")
authmarker_re = re.compile(r" *\[\?\]\[.*")

# A regex to identify extraneous periods in online_lead summaries
extraneous_re = re.compile(r"(?:[\?\!]|[\?\!\'\.]\'\')\s*\.$")

# A regex to identify spurious periods in truncated online_lead summaries
incomplete_re = re.compile(r"[\-,:;]\.$")

# A regex to merge hyphenated words separated in online_lead summaries
hyphenated_re = re.compile(r"(?<=[^ \-]\-) (?!and |\(?or |to )")

# A regex to replace single dash tokens in summaries with double dashes
singledash_re = re.compile(r" \- ")

# Regexes to strip prefixes in a single pass, respecting order in the list
prefixes_re = re.compile('^({0})\s*'.format(
                         '|'.join(re.escape(key) for key in BAD_PREFIXES)))

# Regexes to map stitched/split words in a single pass
stitches_summ_re = re.compile(' {0} '.format(
                              ' | '.join(re.escape(key)
                                         for key in STITCHES_SUMM)))
ambi_stitches_re = re.compile(' {0} '.format(
                              ' | '.join(re.escape(key)
                                         for key in AMBIGUOUS_STITCHES_SUMM)))
splits_in_doc_re = re.compile(' {0} '.format(
                              ' | '.join(re.escape(key)
                                         for key in SPLITS_DOC)))

# A table of Unicode symbol normalizations to match online_lead_paragraph
# summaries to document text
unicode_subs = str.maketrans({'`':       '\'',
                              '´':       '\'',
                              '‘':       '\'',
                              '’':       '\'',
                              '"':       '\'\'',
                              '“':       '\'\'',
                              '”':       '\'\'',
                              '\x86':    '+',
                              '\x91':    '\'',
                              '\x92':    '\'',
                              '\x93':    '\'\'',
                              '\x94':    '\'\'',
                              '\x95':    ' ',
                              '\x96':    '--',
                              '\x97':    '--',
                              '\xa0':    ' ',
                              '\xa9':    '$;',
                              '\xad':    '--',
                              '\xb2':    '2',
                              '\xb7':    '.',
                              '\xbd':    '1/2',
                              '\xbe':    '3/4',
                              u'\u0096': '--',
                              u'\u0097': '--',
                              u'\u2014': '--',
                              u'\u201e': '\'\''})


class NYTDoc:
    """A story in the New York Times corpus.
    """
    def __init__(self, path, file):
        """Parse the story from the given file handle.
        """
        self.path = path
        self.docid = '/'.join(os.path.split(path)[-4:])

        # Parse the document
        try:
            contents = self.extract_text(file)
            self.parse_story(contents)
        except ElementTree.ParseError:
            logging.error("Invalid XML in {0}".format(self.path))
            self.parse_error = True

    def is_well_formed(self):
        """Return whether this article was parsed correctly and has text.
        """
        return hasattr(self, 'full_text') and not hasattr(self, 'parse_error')

    def has_summary(self, summary_type):
        """Return whether this article has an accompanying summary of the
        given type ('abstract', 'lead' or 'online_lead')
        """
        return summary_type is None or summary_type in self.summaries

    def has_descriptors(self, labels, types=('online_general',)):
        """Return whether this article has a descriptor of the given type.
        """
        if types is None:
            types = self.descriptors.keys()

        for type in types:
            if type not in self.descriptors:
                continue

            for label in labels:
                if label in self.descriptors[type] or \
                        label.title() in self.descriptors[type]:
                    return True
        return False

    def parse_story(self, text):
        """Parse an XML representation of a story.
        """
        root = ElementTree.fromstring(text)

        for child in root:
            if child.tag == 'head':
                self.parse_header(child)
            elif child.tag == 'body':
                self.parse_body(child)
            else:
                logging.warning("Unknown top-level tag <{0}> "
                                "in story from {1}"
                                .format(child.tag, self.path))

    def parse_header(self, node):
        """Parse the document header and record metadata.
        """
        if hasattr(self, 'meta'):
            logging.warning("Overwriting multiple headers in {0}"
                            .format(self.path))

        # Metadata including title, doc-id and publication data
        self.meta = {}
        for child in node:
            if child.tag == 'title':
                self.meta['title'] = child.text
            elif child.tag == 'meta':
                self.meta[child.attrib['name']] = child.attrib['content']
            elif child.tag == 'pubdata':
                self.meta.update(child.attrib)
            elif child.tag == 'docdata':
                for gchild in child:
                    if gchild.tag == 'doc-id':
                        self.meta['docid'] = gchild.attrib['id-string']
                    elif gchild.tag == 'identified-content':
                        self.parse_descriptors(gchild)
                    elif gchild.tag not in ('doc.copyright', 'series'):
                        logging.warning("Unknown docdata tag <{0}> "
                                        "in story from {1}"
                                        .format(gchild.tag, self.path))
            else:
                logging.warning("Unknown header tag <{0}> "
                                "in story from {1}"
                                .format(child.tag, self.path))

    def parse_descriptors(self, node):
        """Record descriptors assigned to the document.
        """
        # Tags assigned by the indexing service or automated classifiers
        self.descriptors = {'indexing': set(),
                            'taxonomic': set(),
                            'online': set(),
                            'online_general': set(),
                            'type': set()}

        for tag_node in node:
            if tag_node.tag != 'classifier':
                # Ignore org, person, book title, etc
                continue

            class_type = (tag_node.attrib['class'], tag_node.attrib['type'])
            label = tag_node.text
            if label is None:
                # Missing labels were observed
                continue
            label = label.title() if label.isupper() else label

            if class_type == ('indexing_service', 'descriptor'):
                self.descriptors['indexing'].add(label)
            elif class_type == ('online_producer', 'types_of_material'):
                self.descriptors['type'].add(label)
            elif class_type == ('online_producer', 'taxonomic_classifier'):
                self.descriptors['taxonomic'].add(label)
            elif class_type == ('online_producer', 'descriptor'):
                self.descriptors['online'].add(label)
            elif class_type == ('online_producer', 'general_descriptor'):
                self.descriptors['online_general'].add(label)
            elif class_type not in (('indexing_service', 'names'),
                                    ('indexing_service',
                                     'biographical_categories')):
                logging.warning("Unknown classifier '{0!s}' "
                                "in story from {1}"
                                .format(class_type, self.path))

    def parse_body(self, node):
        """Parse the body and record text.
        """
        if hasattr(self, 'paragraphs'):
            logging.warning("Overwriting multiple bodies in {0}"
                            .format(self.path))

        # 'normal' and 'online' headlines
        self.headlines = {}

        # 'lead', 'online_lead' and 'abstract' where available
        self.summaries = {}

        for child in node:
            if child.tag == 'body.head':
                for gchild in child:
                    if gchild.tag == 'hedline':
                        # Record headlines
                        for ggchild in gchild:
                            if 'class' not in ggchild.attrib:
                                self.headlines['print'] = ggchild.text
                            elif ggchild.attrib['class'] == 'online_headline':
                                self.headlines['online'] = ggchild.text
                            else:
                                logging.warning("Unknown headline class {0} "
                                                "in story from {1}".format(
                                                    ggchild.attrib['class'],
                                                    self.path))
                    elif gchild.tag == 'abstract':
                        # Record abstractive summary
                        abstract = self.read_block(gchild)
                        if len(abstract) > 0:
                            self.summaries['abstract'] = abstract

                    elif gchild.tag not in ('byline', 'dateline'):
                        logging.warning("Unknown *line type {0} "
                                        "in story from {1}"
                                        .format(gchild.tag, self.path))

            elif child.tag == 'body.content':
                for gchild in child:
                    if gchild.tag != 'block' or 'class' not in gchild.attrib:
                        logging.warning("Unexpected body content tag {0} "
                                        "in story from {1}"
                                        .format(gchild.tag, self.path))
                        continue
                    if gchild.attrib['class'] == 'lead_paragraph':
                        # Record lead paragraph summary
                        self.summaries['lead'] = self.read_block(gchild)

                    elif gchild.attrib['class'] == 'online_lead_paragraph':
                        # Record online lead paragraph summary
                        self.summaries['online_lead'] = self.read_block(gchild)

                    elif gchild.attrib['class'] == 'full_text':
                        # Record article text
                        self.full_text = self.read_block(gchild)

                    elif gchild.attrib['class'] == 'correction_text':
                        # Record correction if present
                        self.correction = self.read_block(gchild)

                    else:
                        logging.warning("Unknown body content class {0} "
                                        "in story from {1}"
                                        .format(ggchild.attrib['class'],
                                                self.path))

            elif child.tag != 'body.end':
                logging.warning("Unknown header tag <{0}> "
                                "in story from {1}"
                                .format(child.tag, self.path))

    def read_block(self, node):
        """Read a block of paragraph-formatted text and return a list
        of paragraph strings.
        """
        paragraphs = []
        for child in node:
            if child.tag != 'p':
                logging.error("Malformed text block in story from {1}"
                              .format(child.tag, self.path))
                continue
            if child.text is None:
                continue
            paragraphs.append(child.text)
        return paragraphs

    @staticmethod
    def extract_text(file):
        """Extract UTF-8 text from a file handle.
        """
        lines = []
        for line in file:
            try:
                decoded = line.decode('utf-8', 'strict')
            except UnicodeDecodeError:
                print(line)
                raise
            lines.append(decoded)
        return ''.join(lines)

    def has_reachable_summary(self, summary_type,
                              comparison='is_identical_to'):
        """Return whether the sentences of a summary are contained within
        the sentences of the document under some sentence-level function
        which establishes containment.
        """
        if summary_type not in self.summaries:
            return False
        if len(self.summaries[summary_type]) == 0:
            # Unlikely that this will happen
            logging.warning("Empty {0} in {1}".format(summary_type, self.path))
            return False

        doc_sents = [sent for paragraph in
                     self.get_cached_sentences(self.full_text,
                                               cache_name='full_text')
                     for sent in paragraph]
        ref_sents = [sent for paragraph in
                     self.get_cached_sentences(self.summaries[summary_type],
                                               cache_name=summary_type)
                     for sent in paragraph]

        for ref_sent in ref_sents:
            found_match = False
            for doc_sent in doc_sents:
                if getattr(ref_sent, comparison)(doc_sent):
                    found_match = True
            if not found_match:
                return False

        return True

    def has_extractive_summary(self, summary_type):
        """Return whether each sentence in a summary is identical to
        some sentence from the input document.
        """
        return self.has_reachable_summary(summary_type,
                                          comparison='is_identical_to')

    def has_semi_extractive_summary(self, summary_type):
        """Return whether each sentence in a summary is contained within
        some sentence from the input document.
        """
        return self.has_reachable_summary(summary_type,
                                          comparison='is_contained_in')

    def has_sub_extractive_summary(self, summary_type):
        """Return whether each sentence in a summary is a subsequence of
        some sentence from the input document.
        """
        return self.has_reachable_summary(summary_type,
                                          comparison='is_subseq_of')

    def has_sentential_summary(self, summary_type):
        """Return whether the summary is composed of complete sentences.
        """
        if not self.has_summary(summary_type):
            return False

        ref_sents = [sent for paragraph in
                     self.get_cached_sentences(self.summaries[summary_type],
                                               cache_name=summary_type)
                     for sent in paragraph]

        # First, check that the summary ends with a valid sentence terminator
        if not ref_sents[-1].has_eos_punct():
            return False

        # Spurious periods are also often added to truncated summaries
        if incomplete_re.search(ref_sents[-1].raw):
            return False

        # Next, ensure that there is at least one verb in the summary
        for ref_sent in ref_sents:
            if ref_sent.has_verb():
                return True
        return False

    def has_covering_summary(self, summary_type):
        """Return whether the full text of the document is fully covered
        by the summary.
        """
        if not self.has_summary(summary_type):
            return False

        # Collect the sentences stripped of all non-alphanumeric characters
        full_text = [sent.get_stripped() for paragraph in
                     self.get_cached_sentences(self.full_text,
                                               cache_name='full_text')
                     for sent in paragraph]
        ref_sents = [sent.get_stripped() for paragraph in
                     self.get_cached_sentences(self.summaries[summary_type],
                                               cache_name=summary_type)
                     for sent in paragraph]

        # Assume that covering summaries will have approximately the same
        # number of sentences as the document
        if abs(len(full_text) - len(ref_sents)) > 1:
            return False

        return ''.join(full_text) == ''.join(ref_sents)

    def has_allcaps_summary(self, summary_type):
        """Return whether the summary is all uppercase -- an indication
        that it is a title or location and not a real sentence.
        """
        if not self.has_summary(summary_type):
            return False
        for paragraph in self.summaries[summary_type]:
            for sent in paragraph:
                if sent.upper() != sent:
                    return False
        return True

    def has_bounded_summary(self, summary_type, measure='char',
                            lower_bound=1, upper_bound=int(1e9)):
        """Return whether the summary fits within the given bounds.
        """
        if not self.has_summary(summary_type):
            return False

        ref_sents = [sent for paragraph in
                     self.get_cached_sentences(self.summaries[summary_type],
                                               cache_name=summary_type)
                     for sent in paragraph]

        if measure == 'char':
            size = sum(len(sent.raw)
                       for sent in ref_sents) + len(ref_sents) - 1
        elif measure == 'word':
            size = sum(len(sent.get_words()) for sent in ref_sents)
        elif measure == 'sent':
            size = len(ref_sents)

        return lower_bound <= size <= upper_bound

    def is_templated(self):
        """Return whether this article follows a structure or template that
        makes it inappropriate for the summarization task.
        """
        # Check if the article type descriptors are problematic
        for descriptor in self.descriptors['type']:
            if descriptor in BAD_DESCRIPTORS:
                return True

        # Check if the article title indicates a known template
        for title in self.headlines.values():
            if title in BAD_TITLES:
                return True

        if 'online_lead' in self.summaries:
            online_lead_raw = self.summaries['online_lead']

            # Check if the full online lead summary indicates a known template
            if ' '.join(online_lead_raw) in BAD_SUMMS:
                return True

            # Check if the first sentence of the online lead summary indicates
            # a known template. Note that this follows preprocessing.
            online_lead = self.get_cached_sentences(online_lead_raw,
                                                    cache_name='online_lead')
            if online_lead[0][0].raw in BAD_SUMMLEADS:
                return True

        # Check if the the first sentence of the article indicates a a roundup
        # of sub-stories
        if len(self.full_text) == 0 or roundup_pt_re.match(self.full_text[0]):
            return True

        # Check if the first sentence of the article indicates a known
        # template. Note that this follows preprocessing.
        full_text = self.get_cached_sentences(self.full_text,
                                              cache_name='full_text')
        lead_sent = full_text[0][0].raw
        if lead_sent in BAD_LEADS:
            return True

        # Check if the first sentence of the article is all uppercase text,
        # often indicating a book review with structured content
        if lead_sent[-1].isalnum() and lead_sent.isupper():
            return True

        return False

    @staticmethod
    def get_tokens(paragraphs):
        """Get just the tokens from an NYT field consisting of a list of
        paragraph strings.
        """
        for paragraph in paragraphs:
            for token in tokenize(paragraph, warnings=False):
                yield token

    @staticmethod
    def get_sentences(paragraphs):
        """Get tokenized sentences within each paragraph from a list of
        paragraphs where each paragraph is a string or a list of sentences.
        """
        # Note that this generator yields
        # paragraph = [sent1, sent2, ...] and sent = [token1, token2, ...]
        offset = 0
        for p, paragraph in enumerate(paragraphs):
            sents = split(paragraph) if isinstance(paragraph, str) \
                else paragraph
            yield [sentence.Sentence(raw=sent, sentid=(offset+s),
                                     rel_id=s, par_id=p)
                   for s, sent in enumerate(sents)]
            offset += len(sents)

    def get_cached_sentences(self, paragraphs, cache_name=None,
                             preprocessing=True):
        """Cache the sentences so that exports and checks for extractiveness
        don't regenerate them. Note that the cached versions should not be
        written back to the corpus shelf, otherwise updates to sentence
        splitting, tokenization or the Sentence class will render this
        object stale.
        """
        if cache_name is not None and \
                hasattr(self, 'cache') and \
                cache_name in self.cache:
            # Recover the result from a cache
            sent_paras = self.cache[cache_name]
        else:
            # Preprocess the full text and online lead paragraphs if either
            # is requested
            if preprocessing and (not hasattr(self, 'cache')
                                  or (cache_name == 'full_text'
                                      and 'online_lead' not in self.cache)
                                  or (cache_name == 'online_lead'
                                      and 'full_text' not in self.cache)):
                # Replace stored text for the document and online lead
                self.full_text, self.summaries['online_lead'] = \
                    self.preprocess_all(self.full_text,
                                        self.summaries['online_lead'])

                # Replace the input paragraphs for the corresponding field
                paragraphs = (self.full_text if cache_name == 'full_text'
                              else self.summaries['online_lead'])

            sent_paras = list(self.get_sentences(paragraphs))

            # Cache this result if provided a name
            if cache_name is not None:
                if not hasattr(self, 'cache'):
                    self.cache = {}
                self.cache[cache_name] = sent_paras

        assert len(sent_paras) == len(paragraphs)
        return sent_paras

    @classmethod
    def preprocess_all(cls, full_text_paras, online_lead_paras):
        """Fix capitalized leading words in the full text. Conditionally
        replacement of words in the online lead paragraph if they're
        present in the full text and vice versa.
        """
        # Replace capitalized leading words in the full text when possible
        # in order to minimize discrepancies with the online lead paragraph
        # in downstream processing, e.g., RST parsing.
        full_text_paras = cls.fix_capitalization(full_text_paras,
                                                 online_lead_paras)

        # Fix ambiguous stitched words in the online lead paragraph and
        # full text by checking if the separated version is present in
        # the full text and online lead paragraph respectively.
        online_lead_paras = cls.conditional_replace(online_lead_paras,
                                                    full_text_paras,
                                                    ambi_stitches_re,
                                                    AMBIGUOUS_STITCHES_SUMM)
        full_text_paras = cls.conditional_replace(full_text_paras,
                                                  online_lead_paras,
                                                  splits_in_doc_re,
                                                  SPLITS_DOC)

        return cls.preprocess_full_text(full_text_paras), \
            cls.preprocess_online_lead(online_lead_paras)

    @staticmethod
    def fix_capitalization(tgt_paras, src_paras):
        """Replace uppercase leading words in the target text with equivalent
        mixed-case leading words in the source text.
        """
        tgt = tgt_paras[0]
        src = src_paras[0]
        i = tgt.find(' ')

        if i == -1 or (tgt[-1].isalnum() and tgt.isupper()):
            # Don't edit sentences that appear to be titles
            return tgt_paras

        while tgt[:i].upper() == src[:i].upper():
            if tgt[:i].isupper() or tgt[:i] == tgt[:i].upper():
                j = i + 1 + tgt[i+1:].find(' ')
                if i != j:
                    # Found another space
                    i = j
                    continue
                elif tgt.upper() == src[:len(tgt)].upper():
                    # Replace the whole string if it's identical
                    i = len(tgt)
                else:
                    # Can't find a complete match
                    break

            # Ignore identical spans
            if tgt[:i] == src[:i]:
                break

            # Replace the capitalized prefix and one following word
            logging.warning("Replacing [{0}] -> [{1}] in\n{2}\n"
                            .format(tgt[:i], src[:i], tgt[:80]))
            return [src[:i] + tgt[i:]] + tgt_paras[1:]

        return tgt_paras

    @staticmethod
    def conditional_replace(tgt_paras, src_paras, sub_regex, sub_table):
        """Fix ambiguous stitched words in the target paragraphs by checking
        if the separated version is present in the source paragraphs.
        """
        matches = set()
        for para in tgt_paras:
            matches.update(sub_regex.findall(" {0} ".format(para)))

        if len(matches) == 0:
            return tgt_paras

#        made_replacement = False
        for match in list(matches):
            replacement = sub_table[match.strip()][0]
            found_in_src = False

            for p, para in enumerate(src_paras):
                # Ensure that the replacement occurs at least once in the
                # doc with a leading or trailing space.
                i = para.find(replacement)
                j = 0
                while i != -1:
                    i += j
                    j = i + len(replacement)
                    if ((i == 0 or not para[i-1].isalnum()) and
                            (j == len(para) or not para[j+1].isalnum())):
                        found_in_src = True
                        break

                    # Move on to the next potential appearance
                    i = para[j:].find(replacement)

                if found_in_src:
                    # Only need to find one valid mention
                    break

            if found_in_src:
                logging.warning("Replacing{0}-> {1}\n"
                                .format(match, replacement))
                tgt_paras = [" {0} ".format(para).replace(match,
                             " {0} ".format(replacement)).strip()
                             for para in tgt_paras]
#                made_replacement = True

#        if made_replacement:
#            logging.warning("to produce:\n{0}\n"
#                            .format('\n'.join(tgt_paras)))

        return tgt_paras

    @staticmethod
    def preprocess_full_text(paragraphs):
        """Remove all-caps authors / topics, corrections and page markers.
        Fix spaces before .com. Stitch together accidentally separated words.
        """
        processed_paras = []
        allcaps_paras = []

        for p, para in enumerate(paragraphs):
            # Remove all paragraphs following a correction
            if para.startswith('Correction:'):
                break

            # Remove trailing all-caps paragraphs
            if para.upper() == para:
                allcaps_paras.append(para)
                continue

            # Replace page markers
            markers = pagemarker_re.findall(para)
            if len(markers) > 0:
                logging.warning("Dropping page markers {0} from para:\n{1}\n"
                                .format(', '.join(markers), para))
                para = pagemarker_re.sub(' ', para).strip()

            # Replace unknown author markers
            markers = authmarker_re.findall(para)
            if len(markers) > 0:
                logging.warning("Dropping odd marker {0} from summary:\n{1}\n"
                                .format(', '.join(markers), para))
                para = authmarker_re.sub('', para).strip()

            if para != '':
                # Add back all non-trailing all-caps paragraphs
                if len(allcaps_paras) > 0:
                    processed_paras.extend(allcaps_paras)
                    allcaps_paras = []

                # Fix "nytimes .com" cases
                para = dotcom_fix_re.sub('\\1', para)

                # Add the current paragraph
                processed_paras.append(para)

#        if len(allcaps_paras) > 0:
#            logging.warning("Dropping metadata:\n{0}\n"
#                            .format(allcaps_paras))

        return processed_paras

    @staticmethod
    def preprocess_online_lead(paragraphs):
        """Normalize Unicode characters. Remove page markers, bureau string
        prefixes and names of subjects. Fix spaces before .com. Separate
        accidentally stitched words.
        """
        processed_paras = []

        for p, para in enumerate(paragraphs):
            # Remove prefixes from the start of the summary
            if p == 0:
                new_para = prefixes_re.sub('', para)
#                if len(new_para) < len(para):
#                    logging.warning("Dropping prefix from:\n{0}\n"
#                                    .format(para))
                para = new_para.lstrip()

            # Normalize Unicode characters to match the full text
            para = para.translate(unicode_subs)

            # Replace page markers
            markers = pagemarker_re.findall(para)
            if len(markers) > 0:
                logging.warning("Dropping page marker {0} from summary:\n{1}\n"
                                .format(', '.join(markers), para))
                para = pagemarker_re.sub(' ', para).strip()

            # Replace unknown author markers
            markers = authmarker_re.findall(para)
            if len(markers) > 0:
                logging.warning("Dropping odd marker {0} from summary:\n{1}\n"
                                .format(', '.join(markers), para))
                para = authmarker_re.sub('', para).strip()

            # Remove extraneous periods from paragraphs. Must follow
            # translation from Unicode symbols.
            if extraneous_re.search(para):
                para = para[:-1]

            if para != '':
                # Fix "nytimes .com" cases
                para = dotcom_fix_re.sub('\\1', para)

                # Replace stitched words
                para = stitches_summ_re.sub(
                    lambda m: " {0} ".format(
                        STITCHES_SUMM[m.group(0).strip()][0]),
                    " {0} ".format(para)).strip()

                # Merge hyphenated words that were incorrectly split into
                # two tokens
                para = hyphenated_re.sub('', para)

                # Expand single dash tokens to double dashes to match the
                # full text
                para = singledash_re.sub(' -- ', para)

                # Add the current paragraph
                processed_paras.append(para)

        return processed_paras
