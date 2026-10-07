### `fews_own_dev_zero`

This dataset consists of various files gathered for zero-shot dev set of FEWS. Below is a summary of each file and its contents:

### 📂 Dataset Files

| File Name                  | Description |
|---------------------------|-------------|
| **`gold_data_fews.tsv`**         | Full dataset containing annotated usages with assigned labels and gold sense IDs. |
| **`lemur_fews_short.tsv`**       | Subset similar to the Lemur format; only includes `sense_ids` that appear in `gold_data_fews.tsv`. |
| **`lemur_fews.tsv`**             | Extended version of Lemur format; includes all usages, specifically the first sense of each lemma in the full inventory. |
| **`sense_inv_lem+notlem.tsv`**   | Complete inventory of `sense_ids` for all lemmas found in `gold_data_fews.tsv`. |
| **`sense_inv_without_lem.tsv`** | Dictionary-style inventory used for S1; contains `sense_ids` of all lemmas present in `gold_data_fews.tsv`. |

### 🧠 Use Case

These files are designed for evaluating TSV and sense definition generation. 
For further experimets on the pipeline they got restructured in the basic "o2c" format.
