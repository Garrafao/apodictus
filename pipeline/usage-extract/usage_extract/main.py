import csv
import sys
import time
from pathlib import Path
from random import randint, Random

import click
import nltk
import pandas as pd
from loguru import logger
from pandas.errors import EmptyDataError, MergeError

from usage_extract.corpora.nowcorpus import add_source_info, open_tars, open_zip_folder
from usage_extract.helper.cli import CustomCliGroup
from usage_extract.helper.file import (
    deduplicate_usages,
    export_usage_stats,
    get_corpus_path,
    merge_output_files,
    print_random_usage,
    read_headwords_file,
)
from usage_extract.helper.headwords import preprocess_headwords
from usage_extract.helper.text import (
    add_suffix_to_filename,
    divider,
    naturalsize,
    paths_to_name,
    precisedelta,
    title_divider,
)

pd.options.mode.copy_on_write = True
logger = logger.opt(lazy=True)


@click.group(context_settings={"show_default": True}, cls=CustomCliGroup)
def cli():
    logger.remove()
    logger.add(
        sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} <d>|</> <level>{level}</> <d>|</> {message}", level="INFO"
    )
    logger.add(
        "ue_{time}.log", format="{time:YYYY-MM-DD HH:mm:ss} <d>|</> <level>{level}</> <d>|</> {message}", level="INFO"
    )
    pass


