import argparse
import sys
import subprocess
from pathlib import Path
import logging
import warnings

from model_setup import prepare_gloss_reader_FiEnRu, prepare_gloss_reader_GR
from utilities import transform_to_axolotl, update_embeddings

warnings.filterwarnings("ignore")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dictionary', type=str, help='path to the dictionary to train NSD model')
    parser.add_argument('--usages', type=str, help='path to the tagged usages to train NSD model')
    parser.add_argument('--out', type=str, help='output path of pickle file with weights')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    dictionary_path = Path(args.dictionary)
    usages_path = Path(args.usages)
    out_path = Path(args.out)
    out_dir = out_path if out_path.suffix == '' else out_path.parent

    # check file paths
    if not dictionary_path.exists():
        logging.error("--dictionary path can not be resolved: %s", str(dictionary_path))
        sys.exit(1)
    if not usages_path.exists():
        logging.error("--usages path can not be resolved: %s", str(usages_path))
        sys.exit(1)

    root_dir = Path(__file__).resolve().parent.parent
    data_dir = root_dir / "data"
    temp_dir = data_dir / "temp"
    embedding_dir = data_dir / "embbeddings_tuning"

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(embedding_dir).mkdir(parents=True, exist_ok=True)

    # clone deepchange_at_axolotl repository which provides required scripts
    target_dir = root_dir / "deepchange_at_axolotl"
    if not target_dir.exists():
        subprocess.run([
            "git", "clone",
            "https://github.com/deniskokosss/deepchange_at_axolotl.git",
            str(target_dir)
        ], check=True)

    # embedding file paths
    embeddings_path_FiEnRu = embedding_dir / "GR_FiEnRu.json"
    embeddings_path_GR = embedding_dir / "GR.json"

    # transform input files into the format required by scripts from the deepchange_at_axolotl repository
    logging.info("Transform files to axolotl format")
    transform_to_axolotl(temp_dir / "nsd_train.tsv", dictionary_path, usages_path, False)
    transform_to_axolotl(temp_dir / "nsd_regular.tsv", dictionary_path, usages_path, True)

    # make sure required models are available
    logging.info("Prepare required models")
    GR_FiEnRu_path = data_dir / "models" / "GR_FiEnRu" / "model.safetensors"
    GR_path = data_dir / "models" / "GR" / "model.pt"
    prepare_gloss_reader_FiEnRu()
    prepare_gloss_reader_GR()

    # update/create embeddings
    logging.info("Start vectorization of dictionary entries and usages")
    update_embeddings(embeddings_path_FiEnRu, GR_FiEnRu_path, root_dir, temp_dir, [temp_dir / "nsd_train.tsv"])
    update_embeddings(embeddings_path_GR, GR_path, root_dir, temp_dir, [temp_dir / "nsd_train.tsv"])

    logging.info("Run NSD_train.py to train NSD model")
    subprocess.run([
        "python", "-W", "ignore", str(root_dir / "deepchange_at_axolotl" / "code" / "NSD_train.py"),
        "--embeds", f"{embeddings_path_FiEnRu},{embeddings_path_GR}",
        "--dataset", str(temp_dir / "nsd_regular.tsv"),
        "--model", str(out_path)
    ], check=True)

    logging.info("Execution DONE. See results in %s", str(out_path))