import json
import pickle
import subprocess
from pathlib import Path

import pandas as pd
import logging

logger = logging.getLogger()

# transform results back from axolotl format to original file format
def transform_results_from_axolotl(original_usages: Path, predictions: Path):
    df_original_usages = pd.read_csv(original_usages, sep='\t')
    df_predictions = pd.read_csv(predictions, sep='\t')

    df_original_usages["identifier"] = "usage_" + df_original_usages["identifier"].astype(str) + "_" + df_original_usages["lemma"].astype(str)
    df_predictions_usages = df_predictions[df_predictions['period'] == 'new'].copy()
    df_predictions_usages = df_predictions_usages.rename(columns={'usage_id': 'identifier'})
    cols = ['identifier', 'sense_id', 'prob'] if 'prob' in df_predictions_usages.columns else ['identifier', 'sense_id']
    df_out = pd.merge(df_predictions_usages[cols], df_original_usages.drop(columns=['sense_id'], errors='ignore'), on='identifier', how='left')
    df_out['identifier'] = (df_out['identifier'].astype(str).str.replace(r'^(entry_|usage_)', '', regex=True))
    df_out['identifier'] = df_out.apply(lambda row: row['identifier'][:-len('_' + row['lemma'])], axis=1)

    return df_out


# transform input files to correct format before running outlier2cluster on it
def transform_to_axolotl(output_path: Path, dict_input: Path, usage_input: Path, keep_annotations: bool, remove_empty_dict_lemmas = True):
    df_dict = pd.read_csv(dict_input, sep='\t')
    df_usages = pd.read_csv(usage_input, sep='\t')

    # if sense_id column exists already at this point with possibly annotations, keep or delete as specified
    if "sense_id" in df_usages.columns and not keep_annotations:
        df_usages = df_usages.drop(columns=['sense_id'])

    # rename columns to match required naming scheme
    df_dict = df_dict[["identifier", "lemma", "gloss", "sense_id"]].copy()
    df_dict = df_dict.rename(columns={
        'identifier': 'usage_id',
        'lemma': 'word',
    })
    df_usages = df_usages[["identifier", "lemma", "context", "indexes_target_token"]].copy()
    df_usages = df_usages.rename(columns={
        'identifier': 'usage_id',
        'lemma': 'word',
        'context': 'example',
        'indexes_target_token': 'indices_target_token'
    })

    # to make IDs globally unique add prefix just for outlier2cluster execution. Changed back later
    df_dict["usage_id"] = "entry_" + df_dict["usage_id"].astype(str) + "_" + df_dict["word"].astype(str)
    df_usages["usage_id"] = "usage_" + df_usages["usage_id"].astype(str) + "_" + df_usages["word"].astype(str)
    df_dict["period"] = "old"
    df_usages["period"] = "new"

    # fill empty columns with NA
    columns = ['usage_id', 'word', 'orth', 'sense_id', 'gloss', 'example', 'date', 'period']
    for col in columns:
        if col not in df_dict.columns:
            df_dict[col] = pd.NA
        if col not in df_usages.columns:
            df_usages[col] = pd.NA

    # fill empty index range column with empty string instead of NA (would cause issues with outlier2cluster)
    if "indices_target_token" not in df_dict.columns:
        df_dict["indices_target_token"] = "0:0"
    if "indices_target_token" not in df_usages.columns:
        df_usages["indices_target_token"] = "0:0"

    # write result to file with only the required columns
    columns.append("indices_target_token")

    # remove usages from the input that do not have any associated dictionary senses
    df_usages_no_dict = pd.DataFrame()
    if remove_empty_dict_lemmas:
        lemmas_with_dict = set(df_dict["word"])
        no_dict_mask = ~df_usages["word"].isin(lemmas_with_dict)
        df_usages_no_dict = df_usages[no_dict_mask].copy()

    df_out = pd.concat([df_dict, df_usages], ignore_index=True)[columns]
    df_out.to_csv(output_path, sep='\t', index=False)

    return df_usages_no_dict # return usages that were removed because they did not have any dictionary senses

