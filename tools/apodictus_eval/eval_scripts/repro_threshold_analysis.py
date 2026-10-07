import argparse
import glob
import json
import sys
import pandas as pd
import re
from typing import List
from dataclasses import dataclass
from sklearn.preprocessing import QuantileTransformer
from decimal import Decimal
import numpy as np

@dataclass
class ResultConfiguration:
    name: str # name that shows up in the plots
    path: str # path to the result root directory
    normalize_probs: bool = False# normalize so values between 0 and 1 if set to True
    in_ode: bool | None = None # True: Only in-ODE words; False: Only out-of-ODE words, None: no filtering
    mwe: bool | None = None # True: Only MWE; False: Only SWE, None: no filtering
    no_s1: bool = False


def read_annotated_usages(annotations_path: str, mappings_path: str) -> pd.DataFrame:
    # read annotated usages
    annotation_paths = glob.glob(annotations_path, recursive=True)
    df_annotation = pd.concat([pd.read_csv(a, sep="\t", dtype=str, encoding="utf-8") for a in annotation_paths])
    df_annotation = df_annotation[["sense_id", "identifier", "lemma"]].rename(
        columns={"sense_id": "annotation_id"})

    # only use first named sense_id annotation
    df_annotation["annotation_id"] = df_annotation["annotation_id"].apply(
        lambda sense_id: sense_id.split(",")[0].strip())

    # read mapping files
    mapping_paths = glob.glob(mappings_path, recursive=True)
    df_mapping = pd.concat([pd.read_csv(m, sep="\t", dtype=str, encoding="utf-8") for m in mapping_paths])

    # create dictionary with sense_id mappings
    mapping_dict = {}
    for _, row in df_mapping.iterrows():
        mapping_dict[(row["lemma"], row["new_sense_id"])] = row["old_sense_id"]

    # apply sense_id mappings to get original sense_ids from simplified ones (e.g. 1 -> LMR-1573)
    df_annotation["annotation_id"] = df_annotation.apply(
        lambda r: mapping_dict.get((r["lemma"], r["annotation_id"]), r["annotation_id"]), axis=1)

    return df_annotation[["identifier", "lemma", "annotation_id"]]


# read ode dictionary
def read_ode_dict(ode_path: str) -> pd.DataFrame:
    ode_paths = glob.glob(ode_path, recursive=True)
    df_ode = pd.concat([pd.read_csv(o, sep="\t", dtype=str, encoding="utf-8") for o in ode_paths])
    return df_ode

# read lemur dictionary
def read_lemur_dict(lemur_path: str) -> pd.DataFrame:
    lemur_paths = glob.glob(lemur_path, recursive=True)
    df_lemur = pd.concat([pd.read_csv(l, sep="\t", dtype=str, encoding="utf-8") for l in lemur_paths])
    df_lemur = df_lemur[["sense_id", "lemma"]].rename(columns={"sense_id": "lemur_id"})
    return df_lemur

# try to map values back to their original threshold
def get_original_thresh(threshold: float, prob_mapping: dict) -> float:
    normalized_probs = prob_mapping.keys()
    greater_probs = [p for p in normalized_probs if p > threshold]
    smaller_probs = [p for p in normalized_probs if p < threshold]
    if smaller_probs and greater_probs:
        return (prob_mapping[min(greater_probs)] + prob_mapping[max(smaller_probs)]) / 2
    elif smaller_probs and not greater_probs:
        return prob_mapping[max(smaller_probs)] + 1e-10
    elif not smaller_probs and greater_probs:
        return prob_mapping[min(greater_probs)] - 1e-10
    else:
        print("error.")
        sys.exit(1)

