import argparse
import glob
import io
import sys
from pathlib import Path
import subprocess
import pandas as pd
import warnings
import logging
import zstandard as zstd

from utilities import transform_to_axolotl, transform_results_from_axolotl, update_embeddings, filter_agglomerative, \
    get_model_weights, apply_truncation
from model_setup import prepare_gloss_reader_FiEnRu, prepare_gloss_reader_GR

warnings.filterwarnings("ignore")

def read_input(path: str) -> pd.DataFrame:
    if path.endswith('.zst'):
        with open(path, 'rb') as f:
            decompressor = zstd.ZstdDecompressor()
            with decompressor.stream_reader(f) as reader:
                text_stream = io.TextIOWrapper(reader, encoding='utf-8')
                return pd.read_csv(text_stream, sep='\t')
    else:
        return pd.read_csv(path, sep='\t')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--log_level', type=str,
                        help='log level: "CRITICAL", "ERROR", "WARNING", "INFO" or "DEBUG"(default)', default="INFO")
    parser.add_argument('--dictionary', type=str, help='file path or glob pattern to the dictionary tsv file/s')
    parser.add_argument('--usages', type=str, help='file path or glob pattern to the usages tsv file/s')
    parser.add_argument('--thresh', type=float, help='Threshold for NSD model to consider a sense novel')
    parser.add_argument('--result_dir', type=str, help='path to directory to store results')
    parser.add_argument('--nsd_weights', type=str, default="", help='path to the nsd model weights (pickle file)')
    parser.add_argument('--context_limit', type=int, help='Cut usage to not exceed specified character limit. 0 to disable', default=0)
    parser.add_argument('--delete_embeddings', action='store_true', help="Clear all embeddings before execution")
    parser.add_argument('--ignore_wsi', action='store_true', help="if set don't use wsi results in outlier2cluster method")
    parser.add_argument('--single_feature', type=str, default="",help="Disable if empty string ''. Use only the specified metric for similarity measurement between usages and glosses. Can be 'cosine_0', 'cityblock_0', 'euclidean_0', 'norm_l1_0', 'norm_l2_0', 'cosine_1', 'cityblock_1', 'euclidean_1', 'norm_l1_1', 'norm_l2_1'.")
    parser.add_argument('--max_prob', type=float, default=1.0, help="Usages with no dictionary entries are automatically assigned this score. Should be the highest possible value, depending on metric used")
    args = parser.parse_args()

    if args.nsd_weights == "" and args.single_feature == "":
        logging.error("Either --nsd_weights or --single_feature must be specified but both are empty")
        sys.exit(1)
    if args.single_feature != "" and args.single_feature not in ['cosine_0', 'cityblock_0', 'euclidean_0', 'norm_l1_0', 'norm_l2_0', 'cosine_1', 'cityblock_1', 'euclidean_1', 'norm_l1_1', 'norm_l2_1']:
        logging.error("--single_feature must be one of 'cosine_0', 'cityblock_0', 'euclidean_0', 'norm_l1_0', 'norm_l2_0', 'cosine_1', 'cityblock_1', 'euclidean_1', 'norm_l1_1', 'norm_l2_1' but is %s", args.single_feature)
        sys.exit(1)

    # initialize debugging
    log_levels = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
    }
    logging.basicConfig(
        level=log_levels.get(args.log_level.upper(), logging.INFO),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # check file paths
    dictionaries = glob.glob(args.dictionary, recursive=True)
    if not dictionaries:
        logging.error("No files matched --dictionary input: %s", args.dictionary)
        sys.exit(1)
    usages = glob.glob(args.usages, recursive=True)
    if not usages:
        logging.error("No files matched --usages input: %s", args.usages)
        sys.exit(1)

    root_dir = Path(__file__).resolve().parent.parent
    data_dir = root_dir / "data"
    temp_dir = data_dir / "temp"
    result_dir = Path(args.result_dir)
    nsd_weights_path = Path(args.nsd_weights)

    Path(data_dir / "embeddings").mkdir(parents=True, exist_ok=True)
    Path(args.result_dir).mkdir(parents=True, exist_ok=True)
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    Path(data_dir / "models").mkdir(parents=True, exist_ok=True)

    df_dictionaries = [read_input(d) for d in dictionaries]
    df_dictionaries_combined = pd.concat(df_dictionaries, ignore_index=True)
    df_usages = [read_input(u) for u in usages]
    df_usages_combined = pd.concat(df_usages, ignore_index=True)

    # remove previous results if necessary
    df_usages_combined = df_usages_combined.drop(columns=["prob", "thresh", "is_novel"], errors="ignore")
    df_usages_combined["sense_id"] = ""


    # only continue with dictionary entries where the lemma is in the usages
    df_dictionaries_combined = df_dictionaries_combined[df_dictionaries_combined['lemma'].isin(df_usages_combined['lemma'])]

    df_usages_combined.to_csv(temp_dir / "usages_original.tsv", sep='\t', index=False)

    if df_usages_combined.empty:
        # if the usages dataframe is empty write empty files to the result folder right away, skipping unnecessary steps
        logging.info("Input usages dataframe is empty")
        base_columns = list(df_usages_combined.columns)
        result_columns = base_columns + ["prob", "thresh", "is_novel"]
        pd.DataFrame(columns=base_columns).to_csv(result_dir / "wsd.tsv", sep="\t", index=False)
        pd.DataFrame(columns=base_columns).to_csv(result_dir / "wsi.tsv", sep="\t", index=False)
        pd.DataFrame(columns=result_columns).to_csv(result_dir / "result_raw.tsv", sep="\t", index=False)
        pd.DataFrame(columns=result_columns).to_csv(result_dir / "recorded.tsv", sep="\t", index=False)
        pd.DataFrame(columns=result_columns).to_csv(result_dir / "unrecorded.tsv", sep="\t", index=False)
    else:
        # truncate usages if specified
        if args.context_limit > 0:
            df_usages_combined = apply_truncation(df_usages_combined, args.context_limit)

        df_usages_combined.to_csv(temp_dir / "usages.tsv", sep='\t', index=False)
        df_dictionaries_combined.to_csv(temp_dir / "dictionary.tsv", sep='\t', index=False)

        dictionary_path = temp_dir / "dictionary.tsv"
        usages_path = temp_dir / "usages_original.tsv"

        # clone deepchange_at_axolotl repository which provides required scripts
        target_dir = root_dir / "deepchange_at_axolotl"
        if not target_dir.exists():
            subprocess.run([
                "git", "clone",
                "https://github.com/deniskokosss/deepchange_at_axolotl.git",
                str(target_dir)
            ], check=True)

        # embedding file paths
        embeddings_path_FiEnRu = data_dir / "embeddings" / "GR_FiEnRu.json"
        embeddings_path_GR = data_dir / "embeddings" / "GR.json"

        # Delete existing embeddings before execution if specified, else add to them
        if args.delete_embeddings:
            logging.info("Remove embeddings")
            for file in [embeddings_path_GR, embeddings_path_FiEnRu]:
                if file.exists():
                    file.unlink()

        # transform input files into the format required by scripts from the deepchange_at_axolotl repository
        logging.info("Transform files to axolotl format")
        df_guaranteed_novel = transform_to_axolotl(temp_dir / "data.tsv", dictionary_path, temp_dir / "usages.tsv", False)
        guaranteed_novel_words = df_guaranteed_novel["word"].tolist()
        if len(df_guaranteed_novel) > 0:
            logging.info(f"{len(df_guaranteed_novel)} word usages are automatically labeled as novel witha high score because the word has no dictionary senses.")
            logging.info(f"{len(df_guaranteed_novel['word'].unique())} lemmas are affected:")
            logging.info(f"{df_guaranteed_novel['word'].unique().tolist()}")

        # prepare required models
        logging.info("Prepare required models")
        GR_FiEnRu_path = data_dir / "models" / "GR_FiEnRu" / "model.safetensors"
        GR_path = data_dir / "models" / "GR" / "model.pt"
        prepare_gloss_reader_FiEnRu()
        prepare_gloss_reader_GR()

        # update/create embeddings
        logging.info("Start vectorization of dictionary entries and usages")
        update_embeddings(embeddings_path_FiEnRu, GR_FiEnRu_path, root_dir, temp_dir, [temp_dir / "data.tsv"])
        update_embeddings(embeddings_path_GR, GR_path, root_dir, temp_dir, [temp_dir / "data.tsv"])

        # usages without respective headword senses in the dictionary have to be removed for scripts that require dictionary
        df_data = pd.read_csv(temp_dir / "data.tsv", sep="\t", encoding="utf-8")
        df_data_filtered = df_data[~df_data["word"].isin(guaranteed_novel_words)]
        df_data_filtered.to_csv(temp_dir / "data_filtered.tsv", sep="\t", index=False)

        # run wsd on the data
        logging.info("Run gr_wsd.py for wsd")
        subprocess.run([
            "python", "-W", "ignore", str(root_dir / "deepchange_at_axolotl" / "code" / "gr_wsd.py"),
            "--vectors_file", embeddings_path_FiEnRu,
            "--dataset", str(temp_dir / "data_filtered.tsv"),
            "--pred", str(temp_dir / "temp_wsd.tsv")
        ], check=True)

        df_wsd = pd.read_csv(temp_dir / "temp_wsd.tsv", sep="\t", encoding="utf-8")
        df_guaranteed_novel["sense_id"] = "-"
        df_wsd = pd.concat([df_wsd, df_guaranteed_novel], ignore_index=True)
        df_wsd.to_csv(temp_dir / "wsd.tsv", sep="\t", index=False)

        # transform wsd results back to the original format and save in results
        transform_results_from_axolotl(usages_path,temp_dir / "wsd.tsv").to_csv(result_dir / "wsd.tsv", sep='\t', index=False)

        # remove usages of lemmas which only have one usage (agglomerative will fail otherwise)
        df_one_usage, df_data_filtered = filter_agglomerative(temp_dir / "data.tsv")
        df_data_filtered.to_csv(temp_dir / "agglomerative_input.tsv", sep="\t", index=False)

        # run agglomerative on filtered usages
        logging.info("Run Agglomerative.py for wsi clustering")
        subprocess.run([
            "python", "-W", "ignore", str(root_dir / "deepchange_at_axolotl" / "code" / "Agglomerative.py"),
            "--embeds", embeddings_path_FiEnRu,
            "--dataset", str(temp_dir / "agglomerative_input.tsv"),
            "--predict", str(temp_dir / "wsi.tsv")
        ], check=True)

        # add previously filtered usages back (with cluster 0 for them all as there is only one usage per lemma)
        df_wsi_results = pd.read_csv(temp_dir / "wsi.tsv", sep="\t")
        df_one_usage = df_one_usage.copy()
        df_one_usage["sense_id"] = 0
        pd.concat([df_wsi_results, df_one_usage], ignore_index=True).to_csv(temp_dir / "wsi.tsv" ,sep="\t", index=False)

        # transform wsi results back to the original format and save in results
        transform_results_from_axolotl(usages_path, temp_dir / "wsi.tsv").to_csv(result_dir / "wsi.tsv", sep='\t', index=False)

        # need wsi results without the words with missing dictionary senses for o2c script
        df_wsi_o2c = pd.read_csv(temp_dir / "wsi.tsv", sep="\t")
        df_wsi_guaranteed_novel = df_wsi_o2c[df_wsi_o2c["word"].isin(guaranteed_novel_words)]
        df_wsi_o2c = df_wsi_o2c[~df_wsi_o2c["word"].isin(guaranteed_novel_words)]
        df_wsi_o2c.to_csv(temp_dir / "wsi_o2c.tsv", sep="\t", index=False)

        # only needed for tests replicating axolotl results (they ignore wsi results)
        wsi_results = str(temp_dir / "wsi_o2c.tsv")
        if args.ignore_wsi:
            wsi_results = 'none'

        logging.info("Run outlier2cluster.py")
        outlier2cluster_command=[
            "python", "-W", "ignore", str(root_dir / "deepchange_at_axolotl" / "code" / "outlier2cluster.py"),
            "--embeds", f"{str(embeddings_path_FiEnRu)},{str(embeddings_path_GR)}",
            "--dataset", str(temp_dir / "data_filtered.tsv"),
            "--wsd", str(temp_dir / "temp_wsd.tsv"),
            "--wsi", wsi_results,
            "--tresh", str(args.thresh),
            "--predict", str(temp_dir / "result_axolotl.tsv"),
            "--predict_extended", str(temp_dir / "probs.tsv")
        ]
        if args.single_feature != "":
            outlier2cluster_command += ["--single_feature", args.single_feature]
        else:
            outlier2cluster_command += ["--model", str(nsd_weights_path)]

        subprocess.run(outlier2cluster_command, check=True)

        df_probs = pd.read_csv(temp_dir / "probs.tsv", sep='\t')
        df_probs = df_probs.rename(columns={"is_outlier_prob": "prob"})

        df_result_axolotl = pd.read_csv(temp_dir / "result_axolotl.tsv", sep='\t', encoding="utf-8")
        df_result_temp = pd.merge(df_result_axolotl, df_probs[['usage_id', 'prob']], on='usage_id', how='left')

        # add previously filtered usages without dictionary entries and add probabilities
        if len(df_wsi_guaranteed_novel) > 0:
            df_wsi_guaranteed_novel['prob'] = args.max_prob # used to be 1 but when using other metrics it might need to be greater
            df_result_temp = pd.concat([df_result_temp, df_wsi_guaranteed_novel], ignore_index=True)

        df_result_temp["is_novel"] = df_result_temp["prob"] > args.thresh
        df_result_temp["thresh"] = args.thresh

        df_result_temp.to_csv(temp_dir / "result.tsv", sep='\t', index=False, encoding="utf-8")
        df_result_raw = (transform_results_from_axolotl(usages_path, temp_dir / "result.tsv"))
        df_result_raw["thresh"] = args.thresh
        df_result_raw.to_csv(result_dir / "result_raw.tsv", sep='\t', index=False)

        subprocess.run([
            "python", str(root_dir / "code" / "thresh.py"),
            "--result", str(result_dir / "result_raw.tsv"),
            "--out_recorded", str(result_dir / "recorded.tsv"),
            "--out_unrecorded", str(result_dir / "unrecorded.tsv"),
            "--thresh", str(args.thresh),
        ], check=True)

    if args.nsd_weights != "" and args.single_feature == "":
        get_model_weights(nsd_weights_path, result_dir / "nsd_weights.tsv")

    # dump all run parameters in result folder
    configuration = {"thresh": str(args.thresh),
                    "dictionary_input": str(args.dictionary),
                    "usages_input": str(args.usages),
                    "nsd_weights_path": args.nsd_weights,
                    "single_feature": args.single_feature,
                    "result_dir": str(result_dir.resolve())
                    }

    df_configuration = pd.DataFrame(list(configuration.items()), columns=['parameter', 'value'])
    df_configuration.to_csv(result_dir / "configuration.tsv", sep='\t', index=False)

    logging.info("Execution DONE. See results in %s", str(result_dir))