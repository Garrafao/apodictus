import errno
import re
import tempfile
import time
from collections import defaultdict
from concurrent.futures import as_completed, ProcessPoolExecutor
from os import strerror
from pathlib import Path
from random import Random

from loguru import logger
from pandas.errors import MergeError

from usage_extract.helper.file import (
    add_source_information,
    export_usages,
    extract_tar_to_disk,
    extract_tar_to_disk_filtered,
    extract_zip_to_disk,
    get_tar_members_from_list,
    get_tar_members_from_pattern,
)
from usage_extract.helper.headwords import get_mwe_headwords
from usage_extract.helper.MWETokenizerPlaceholder import MWETokenizerPlaceholder
from usage_extract.helper.text import mark_quote_pairs, naturalsize, precisedelta


def open_tars(
    tar_files: list[Path], headwords: list[tuple[str]], context: int, header: bool, random_seed: int
) -> tuple[int, dict, dict]:
    tar_counter = 0
    break_at = -1
    total_bytes_read = 0
    total_usages_exported = {}
    total_usages_found = {}

    with tempfile.TemporaryDirectory(prefix="usage-extract-", ignore_cleanup_errors=True) as temp_directory:
        extract_path = Path(temp_directory)
        logger.info(f"Using temporary directory '{extract_path}' for extraction")

        for tar_file in tar_files:
            tar_bytes_read, tar_usages_exported, tar_usages_found = open_tar(
                tar_file, extract_path, headwords, context, header, random_seed
            )

            total_bytes_read += tar_bytes_read

            for key, value in tar_usages_exported.items():
                total_usages_exported[key] = total_usages_exported.get(key, 0) + value

            for key, value in tar_usages_found.items():
                total_usages_found[key] = total_usages_found.get(key, 0) + value

            tar_counter += 1
            if break_at > -1 and tar_counter >= break_at:
                logger.warning(f"open_tars: break at tar_counter={tar_counter}")
                break

    return total_bytes_read, total_usages_exported, total_usages_found


def open_tar(
    tar_path: Path, extract_path: Path, headwords: list[tuple[str]], context: int, header: bool, random_seed: int
) -> tuple[int, dict, dict]:
    zip_counter = 0
    break_at = -1
    zip_executor = ProcessPoolExecutor(max_workers=3)
    zip_futures = []
    tar_bytes_read = 0
    tar_usages_exported = {}
    tar_usages_found = {}

    try:
        extract_tar_to_disk(tar_path, extract_path)
    except Exception as e:
        logger.error(f"Could not extract tar '{tar_path.name}' ({e})")
        return 0, 0, {}

    zip_extract_paths = []

    for zip_path in sorted(extract_path.glob("*.zip")):
        try:
            zip_extract_path = extract_zip_to_disk(zip_path, extract_path)
            zip_extract_paths.append(zip_extract_path)
        except Exception as e:
            logger.error(f"Could not extract zip '{zip_path.name}' ({e})")

        zip_counter += 1
        if break_at > -1 and zip_counter >= break_at:
            logger.warning(f"open_tar: break at zip_counter={zip_counter}")
            break

    for zip_folder in zip_extract_paths:
        fix_au_filename(zip_folder)
        future = zip_executor.submit(open_zip_folder, zip_folder, headwords, context, header, random_seed)
        zip_futures.append(future)

    for future in as_completed(zip_futures):
        zip_bytes_read, zip_usages_exported, zip_usages_found, folder = future.result()

        tar_bytes_read += zip_bytes_read

        for key, value in zip_usages_exported.items():
            tar_usages_exported[key] = tar_usages_exported.get(key, 0) + value

        for key, value in zip_usages_found.items():
            tar_usages_found[key] = tar_usages_found.get(key, 0) + value

        # Remove zip folder
        try:
            for file in folder.glob("*.txt"):
                file.unlink()

            folder.rmdir()
        except Exception as e:
            logger.error(f"Folder could not be deleted. ({e})")

    zip_executor.shutdown()

    return tar_bytes_read, tar_usages_exported, tar_usages_found


def open_zip_folder(
    folder: Path, headwords: list[tuple[str]], context: int, header: bool, random_seed: int
) -> tuple[int, dict, dict, Path]:
    file_counter = 0
    break_at = -1
    file_executor = ProcessPoolExecutor(max_workers=16)
    file_futures = []
    zip_bytes_read = 0
    zip_usages_exported = {}
    zip_usages_found = {}

    for file in sorted(folder.glob("*.txt")):
        filename = file.name
        file_id = get_file_id(filename)
        filesize = file.stat().st_size
        zip_bytes_read += filesize
        future = file_executor.submit(
            read_corpus_file, file, filename, file_id, filesize, headwords, context, header, random_seed
        )
        file_futures.append(future)
        logger.info(f"Added '{filename}' [{file_id}] ({naturalsize(filesize)}) to reader pool")

        file_counter += 1
        if break_at > -1 and file_counter >= break_at:
            logger.warning(f"open_zip: break at file_counter={file_counter}")
            break

    for future in as_completed(file_futures):
        file_usages_exported, file_usages_found = future.result()  # blocks

        for key, value in file_usages_exported.items():
            zip_usages_exported[key] = zip_usages_exported.get(key, 0) + value

        for key, value in file_usages_found.items():
            zip_usages_found[key] = zip_usages_found.get(key, 0) + value

    file_executor.shutdown()

    return zip_bytes_read, zip_usages_exported, zip_usages_found, folder


