# Data Overview

This folder contains resources for running and evaluating the pipeline. Below is a description of each file and directory.

> [!IMPORTANT]
> If you add new directories or files, be sure to update this README accordingly.

````
📁 data/
├── 📁 dev3/
├── 📁 fews_own_dev_zero/
├── 📁 dev1/
├── 📁 trial1/
├── 📁 trial1_pipeline_inputs/
├── 📄 README.md         -this file
````

### `dev3/`
- **Description:** Contains all data relevant to the dataset dev3 (Called 'Test Dataset' in the paper)
- **Purpose:** Main dataset for pipeline evaluation
- see [README](dev3/README.md)

### `fews_own_dev_zero/`
- **Description:** FEWS Dev Set (Zero-Shot)
- **Purpose:**  Zero-Shot evaluation on FEWS data
- see [README](fews_own_dev_zero/README.md)

### `dev1/`
- **Description:** Small dataset with annotations
- **Purpose:** small annotated dataset that was used in early evaluations of the pipeline
- see [README](dev1/README.md)

### `trial1/`
- **Description:** A small annotated dataset
- **Purpose:**  Regression testing
- see [README](trial1/README.md)

### `trial1_pipeline_inputs/`
- **Description:** Files that can be used as input to the pipeline for trial1 dataset
- **Purpose:**  Additional input files for trial1 dataset

## Run pipeline on datasets
For each provided dataset and their annotations there are also the respective dictionaries and the raw usages available which can be specified in the configuration files as input to the pipeline. Basic configuration files for running the pipeline on these datasets are available in the [/pipeline](../pipeline) directory and can be further modified:

dev1
- [`dev1_annotation.env`](../pipeline/dev1_annotation.env): Uses dev1 dictionaries and a precomputed set of usages

dev3
- [`dev3_annotation.env`](../pipeline/dev3_annotation.env): Uses dev3 dictionaries and a precomputed set of usages 
- [`dev3_annotation_LFS.env`](../pipeline/dev3_annotation_LFS.env): Uses a modified dev3 dictionary (LFS) and a reduced set of precomputed usages, which are necessary for this (for more information check the respective [README](dev3/alternative_inputs/README.md) or read the paper)
- [`dev3_annotation_MFS.env`](../pipeline/dev3_annotation_MFS.env): Uses a modified dev3 dictionary (MFS) and a reduced set of precomputed usages, which are necessary for this (for more information check the respective [README](dev3/alternative_inputs/README.md) or read the paper)

trial1
- [`config_trial1_skipS0.env`](../pipeline/config_trial1_skipS0.env): Uses trial_1 dictionaries and precomputed usages
