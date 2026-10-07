import csv
import io
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from pathlib import Path, PurePath
from random import Random
from tarfile import TarFile, TarInfo
from zipfile import ZipFile

import pandas as pd
from loguru import logger

from usage_extract.helper.text import (
    add_suffix_to_filename,
    highlight_headword_in_usage,
    naturalsize,
    paths_to_name,
    precisedelta,
    tarinfos_to_name,
    title_divider,
    wlp_to_text,
)

HEADER = [
    "lemma",
    "pos",
    "date",
    "grouping",
    "identifier",
    "description",
    "context",
    "indexes_target_token",
    "indexes_target_sentence",
    "filename",
    "region",
    "url",
    "title",
]


def get_corpus_path(corpus_path: str) -> Path:
    path = Path(corpus_path)
    if not path.exists():
        raise FileNotFoundError("Corpus path not found.")
    elif not path.is_dir():
        raise NotADirectoryError("Corpus path must point to a directory.")
    else:
        return path


def read_headwords_file(headwords_path: str) -> set:
    if not Path(headwords_path).is_file():
        raise FileNotFoundError("Headwords file not readable.")

    extension = Path(headwords_path).suffix
    logger.debug(f"{extension} extension")

    if extension not in (".txt", ".json"):
        raise ValueError("Headwords must be contained in '.txt' or '.json' file.")

    headwords = None

    with open(headwords_path) as headwords_file:
        if extension == ".txt":
            headwords = [line.rstrip() for line in headwords_file.readlines()]
        elif extension == ".json":
            try:
                headwords = json.load(headwords_file)
            except JSONDecodeError as error:
                raise JSONDecodeError(f"Headwords json file malformed: {error.msg}", error.doc, error.pos)

    logger.debug(type(headwords))
    if not isinstance(headwords, list):
        raise ValueError("Headwords must be a list. (JSON array/txt separated by line)")
    elif len(headwords) == 0:
        raise ValueError("Headword list cannot be empty.")
    else:
        logger.info("Successfully read headwords file.")

        return headwords


def extract_tar_to_disk(tar_path: Path, extract_path: Path):
    logger.info(f"Start extracting tar '{tar_path.name}'")
    start = time.perf_counter()
    TarFile(tar_path).extractall(path=extract_path, filter="data")
    stop = time.perf_counter()
    tar_bytes = tar_path.stat().st_size
    time_elapsed = stop - start
    speed = f"{naturalsize(tar_bytes/time_elapsed)}/s"

    logger.info(f"Extracted tar '{tar_path.name}' ({naturalsize(tar_bytes)}) in {precisedelta(time_elapsed)} ({speed})")


def extract_tar_to_disk_filtered(tar_path: Path, extract_path: Path, members: list[TarInfo]) -> None:
    logger.info(f"Start extracting {tarinfos_to_name(members)} from tar '{tar_path.name}'")
    start = time.perf_counter()
    TarFile(tar_path).extractall(path=extract_path, members=members, filter="data")
    stop = time.perf_counter()
    tar_bytes = sum([member.size for member in members])
    time_elapsed = stop - start
    speed = f"{naturalsize(tar_bytes/time_elapsed)}/s"
    logger.info(
        f"Extracted {tarinfos_to_name(members)} from tar '{tar_path.name}' ({naturalsize(tar_bytes)}) in {precisedelta(time_elapsed)} ({speed})"
    )


def extract_zip_to_disk(zip_path: Path, extract_path: Path, remove_original=True) -> Path:
    logger.info(f"Start extracting zip '{zip_path.name}'")
    zip_extract_path = extract_path.joinpath(zip_path.stem)

    start = time.perf_counter()
    with ZipFile(zip_path, "r") as handle:
        with ThreadPoolExecutor(100) as exe:
            _ = [exe.submit(handle.extract, m, zip_extract_path) for m in handle.namelist()]

    stop = time.perf_counter()
    zip_compressed_size = zip_path.stat().st_size
    zip_extract_size = sum(file.stat().st_size for file in zip_extract_path.glob("*.txt") if file.is_file())
    time_elapsed = stop - start
    speed = f"{naturalsize(zip_extract_size/time_elapsed)}/s"

    logger.info(
        f"Extracted zip '{zip_path.name}' ({naturalsize(zip_compressed_size)} -> {naturalsize(zip_extract_size)}) in {precisedelta(time_elapsed)} ({speed})"
    )

    # Remove original zip file
    if remove_original:
        zip_path.unlink()

    return zip_extract_path


def get_tar_members_from_pattern(tar_path: Path, pattern: str) -> list[TarInfo]:
    names = TarFile(tar_path).getnames()
    members_pattern = [name for name in names if PurePath(name).match(pattern)]

    return get_tar_members_from_list(tar_path, members_pattern)


def get_tar_members_from_list(tar_path: Path, member_list: list[str]) -> list[TarInfo]:
    members = []
    for member in sorted(member_list):
        try:
            members.append(TarFile(tar_path).getmember(member))
        except KeyError:
            logger.info(f"'{member}' not present in tar '{tar_path.name}'")

    if not members:
        logger.info(f"No filter matches for tar '{tar_path.name}.")

    return members


