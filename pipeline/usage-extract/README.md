# usage-extract
Extract usages for given headwords from the [NOW corpus](https://www.english-corpora.org/now/).

## Setup
*Tested with Python 3.11.11 and PyPy 7.3.19*

### Virtual environment
Create a virtual environment before installing with `virtualenv -p pypy3 .venv`

*For optimal performance, use [pypy](https://github.com/pypy/pypy). Using PyPy results roughly in a 2x speed-up compared to vanilla python.*

Activate the environment with `source .venv/bin/activate`

### Installation
Install the module with `pip install .`

This allows the script to be used anywhere with `ue`, if the environment is active.

## Usage
```
Usage: ue extract [OPTIONS]

Options:
  -h, --headwords-file, --headwords TEXT
                                  Path to headwords file
  --corpus-path, --corpus TEXT    Path to corpus
  -o, --output-file, --output TEXT
                                  Path to output file
  -c, --context INTEGER           Context before and after headword in usage
                                  (in tokens)  [default: 150]
  -s, --random-seed, --seed INTEGER
                                  Random seed used for subsampling during
                                  retrieval
  --tar-filter, --filter TEXT     Filter for tar files to be processed
  --help                          Show this message and exit.
```
### Example usages
| Description | Option |
| --- | --- |
| Headwords stored in headwords.txt | `-h headwords.txt`
| Output to different file | `-o custom.tsv`
| Set context to 50 | `-c 50`
| Only process target.tar | `--filter target.tar`
| Only process tar files starting with '10-' (supports globbing) | `--filter '10-*.tar'`
| Different corpus path | `--corpus /mount/spam/eggs/corpus/`
| Specify random seed | `--seed 271828`

## Input
### Corpus
The [NOW corpus](https://www.english-corpora.org/now/) is available in three different [formats](https://www.corpusdata.org/formats.asp): database, linear text and word/lemma/PoS (wlp).
The data is divided into tar files by quarter of the year, containing zip files for each month.
These in turn include the files for each supported language.

For this application the annotated wlp data is most suitable.
It is provided in [TSV](https://en.wikipedia.org/wiki/Tab-separated_values) files tagged with [CLAWS 7](https://ucrel.lancs.ac.uk/claws7tags.html) and encoded with [CP-1252](https://en.wikipedia.org/wiki/Windows-1252).

### Excerpt from wlp data
| text_id | token_id | word | lemma | pos
| --- | --- | --- | --- | ---
| 1334916 | 262406 | @@1334916 |  | fo
| 1334916 | 262407 | \<h\> | null
| 1334916 | 262408 | Britain | britain | np1
| 1334916 | 262409 | is | be | vbz
| 1334916 | 262410 | facing | face | vvg
| 1334916 | 262411 | an | a | at1

### Headwords
A list of headwords must be provided in a line-separated text file.
To retrieve usages for suffix headwords, a leading hyphen must be added for them to be processed correctly.

### Example headwords file `headwords.txt`
```
good
bad
-ish
```

## Output
By default, the output is written to the `output` folder and divided into multiple files.
The filenames follow the format `usages_{file_id}.tsv`, e.g. `usages_1234ABCD.tsv` (see below for an explanation of `file_id`).

If an output file is specified, headerless usage files will be written to the output folder and merged into the single output file. 
In this case, the output folder and its contents will be deleted afterwards.

When exporting `quoting=csv.QUOTE_MINIMAL` is specified.

### Usages file
The usage file(s) follow the [DURel](https://durel.ims.uni-stuttgart.de/docs/upload/file-type) format with the following keys:
| Column | Description |
| --- | --- |
| `lemma` | headword/lemma the usage is associated with
| `pos` | lemma's part of speech tag from the [CLAWS 7](https://ucrel.lancs.ac.uk/claws7tags.html) tagset
| `identifier` | usages's `source_id`
| `context` | usage text with the specified context surrounding the target word
| `indexes_target_token` | target word's position as a char range, for example, `5:11` implies the word spans from char index 5 to 10 of the corresponding usage text (excluding the upper boundary like with Python ranges)
| `indexes_target_sentence` | valid char range of the entire usage

The columns `date`, `grouping` and `description` are left empty.

The aforementioned field `source_id` makes it possible to trace the origin of the usage as it combines:
- an abbreviation of the name of the source corpus, currently `NOW`
- a `file_id` which consist of up to eight non-alphanumeric characters from the end of the filename, ignoring the extension (`SPAMEGGS-12-34_ab cd.txt` → `1234ABCD`)
- and a unique id within that corpus, e.g. a `text_id`

The format is extended by the following columns:
| Column | Description |
| --- | --- |
| `filename` | filename of usage origin
| `region` | region from filename
| `url` | url the document was scraped from
| `title` | document's title

### Example usages file `usages_1234AB.tsv` (empty columns omitted)
| lemma | pos | identifier | context | indexes_target_token | indexes_target_sentence | filename | region | url | title
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---
good | jj | NOW-1234AB-654320-1 | <usage_1> | 0:4 | 0:241 | 12-34-ab.txt | ab | https://test.ab/good | test good
bad | jj | NOW-1234AB-654321-1 | <usage_2> | 111:114 | 0:502 | 12-34-ab.txt | ab | https://test.ab/bad | test bad
