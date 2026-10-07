# apodictus_eval

## 1. [`eval_scripts`](eval_scripts)
### 1.1 `eval_scripts/threshold_heatplot.ipynb`

Use this notebook to create Macro Precision, Macro Recall and Macro F-score heatplots. The script requires one or more pipeline results with no thresholds applied. This can be achieved by choosing '0' or negative threshold for S1 and a very high threshold for S3 when executing the pipeline. The script will then dynamically apply thresholds itself, in a loop over different threshold combinations to finally produce the heatplot.

Specify parameters in the first cells of the notebook:
- `result_inputs`: List of results to plot heatmaps for. Each result has to be specified as ResultConfiguration objects with attributes:
  - `name`: Name of the results displayed in the plots
  - `path`: Path to the root directory of the results (regular pipeline outputs containing "s1/result_raw.tsv" and "s3/result_raw.tsv")
  - `thresholds`: List of thresholds used for the heatmap
  - `in_ode`: True: Filter by in_ode=True; False: Filter by in_ode=False; None: no filter applied
  - `mwe`: True: Filter by mwe=True; False: Filter by mwe=False; None: no filter applied
  - `normalize_probs`: If True, normalize probabilities to be below 1.0 (dividing by max prob)
  
  for example:
  ````
  thresholds_regular = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]
  ResultConfiguration("Own Weights", "../results/full_run_annotation/own_dev_regular", thresholds=thresholds_regular, in_ode=None, mwe=None, normalize_probs=False),
  ````
- `annotations_path`(str): path or glob pattern to annotation files
- `mappings_path`(str): path or glob pattern to mapping files to map simplified annotations back to the original sense_id
- `lemur_path`(str): path to LEMUR tsv dictionary as used as input in the pipeline
- `ode_path`(str): path to ODE tsv dictionary as used as input in the pipeline
- `pdf_out`(str): output path for result plots PDF
- `show_sense_counts`(bool): if true calculate for each heatmap a table with the number of senses considered in their calculation

Several results based on the dev3 annotation are already available at [\results](\results) and can be used for the heatmaps.
In the notebook all parameters are already set and the notebook can be run as it is.


## 1.2 `eval_scripts/pr_table.ipynb`

Given annotations and one pipeline result output produce a precision recall table.


Specify parameters in the first cells of the notebook:
- `annotations_path`(str): path or glob pattern to annotation files
- `dictionaries_path`(str): path or glob pattern to the dictionary files of the annotation
- `mappings_path`(str): path or glob pattern to the mapping files of the annotation
- `s1_path`(str): path to the raw_result.tsv file of the S1 results
- `s3_path`(str): path to the raw_result.tsv file of the S3 results
- `s3_thresh`(float | None): If specified reapply the threshold on the s3 results. This only works for a threshold lower than the one used in the results.

In the notebook all parameters are already set for the dev3 annotations and the respective release_1 pipeline results (also used in thesis)


## 1.3 `eval_scripts/prob_distribution.ipynb`

Given annotations and a 'result_raw.tsv' file from pipeline results produce several plots analyzing the probability distribution.

Specify parameters in the first cells of the notebook:
- `annotations_path`(str): path or glob pattern to annotation files
- `dictionaries_path`(str): path or glob pattern to the dictionary files of the annotation
- `mappings_path`(str): path or glob pattern to the mapping files of the annotation
- `result_raw_path`(str): path to a raw_result.tsv file from pipeline results
- `step`(str): Either "S1" or "S3". Plots are adjusted depending on which pipeline step the provided results belong to

In the notebook all parameters are already set for the dev3 annotations and the respective release_1 pipeline results (also used in thesis).

## 2. [`results`](results)

Contains several results which can be used as input to `eval_scripts/pr_table.ipynb` to produce threshold heatmaps
