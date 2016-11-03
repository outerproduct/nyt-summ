#! /usr/bin/env python3
# Author: Kapil Thadani (kapil@cs.columbia.edu)

import argparse
from corpus import NYTCorpus


def add_args(parser):
    """Command-line arguments to extract a summarization dataset from the
    NYT Annotated Corpus.
    """
    # Paths to NYT data and temporary storage
    parser.add_argument('--nyt_path', action='store',
                        help='path to data/ in LDC release of NYT corpus',
                        default='/homes/thadani/resources/NYT/data')
    parser.add_argument('--shelf_path', action='store',
                        help='path to store a shelf of NYT data',
                        default='.')

    # Filters for NYT corpus based on descriptors and summary type
    parser.add_argument('--summary_type', action='store',
                        choices=('abstract', 'lead', 'online_lead'),
                        help='type of NYT summary to consider',
                        default='online_lead')
    parser.add_argument('--descriptors', action='store', nargs='+',
                        help='topics of docs to extract',
                        default=None)
    parser.add_argument('--descriptor_types', action='store', nargs='+',
                        choices=('indexing', 'online', 'online_general',
                                 'taxonomic', 'type'),
                        help='topic categories considered for --descriptors',
                        default=('online_general',))
    parser.add_argument('--exclude', action='store_true',
                        help='drop docs with --descriptors')

    # Filters for extracted docs based on the summary size
    parser.add_argument('--limit', action='store', type=int,
                        help='number of docs to consider',
                        default=None)
    parser.add_argument('--cost_type', action='store',
                        choices=('char', 'word', 'sent'),
                        help='type of cost per unit', default='char')
    parser.add_argument('--min_ref_cost', action='store', type=int,
                        help='minimum cost of a reference summary',
                        default=1)
    parser.add_argument('--max_ref_cost', action='store', type=int,
                        help='maximum cost of a reference summary',
                        default=int(1e9))
    parser.add_argument('--min_ref_sents', action='store', type=int,
                        help='minimum number of reference summary sentences',
                        default=1)
    parser.add_argument('--max_ref_sents', action='store', type=int,
                        help='maximum number of reference summary sentences',
                        default=int(1e9))

    # Mutually-exclusive filters for extractive and near-extractive summaries.
    # Multiple filters are treated as disjunctive, i.e., combinations of
    # the single-filter datasets
    parser.add_argument('--extractive', action='store_true',
                        help='every summary sentence comes from the doc')
    parser.add_argument('--semi_extractive', action='store_true',
                        help='one or more summary sentence is a contiguous '
                             'substring in a doc sentence; rest extractive')
    parser.add_argument('--sub_extractive', action='store_true',
                        help='one or more summary sentence is a '
                             'non-contiguous subsequence in a doc sentence; '
                             'rest semi-extractive')

    # Dataset partitioning by date
    parser.add_argument('--partition', action='store',
                        choices=('train', 'dev', 'test'),
                        help='dataset partition to extract',
                        default=None)
    parser.add_argument('--id_split', action='store', nargs=2,
                        help='any two prefixes of YYYY/MM/DD/DOCID to divide '
                             'the train/dev/test partition',
                        default=['2005/', '2006/'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="NYT summary extraction")
    add_args(parser)
    args = parser.parse_args()

    # Load (or create) a cached corpus of NYT docs
    nyt_corpus = NYTCorpus(nyt_path=args.nyt_path,
                           shelf_path=args.shelf_path,
                           summary_type=args.summary_type,
                           descriptors=args.descriptors,
                           descriptor_types=args.descriptor_types,
                           exclude=args.exclude)

    # Filter documents from the corpus by their summaries
    dataset = nyt_corpus.export_dataset(
        limit=args.limit,
        extractive=args.extractive,
        semi_extractive=args.semi_extractive,
        sub_extractive=args.sub_extractive,
        summary_type=args.summary_type,
        cost_type=args.cost_type,
        min_ref_cost=args.min_ref_cost,
        max_ref_cost=args.max_ref_cost,
        min_ref_sents=args.min_ref_sents,
        max_ref_sents=args.max_ref_sents)

    # Optionally extract a specific dataset partition
    if args.partition is None:
        dataset = list(dataset)
        print("{0} docs".format(len(dataset)))
    else:
        i, j = sorted(args.id_split)
        if i.isnumeric() and j.isnumeric():
            i, j = int(i), int(j)

        dataset = [doc for doc in dataset if
                   (args.partition == 'train' and doc.docid < i) or
                   (args.partition == 'dev' and i <= doc.docid < j) or
                   (args.partition == 'test' and j <= doc.docid)]

        print("{0} partition: {1} docs".format(args.partition.capitalize(),
                                               len(dataset)))