def add_source_information(sources_files: list[Path], usage_files: list[Path]) -> None:
    start_total = time.perf_counter()
    sources = read_now_source_files(sources_files)

    total_bytes_read = 0
    total_bytes_write = 0

    if len(usage_files) > 1:
        logger.info(f"Start reading usage files {paths_to_name(usage_files)}")

    for usage_file in usage_files:
        start = time.perf_counter()
        logger.info(f"Start reading usage file '{usage_file.name}'")

        df = pd.read_csv(usage_file, on_bad_lines="warn", sep="\t", dtype=str)
        bytes_read = usage_file.stat().st_size

        # Drop columns found in sources file
        df = df.drop("date url title".split(), axis=1)

        # Retrieve text_id from identifier
        df["text_id"] = df["identifier"].apply(lambda id: id.split("-")[2])

        # Merge with sources
        dfj = pd.merge(df, sources, on="text_id", how="left", validate="m:1")

        # Restore column order
        dfj = dfj[HEADER]
        dfj.to_csv(usage_file, sep="\t", index=False, quoting=csv.QUOTE_MINIMAL)

        stop = time.perf_counter()
        bytes_write = usage_file.stat().st_size
        total_bytes_read += bytes_read
        total_bytes_write += bytes_write
        time_elapsed = stop - start
        speed = f"{naturalsize((bytes_read + bytes_write)/time_elapsed)}/s"

        logger.info(
            f"Added information to '{usage_file.name}' ({naturalsize(bytes_read)} "
            f"{'+' if bytes_write - bytes_read >= 0 else ''}{naturalsize(bytes_write - bytes_read)} "
            f"-> {naturalsize(bytes_write)}) in {precisedelta(time_elapsed)} ({speed})"
        )
        if bytes_write - bytes_read < 0:
            logger.warning("File size has decreased! Check if sources are correct.")

    stop_total = time.perf_counter()
    time_elapsed = stop_total - start_total
    speed = f"{naturalsize((total_bytes_read + total_bytes_write)/time_elapsed)}/s"
    if len(usage_files) > 1:
        logger.info(
            f"Added information to {paths_to_name(usage_files)} ({naturalsize(total_bytes_read)} "
            f"{'+' if total_bytes_write - total_bytes_read >= 0 else ''}{naturalsize(total_bytes_write - total_bytes_read)} "
            f"-> {naturalsize(total_bytes_write)}) in {precisedelta(time_elapsed)} ({speed})"
        )


def read_now_source_files(sources_files: list[Path]) -> pd.DataFrame:
    start = time.perf_counter()
    if len(sources_files) > 1:
        logger.info(f"Start reading source files {paths_to_name(sources_files)}")

    df_list = []
    total_bytes_read = 0

    for sources_file in sources_files:
        df, file_bytes_read = read_now_source_file(sources_file)
        df_list.append(df)
        total_bytes_read += file_bytes_read

    df = pd.concat(df_list)

    stop = time.perf_counter()
    time_elapsed = stop - start
    speed = f"{naturalsize(total_bytes_read/time_elapsed)}/s"
    if len(sources_files) > 1:
        logger.info(
            f"Read source files {paths_to_name(sources_files)} ({naturalsize(total_bytes_read)}) in {precisedelta(time_elapsed)} ({speed})"
        )

    return df


def read_now_source_file(sources_file: Path) -> pd.DataFrame:
    start = time.perf_counter()
    logger.info(f"Start reading source file '{sources_file.name}'")

    with open(sources_file, encoding="cp1252", errors="backslashreplace") as file:
        df = pd.read_csv(
            file, on_bad_lines="skip", sep="\t", names=["text_id", "date", "region", "url", "title"], dtype=str
        )

        # Drop malformed rows with NA/NAN
        df = df.dropna()

        df["date"] = df["date"].apply(lambda x: f"20{x}")
        df = df["text_id date url title".split()]

        stop = time.perf_counter()
        bytes_read = sources_file.stat().st_size
        time_elapsed = stop - start
        speed = f"{naturalsize(bytes_read/time_elapsed)}/s"
        logger.info(
            f"Read source file '{sources_file.name}' ({naturalsize(bytes_read)}) in {precisedelta(time_elapsed)} ({speed})"
        )

        return df, bytes_read


