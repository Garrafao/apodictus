# Experiments: SDG+WSD vs. WSI

This repository contains the experiments comparing **SDG+WSD** and **WSI**.

---

## Setup

Before running the experiments, configure the setup file `config.py` with the following parameter:

"dataset_path": "Path to the usages available"

he input data has to be in the o2c format of the pipeline and should contain an additional column named sense_id_gold. Which contains the gold sense for given usage.

Make sure to change the config.py accordingly:
| Option             | type | Description                                                                                         |
|--------------------|--|-----------------------------------------------------------------------------------------------------|
| model        | string | Use desired Model like ["google/gemma-3-12b-it", ...]                                       |
| cuda_device       | integer | select cuda device (atleast 1 is required)
| dataset_path        | string | Path to input file                                       |
| sampling_params        | hyperparameter | Here you can specify WANB values if you want to track the run online on                                 |

For Sampling_params:
| Parameter            | Typical Range     | Simple Explanation                                                                 |
|----------------------|-------------------|-------------------------------------------------------------------------------------|
| `temperature`        | 0.0 – 1.0          | How random the responses are. Lower = more focused, higher = more creative.         |
| `top_p`              | 0.1 – 1.0          | Controls how many words are considered. Lower = safer, higher = more varied.        |
| `top_k`              | 1 – 1000           | Only picks from the top K words. Lower = more predictable, higher = more options.   |
| `max_tokens`         | 1 – 4000+          | How long the response can be. Higher = longer answers.                              |
| `presence_penalty`   | -2.0 – 2.0         | Encourages new topics. Higher = more new ideas, lower = more of the same.           |
| `frequency_penalty`  | -2.0 – 2.0         | Reduces repeated words. Higher = less repetition.                                   |
| `repetition_penalty` | 1.0 – 2.0          | Makes repeats less likely. Higher = fewer repeated words or phrases.                |


### example input file
| Field                   | Description                                                                                   |
|-------------------------|-----------------------------------------------------------------------------------------------|
| `identifier`            | A unique ID for the usage example or data entry.                                              |
| `lemma`                 | The base form of the word being analyzed (e.g., "run", "arm").                                |
| `context`               | The full sentence or text snippet where the lemma appears.                                    |
| `indexes_target_token`  | The start and end character positions of the lemma within the context (e.g., `14:18`).        |
| `pos`                   | Part of speech of the lemma (e.g., noun, verb). May be left blank if not available.           |
| `date`                  | Date of the source text or usage, if applicable. May be left blank.                           |
| `grouping`              | Grouping of similar usages.                                       |
| `description`           | Additional notes or explanation about the usage. May be left blank.                                              |
| `indexes_target_sentence` | The start and end character positions of the full sentence in the original text. Optional. |
| `is_novel`              | The boolean value of novel or not. Optional.                                   |
| `thresh`              | The threshold used in the pipeline step. Optional.                                    |
| `sense_id_gold`         | The gold sense id from annotation.                                    |

---

## Run

To run the experiments use: 
`python main.py`

## Results

Average per lemma adjusted rand index is calculated



