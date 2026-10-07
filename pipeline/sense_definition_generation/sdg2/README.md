# Lemur Definition Generation and WSD Pipeline

This repository provides a pipeline for generating and refining word sense definitions using LLMs. It operates on the Lemur dataset and integrates context-based usage data to improve definition quality and perform word sense disambiguation (WSD).

## Overview

The pipeline performs the following major steps:

1. **Load and preprocess Lemur definitions.**
2. **Generate improved definitions using LLMs.**
3. **Integrate context sentences and generate context-aware definitions.**
4. **Use LLMs to choose the best definition.**
5. **Apply an LLM-based WSD method.**
6. **Save and log outputs (optionally via Weights & Biases).**

---

## Files

### `main.py`

Main entry point to run the entire pipeline.

### `lemur_retrieval.py`

Contains `get_lemur_definitions`, which loads and merges Lemur datasets.

### `prompt_builder.py`

Builds various prompts used for generating or evaluating definitions.

---

Make sure to change the config.py:
| Option             | type | Description                                                                                         |
|--------------------|--|-----------------------------------------------------------------------------------------------------|
| model        | string | Use desired Model like ["google/gemma-3-12b-it", ...]                                       |
| cuda_device       | integer | select cuda device (1 is required)
| dataset_path        | string | Path to input file                                       |
| group_sense_id        | boolean | Keep true to create for assigned clusters, false will generate for each usage                                     |
| sampling_params        | hyperparameter | Here you can specify WANB values if you want to track the run online on wandb                                      |

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


---
### example ouput file
| Field                 | Description                                                                                      |
|-----------------------|--------------------------------------------------------------------------------------------------|
| `lemma`               | The base or dictionary form of the word being defined (e.g., "bank", "light").                  |
| `sense_id`            | A unique identifier for a specific sense (meaning) of the lemma.                                |
| `generated_definition`| The automatically generated definition for this particular sense of the lemma.                  |
| `context`             | A sentence or passage where the lemma is used, helping illustrate its meaning in this sense.    |

And additional columns for the created definitions explained later in this readme file

---

## Setup

### Requirements

- Access to GPU (CUDA)
- HuggingFace-supported LLM via `vllm`
- `wandb` (optional, for logging)


---

## Usage

### Run the pipeline

```bash
python main.py --s3in path/to/input.tsv --outpath path/to/output.tsv
```

- `--s3in`: Path to input dataset (e.g., O2C sense-assigned dataset)
- `--outpath`: Path to save final output with generated definitions

---

## Pipeline Steps (Inside `main.py`)

### 1. Load Lemur Definitions

- Uses `get_lemur_definitions` to merge Lemur300 and Lemur1000 datasets.

### 2. Improve Existing Lemur Definitions

- Prompts built using `build_prompt_improve_existing_def`
- Generated definitions saved as `generated_definition`

### 3. Generate Definitions from Lemur Definition + Usages

- Uses `build_prompt_lem_group`
- New definitions saved as `gen_def_lemur+usages`

### 4. Generate Definitions from Usages Only

- Uses `build_prompt_group`
- New definitions saved as `gen_def_usages`

### 5. LLM-Based Definition Selection

- Uses `build_prompt_llm_def_decision`
- Best choice saved in `def_llm_chosen`

### 6. LLM-Based Word Sense Disambiguation (WSD)

- Uses `build_prompt_llm_based_wsd`
- Chosen sense ID saved in output

---

## Outputs

- Final TSV with definitions and choices: saved to path from `--outpath`
- Optional: Weights & Biases tables for each generation/decision step

---

## Example Output Columns

- `lemma`
- `definition`
- `generated_definition`
- `gen_def_usages`
- `gen_def_lemur+usages`
- `def_llm_chosen`
- `sense_id`
- `usages`


---
