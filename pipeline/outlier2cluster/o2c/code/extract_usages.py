# extract usages for the sampled lemmas and compress results (save to /dataset/usages)
import argparse
import csv
import logging
import shutil
import sys
from collections import defaultdict

import pandas as pd
from pathlib import Path, PurePath
import zstandard as zstd
import subprocess
import regex


def process_headword(headword: str) -> tuple[str]:
    # Pre-split
    headword = apply(headword, [replace_multi_whitespace, str.strip])

    # Manual conversion
    lookup = {
        "dead one, dead 'un": ["dead one", "dead 'un"],
        "high (also tall) cotton": ["high cotton", "tall cotton"],
        "lord knows (plus clause)": ["lord know"],
        "like-as-we/they-lie": ["like-as-we-lie", "like-as-they-lie"],
        "(There is) luck in odd numbers": ["There is luck in odd number", "luck in odd number"],
        "from your lips (also mouth) to God's ears": ["from your lips to God's ear", "from your mouth to God's ear"],
        "fiddle while Rome (and varr.) burns": ["fiddle while # burn"],
        "back-of-(a- or -the)-napkin": ["back-of-a-napkin", "back-of-the-napkin"],
        "ista": ["-ista"],
        "drinker": ["-drinker"],
        "to come back to haunt someone": ["to come back to haunt #"],
        "to fake it till one makes it": ["to fake it till # make it"],
        "have someone for breakfast": ["have # for breakfast"],
        "feel someone's pain": ["feel #'s pain", "feel # pain"],
        "to live rent free in one's head": ["to live rent free in #'s head", "to live rent free in # head"],
        "to shoot one's shot": ["to shoot #'s shot", "to shoot # shot"],
        "to read (a person) his or her rights": ["to read # # right"],
    }

    headwords = []

    if "|" in headword:
        headwords = headword.split("|")
    elif "/" in headword and "-" not in headword:
        headwords = headword.split("/")
    elif headword in lookup:
        headwords = lookup[headword]
    # Add original headword to output if split did not provide anything
    else:
        headwords = [headword]

    methods = [remove_abbreviation_brackets_end, remove_to_the_with_comma_end, str.strip]
    headwords = [apply(entry, methods) for entry in headwords]

    return tuple(headwords)


def apply(text: str, methods):
    for method in methods:
        text = method(text)
    return text


def replace_multi_whitespace(text: str):
    return regex.sub(r"\s+", " ", text)


def remove_to_the_with_comma_end(text: str):
    return regex.sub(r",\s+(to|the)\s*$", "", text)