# add embeddings to existing embedding json if a file already exists, else create it anew
def update_embeddings(embeddings_path: Path, model_path: Path, root_path: Path, temp_path: Path, target_files: list[Path]):
    # if embeddings file already exists add new embeddings to it
    if embeddings_path.exists():
        # get all sense and usage IDs with embeddings already in the file
        with open(embeddings_path) as f1:
            embedding_json = json.load(f1)
        sense_ids = list(embedding_json["glosses"].keys())
        usage_ids = list(embedding_json["contexts"].keys())

        # get all the input data (usages and dictionaries)
        df_files = []
        for file in target_files:
            df_file = pd.read_csv(file, sep="\t")
            df_files.append(df_file)

        df_all_data = pd.concat(df_files, ignore_index=True)

        # filter out all usages and senses that are already in the embeddings file and write to tsv file
        embedded_uid_mask = (df_all_data["period"] == "new") & (df_all_data["usage_id"].isin(usage_ids))
        embedded_sid_mask = (df_all_data["period"] == "old") & (df_all_data["sense_id"].isin(sense_ids))
        df_all_data_filtered = df_all_data[~embedded_uid_mask & ~embedded_sid_mask]
        if len(df_all_data_filtered) > 0:
            df_all_data_filtered.to_csv(temp_path / "to_vectorize.tsv", sep="\t", index=False)

            # run vectorization only on that data (senses and usages not already in the embeddings file)
            subprocess.run([
                "python", "-W", "ignore", str(root_path / "deepchange_at_axolotl" / "code" / "gr_vectorize.py"),
                "--model", model_path,
                "--datasets", str(temp_path / "to_vectorize.tsv"),
                "--out_file", str(temp_path / "vectorized.tsv")
            ], check=True)

            # merge these new embeddings with the old file
            with open(embeddings_path) as f_old, open(temp_path / "vectorized.tsv") as f_new:
                old_embeddings = json.load(f_old)
                new_embeddings = json.load(f_new)
            merged = {
                "glosses": {**old_embeddings["glosses"], **new_embeddings["glosses"]},
                "contexts": {**old_embeddings["contexts"], **new_embeddings["contexts"]}
            }
            # done, write back
            with open(embeddings_path, "w") as f_out:
                json.dump(merged, f_out)

    # if no embeddings file exists yet run as usual
    else:
        dataset_paths = ",".join(str(file) for file in target_files)
        subprocess.run([
            "python", "-W", "ignore", str(root_path / "deepchange_at_axolotl" / "code" / "gr_vectorize.py"),
            "--model", model_path,
            "--datasets", dataset_paths,
            "--out_file", str(embeddings_path.resolve())
        ], check=True)

# get model weights from pkl file,
# order of the weights and the respective feature names are reconstructed manually and changes might break the assignments
def get_model_weights(model_path: Path, out_file: Path):
    # extract nsd weights from pkl file
    with open(model_path, "rb") as m:
        model = pickle.load(m)
    clf = model.named_steps["clf"]

    weights = clf.coef_[0]
    feature_names = [
        "cosine_0", "cityblock_0", "euclidean_0", "norm_l1_0", "norm_l2_0",
        "cosine_1", "cityblock_1", "euclidean_1", "norm_l1_1", "norm_l2_1",
        "n_old_usages", "n_new_usages", "n_old_senses"
    ]

    df_weights = pd.DataFrame([weights], columns=feature_names)
    df_weights.to_csv(out_file, sep="\t", index=False)

# filter data before agglomerative execution to exclude lemmas with only one usage (no clustering possible)
def filter_agglomerative(data_path: Path):
    # get usages
    df_data = pd.read_csv(data_path, sep="\t")
    df_data = df_data[df_data["period"] == "new"]

    # get list of lemmas that only have one usage in the file
    lemma_counts = df_data["word"].value_counts()
    lemmas_one_usage = lemma_counts[lemma_counts == 1].index

    df_one_usage = df_data[df_data["word"].isin(lemmas_one_usage)].copy()
    df_data_filtered = df_data[~df_data["word"].isin(lemmas_one_usage)].copy()
    return df_one_usage, df_data_filtered

# truncate context column of dataframe according to max length (in characters). Tries to center target word
def truncate_context_around_target(context, target_span, max_length=512):
    """
    Truncate `context` so its length <= max_length, but keep target token fully inside.
    target_span: str in format "start:end" (character positions)
    """
    # get basic info
    start_idx, end_idx = map(int, target_span.split(':'))
    context_length = len(context)
    target_length = end_idx - start_idx

    # return without change if below limit
    if context_length <= max_length:
        return context, target_span, f"0:{len(context)}"

    if target_length > max_length:
        return context[start_idx:end_idx], f"0:{target_length}", f"0:{target_length}"

    # Get indices for ideal context size around target word, just under the limit
    before_length = (max_length - target_length) // 2
    after_length = max_length - target_length - before_length

    # calculate actual slices around target word
    slice_start = max(0, start_idx - before_length)
    slice_end = min(context_length, end_idx + after_length)

    # try to extend borders to left or right if actual length allows more
    actual_length = slice_end - slice_start
    if actual_length < max_length: # first try to expand to the right
        extra_needed = max_length - actual_length
        slice_end = min(context_length, slice_end + extra_needed)
        actual_length = slice_end - slice_start
    if actual_length < max_length: # if still space left try to expand to the left
        extra_needed = max_length - actual_length
        slice_start = max(0, slice_start - extra_needed)

    # get final indices and the truncated context
    new_start = start_idx - slice_start
    new_end = end_idx - slice_start
    new_span = f"{new_start}:{new_end}"
    new_context = context[slice_start:slice_end]

    return new_context, new_span, f"0:{len(new_context)}"

def apply_truncation(df_in: pd.DataFrame, max_length: int):
    df_in[['context', 'indexes_target_token', 'indexes_target_sentence']] = df_in.apply(lambda row: pd.Series(truncate_context_around_target(row['context'], row['indexes_target_token'], max_length)), axis=1)
    return df_in
