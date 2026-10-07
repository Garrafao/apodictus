import argparse
import sys
from pathlib import Path
import pandas as pd
import warnings
import logging

warnings.filterwarnings("ignore")

# transform lemur dictionary tsv to input dictionary tsv suitable for the pipeline
def transform_lemur(lemur_files: list[Path]):
    df_lemur = pd.DataFrame()
    for file in lemur_files:
        df = pd.read_csv(file, sep=',', encoding="utf-8", dtype={"Issue key": str, "Headword/Lemma": str, "Definition": str})
        df["source"] = str(file.resolve())
        df_lemur = pd.concat([df_lemur, df])
    df_lemur = df_lemur.rename(columns={"Issue key": "sense_id", "Headword/Lemma": "lemma", "Definition": "gloss"})
    df_lemur["lemma"] = df_lemur["lemma"].astype(str).apply(lambda x: x.strip())
    df_lemur["identifier"] = [f"lemur_{i}" for i in range(0, len(df_lemur))]
    df_lemur = df_lemur[["identifier", "lemma", "sense_id", "gloss", "source"]]
    return df_lemur


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lemur', type=str, nargs='+', help='path to the lemur csv file')
    parser.add_argument('--out', type=str, help='output path of transformed dictionary file')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    out_path = Path(args.out)

    # check file paths
    lemur_paths = []
    for arg in args.lemur:
        path = Path(arg)
        if not Path(path).exists():
            logging.error("--lemur path cannot be resolved: %s", str(path))
            sys.exit(1)
        lemur_paths.append(path)


    logging.info("Transform lemur file to required dictionary format")
    df_lemur_transformed = transform_lemur(lemur_paths)
    df_lemur_transformed.to_csv(out_path, sep="\t", index=False, encoding="utf-8")

    logging.info("Done. See result in %s", str(out_path))