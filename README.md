Extraction and pre-processing of summarization datasets from the New York Times Annotated Corpus ([LDC2008T19](https://catalog.ldc.upenn.edu/LDC2008T19)).

### Installation

This library was developed and tested under Python 3.4. Feel free to send me errors or pull requests for extending compatibility to earlier versions of Python.

We depend on [NLTK](http://www.nltk.org/) for first-pass sentence splitting and [spaCy](https://spacy.io/) for verb detection via part-of-speech tagging.
```
$ pip3 install nltk
$ pip3 install spacy
```

### Usage

The typical flow for constructing a summarization dataset consists of:
  * Reading the compressed NYT corpus on disk and caching documents with the required topics and summaries in a [shelf](https://docs.python.org/3/library/shelve.html). This is skipped if the shelf already exists.
  * Filtering these documents as per summary properties like length and degree of extractiveness and pre-processing them to resolve errors and artifacts.
  * Splitting the filtered dataset into a train/dev/test partition and caching it for further experimentation.

This flow is illustrated in `main.py` with all relevant parameters exposed as command-line arguments. To get started, run:
```
main.py --help
```

### Citation

If you use this code in a research project, please cite:

Junyi Jessy Li, Kapil Thadani and Amanda Stent. The Role of Discourse Units in Near-Extractive Summarization. In *Proceedings of the 17th Annual Meeting of the Special Interest Group on Discourse and Dialogue (SIGDIAL).* 2016.

```
@InProceedings{li-thadani-stent-edusumm16,
  author    = {Li, Junyi Jessy  and  Thadani, Kapil  and  Stent, Amanda},
  title     = {The Role of Discourse Units in Near-Extractive Summarization},
  booktitle = {Proceedings of the 17th Annual Meeting of the Special Interest Group on Discourse and Dialogue (SIGDIAL)},
  year      = {2016},
}
```

Document IDs for the datasets used in this paper are available [here](http://www.cs.columbia.edu/~kapil/datasets/docids_nytsumm.tgz).