def calc_metrics(s1_preds: pd.DataFrame, s3_preds: pd.DataFrame, threshold_s3: float, lemur_base: pd.DataFrame):
    # get total number of LEMUR sense usages for each LEMUR sense
    df_total_lemur_senses = s1_preds["annotation_id"].value_counts().rename_axis("annotation_id").reset_index(name="lemur_sense_count_total")
    df_res = lemur_base.merge(df_total_lemur_senses, how="left", left_on="lemur_id", right_on="annotation_id").drop(columns=["annotation_id"])
    df_res["lemur_sense_count_total"] = df_res["lemur_sense_count_total"].fillna(0).astype(int)

    s3_preds_thresh = s3_preds[s3_preds["prob"]<threshold_s3].copy()

    # get number of usages predicted as LEMUR evidence for each LEMUR sense
    df_predicted_lemur_count = s3_preds_thresh["prediction_id"].value_counts().rename_axis("prediction_id").reset_index(name="predicted_lemur_count")
    df_res = df_res.merge(df_predicted_lemur_count, how="left", left_on="lemur_id", right_on="prediction_id").drop(columns=["prediction_id"])
    df_res["predicted_lemur_count"] = df_res["predicted_lemur_count"].fillna(0).astype(int)

    # get number of usages correctly labeled as LEMUR evidence for each LEMUR sense
    correct_counts = s3_preds_thresh[s3_preds_thresh["prediction_id"] == s3_preds_thresh["annotation_id"]]["prediction_id"].value_counts().rename_axis("prediction_id").reset_index(name="correct_predictions")
    df_res = df_res.merge(correct_counts, how="left", left_on="lemur_id", right_on="prediction_id").drop(columns=["prediction_id"])
    df_res["correct_predictions"] = df_res["correct_predictions"].fillna(0).astype(int)

    # ignore precision where no LEMUR predictions were made and recall where no LEMUR usages exist to begin with
    df_valid_precision = df_res[df_res["predicted_lemur_count"] > 0].copy()
    df_valid_recall = df_res[df_res["lemur_sense_count_total"] > 0].copy()

    # calculate macro precision
    df_valid_precision["precision"] = df_valid_precision["correct_predictions"] / df_valid_precision["predicted_lemur_count"]
    macro_precision = df_valid_precision["precision"].mean()

    # calculate macro recall
    df_valid_recall["recall"] = df_valid_recall["correct_predictions"] / df_valid_recall["lemur_sense_count_total"]
    macro_recall = df_valid_recall["recall"].mean()

    precision_valid_senses = len(df_valid_precision)
    recall_valid_senses = len(df_valid_recall)

    return macro_precision, macro_recall, precision_valid_senses, recall_valid_senses

def calc_results(result_inputs: List[ResultConfiguration], df_annotation: pd.DataFrame) -> pd.DataFrame:
    results = []
    for result in result_inputs:
        # read required result files
        s1_raw_results = glob.glob(result.path + "/s1/result_raw.tsv")
        s3_raw_results = glob.glob(result.path + "/s3/result_raw.tsv")
        if not s1_raw_results:
            print(f"could not find /s1/result_raw.tsv in {result.path}")
            sys.exit(1)
        if not s3_raw_results:
            print(f"could not find /s3/result_raw.tsv in {result.path}")
            sys.exit(1)
        df_s1_raw_results = pd.read_csv(s1_raw_results[0], sep="\t", encoding="utf-8", dtype={"identifier": str, "sense_id": str, "lemma": str, "prob": float})[["identifier", "lemma", "prob"]]
        df_s3_raw_results = pd.read_csv(s3_raw_results[0], sep="\t", encoding="utf-8", dtype={"identifier": str, "sense_id": str, "lemma": str, "prob": float})[["identifier", "lemma", "prob", "sense_id"]].rename(columns={"sense_id": "prediction_id"})

        s1_prob_mapping = {s1_prob: s1_prob for s1_prob in df_s1_raw_results["prob"].tolist()}
        s3_prob_mapping = {s3_prob: s3_prob for s3_prob in df_s3_raw_results["prob"].tolist()}

        # normalize probs using quantile transformer
        if result.normalize_probs:
            qt = QuantileTransformer(n_quantiles=100, output_distribution="uniform", random_state=0)
            probs_s1 = qt.fit_transform(df_s1_raw_results["prob"].to_numpy().reshape(-1, 1)).ravel()
            probs_s3 = qt.fit_transform(df_s3_raw_results["prob"].to_numpy().reshape(-1, 1)).ravel()
            eps = 1e-6
            probs_s1 = np.clip(probs_s1, eps, 1 - eps)
            probs_s3 = np.clip(probs_s3, eps, 1 - eps)

            # store mappings to later map back and recompute a threshold
            s1_prob_mapping = {s1_new: s1_original for s1_original, s1_new in zip(df_s1_raw_results["prob"].tolist(), probs_s1)}
            s3_prob_mapping = {s3_new: s3_original for s3_original, s3_new in zip(df_s3_raw_results["prob"].tolist(), probs_s3)}
            df_s1_raw_results["prob"] = probs_s1
            df_s3_raw_results["prob"] = probs_s3

        # merge results with annotations
        df_s1_merged = df_annotation.merge(df_s1_raw_results, on=["lemma", "identifier"], how="inner").copy()
        df_s3_merged = df_annotation.merge(df_s3_raw_results, on=["lemma", "identifier"], how="inner").copy()
        df_lemur_base = df_lemur.copy()

        # apply filters if specified
        if result.in_ode is not None:
            df_s1_merged = df_s1_merged[df_s1_merged["in_ode"] == result.in_ode].copy()
            df_s3_merged = df_s3_merged[df_s3_merged["in_ode"] == result.in_ode].copy()
            df_lemur_base = df_lemur_base[df_lemur_base["in_ode"] == result.in_ode].copy()
        if result.mwe is not None:
            df_s1_merged = df_s1_merged[df_s1_merged["mwe"] == result.mwe].copy()
            df_s3_merged = df_s3_merged[df_s3_merged["mwe"] == result.mwe].copy()
            df_lemur_base = df_lemur_base[df_lemur_base["mwe"] == result.mwe].copy()

        ids = set(df_s1_raw_results["identifier"].tolist())
        df_annotation_filtered = df_annotation[df_annotation["identifier"].isin(ids)]

        # for each combination of specified thresholds calculate metrics
        step_size = Decimal("0.01")
        step_count = int(Decimal("1.0") / step_size)
        thresholds = [float(i * step_size) for i in range(step_count + 1)]
        t1_thresholds = thresholds
        if result.no_s1:
            t1_thresholds = [0.0]
        for t1 in t1_thresholds:
            for t3 in thresholds:
                df_s1_filtered = df_s1_merged[df_s1_merged["prob"] > t1].copy()
                df_s3_filtered = df_s3_merged[df_s3_merged["identifier"].isin(df_s1_filtered["identifier"].tolist())].copy()
                precision, recall, valid_p, valid_r = calc_metrics(df_annotation_filtered,  df_s3_filtered, t3, df_lemur_base)
                results.append({"Precision": precision, "Recall": recall, "result_name": result.name, "t1": str(t1), "t3": str(t3), "valid_p_count": valid_p, "valid_r_count": valid_r, "t1_original": get_original_thresh(t1, s1_prob_mapping), "t3_original": get_original_thresh(t3, s3_prob_mapping)})
    return pd.DataFrame(results)