def fix_au_filename(folder: Path):
    common_prefix = folder.name.replace("-wlp", "")
    for file in folder.glob("*.txt"):
        filename = file.name
        if not filename.startswith(common_prefix):
            region = Path(filename).stem.split("-")[-1]
            fix = f"{common_prefix}-{region}.txt"
            logger.debug(f"old: {filename} / region: {region} / fix: {fix}")
            if region == "au":
                file.rename(file.parent.joinpath(fix))
                logger.info(f"Fixed filename from '{filename}' to '{fix}'")


def read_corpus_file(
    path: Path,
    filename: str,
    file_id: str,
    filesize: int,
    headwords: list[tuple[str]],
    context: int,
    header: bool,
    random_seed: int,
) -> tuple[dict, dict]:
    start = time.perf_counter()
    extract = []
    text_id: int = -1
    token_id_text_start: int = -1
    text: list = []
    mwe_headwords = get_mwe_headwords(headwords)
    region = get_region_from_filename(filename)
    random = Random(random_seed)
    usages_exported = {}
    usages_found = {}

    # NOW corpus files use Windows Codepage 1252 encoding
    with open(path, encoding="cp1252") as file:
        for line in file:
            # Split tab-seperated line
            line_split = line.split("\t")

            # Skip malformed lines
            if len(line_split) != 5:
                if line.encode("cp1252") == b"\x1a":
                    logger.debug(f"Malformed line: '{line.rstrip()}'")
                else:
                    logger.warning(f"Malformed line: '{line.rstrip()}'")
                continue

            # Assign values to corresponding "column" and strip line ending
            word = line_split[2]
            lemma = line_split[3]
            pos = line_split[4].rstrip()

            # Use lowercase word form as substitute for empty lemma column
            if not lemma:
                lemma = word.lower()

            # Detect start of new text -> set ids
            if word.startswith("@@") and pos == "fo":
                # Skip if either id not set (start of first text -> no previous ids set OR malformed lines)
                if text_id != -1 and token_id_text_start != -1:
                    # Merge multi-word expressions to one token (only process MWE headwords, not all)
                    text = merge_multiword_expressions(text, mwe_headwords)

                    # Mark quotes pairs on entire text for best matching of open and close quotes
                    mark_quote_pairs(text)

                    for headword in headwords:
                        usages, usages_found_headword = find_longest_usages(text, headword, context, random)
                        usages_found[headword[0]] = usages_found.get(headword[0], 0) + usages_found_headword

                        if not usages:
                            continue

                        for usage in usages:
                            target_position_text = usage[4]
                            target_token_id = token_id_text_start + target_position_text
                            source_id = f"NOW-{file_id}-{text_id}-{target_token_id}"
                            usage[4] = source_id
                            usage[9] = filename
                            usage[10] = region
                            extract.append(usage)

                # Set variables for new text
                try:
                    text_id = int(line_split[0])
                    # Use token id of first real token -> +1
                    token_id_text_start = int(line_split[1]) + 1
                except ValueError as e:
                    logger.warning(f"Could not parse text/token ids ({e})")

                text = []
                continue

            text.append([word, lemma, pos])

    stop = time.perf_counter()
    time_elapsed = stop - start
    speed = f"{naturalsize(filesize/time_elapsed)}/s"
    logger.info(
        f"Finished reading '{filename}' [{file_id}] ({naturalsize(filesize)}) in {precisedelta(time_elapsed)} ({speed})"
    )

    usages_exported = export_usages(extract, f"usages_{file_id}.tsv", "./output", header=header)

    return usages_exported, usages_found


def find_longest_usages(text: list[list[str]], headword: tuple[str], context: int, random: Random):
    output = []
    targetword_positions = []
    token_max = len(text) - 1
    token_no = -1
    is_suffix = headword[3]
    is_mwe = len(headword[1].split("_")) > 0
    has_placeholder = "#" in headword[1]
    tokenizer = MWETokenizerPlaceholder(get_mwe_headwords([headword]))

    for _, lemma, _ in text:
        token_no += 1

        # Use processed headword (at index 1)
        if lemma == headword[1] or (is_suffix and lemma.endswith(headword[1])):
            targetword_positions.append(token_no)
        elif is_mwe and has_placeholder and "_" in lemma and not lemma.startswith("xx_"):
            merged = tokenizer.tokenize_placeholder(lemma.split("_"))
            # If lemma matches headword, it will be combined into one token -> len = 1
            if len(merged) == 1:
                targetword_positions.append(token_no)

    if len(targetword_positions) == 0:
        return None, 0

    for position_text in targetword_positions:
        usage_start = max(position_text - context, 0)
        usage_end = min(position_text + context, token_max)
        # Relative position to usage start
        position_usage = position_text - usage_start

        # Sample if below sample probability threshold
        if random.random() <= headword[2]:
            output.append(
                # lemma pos date grouping identifier description context indexes_target_token indexes_target_sentence filename region url title
                # Use original unprocessed headword (at index 0)
                [
                    headword[0],
                    text[position_text][2],
                    None,
                    None,
                    position_text,
                    None,
                    text[usage_start : usage_end + 1],
                    position_usage,
                    None,
                    None,
                    None,
                    None,
                    None,
                ]
            )

    return output, len(targetword_positions)


