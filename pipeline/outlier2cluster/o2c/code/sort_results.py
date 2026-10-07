import argparse
import logging
from pathlib import Path
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Split usage files by lemma according to info.tsv mapping.")
    parser.add_argument('--info', type=str, required=True, help="path to info.tsv file containing lemma to file path mappings, created during usage extraction")
    parser.add_argument('--out', type=str, required=True, help="directory to write split usage files")
    parser.add_argument('--files', type=str, nargs='+', required=True, help="usage files to split (e.g. recorded.tsv unrecorded.tsv)")


    args = parser.parse_args()

    output_dir = Path(args.out)
    files = args.files

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    info_path = Path(args.info)
    if not info_path.exists():
        logging.error(f"info.tsv not found in {info_path}")
        return

    # load word to file-path mapping into python dictionary
    df_info = pd.read_csv(info_path, sep="\t", encoding="utf-8")
    lemma_to_path = dict(zip(df_info['headword'], df_info['path']))

    for file in files:
        file_path = Path(file)
        if not file_path.exists():
            logging.warning("File at %s not found, skip", str(file_path))
            continue

        df_file = pd.read_csv(file_path, sep="\t", encoding="utf-8")

        # For each lemma in info.tsv, filter usages and save
        for lemma, path in lemma_to_path.items():
            df_lemma = df_file[df_file["lemma"] == lemma]

            out_dir = output_dir / path
            out_dir.mkdir(parents=True, exist_ok=True)

            # Save filtered usage rows into a file named like file inside that directory
            out_file = out_dir / Path(file).name
            df_lemma.to_csv(out_file, sep="\t", index=False, encoding="utf-8")
    df_info.to_csv(output_dir / "info.tsv", sep="\t", index=False, encoding="utf-8")
    logging.info("Sorted results in %s", str(output_dir))

if __name__ == "__main__":
    main()
