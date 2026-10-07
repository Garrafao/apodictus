# APODICTUS

Dictionaries have to be regularly updated. This repository contains tools that help automate various aspects of the dictionary maintenance process. These tools are combined in a basic [pipeline](pipeline/pipeline1-diagram.png). Also an [annotated dataset](data/dev3/README.md) (2746 usages of 47 headwords) is introduced and the pipeline is evaluated on this dataset.

This code accompanies our [LREC 2026 paper](https://lrec.elra.info/lrec2026-main-924). If you use the code, please cite:

> F. Blessing, J. S. Sax, J. Kaufmann, W. Zhao, N. Arefyev, and D. Schlechtweg, "APODICTUS: Automatic Processing of DICTionary Update candidateS," in *Proceedings of the Fifteenth Language Resources and Evaluation Conference (LREC 2026)*, Palma, Mallorca, Spain, 2026, pp. 11800–11812. doi: 10.63317/3rtgegtzmpmv.

<details>
<summary>BibTeX</summary>

```bibtex
@inproceedings{blessing-etal-2026-apodictus,
  title = {APODICTUS: Automatic Processing of DICTionary Update candidateS},
  author = {Blessing, Felix and Sax, Johannes S. and Kaufmann, Julian and Zhao, Wei and Arefyev, Nikolay and Schlechtweg, Dominik},
  booktitle = {Proceedings of the Fifteenth Language Resources and Evaluation Conference (LREC 2026)},
  month = {May},
  year = {2026},
  pages = {11800--11812},
  address = {Palma, Mallorca, Spain},
  publisher = {European Language Resources Association (ELRA)},
  editor = {Piperidis, Stelios and Bel, Núria and van den Heuvel, Henk and Ide, Nancy and Krek, Simon and Toral, Antonio},
  doi = {10.63317/3rtgegtzmpmv}
}
```

</details>

 ### Important: step names differ from the paper

Compared to this repository, in the paper the step naming was adjusted to match the actual order of execution for clarity. S0 and S1 are the same in both, while S2 and S3 are swapped:

| Paper naming                         | This repository |
|--------------------------------------|---|
| S0: Usage extraction                 | S0 |
| S1: Unrecorded Usage Detection (UUD) | S1 |
| S2: Proposal Usage Detection         | **S3** |
| S3: Sense Proposal Generation        | **S2** |

# 📦 Installation
> [!NOTE]
> The following instructions were tested on MacOs, depending on your hardware you may need to modify them.

**Create and activate a conda environment with pytorch 2.7.0:**
```
conda create -n autodict python=3.10 pytorch=2.7.0 -c pytorch -c conda-forge
conda activate autodict
```

**To install dependencies, from the root directory run:**
```
pip install -r requirements.txt
pip install -e pipeline/usage-extract
```

## Sanity Check

To check that installation is successful, run the (baseline) pipeline on a small trial set. This should finish in a few minutes even when runnning on a CPU.
```
cd pipeline
bash pipeline.sh config_trial1.env
```


> [!NOTE]
> We employed [the NOW corpus](https://www.english-corpora.org/now/) to get usages for analysis. 
> However, to run the sanity check no access to NOW is required as the minimal subcorpus for the sanity check is provided in this repository.
> If you want to skip retrieval regardless, instead of `config_trial1.env` use the config file `config_trial1_skipS0.env` which consumes the pre-retrieved usages.

> [!NOTE]
> If you want to run a toy definition generation model as part of the sanity check,instead of `config_trial1.env` use the config file `config_trial1_with_sdg.env`.
> If you see errors during the definition generation step, try reinstalling the VLLM library following the instructions for your specific hardware (not provided in this repo). 

# 🧩 Reproduction of the paper results

### Table7: Macro Precision and Coverage for LEMUR Sense Proposals

```
cd pipeline
bash pipeline.sh dev3_annotation.env
python evaluate_dev3.py --out_dir "my_eval_results" --config "dev3_annotation.env" --name "my_pipeline_run" --leaderboard
```

**📊 Results**
```                            
| subset            | macroP | coverage |
|----------------------------|----------|
| out-of-dict       | 0.84   | 10/24    |
| in-dict           | 0.25   | 4/24     |
| TOTAL             | 0.67   | 14/48    |
```  
> [!Note]
> -	macroP: precision of usage detection for the LEMUR sense proposals, macro-averaged across the LEMUR sense proposals. <br>
> -	coverage: the proportion of the LEMUR sense proposals with at least one usage detected.<br>
> - more detailed results can be found in the output directory (e.g. "my_eval_results" specified in the command above)

### Figure2: Macro precision (y-axis) vs. coverage (x-axis)
```
bash reproduce_gridsearch.sh &>reproduce_gridsearch.logs
```
The script runs the following steps:
1) build a grid with different USD models and T1,T3 thresholds, then for each node in the grid build predictions for the development set;
2) calculate metrics for each node in the grid;
3) build plots.

> [!Note]
> Be prepared to wait a few hours for the grid search to finish, e.g. it takes 4-5 hours when running on a MacBook CPU. <br>

### Pre-publication data updates
A small number of LEMUR proposals were updated/simplified before publication for copyright reasons. This does not affect
the metrics reported in [Table 7](#table7-macro-precision-and-coverage-for-lemur-sense-proposals).

The updated files and entries are:

- `data/dev1/dictionaries/lemur_dictionary.tsv`: lobby
- `data/dev3/dictionaries/lemur_dictionary.tsv`: kanafeh, Netflix and chill, sideway, superheroic, to thread the needle, buckshee, VOC
- `data/trial1/lobby/dict.tsv`: lobby
- `data/trial1/tar/dict.tsv`: tar

**📊 Results**

The script dumps the [lineplots from the paper](tools/apodictus_eval/plots/raw_results/lineplots.png) 
and the corresponding [interactive line plots](tools/apodictus_eval/plots/raw_results/interactive_plots.html).



# 📁 Repository Structure

## [/data](data)
Data: the development sets, results and analysis.

## [/pipeline](pipeline)
The baseline pipeline.

## [/tools](tools)
Different tools for data transformation and analysis.