def merge_multiword_expressions(
    wlp: list[list[str]], mwe_headwords: list[tuple[str]], separator="_"
) -> list[list[str]]:
    wlp_lemmas = [entry[1] for entry in wlp]
    tokenizer = MWETokenizerPlaceholder(mwe_headwords, separator)
    merged = tokenizer.tokenize_placeholder(wlp_lemmas)

    offset = 0
    wlp_new = []
    for index, token in enumerate(merged):
        if "_" not in token or "_" in wlp_lemmas[index + offset]:
            wlp_new.append(wlp[index + offset])
        else:
            # logger.info(f"index: {index} / offset: {offset} / token: {token}")
            # Number of words in expression are n+1 for n separators
            word_count = token.count("_") + 1

            # Merge corresponding form and PoS, token is already from merged list, e.g. "catch_up"
            form_new = " ".join([entry[0] for entry in wlp[index + offset : index + offset + word_count]])
            pos_new = "mwe_" + "_".join([entry[2] for entry in wlp[index + offset : index + offset + word_count]])
            wlp_new.append([form_new, token, pos_new])

            # Offset from wlp to merged lists due to merging ["catch","up"] -> ["catch_up"] increases offset by one
            offset += word_count - 1
            # logger.info(f"form_new: {form_new} / pos_new: {pos_new} / offset_new: {offset}")

    return wlp_new


def get_region_from_filename(filename: str) -> str:
    try:
        return "".join(filter(str.isalpha, Path(filename).stem.split("-")[-1])).upper()
    except (IndexError, OSError) as e:
        logger.warning(f"Could not determine region for '{filename}'. ({e})")


# Only unique for NOW corpus
def get_file_id(filename) -> str:
    # Get filename root -> name for name.ext
    filename_root = Path(filename).stem

    # Replace non-alphanumeric characters with ''
    file_id = re.sub(r"[^A-Za-z0-9]", "", filename_root)

    # Convert to uppercase and take <= 8 last characters
    file_id = file_id.upper()[-8:]

    return file_id


def add_source_info(usage_files: list[Path], sources_path: Path, detect_years=True, years=None) -> None:
    with tempfile.TemporaryDirectory(prefix="usage-extract-", ignore_cleanup_errors=True) as temp_directory:
        extract_path = Path(temp_directory)
        logger.info(f"Using temporary directory '{extract_path}' for extraction")

        if detect_years:
            logger.info("Start detecting years based on usage filenames")
            files_by_year = defaultdict(list)

            # Group files by their year
            for file in usage_files:
                # Remove non-digit characters from filename
                year = re.sub(r"\D", "", file.name)
                # Pad year from two to four digits
                year = f"20{year[:2]}"
                files_by_year[year].append(file)

            years = sorted(files_by_year.keys())
            logger.info(f"Detected years: {years}")

            year_files = [f"{year}-sources.txt" for year in years]

            try:
                members = get_tar_members_from_list(sources_path, year_files)
                extract_tar_to_disk_filtered(sources_path, extract_path.joinpath("sources"), members)
            except OSError as e:
                logger.error(f"Could not extract tar '{sources_path.name}'")
                raise e

            for year in years:
                usage_files_year = sorted(files_by_year[year])
                source_file = extract_path.joinpath("sources").joinpath(f"{year}-sources.txt")

                try:
                    add_source_information([source_file], usage_files_year)
                except (OSError, MergeError) as e:
                    logger.error(f"Could not add source information for files from year '{year}'")
                    raise e
        else:
            if not years:
                years = "*"
            elif len(years) == 2:
                years = f"20{years}"
                logger.info(f"Padded years to four characters '{years}'")

            pattern = f"{years}-sources.txt"
            logger.info(f"Matching source files with pattern '{pattern}'")
            try:
                members = get_tar_members_from_pattern(sources_path, pattern)
                extract_tar_to_disk_filtered(sources_path, extract_path.joinpath("sources"), members)
            except OSError as e:
                logger.error(f"Could not extract tar '{sources_path.name}'")
                raise e

            sources_files = sorted(extract_path.joinpath("sources").glob(f"{years}-sources.txt"))

            if len(sources_files) == 0:
                raise FileNotFoundError(errno.ENOENT, strerror(errno.ENOENT), f"{years}-sources.txt")

            add_source_information(sources_files, usage_files)
