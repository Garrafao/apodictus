import argparse
import glob
import logging
import sys
from pathlib import Path
import os
import time

import pandas as pd
from sklearn.metrics import precision_score, recall_score

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # parser.add_argument('--result_dir', type=str, help='Path to result directory as it is produced by pipeline.sh, containing s1/result_raw.tsv and s3/result_raw.tsv.')
    parser.add_argument('--config', type=str, default=None, help='Path to the configuration file used to produce these results.')
    parser.add_argument('--leaderboard', action='store_true', help='True/False whether result should be added to the leaderboard.tsv file.')
    parser.add_argument('--name', type=str, default=None, help='Name of the result in the leaderboard.tsv file.')
    parser.add_argument('--out_dir', type=str, default=".", help='Resulting file will be saved to this directory')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    config_path = args.config

    configuration = {}
    if config_path:
        # read configuration
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key = line.split("=")[0].strip()
                    value = line.split("=")[1].strip()
                    configuration[key] = value

    all_config_vals = ["result_dir", "s0_precomputed", "headword_files", "corpus_filter", "total_usage_limit",
                       "context_range", "random_state", "dictionary_s1", "threshold_s1", "max_usage_length_s1",
                       "model_weights_s1", "single_feature_s1", "max_prob_s1", "dictionary_s3", "threshold_s3",
                       "max_usage_length_s3", "model_weights_s3", "single_feature_s3", "max_prob_s3",
                       "use_small_config"]

    config_dict = {key: configuration.get(key, "") for key in all_config_vals}
    # result_dir = Path(args.result_dir)
    result_dir = Path(eval(config_dict['result_dir']))
    print(result_dir)
    out_dir = Path(args.out_dir)
    save_to_leaderboard = args.leaderboard
    result_name = args.name

    script_dir = Path(__file__).resolve().parent
    annotations_path = script_dir / "../data/dev3/annotated_usages/**/*usage_sample.tsv"
    mappings_path = script_dir / "../data/dev3/annotated_usages/**/*mappings.tsv"
    ode_path = script_dir / Path("../data/dev3/dictionaries/ode_dictionary.tsv")
    lemur_path = script_dir / Path("../data/dev3/dictionaries/lemur_dictionary.tsv")

    s1_paths = glob.glob(str(result_dir / "**/s1/result_raw.tsv*"), recursive=True)
    if not s1_paths:
        logging.error("No result_raw.tsv found in %s", str(result_dir))
        sys.exit(1)
    s1_path = Path(s1_paths[0])
    s3_paths = glob.glob(str(result_dir / "**/s3/result_raw.tsv*"), recursive=True)
    if not s3_paths:
        logging.error("No result_raw.tsv found in %s", str(result_dir))
        sys.exit(1)
    s3_path = Path(s3_paths[0])
    if not config_path:
        logging.warning("No configuration specified. No parameters will be added in the evaluation output file.")
    elif not Path(config_path).is_file():
        logging.error("No configuration file found at %s.", config_path)
        sys.exit(1)

    logging.info("Start evaluation of results from %s", str(result_dir))

    if not result_name:
        if config_path:
            result_name = Path(config_path).stem + "_results"
        else:
            result_name = time.strftime("results_evaluated_%Y-%m-%d_%H-%M-%S")

    # read annotated usages
    annotation_paths = glob.glob(str(annotations_path), recursive=True)
    df_annotation = pd.concat([pd.read_csv(a, sep="\t", dtype=str, encoding="utf-8") for a in annotation_paths])
    df_annotation = df_annotation[["sense_id", "identifier", "lemma"]].rename(columns={"sense_id": "annotation_id"})

    # only use first named sense_id annotation
    df_annotation["annotation_id"] = df_annotation["annotation_id"].apply(
        lambda sense_id: sense_id.split(",")[0].strip())

    # read sense_id mappings from annotations
    mapping_paths = glob.glob(str(mappings_path), recursive=True)
    df_mapping = pd.concat([pd.read_csv(m, sep="\t", dtype=str, encoding="utf-8") for m in mapping_paths])

    # create dictionary with sense_id mappings
    mapping_dict = {}
    for _, row in df_mapping.iterrows():
        mapping_dict[(row["lemma"], row["new_sense_id"])] = row["old_sense_id"]

    # apply sense_id mappings to get original sense_ids from simplified ones (e.g. 1 -> LMR-1573)
    df_annotation["annotation_id"] = df_annotation.apply(
        lambda r: mapping_dict.get((r["lemma"], r["annotation_id"]), r["annotation_id"]), axis=1)

    df_annotation = df_annotation[["identifier", "lemma", "annotation_id"]]

    # read dictionaries
    df_ode = pd.read_csv(ode_path, sep="\t", dtype=str, encoding="utf-8")
    ode_lemmas = df_ode["lemma"].tolist()
    df_lemur = pd.read_csv(lemur_path, sep="	", dtype=str, encoding="utf-8")
    df_lemur = df_lemur[["sense_id", "lemma"]].rename(columns={"sense_id": "lemur_id"})
    df_lemur = df_lemur[df_lemur["lemma"].isin(set(df_annotation["lemma"].tolist()))]

    # add in-/out-of ODE column to lemur dict
    df_lemur["in_ode"] = df_lemur["lemma"].apply(lambda lemma: lemma in ode_lemmas)

    df_s1 = pd.read_csv(s1_path, sep="\t", dtype={"lemma": str, "identifier": str, "prob": float, "thresh": float, "sense_id": str}, encoding="utf-8")[["lemma", "identifier", "prob", "thresh", "sense_id"]].rename(columns={"sense_id": "prediction_id"})
    df_s3 = pd.read_csv(s3_path, sep="\t", dtype={"lemma": str, "identifier": str, "prob": float, "thresh": float, "sense_id": str}, encoding="utf-8")[["lemma", "identifier", "prob", "thresh", "sense_id"]].rename(columns={"sense_id": "prediction_id"})

    df_s1 = df_s1.merge(df_annotation, on=["lemma", "identifier"], how="inner")
    df_s3 = df_s3.merge(df_annotation, on=["lemma", "identifier"], how="inner")

    if len(df_annotation) != len(df_s1):
        logging.error("The results do not contain all usages from the annotations. Only %s/%s usages are contained in the unfiltered s1 file", str(len(df_s1)), str(len(df_annotation)))
    logging.info("Evaluate results based on %s usages.", str(len(df_s1)))

    # apply threshold to the result_raw.tsv files
    df_s3_threshold = df_s3[df_s3["prob"] < df_s3["thresh"]].copy()

    # get total number of LEMUR sense usages for each LEMUR sense from unfiltered s1 result_raw.tsv file
    df_total_lemur_senses = df_s1["annotation_id"].value_counts().rename_axis("annotation_id").reset_index(
        name="lemur_sense_count_total")
    df_res = df_lemur.merge(df_total_lemur_senses, how="left", left_on="lemur_id", right_on="annotation_id").drop(
        columns=["annotation_id"])
    df_res["lemur_sense_count_total"] = df_res["lemur_sense_count_total"].fillna(0).astype(int)

    # get number of usages predicted as LEMUR evidence for each LEMUR sense
    df_predicted_lemur_count = df_s3_threshold["prediction_id"].value_counts().rename_axis("prediction_id").reset_index(
        name="predicted_lemur_count")
    df_res = df_res.merge(df_predicted_lemur_count, how="left", left_on="lemur_id", right_on="prediction_id").drop(
        columns=["prediction_id"])
    df_res["predicted_lemur_count"] = df_res["predicted_lemur_count"].fillna(0).astype(int)

    # get number of usages correctly labeled as LEMUR evidence for each LEMUR sense
    correct_counts = df_s3_threshold[df_s3_threshold["prediction_id"] == df_s3_threshold["annotation_id"]][
        "prediction_id"].value_counts().rename_axis("prediction_id").reset_index(name="correct_predictions")
    df_res = df_res.merge(correct_counts, how="left", left_on="lemur_id", right_on="prediction_id").drop(
        columns=["prediction_id"])
    df_res["correct_predictions"] = df_res["correct_predictions"].fillna(0).astype(int)

    df_res_in_ode = df_res[df_res["in_ode"]]
    df_res_out_ode = df_res[~df_res["in_ode"]]

    def calc_metrics(df_result_table: pd.DataFrame):
        # ignore precision where no LEMUR predictions were made and recall where no LEMUR usages exist to begin with
        df_valid_precision = df_result_table[df_result_table["predicted_lemur_count"] > 0].copy()
        df_valid_recall = df_result_table[df_result_table["lemur_sense_count_total"] > 0].copy()

        # calculate macro precision
        df_valid_precision["precision"] = df_valid_precision["correct_predictions"] / df_valid_precision[
            "predicted_lemur_count"]
        macro_precision = df_valid_precision["precision"].mean()

        # calculate macro recall
        df_valid_recall["recall"] = df_valid_recall["correct_predictions"] / df_valid_recall["lemur_sense_count_total"]
        macro_recall = df_valid_recall["recall"].mean()

        # overall precision and recall
        recall = df_result_table["correct_predictions"].sum() / df_result_table["lemur_sense_count_total"].sum()
        precision = df_result_table["correct_predictions"].sum() / df_result_table["predicted_lemur_count"].sum()

        return macro_precision, macro_recall, precision, recall

    macro_p, macro_r, p, r = calc_metrics(df_res)
    macro_p_in_ode, macro_r_in_ode, p_in_ode, r_in_ode = calc_metrics(df_res_in_ode)
    macro_p_out_ode, macro_r_out_ode, p_out_ode, r_out_ode = calc_metrics(df_res_out_ode)

    coverage = int((df_res["predicted_lemur_count"] > 0).sum())
    coverage_in_ode = int((df_res_in_ode["predicted_lemur_count"] > 0).sum())
    coverage_out_ode = int((df_res_out_ode["predicted_lemur_count"] > 0).sum())

    metrics_dict = {
        "macro_p": round(macro_p, 4),
        "macro_r": round(macro_r, 4),
        "p": round(p, 4),
        "r": round(r, 4),
        "coverage": coverage,
        "macro_p_in_ode": round(macro_p_in_ode, 4),
        "macro_r_in_ode": round(macro_r_in_ode, 4),
        "p_in_ode": round(p_in_ode, 4),
        "r_in_ode": round(r_in_ode, 4),
        "coverage_in_ode": coverage_in_ode,
        "macro_p_out_ode": round(macro_p_out_ode, 4),
        "macro_r_out_ode": round(macro_r_out_ode, 4),
        "p_out_ode": round(p_out_ode, 4),
        "r_out_ode": round(r_out_ode, 4),
        "coverage_out_ode": coverage_out_ode
    }


    df_final_result = pd.DataFrame([{**{"name": result_name},**metrics_dict, **config_dict}])
    os.makedirs(out_dir, exist_ok=True)
    df_final_result.to_csv(out_dir / "eval.tsv", sep="\t", index=False, encoding="utf-8")
    df_res.to_csv(out_dir / "pr-table.tsv", sep="\t", index=False, encoding="utf-8")
    logging.info(f"Results '{result_name}' written to '%s'", out_dir)

    leaderboard_path = script_dir / Path("../data/leaderboard.tsv")

    if save_to_leaderboard:
        if leaderboard_path.exists():
            df_leaderboard = pd.read_csv("../data/leaderboard.tsv", dtype=str, sep="\t", encoding="utf-8")
            df_leaderboard = pd.concat([df_leaderboard, df_final_result], ignore_index=True).sort_values(by="name", ascending=False)
        else:
            df_leaderboard = df_final_result
        df_leaderboard.to_csv("../data/leaderboard.tsv", sep="\t", index=False, encoding="utf-8")

    total_senses = len(df_res)
    total_senses_in_ode = len(df_res_in_ode)
    total_senses_out_ode = len(df_res_out_ode)

    print()
    print("| subset            | macroP | coverage |")
    print("|-------------------|--------|----------|")

    ood_macro_p = f"{macro_p_out_ode:.2f}"
    ood_coverage = f"{coverage_out_ode}/{total_senses_out_ode}"
    print(f"| out-of-dict       | {ood_macro_p:<6} | {ood_coverage:<8} |")

    id_macro_p = f"{macro_p_in_ode:.2f}"
    id_coverage = f"{coverage_in_ode}/{total_senses_in_ode}"
    print(f"| in-dict           | {id_macro_p:<6} | {id_coverage:<8} |")

    t_macro_p = f"{macro_p:.2f}"
    t_coverage = f"{coverage}/{total_senses}"
    print(f"| TOTAL             | {t_macro_p:<6} | {t_coverage:<8} |")