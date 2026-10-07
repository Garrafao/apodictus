import argparse
import glob
import io
import logging
import sys

import pandas as pd
import zstandard as zstd
from pathlib import Path


def read_input(path: str) -> pd.DataFrame:
    if path.endswith('.zst'):
        with open(path, 'rb') as f:
            decompressor = zstd.ZstdDecompressor()
            with decompressor.stream_reader(f) as reader:
                text_stream = io.TextIOWrapper(reader, encoding='utf-8')
                return pd.read_csv(text_stream, sep='\t')
    else:
        return pd.read_csv(path, sep='\t')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file_s1', type=str, required=True, help="initial usage file/s. Path or glob pattern")
    parser.add_argument('--file_s1t', type=str, required=True, help="unrecorded output after S1t")
    parser.add_argument('--file_s3t', type=str, required=True, help="recorded output after S3t")
    parser.add_argument('--lemur_file', type=str, required=True, help="lemur dictionary tsv file")
    parser.add_argument('--dict_file', type=str, required=True, help="dictionary tsv file")
    parser.add_argument('--info', type=str, required=True, help="path to info.tsv containing all headwords")
    parser.add_argument('--output_dir', type=str, help="output directory for statistic files")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    out_dir = Path(args.output_dir)

    # read relevant data from usage-extraction info.tsv
    df_info = pd.read_csv(args.info, sep='\t')
    df_info = df_info.rename(columns={"headword": "lemma",
                                      "usages_found": "S0_usages_found",
                                      "usages_exported": "S0_usages_exported",
                                      "usages_deduplicated": "S0_usages_deduplicated"})
    # select relevant columns
    df_info = df_info[["lemma", "S0_usages_found", "S0_usages_exported", "S0_usages_deduplicated"]]

    # read the results/usages from different pipeline steps
    files_s1 = glob.glob(args.file_s1, recursive=True)
    if not files_s1:
        logging.error("No files matched --file_s1 input: %s", args.file_s1)
        sys.exit(1)
    df_s1_list = [read_input(f) for f in files_s1]
    df_s1 = pd.concat(df_s1_list, ignore_index=True)
    df_s1t = pd.read_csv(args.file_s1t, sep='\t')
    df_s3t = pd.read_csv(args.file_s3t, sep='\t')

    count_s1 = df_s1['lemma'].value_counts().rename("S1_input_usage_count")
    count_s1t = df_s1t['lemma'].value_counts().rename("S1t_usage_count")
    count_s3t = df_s3t['lemma'].value_counts().rename("S3t_usage_count")

    # combine all the lemma usage counts in one file
    df_counts = pd.concat([count_s1, count_s1t, count_s3t], axis=1).fillna(0).astype(int)
    df_counts = df_counts.reset_index().rename(columns={"index": "lemma"})
    df_counts = df_info.merge(df_counts, on="lemma", how="left")

    # get lemur and ode counts for lemmas
    lemur_dict = pd.read_csv(args.lemur_file, sep='\t')
    lemur_counts = lemur_dict['lemma'].value_counts().rename("LEMUR_entry_count")

    dictionary = pd.read_csv(args.dict_file, sep='\t')
    ode_counts = dictionary['lemma'].value_counts().rename("ODE_entry_count")

    # add lemur and ode entry counts to file
    df_counts = df_counts.join(lemur_counts, on="lemma", how='left')
    df_counts = df_counts.join(ode_counts, on="lemma", how='left')

    # prepare for saving
    df_counts = df_counts.fillna(0)
    numeric_cols = df_counts.columns.difference(['lemma'])
    df_counts[numeric_cols] = df_counts[numeric_cols].astype(int)
    column_order = ["lemma", "ODE_entry_count", "LEMUR_entry_count", "S0_usages_found", "S0_usages_exported", "S0_usages_deduplicated","S1_input_usage_count" ,"S1t_usage_count", "S3t_usage_count"]
    df_counts = df_counts[column_order]
    df_counts = df_counts.sort_values(by="lemma", ascending=False)

    # safe result
    df_counts.to_csv(out_dir / "usage_counts.tsv", sep='\t', index=False)

    # get all LEMUR senses for the target headwords
    headwords = df_info["lemma"].to_list()
    df_lemur_target_headwords = lemur_dict[lemur_dict['lemma'].isin(headwords)].copy()

    # Get LEMUR evidence counts
    sense_counts = df_s3t['sense_id'].value_counts().rename_axis('sense_id').reset_index(name='evidence_count')

    # combine LEMUR sense information and the respective sense counts
    df_evidence = pd.merge(df_lemur_target_headwords, sense_counts, on='sense_id', how='left')

    df_evidence['evidence_count'] = df_evidence['evidence_count'].fillna(0).astype(int)

    # Add other information such as total usage count and percentage of evidence usages
    df_evidence = df_evidence.merge(count_s1.rename("total_usages"), left_on='lemma', right_index=True, how='left')
    df_evidence['total_usages'] = df_evidence['total_usages'].fillna(0).astype(int)
    df_evidence["evidence_ratio"] = df_evidence["evidence_count"] / df_evidence["total_usages"]
    df_evidence['evidence_ratio'] = df_evidence['evidence_ratio'].fillna(0)

    # Reorder columns and sort rows
    first_cols = ["lemma", "sense_id", "total_usages", "evidence_count", "evidence_ratio"]
    remaining_cols = [col for col in df_evidence.columns if col not in first_cols]
    df_evidence = df_evidence[first_cols + remaining_cols]
    df_evidence = df_evidence.sort_values(by=["lemma", "sense_id"])

    df_evidence = df_evidence.drop(columns=["identifier"])
    # Save the merged dataframe to a TSV file
    df_evidence.to_csv(out_dir / "evidence.tsv", sep='\t', index=False)


if __name__ == "__main__":
    main()
