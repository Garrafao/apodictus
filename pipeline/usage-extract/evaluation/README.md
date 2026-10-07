<div align="center">

# 📈 Evaluation
</div>

To replicate the thesis recall results, access to the NOW corpus is needed.
Specifically, for the date range of the dev set, that is 2020 to 2024.

Alternatively, you can use the provided files that were produced by usage retrieval and searching the NOW web interface, to only replicate the creation of the tables.

To calculate precision, for each of the 60 headwords, up to five usages were randomly sampled from the retrieval run.
They were annotated binarily, ascertaining whether they fit the query lemma.
The result can be found in `provided/precision_sample.tsv`.

## 🚀 Running Retrieval
If you want to replicate retrieval itself, please use [these](../README.md) instructions for installation.
After setup, the following command runs the retrieval.

```
ue extract --headwords provided/dev_set.txt --filter "2*" --target 10000 --output dev_output.tsv
```

This will result in the files `dev_output.tsv` and `usage_stats.tsv`.
While the former does include the resulting usages, the latter contains the number of usages found and the number of usages exported.
These two values may differ as the usages are sampled to reach the target of 10000 usages per headword.

## 🔎 Searching NOW Web Interface
For each headword, the web interface was queried to get the number of usages contained in the corpus.
This was done by hand.
Each headword was searched in two ways: lowercase for matching the exact word form, and an uppercased version which matches on the lemma level.
A line in the files of the folder `now_stats` looks like this:
```
study drug	1012	1307
```
It contains the number of word form matches and lemma matches for each headword.

Assuming the data from that timeframe is not altered by NOW corpus, the numbers should stay the same.
Previous search results can be found in the `provided/now_stats` folder.

## 📊 Creating the Tables
To finally create the thesis tables, run the python notebook `evaluation.ipynb`.

Depending on which parts you want to replicate, paths in the notebook need to be adjusted to point to the correct folder/files.
Change the path variables in the first cell accordingly.
