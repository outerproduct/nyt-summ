#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

from doc import NYTDoc
from lexical import idf
import glob
import logging
import os
import shelve
import tarfile
from utils.timer import Timer


class NYTCorpus:
    """The New York Times annotated corpus.
    """
    def __init__(self, nyt_path, shelf_path, **kwargs):
        """Initialize the stories in the corpus with the given filters.
        """
        self.logger = logging.getLogger(__name__)

        self.filters = kwargs

        self.shelf_path = os.path.join(shelf_path,
                                       self.get_filename(suffix='.shelf',
                                                         **self.filters))

        if os.path.exists(self.shelf_path):
            # Load the documents via the shelf. Since we're not using
            # writeback, modifying a doc will not result in a commit
            # but assigning it to self.docs will.
            logging.info("Reading NYT corpus from {0}".format(self.shelf_path))
            self.docs = shelve.open(self.shelf_path, flag='r', writeback=False)
        else:
            # Load and filter all the documents as entries in a new shelf.
            logging.info("Saving NYT corpus to {0}".format(self.shelf_path))
            self.docs = shelve.open(self.shelf_path, flag='c', writeback=False)
            for doc in self.filter_docs(nyt_path, **self.filters):
                self.docs[doc.path] = doc

    def __del__(self):
        """Close the shelf.
        """
        if hasattr(self, 'docs'):
            self.docs.close()

    def get_idf(self, pickle_path, **kwargs):
        """Return an IDF table over the current document set, generating
        it from scratch if necessary.
        """
        # Generate an IDF dictionary from this document set and save it
        idf_table = idf.IDFTable(self.get_filename(suffix='', **self.filters),
                                 pickle_path,
                                 **kwargs)
        if idf_table.loaded:
            logging.debug("IDF table loaded directly from {0}"
                          .format(idf_table.idf_path))
            return idf_table

        with Timer() as t:
            for doc in self.docs.values():
                logging.debug("Counting tokens in {0}".format(doc.path))
                if not self.logger.isEnabledFor(logging.DEBUG):
                    t.status("Counting tokens in {0}".format(doc.path))

                idf_table.add_doc(doc.get_tokens(doc.full_text))

            # Saves the document frequencies to disk
            idf_table.done_adding_docs()

        return idf_table

    def filter_docs(self, path, summary_type=None, descriptors=None,
                    descriptor_types=('online_general',),
                    exclude=False, **kwargs):
        """Yield filtered stories from the loaded corpus or drawn from disk.
        """
        doc_source = self.get_all_docs(path, **kwargs) \
            if path is not None else self.docs.values()

        for doc in doc_source:
            has_summary = summary_type is None or doc.has_summary(summary_type)
            has_descriptors = descriptors is None or doc.has_descriptors(
                descriptors, types=descriptor_types)
            has_both = has_summary and has_descriptors

            # When exclude is True, only the documents that don't match the
            # filters are returned. If no filters are supplied, nothing will
            # be returned.
            if has_both ^ exclude:
                yield doc

    def export_dataset(self, limit=None, summary_type=None,
                       extractive=False, semi_extractive=False,
                       sub_extractive=False,
                       keep_nonsents=False, keep_allcaps=False,
                       keep_templated=False, keep_covering=False,
                       cost_type='char',
                       min_ref_cost=1, max_ref_cost=int(1e9),
                       min_ref_sents=1, max_ref_sents=int(1e9),
                       **kwargs):
        """Export a subset of the documents.
        """
        i = 0
        with Timer() as t:
            for doc in self.docs.values():
                # Does the document have the right type of summary?
                if not doc.has_summary(summary_type):
                    continue

                if not keep_allcaps and \
                        doc.has_allcaps_summary(summary_type):
                    # Summary must not be an all-caps title
                    continue

                if not keep_templated and doc.is_templated():
                    # Document must not be a template
                    continue

                if not doc.has_bounded_summary(summary_type, measure='sent',
                                               lower_bound=min_ref_sents,
                                               upper_bound=max_ref_sents):
                    # Summary must contain the expected number of sentences
                    continue

                if not doc.has_bounded_summary(summary_type, measure=cost_type,
                                               lower_bound=min_ref_cost,
                                               upper_bound=max_ref_cost):
                    # Summary must fit within the given summarization budget
                    continue

                if extractive and semi_extractive and sub_extractive:
                    if not doc.has_sub_extractive_summary(summary_type):
                        # Summary must be either extractive, semi-extractive
                        # and sub-extractive, all implied by the function above
                        continue
                elif extractive and semi_extractive:
                    if not doc.has_semi_extractive_summary(summary_type):
                        # Summary must be either semi-extractive or extractive,
                        # both implied by the function above
                        continue
                elif extractive and sub_extractive:
                    if (not doc.has_sub_extractive_summary(summary_type)) or \
                            (doc.has_semi_extractive_summary(summary_type) and
                             not doc.has_extractive_summary(summary_type)):
                        # Summary must be either sub-extractive or extractive
                        # but not semi-extractive
                        continue
                elif semi_extractive and sub_extractive:
                    if (not doc.has_sub_extractive_summary(summary_type)) or \
                            doc.has_extractive_summary(summary_type):
                        # Summary must be either sub-extractive or
                        # semi-extractive but not extractive
                        continue
                elif extractive:
                    if not doc.has_extractive_summary(summary_type):
                        # Summary must be entirely extractive
                        continue
                elif semi_extractive:
                    if (not doc.has_semi_extractive_summary(summary_type)) or \
                            doc.has_extractive_summary(summary_type):
                        # Summary must be semi-extractive but not extractive
                        continue
                elif sub_extractive:
                    if (not doc.has_sub_extractive_summary(summary_type)) or \
                            doc.has_semi_extractive_summary(summary_type):
                        # Summary must be strictly sub-extractive but not
                        # extractive or semi-extractive
                        continue

                if not keep_nonsents and \
                        not doc.has_sentential_summary(summary_type):
                    # Summary must contain valid sentences
                    continue

                if not keep_covering and \
                        doc.has_covering_summary(summary_type):
                    # Summary must not cover the whole document
                    continue

                # Have we produced enough data?
                i += 1
                if limit is not None and i > limit:
                    break

                t.status("Exporting {0}".format(doc.docid))
                yield doc

    def dump_text(self, limit=None):
        """Just write out the paragraphs from each document.
        """
        i = 0
        for path, doc in self.docs.items():
            # print("Reading {0}", path, end='\r')
            i += 1
            if limit is not None and i > limit:
                break

            for paragraph in doc.full_text:
                print(paragraph)

    def dump_descriptors(self, limit=None):
        """Just write out all the descriptors seen in the corpus.
        """
        descriptors = {}
        i = 0
        for path, doc in self.docs.items():
            # print("Reading {0}", path, end='\r')
            i += 1
            if limit is not None and i > limit:
                break

            for type, label_set in doc.descriptors.items():
                if type not in descriptors:
                    descriptors[type] = {}
                for label in label_set:
                    if label not in descriptors[type]:
                        descriptors[type][label] = 1
                    else:
                        descriptors[type][label] += 1

        for type, label_freqs in descriptors.items():
            print("{0}:".format(type))
            for label, freq in sorted(label_freqs.items(),
                                      key=lambda x: x[1],
                                      reverse=True):
                print("{0}\t{1}".format(freq, label))
            print()

    def check_extractive(self, summary_type=None):
        """Return the fraction of instances which are extractive
        for a given summary type.
        """
        assert summary_type is not None

        num_docs = 0
        num_extractive = 0
        for doc in self.docs.values():
            num_docs += 1
            if doc.has_extractive_summary(summary_type) is True:
                num_extractive += 1
            print("{0}/{1}: {2:.3f}".format(num_extractive, num_docs,
                                            num_extractive / num_docs),
                  end='\r')
        print("\n")

    @staticmethod
    def get_filename(summary_type=None, descriptors=None, exclude=False,
                     suffix=''):
        """Generate a consistent filename for shelf/index/idf files
        generated from this document collection.
        """
        return ''.join(('nyt',
                        '.X' if exclude else '',
                        ('.' + summary_type)
                        if summary_type is not None else '',
                        ('.' + '+'.join(descriptor.replace(' ', '_')
                                        for descriptor in descriptors))
                        if descriptors is not None else '',
                        suffix))

    @staticmethod
    def get_all_docs(path, subset=None, logger=logging.getLogger(__name__)):
        """Yield stories from disk, optionally filtered through a collection
        of valid stories.
        """
        if subset is not None:
            # Ensure quick lookups
            subset = set(subset)

        years = os.listdir(path)
        with Timer() as t:
            i = 0
            for year in years:
                month_tarballs = glob.glob(os.path.join(path, year, '*.tgz'))
                for month_tarball in month_tarballs:
                    with tarfile.open(month_tarball, 'r:gz') as f:
                        for member in f:
                            if not member.isfile():
                                continue

                            # Path of the member inside the tgz files
                            member_path = os.path.join(year, member.name)
                            i += 1

                            if subset is None or member_path in subset:
                                logging.debug("Reading {0}"
                                              .format(member_path))
                                if not logger.isEnabledFor(logging.DEBUG):
                                    t.status("Reading doc {0}: {1}"
                                             .format(i, member_path))

                                doc = NYTDoc(member_path,
                                             f.extractfile(member))
                                if doc.is_well_formed():
                                    yield doc