def deduplicate_usages(usage_file: Path, deduplicated_file: Path, duplicates_file: Path) -> None:
    start = time.perf_counter()
    logger.info(f"Start reading usage file '{usage_file.name}'")

    df = pd.read_csv(usage_file, sep="\t")
    bytes_read = usage_file.stat().st_size
    rows_read = len(df)

    dfg = df.groupby(["context", "indexes_target_token"]).agg(
        count=("context", "size"), identifier=("identifier", "first"), lemma=("lemma", "first")
    )

    # Select count > 1, i.e. duplicates; sort by count and identifier
    dfg = dfg[dfg["count"] > 1].sort_values(by="count identifier".split(), ascending=[False, True])
    dfg["lemma identifier count".split()].to_csv(duplicates_file, sep="\t", index=False, quoting=csv.QUOTE_MINIMAL)
    logger.info(f"Wrote duplicate counts to '{duplicates_file.name}'")

    # Drop duplicates, keep first -> this is the one in duplicate file
    df_dedup = df.drop_duplicates(["lemma", "context"], keep="first")
    df_dedup.to_csv(deduplicated_file, sep="\t", index=False, quoting=csv.QUOTE_MINIMAL)
    logger.info(f"Wrote deduplicated usages to '{deduplicated_file.name}'")

    stop = time.perf_counter()
    bytes_write = deduplicated_file.stat().st_size
    rows_write = len(df_dedup)
    time_elapsed = stop - start
    speed = f"{naturalsize((bytes_read + bytes_write)/time_elapsed)}/s"

    logger.info(
        f"Deduplicated '{usage_file.name}' ({'+' if rows_write - rows_read >= 0 else ''}{rows_write-rows_read} rows) "
        f"({naturalsize(bytes_read)} {'+' if bytes_write - bytes_read >= 0 else ''}{naturalsize(bytes_write - bytes_read)} "
        f"-> {naturalsize(bytes_write)}) in {precisedelta(time_elapsed)} ({speed})"
    )


def merge_output_files(output_file, usages_files: list[Path], delete_source_after_merge=True) -> None:
    logger.info("Start merging output files.")

    # Write header to output file
    with open(output_file, "w", newline="", encoding="utf-8") as tsv_file:
        writer = csv.writer(tsv_file, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(HEADER)

    # Append each usage file to output file
    with open(output_file, "ab") as tsv_file:
        for usages_file in usages_files:
            with open(usages_file, "rb") as part:
                shutil.copyfileobj(part, tsv_file)
            if delete_source_after_merge:
                Path(usages_file).unlink()


def export_usages(extract: list[list], usages_file: str, output_dir: str, header=True) -> dict:
    usages_exported = {}

    path = Path(output_dir).joinpath(usages_file)

    with open(path, "w", newline="", encoding="utf-8") as tsv_file:
        writer = csv.writer(tsv_file, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

        # Header
        if header:
            writer.writerow(HEADER)

        for usage in extract:
            try:
                usage[6], usage[7], usage[8] = wlp_to_text(usage[6], usage[7], do_cleanup=True)

                # lemma pos date grouping identifier description context indexes_target_token indexes_target_sentence
                writer.writerow(usage)
                usages_exported[usage[0]] = usages_exported.get(usage[0], 0) + 1
            except ValueError as error:
                logger.warning(
                    f"Skipping export for headword '{usage[0]}' with usage_id '{usage[4]}' at token '{usage[7]}' ({error})"
                )

    return usages_exported


def export_usage_stats(
    headwords: list[tuple[str]], usages_found: dict, usages_exported: dict, output_file: str, header=True
):
    with open(output_file, "w", newline="", encoding="utf-8") as tsv_file:
        writer = csv.writer(tsv_file, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

        # Header
        if header:
            writer.writerow(["lemma", "found", "exported"])

        for headword in headwords:
            lemma = headword[0]
            found = usages_found.get(lemma, 0)
            exported = usages_exported.get(lemma, 0)
            writer.writerow([lemma, found, exported])


def print_random_usage(usage_file: Path, random: Random, includes_header=False) -> bool:
    # Can raise FileNotFoundError
    file = open(usage_file)
    line_count = 0
    with file:
        line_count = sum(1 for _ in file)

    if line_count == 0 or includes_header and line_count == 1:
        raise ValueError("Usage file is empty.")

    start_line = 1 if includes_header else 0
    random_usage_line = random.randint(start_line, line_count - 1)
    line_extract = ""
    with open(usage_file) as file:
        # Include relevant line
        for i, line in enumerate(file):
            if i == random_usage_line:
                line_extract = line.strip()
                break

    if line_extract == "":
        raise ValueError(f"Randomly picked line {random_usage_line + 1} is empty.")

    try:
        csv_reader = csv.DictReader(
            io.StringIO(line_extract),
            fieldnames=HEADER,
            delimiter="\t",
            quoting=csv.QUOTE_MINIMAL,
        )
        random_usage = next(csv_reader)
        logger.info(title_divider("RANDOM EXAMPLE USAGE"))
        logger.info(f"Usage id: '{random_usage['identifier']}'")
        logger.info(f"Headword: '{random_usage['lemma']}'")
        logger.info(f"Target word position (in chars): '{random_usage['indexes_target_token']}'")
        highlighted_usage = highlight_headword_in_usage(random_usage["context"], random_usage["indexes_target_token"])
        logger.opt(colors=True).info(f"Usage: '{highlighted_usage}'")
    except StopIteration:
        raise ValueError("No entry found but iteration ended.")
