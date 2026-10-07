

# 1 Setup

To use the scripts of this pipeline step first prepare an environment with the required dependencies.

**Create and activate conda environment by executing:**

```conda create -n autodict python=3.10 pytorch=2.7.1 -c pytorch -c conda-forge```

```conda activate autodict```

**Execute:**

```pip install -r requirements.txt```
&nbsp;

---
**Exception**

For ```extract_usages.py``` follow instructions from [usage-extract](../../usage-extract/README.md) and after activating the environment and installing the module run:

```pip install pandas zstandard```

# 2. Example Workflow

---
When using LEMUR tsv and ODE xml files as input first transform them to the required format using:

[```ode_to_dict.py```](#ode_to_dictpy)

[```lemur_to_dict.py```](#lemur_to_dictpy)

---
If not available yet use the [usage-extract](../../usage-extract/README.md) tool or the [```extract_usages.py```](#extract_usagespy) script to generate usages to use as input

---
If no NSD model weights are available use

[```tune_nsd.py```](#tune_nsdpy)


---
Run main task of labeling usages recorded/unrecorded

[```main.py```](#31-mainpy)

---
To get a clean result file structure run

[```sort_results.py```](#sort_resultspy)

# 3.1. Scripts

## 3.1 main.py
```python main.py```

Main script takes dictionary and usage files and performs WSD, NSD and WSI to detect unrecorded usages which will be assigned to a cluster while recorded usages will be asigned to a dictionary sense. 

### Parameters

| Option                | type                | Description                                                                                                                                                 | default value |
|-----------------------|---------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| `--log_level`         | string              | Output in console all logging messages up to this level: <br>`[CRITICAL, ERROR, WARNING, INFO, DEBUG]`                                                      | `"INFO"`      |
| `--dictionary`        | string              | Path or glob pattern to the dictionary tsv file(s).                                                                                                         | -             |
| `--usages`            | string              | Path or glob pattern to the usages tsv file(s).                                                                                                             | -             |
| `--thresh`            | float               | Threshold for the NSD model to determine if a sense is novel. (float between 0 and 1)                                                                       | -             |
| `--result_dir`        | string              | Directory path where results will be stored.                                                                                                                | -             |
| `--nsd_weights`       | string              | Path to the NSD model weights (pickle file). Use tune_nsd.py to generate such a file using annotated data or use provided file in `data/models/NSD/NSD.pkl` | -             |
| `--context_limit`     | int                 | Cut usage to not exceed specified character limit. 0 to disable                                                                                         | `0`           |
| `--delete_embeddings` | `action='store_true'` | If set, all existing embeddings will be removed before recomputing.                                                                                         | `False`       |


### Inputs

Requires at least one dictionary tsv file containing word sense information and at least one tsv file containing respective word usages which will be compared against the dictionary to detect recorded/unrecorded usages and assign sense_ids / clusters.

---
**Dictionary Input Format**
```
identifier	lemma	sense_id	gloss
entry_1	arm	arm_010	a weapon     
entry_2	arm	arm_011	a body part
entry_3	snake	snake001	an animal
```

If you have an ODE xml file or LEMUR tsv file you can use [ode_to_dict.py](#ode_to_dictpy) or [lemur_to_dict.py](#lemur_to_dictpy) to convert them to this format. 

---
**Usages Input Format**
```
identifier	lemma	context	indexes_target_token	pos	date	grouping	description	indexes_target_sentence
usage_1	arm	They smuggled arms across the border at night.	14:18
usage_2	arm	He broke his arm playing football.	13:16
usage_3	arm	The rebels stockpiled arms in hidden bunkers.	22:26
usage_4	snake	A snake slithered across the path.	2:7
```

### Outputs

The script produces the following output files:

`configuration.tsv`  
  Contains major parameters used during execution like threshold values and input files

`nsd_weights.tsv`  
  Stores the NSD model weights used to compute recorded/unrecorded probabilities.

`results_raw`  
  Complete output file containing all recorded and unrecorded usages

`recorded.tsv`  
  Contains only the usages classified as *recorded* after thresholding.

`unrecorded.tsv`  
  Contains only the usages classified as *unrecorded* after thresholding.

`wsd.tsv`  
  Includes Word Sense Disambiguation (WSD) results for all input usages.

`wsi.tsv`  
  Includes Word Sense Induction (WSI) results for all input usages.


**Processed Usages Output**



```
identifier	lemma	sense_id	prob    thresh  is_novel	context	indexes_target_token	pos	date	grouping	description	indexes_target_sentence
usage_1	arm	arm_010	0.56    0.4 True	They smuggled arms across the border at night.	28:34
usage_2	arm	arm_011	0.72    0.4 True	He broke his arm playing football.	33:39
```

---

## ode_to_dict.py

```python ode_to_dict.py```

Script to transform ODE xml dictionary files into the required dictionary tsv format.

| Option                        | Type      | Description                                                                    | Default  |
| ----------------------------- | --------- | ------------------------------------------------------------------------------ | -------- |
| `--log_level`                 | string    | Output in console all logging messages up to this level: <br>`[CRITICAL, ERROR, WARNING, INFO, DEBUG]`                       | `"INFO"` |
| `--ode_files`                 | string\[] | One or more paths to ODE XML dictionary files                                  | -        |
| `--out`                       | string    | Output path for the resulting dictionary `.tsv` file                           | -        |
| `--ignore_sense_regions`      | string\[] | List of regional labels for which entire senses should be ignored              | `["US"]` |
| `--ignore_definition_regions` | string\[] | List of regional labels for which definitions should be ignored        | `["US"]` |
| `--ignore_posunit_regions`    | string\[] | List of regional labels for which entire part-of-speech units should be ignored | `["US"]` |


The ODE xml files include definitions, senses, or entire part-of-speech units that appear in both "US" and "British" variants with minimal differences. To avoid duplication, entries labeled with the "US" region are ignored by default when generating the dictionary .tsv file.

## lemur_to_dict.py

```python lemur_to_dict.py```

Script to transform LEMUR tsv files into the required dictionary tsv format.

| Option     | Type   | Description                                                                                                         | Default |
|------------| ------ | ------------------------------------------------------------------------------------------------------------------- | ------- |
| `--lemur`  | string | One or more paths to Lemur dictionary CSV files (must include columns: `Issue key`, `Headword/Lemma`, `Definition`) | -       |
| `--out`    | string | Output path where the transformed dictionary `.tsv` file will be written                                            | -       |


## extract_usages.py

```python extract_usages.py```

This script extracts usage examples for target words from the NOW corpus. It processes headword lists, applies optional corpus filters, and extracts contextual usages with specified parameters. Usages are saved in compressed TSV files organized by lemma.

### Setup

For ```extract_usages.py``` follow instructions from [usage-extract](../../usage-extract/README.md) and after activating the environment and installing the module run:

```pip install pandas zstandard```

### Parameters

| Option              | Type           | Description                                                                                            | Default     |
|---------------------|----------------|--------------------------------------------------------------------------------------------------------|-------------|
| `--log_level`       | string         | Output in console all logging messages up to this level: <br>`[CRITICAL, ERROR, WARNING, INFO, DEBUG]` | `"INFO"`    |
| `--context_range`   | int            | Number of words around the target word to include in the extracted usage                               | -           |
| `--result_dir`      | string         | Directory path where extracted usages will be saved                                                    | -           |
| `--total_usage_limit` | int          | Maximum number of usages to extract per lemma                                                          | -           |
| `--corpus_filter`   | string         | Glob pattern to filter which NOW corpus files to include                                               | -           |
| `--headword_files`  | string (list)  | Paths to text files containing target words, one word per line                                         | -           |
| `--random_state`    | int            | Random seed used for sampling/shuffling usages. Only relevant when applying limit.                     | `464`       |

### Inputs
**Example Headwords File (`headwords_example.txt`)**

```
apple
banana
cell
wagon
to come back to haunt somebody
```
### Outputs
In the specified result directory, for each headword a compressed tsv file containing the usages for that lemma is created. The info.tsv file provides information about the number of extracted usages per headword and the path to the usages file
```
result_directory/
├── headword_file1/
│   ├── 1/
│   │   └── usages_shuffle.tsv.zst
│   ├── 2/
│   │   └── usages_shuffle.tsv.zst
│   └── ...
├── headword_file2/
│   ├── 1/
│   │   └── usages_shuffle.tsv.zst
│   ├── 2/
│   │   └── usages_shuffle.tsv.zst
│   └── ...
└── info.tsv
```
**Example Extracted Usages File**
```
identifier	lemma	context	indexes_target_token	pos	date	grouping	description	indexes_target_sentence
NOW-1	arm	They smuggled arms across the border at night.	14:18
NOW-2	arm	He broke his arm playing football.	13:16
NOW-3	arm	The rebels stockpiled arms in hidden bunkers.	22:26
```

## sort_results.py

``python sort_results.py``

Takes a list of tsv files and puts them into the same filestructure used for the outputs of `extract_usages.py`, specified in the info.tsv. Files have to be tsv files and contain a "lemma" column.

| Option    | Type          | Description                                                                                       | Default |
| --------- | ------------- | ------------------------------------------------------------------------------------------------- | ------- |
| `--info`  | string        | Path to `info.tsv` file containing mappings of lemmas to output subdirectory paths                | –       |
| `--out`   | string        | Directory where the split usage files will be written                                             | –       |
| `--files` | string (list) | One or more usage files (`.tsv`) to be split according to the lemma-to-path mapping in `info.tsv` | –       |


## stats.py

``python stats.py``

Save useful information such as usage count per lemma throughout the different pipeline steps and number of dictionary entries in a .tsv file 

| Option          | Type          | Description                                                                         | Default |
| --------------- | ------------- | ----------------------------------------------------------------------------------- | ------- |
| `--file_s1`     | string        | Glob pattern or path to the initial usage file(s) (all usages before filtering steps) | –       |
| `--file_s1t`    | string        | Path to `.tsv` file containing unrecorded usages after step S1t                     | –       |
| `--file_s3t`    | string        | Path to `.tsv` file containing recorded usages after step S3t                       | –       |
| `--lemur_files` | string (list) | One or more CSV files from LEMUR, used to count lemma dictionary entries            | –       |
| `--dict_file`   | string        | Dictionary file in `.tsv` format used to count ODE entries per lemma                | –       |
| `--info`        | string        | Path to `info.tsv` file from usage extraction containing all lemmas                 | –       |
| `--output`      | string        | Output filename to write the combined lemma statistics table to                     | –       |


## tune_nsd.py

``python tune_nsd.py``

Script used to create a pickle file with tuned weights for the NSD model. Annotated data has to be provided as inputs.

| Option         | Type   | Description                                                                                  | Default |
| -------------- | ------ | -------------------------------------------------------------------------------------------- | ------- |
| `--dictionary` | string | Path to the dictionary file used for training the NSD model                                  | –       |
| `--usages`     | string | Path to the tagged usages file used for training the NSD model                               | –       |
| `--out`        | string | Output path for the trained model (a pickle file with learned weights); can include filename | –       |


### Inputs

**Dictionary File**

A regular dictionary file
```
identifier	lemma	sense_id	gloss
entry_1	arm	arm_010	a weapon     
entry_2	arm	arm_011	a body part
```
**Annotated Usages**

Usages annotated with senses from the dictionary

```
identifier	sense_id	lemma	context	indexes_target_token    date    pos grouping	description	indexes_target_sentence
id_1    arm_011 arm He broke his arm playing football.  13:16
id_2    arm_010 arm The rebels stockpiled arms in hidden bunkers.   22:26
id_3    arm_010 arm They smuggled arms across the border at night.  14:18
```