def prepare_output(result: pd.DataFrame):
    # save data to file so it can be used to plot outside this notebook
    plot_data = []
    for model_name, model_rows in result.groupby("result_name"):
        model_rows_clean = model_rows.dropna(subset=["Precision", "valid_p_count", "Recall"])
        if model_rows_clean.empty:
            continue
        # For each number of considered senses, get the highest possible precision, recall is second decider
        for valid_count, target_count_rows in model_rows_clean.groupby("valid_p_count"):
            highest_precision_rows = target_count_rows[
                target_count_rows["Precision"] == target_count_rows["Precision"].max()]
            best_row = \
            highest_precision_rows[highest_precision_rows["Recall"] == highest_precision_rows["Recall"].max()].iloc[
                [0]].copy()
            best_row["model"] = model_name
            plot_data.append(best_row)
    df_plot = pd.concat(plot_data)
    return df_plot

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configs', type=str, help='Path or globbing pattern to configuration files')
    args = parser.parse_args()

    # resolve given configuration paths
    configuration_paths = glob.glob(args.configs, recursive=True)
    if not configuration_paths:
        print(f"No files matched --configs input: {args.configs}")
        sys.exit(1)

    # generate plots for each configuration
    for configuration_path in configuration_paths:
        with open(configuration_path) as config_file:
            config = json.load(config_file)

            out_path = config["out_path"]

            # read required data
            df_annotations = read_annotated_usages(config["annotations_path"], config["mappings_path"])
            df_lemur = read_lemur_dict(config["lemur_path"])
            df_lemur = df_lemur[df_lemur["lemma"].isin(set(df_annotations["lemma"].tolist()))]
            df_ode = read_ode_dict(config["ode_path"])

            # add filter columns in_ode=True/False and mwe=True/False
            ode_lemmas = df_ode["lemma"].tolist()
            df_annotations["in_ode"] = df_annotations["lemma"].apply(lambda r: r in ode_lemmas)
            df_lemur["in_ode"] = df_lemur["lemma"].apply(lambda r: r in ode_lemmas)
            df_annotations["mwe"] = df_annotations["lemma"].apply(lambda r: len(re.split(r"[\s\-]+", r)) > 1)

            # for each pipeline result specified in the file read the result configuration
            result_configurations = []
            for result_configuration in config["result_configurations"]:
                result_configurations.append(ResultConfiguration(
                    name=result_configuration["name"],
                    path=result_configuration["path"],
                    in_ode=result_configuration.get("in_ode"),
                    mwe=result_configuration.get("mwe"),
                    normalize_probs=result_configuration.get("normalize_probs", False),
                    no_s1=result_configuration.get("no_s1", False),
                ))
            result = calc_results(result_configurations, df_annotations)
            result.to_csv(out_path + ".raw", sep="\t", index=False)
            df_out = prepare_output(result)
            df_out.to_csv(out_path, sep="\t", index=False)