def remove_abbreviation_brackets_end(text: str):
    return regex.sub(r"\s+\([A-Z]+\)\s*$", "", text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--log_level', type=str,
                        help='log level: "CRITICAL", "ERROR", "WARNING", "INFO" or "DEBUG"(default)', default="INFO")
    parser.add_argument('--context_range', type=int, help='context range around the target word in the retrieved usage')
    parser.add_argument('--result_dir', type=str, help='Path to directory to store the extracted usages')
    parser.add_argument('--total_usage_limit', type=int, help='total limit of usages per lemma')
    parser.add_argument('--corpus_filter', type=str, help='specify files to include of the NOW corpus. Globbing possible')
    parser.add_argument('--headword_files', type=str, nargs='+', help="paths to txt files containing target words separated by newline")
    parser.add_argument('--random_state', type=int, help="random state for sampling", default=464)
    parser.add_argument('--trial_corpus', type=str, help="path to trial corpus")
    parser.add_argument('--sources_path', type=str, help="path to corpus source tar")
    parser.add_argument('--corpus_path', type=str, help="path to the NOW corpus (wlp folder), defaults to the path set in usage-extract")

    args = parser.parse_args()

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

    # parameters
    context = args.context_range
    corpus_filter = args.corpus_filter
    total_usage_limit = args.total_usage_limit
    random_state = args.random_state
    trial_corpus = args.trial_corpus
    sources_path = args.sources_path
    corpus_path = args.corpus_path
    usage_compression_level = 22

    # Retrieve years from filter (maybe containing file extensions)
    years = PurePath(corpus_filter).stem

    # Check if year is valid
    match = regex.match(r"(^1[0-9\*])|(^2[0-4\*])|(^\*)", years)
    if match:
        years = f"20{match.group(0)}"
        logging.info(f"Loading years '{years}' when adding source info.")
    else:
        years = "*"
        logging.warning("Could not determine years. Loading all years when adding source info.")

    # check paths
    target_files = []
    for arg in args.headword_files:
        path = Path(arg)
        if not path.exists():
            logging.error("--headword_files path cannot be resolved: %s", str(path))
            sys.exit(1)
        target_files.append(path)

    # prepare directories
    root_dir = Path(__file__).resolve().parent
    temp_dir = root_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)

    # initialize zstd compressor
    compressor = zstd.ZstdCompressor(level=usage_compression_level)

    # process headwords before running usage extraction and keep the mapping
    headword_mapping = {}
    for target_file in target_files:
        df = pd.read_csv(target_file, sep="\t", header=None, encoding="utf-8", names=["headword"])

        headword_mapping[target_file.stem] = defaultdict(list)
        # Strip and split headwords
        df["processed_headwords"] = df["headword"].apply(process_headword)

        # Create new rows for rows with multiple entries in
        df = df.explode("processed_headwords", ignore_index=True)
        df = df.rename(columns={"headword": "original_headword", "processed_headwords": "processed_headword"})

        for orig, proc in zip(df["original_headword"], df["processed_headword"]):
            headword_mapping[target_file.stem][orig].append(proc)

        # Use tab as seperator to avoid quoting even though only one column is exported
        df["processed_headword"].to_csv(temp_dir / f"{target_file.stem}.txt", index=False, header=None, sep="\t")

        # Export mapping to result folder for analysis
        # TODO: remove as obsolete
        df[["original_headword", "processed_headword"]].to_csv(result_dir / f"{target_file.stem}_map.tsv", index=False, sep="\t", quoting=csv.QUOTE_MINIMAL)

    statistics = []
    # extract usages for all lemmas contained in the specified files
    for file in target_files:
        file_dir = result_dir / file.stem
        processed_file = temp_dir / f"{file.stem}.txt"

        with open(processed_file, encoding="utf-8") as f:
            # use usage-extract tool to extract usages from NOW corpus
            extract_path = temp_dir / f"{file.stem}_extract.tsv"
            stats_path = temp_dir / f"{file.stem}_stats.tsv"

            if not trial_corpus:
                command = ["ue", "extract", "--headwords", processed_file, "--filter", corpus_filter, "--context", str(context), "--output", extract_path, "--seed", str(random_state), "--stats", stats_path]
                # Without a corpus path, usage-extract falls back to its default corpus path
                if corpus_path:
                    command.extend(["--corpus", corpus_path])
            else:
                command = ["ue", "extract", "--headwords", processed_file, "--corpus", trial_corpus, "--text-files", "--context", str(context), "--output", extract_path, "--seed", str(random_state), "--stats", stats_path]

            if total_usage_limit > 0:
                command.extend(["--target", str(2*total_usage_limit)])

            subprocess.run(command, check=True)

            # Deduplicate extracted usages
            # TODO: use mapping for frequency calculation, move to output folder
            duplicates_path = temp_dir / f"{file.stem}_duplicates.tsv"
            command = ["ue", "deduplicate", extract_path, "--deduplicated", extract_path, "--duplicates", duplicates_path]
            subprocess.run(command, check=True)

            # Add source information
            if not sources_path:
                command = ["ue", "add-sources", extract_path, "--years", years]
            else:
                command = ["ue", "add-sources", extract_path, "--years", years, "--sources-path", sources_path]

            subprocess.run(command, check=True)

            if Path(extract_path).exists():
                df_all_usages = pd.read_csv(extract_path, sep="\t", encoding="utf-8")
                df_stats_export = pd.read_csv(stats_path, sep="\t", encoding="utf-8")
                for count, (original_headword, processed_headword) in enumerate(headword_mapping[file.stem].items()):
                    lemma_path = file_dir / str(count + 1)
                    lemma_path.mkdir(parents=True, exist_ok=True)

                    # collect all usages of the word and convert lemma value back to original
                    df_usages = df_all_usages[df_all_usages["lemma"].isin(processed_headword)].copy()
                    df_usages["lemma"] = original_headword

                    df_usages = df_usages.sample(frac=1, random_state=random_state)  # shuffle

                    # apply upper limit to usage count if specified
                    if total_usage_limit > 0:
                        df_usages = df_usages.head(total_usage_limit).copy()
                    df_usages.to_csv(lemma_path / "usages_shuffle.tsv", sep="\t", index=False, encoding="utf-8")

                    df_stats_lemma = df_stats_export[df_stats_export["lemma"].isin(processed_headword)].sum()

                    path_str = f"{file.stem}/{count + 1}"
                    statistics.append({
                        "path": path_str,
                        "headword": original_headword,
                        "usages_found": df_stats_lemma["found"],
                        "usages_exported": df_stats_lemma["exported"],
                        "usages_deduplicated": len(df_usages),
                    })

                    # compress the usages file
                    with open(lemma_path / "usages_shuffle.tsv", "rb") as f_in, open(
                            lemma_path / "usages_shuffle.tsv.zst", "wb") as f_out:
                        with compressor.stream_writer(f_out) as c_stream:
                            c_stream.write(f_in.read())
                    (lemma_path / "usages_shuffle.tsv").unlink()
                extract_path.unlink()
            else:
                logging.info("No extracted usages found for lemmas in file %s", str(file))

    df_statistics = pd.DataFrame(statistics)

    info_path = Path(result_dir / "info.tsv")
    if info_path.exists():
        df_existing = pd.read_csv(info_path, sep="\t", encoding="utf-8")
        df_existing = df_existing[~df_existing["path"].isin(df_statistics["path"])]
        df_merged = pd.concat([df_existing, df_statistics], ignore_index=True)
    else:
        df_merged = df_statistics
    df_merged.to_csv(info_path, sep="\t", index=False, encoding="utf-8")
    shutil.rmtree(temp_dir)
