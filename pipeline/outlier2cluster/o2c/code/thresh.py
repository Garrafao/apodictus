import argparse
from pathlib import Path
import pandas as pd
import logging
import sys


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=str, help='path to the result tsv file with novel sense probability column "prob"')
    parser.add_argument('--thresh', type=float, help='Probability threshold to consider sense usage novel')
    parser.add_argument('--out_recorded', type=str, help="Output path for recorded usages")
    parser.add_argument('--out_unrecorded', type=str, help='Output file path for unrecorded usages')
    args = parser.parse_args()

    # initialize logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # check input parameters
    if not Path(args.result).is_file():
        logging.error("Input result file path can not be resolved: %s", args.result)
        sys.exit(1)
    out_recorded_dir = Path(args.out_recorded).parent
    if not out_recorded_dir.exists():
        logging.error("Parent directory of --out_recorded can not be resolved: %s", out_recorded_dir)
        sys.exit(1)
    out_unrecorded_dir = Path(args.out_unrecorded).parent
    if not out_unrecorded_dir.exists():
        logging.error("Parent directory of --out_unrecorded can not be resolved: %s", out_unrecorded_dir)
        sys.exit(1)

    logging.info("Apply threshold %s", args.thresh)

    # apply threshold to result
    df_result = pd.read_csv(args.result, sep='\t', encoding="utf-8", dtype={'sense_id': str, "prob": float})
    df_result["thresh"] = args.thresh
    unrecorded_mask = df_result["prob"] > args.thresh
    df_unrecorded = df_result[unrecorded_mask].copy()
    df_recorded = df_result[~unrecorded_mask].copy()
    df_unrecorded["is_novel"] = True
    df_recorded["is_novel"] = False

    df_unrecorded.to_csv(args.out_unrecorded, sep='\t', index=False, encoding="utf-8")
    df_recorded.to_csv(args.out_recorded, sep='\t', index=False, encoding="utf-8")

    logging.info("Out of a total of %d usages, %d were labeled as novel sense usages", len(df_result), len(df_unrecorded))
    logging.info("Done. See recorded usages at %s and unrecorded usages at %s", args.out_recorded, args.out_unrecorded)