@cli.command("extract")
@click.option(
    "--headwords-file",
    "--headwords",
    "-h",
    "headwords_path",
    help="Path to headwords file",
)
@click.option("--corpus-path", "--corpus", "corpus_path_input", help="Path to corpus (wlp folder)")
@click.option(
    "--output-file",
    "--output",
    "-o",
    "output_file",
    help="Path to output file",
)
@click.option("--statistics-file", "--stats", help="Path to statistics file")
@click.option(
    "--context",
    "-c",
    "context",
    default=150,
    help="Context before and after headword in usage (in tokens)",
)
@click.option(
    "--target-usage-number",
    "--target",
    "-t",
    "-n",
    default=10000,
    help="Target number of usages per headword",
)
@click.option(
    "--random-seed",
    "--seed",
    "-s",
    "random_seed",
    type=int,
    help="Random seed used for subsampling during retrieval",
)
@click.option("--tar-filter", "--filter", "tar_filter", help="Filter for tar files to be processed")
@click.option("--archive-files/--text-files", "archive", default=True, help="Specify the corpus file type (archive/text files)")
def extract(
    headwords_path: str,
    corpus_path_input: str,
    output_file: str,
    statistics_file: str,
    context: int,
    target_usage_number: int,
    random_seed: int,
    tar_filter: str,
    archive: bool
):
    # Download punkt_tab for headword tokenization
    nltk.download("punkt_tab", quiet=True)

    start_total = time.perf_counter()
    corpus_path = "/mount/resources3/corpora/NOW/wlp"
    headwords: set = set()
    merge_output = False
    output_folder = Path("./output")
    usage_file_pattern = "usages_*.tsv"

    if corpus_path_input:
        try:
            corpus_path = get_corpus_path(corpus_path_input)
        except (FileNotFoundError, NotADirectoryError) as error:
            logger.error(error)
            sys.exit(1)
    else:
        logger.info("Using default corpus path.")
        corpus_path = Path(corpus_path)

    if headwords_path:
        try:
            headwords = read_headwords_file(headwords_path)
        except (FileNotFoundError, ValueError) as error:
            logger.error(error)
            sys.exit(1)
    else:
        logger.error("Headwords file must be specified.")
        sys.exit(1)

    if len(list(output_folder.glob("*"))) != 0:
        logger.warning("Output directory not empty.")

    if output_file:
        if Path(output_file).is_dir():
            logger.error("Output file path cannot point to directory.")
            sys.exit(1)

        extension = Path(output_file).suffix
        if extension not in (".tsv", ".json"):
            logger.error("Output file must have .tsv or .json extension.")
            sys.exit(1)

        if Path(output_file).exists():
            logger.warning("Output file already exists. Overwriting.")

        merge_output = True

    statistics_file = Path(statistics_file) if statistics_file else Path("usage_stats.tsv")
    if statistics_file.exists():
        logger.warning("Statistics file already exists. Overwriting.")

    # Check if context is valid
    if context < 1:
        logger.error("Context must be at least 1.")
        sys.exit(1)

    if target_usage_number < 1:
        logger.error("Target usage number must be at least 1.")
        sys.exit(1)

    if archive and not tar_filter:
        tar_filter = "*.tar"
        logger.info("Using default tar filter.")

    if not random_seed:
        random_seed = randint(1, 2**64)
        logger.info("Generated random seed.")

    # Create random object with seed
    random = Random(random_seed)

    logger.info(title_divider("PARAMETERS"))
    logger.info(f"Corpus path: '{corpus_path}'")
    logger.info(f"Headwords path: '{headwords_path}'")
    logger.info(f"Statistics file: '{statistics_file.name}'")
    logger.info(f"Context (in tokens): '{context}'")
    logger.info(f"Target usage number: '{target_usage_number}'")
    logger.info(f"Random seed: '{random_seed}'")
    if archive:
        logger.info(f"Tar filter: '{tar_filter}'")
    logger.info(f"Corpus file type: '{'archive' if archive else 'text'}'")

    if merge_output:
        logger.info(f"Usages output file: '{output_file}'")
        logger.info(divider())
    else:
        logger.info(divider())
        logger.info(f"Usages output folder: '{output_folder}'")

    if archive:
        tar_files = sorted(corpus_path.glob(tar_filter))
        number_of_tars = len(tar_files)
        if number_of_tars == 0:
            logger.info(f"No match for tar filter ('{tar_filter}'). Aborting.")
            sys.exit(1)

        logger.info(f"Tar filter match: {paths_to_name(tar_files)}")

        # Calculate size of selected tars for calculation of sampling probabilites
        tar_size = sum(file.stat().st_size for file in tar_files if file.is_file())
    else:
        # Setting tar_size to 0 -> estimate of 0 corpus words -> sample everything
        tar_size = 0

    # Preprocess headwords (for example, replace spaces with underscores for MWE processing)
    headwords = preprocess_headwords(headwords, tar_size, target_usage_number)
    logger.info(f"Headwords: {headwords}")
    logger.info(title_divider())

    start = time.perf_counter()

    # Create folder for export, if it does not exist
    output_folder.mkdir(exist_ok=True)

    if archive:
        total_bytes_read, total_usages_exported, total_usages_found = open_tars(
            tar_files, headwords, context, header=not merge_output, random_seed=random_seed
        )
    else:
        total_bytes_read, total_usages_exported, total_usages_found, _ = open_zip_folder(
            corpus_path, headwords, context, header=not merge_output, random_seed=random_seed
        )

    export_usage_stats(headwords, total_usages_found, total_usages_exported, statistics_file)

    usages_exported = sum(total_usages_exported.values())
    usages_found = sum(total_usages_found.values())

    stop = time.perf_counter()
    time_elapsed = stop - start

    # Logging metadata of extraction
    logger.info(title_divider("EXTRACTION"))
    logger.info(f"Extraction took {precisedelta(time_elapsed)}")
    logger.info(f"Total uncompressed size: {naturalsize(total_bytes_read)}")
    logger.info(f"Speed: {naturalsize(total_bytes_read / time_elapsed)}/s")
    logger.info(divider())
    logger.info(f"Usages found: {usages_found:_}")
    logger.info(f"Usages exported: {usages_exported:_}")

    # Display random usage if any have been found
    if usages_exported == 0:
        logger.info("No usages found. Aborting random sample display.")
    else:
        success = False
        attempt = 0
        max_attempts = 5
        while not success and attempt < max_attempts:
            try:
                attempt += 1
                random_usage_file = random.choice(list(Path("output").glob(usage_file_pattern)))
                print_random_usage(random_usage_file, random, includes_header=not merge_output)
                success = True
            except (ValueError, FileNotFoundError, csv.Error) as error:
                logger.warning(f"Could not display usage sample from '{random_usage_file}'. ({error})")

        if not success:
            logger.error(f"Aborting random sample display after {attempt} attempt{'s' if attempt > 1 else ''}.")

    logger.info(title_divider("EXPORT"))
    usages_file_bytes = sum(file.stat().st_size for file in output_folder.glob(usage_file_pattern) if file.is_file())
    usages_file_size = naturalsize(usages_file_bytes)
    total_bytes_write = usages_file_bytes

    if merge_output:
        start_merge = time.perf_counter()
        merge_output_files(output_file, sorted(Path("output").glob(usage_file_pattern)), delete_source_after_merge=True)
        stop_merge = time.perf_counter()
        time_elapsed_merge = stop_merge - start_merge
        logger.info(f"Merging output files took {precisedelta(time_elapsed_merge)}")
        logger.info(f"Usages file size: {usages_file_size}")
        logger.info(f"Speed: {naturalsize(usages_file_bytes / time_elapsed_merge)}/s")
        # Remove folder after merge
        output_folder.rmdir()
    else:
        logger.info(f"Usages files size: {usages_file_size}")

    stop_total = time.perf_counter()
    total_time_elapsed = stop_total - start_total
    logger.info(title_divider("TOTAL"))
    logger.info(f"Program took {precisedelta(total_time_elapsed)}")
    logger.info(f"Total size (read and write): {naturalsize(total_bytes_read + total_bytes_write)}")
    logger.info(f"Speed (read and write): {naturalsize((total_bytes_read + total_bytes_write) / total_time_elapsed)}/s")


@cli.command(name="add-sources", aliases=["sources"])
@click.argument("usage_files")
@click.option("--sources-path", "--sources", "-s", help="Path to sources.tar")
@click.option("--detect/--no-detect", "detect_years", default=False, help="Detect years by usage file naming")
@click.option("--years", "--year", help="Year(s) of source files to be loaded")
def add_sources(usage_files, sources_path, detect_years, years):
    """USAGE_FILES\tPath to usage input files"""

    start = time.perf_counter()
    if not sources_path:
        sources_path = Path("/mount/resources3/corpora/NOW/sources.tar")
    else:
        sources_path = Path(sources_path)

    logger.info(title_divider("PARAMETERS"))
    logger.info(f"Sources path: '{sources_path}'")
    logger.info(f"Usage files: '{usage_files}'")
    logger.info(f"Detect years: '{detect_years}'")
    logger.info(f"Years: '{years}'")
    logger.info(divider())

    try:
        usage_file_list = []
        # Try to glob, if asterisk in parameter 'usage_files'
        if "*" in usage_files:
            usage_file_list = sorted(Path(".").glob(usage_files))
        # Assume single file, try to open it
        else:
            usage_file_path = Path(usage_files)
            open(usage_file_path)
            usage_file_list.append(usage_file_path)

        add_source_info(usage_file_list, sources_path, detect_years, years)
    except (OSError, EmptyDataError, MergeError, NotImplementedError) as e:
        logger.error(f"Could not add source information. ({e})")
        sys.exit(1)

    stop = time.perf_counter()
    time_elapsed = stop - start
    logger.info(title_divider("ADD-SOURCES"))
    logger.info(f"Adding source information took {precisedelta(time_elapsed)}")


@cli.command(name="deduplicate", aliases=["dedup"])
@click.argument(
    "usage_file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option("--deduplicated-file", "--deduplicated", "--dedup", "-o", help="Deduplicated output usage file")
@click.option("--duplicates-file", "--duplicates", "--dup", help="Duplicate statistics file")
def add_sources(usage_file, deduplicated_file, duplicates_file):
    """USAGE_FILE\tPath to usage input file"""

    start = time.perf_counter()
    if not usage_file:
        logger.error("Usage file must be specified.")
        sys.exit(1)

    usage_file = Path(usage_file)
    deduplicated_file = Path(deduplicated_file) if deduplicated_file else add_suffix_to_filename(usage_file, "_dedup")
    duplicates_file = Path(duplicates_file) if duplicates_file else add_suffix_to_filename(usage_file, "_dup")

    logger.info(title_divider("PARAMETERS"))
    logger.info(f"Usage file: '{usage_file.name}'")
    logger.info(f"Deduplicated file: '{deduplicated_file.name}'")
    logger.info(f"Duplicates file: '{duplicates_file.name}'")
    logger.info(divider())

    try:
        deduplicate_usages(usage_file, deduplicated_file, duplicates_file)
    except OSError as e:
        logger.error(f"Could not deduplicate '{usage_file.name}'. ({e})")
        sys.exit(1)

    stop = time.perf_counter()
    time_elapsed = stop - start
    logger.info(title_divider("DEDUPLICATE"))
    logger.info(f"Deduplicating the usage file took {precisedelta(time_elapsed)}")
