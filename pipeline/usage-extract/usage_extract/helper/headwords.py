from math import floor
from pathlib import Path

import pandas as pd
from loguru import logger
from nltk.tokenize import word_tokenize

from usage_extract.helper.text import apply, remove_to_from_verb_headwords, replace_multi_whitespace


def preprocess_headwords(headwords: list[str], tar_size: int, target_usage_number: int) -> set[str]:
    # Remove duplicate headwords
    headwords = set(headwords)

    # Calculate sample probabilities for each headword
    sample_probabilities = get_headword_sample_probability(headwords, tar_size, target_usage_number)

    # Process each headword
    headwords = {preprocess_headword(headword, sample_probabilities) for headword in headwords}
    return headwords


def preprocess_headword(headword: str, sample_probabilities: dict) -> tuple[str, str, float]:
    methods = [
        str.lower,
        # keep_alphanumeric_underscore,
        replace_multi_whitespace,
        str.strip,
        remove_to_from_verb_headwords,
        str.strip,
        tokenize_separator,
    ]

    headword_processed = apply(headword, methods)

    # Detect type 'suffix' if headword starts with "-"
    is_suffix = headword_processed.startswith("-")
    if is_suffix:
        # Remove hyphen for matching
        headword_processed = headword_processed[1:]

    return headword, headword_processed, sample_probabilities.get(headword, 1), is_suffix


def get_headword_sample_probability(headwords: set[str], tar_size: int, target_usage_number: int) -> dict:
    headword_probabilities = {}
    # frequency_file_name = "freq_words_wordfreq.tsv.zst"
    frequency_file_name = "freq_lemmas_ue_lemur.tsv"
    frequency_file = list(Path().glob(f"**/{frequency_file_name}"))

    if len(frequency_file) == 1:
        frequency_file = frequency_file[0].resolve(strict=False)
        logger.info(f"Word frequency file found at '{frequency_file}'")
    else:
        logger.warning(
            f"Word frequency file '{frequency_file_name}' not found. Headword sample probabilities will all be 1."
        )
        return {}

    df = pd.read_csv(frequency_file, sep="\t", index_col="lemma")
    wordlist = df.to_dict()["frequency"]

    # By sampling files -> average of 7.9 bytes (compressed) per line
    corpus_words = floor(tar_size / 7.9)
    logger.info(f"Corpus word estimate (for selected tars): {corpus_words:_}")

    for headword in headwords:
        frequency = wordlist.get(headword, 0)
        if frequency == 0:
            frequency = wordlist.get(headword.lower(), 0)
        estimate_number_usages = max(frequency * corpus_words, 1)
        sample_probability = min(1, target_usage_number / estimate_number_usages)
        headword_probabilities[headword] = sample_probability

    return headword_probabilities


def tokenize_separator(headword: str, separator="_") -> str:
    return separator.join(word_tokenize(headword))


def get_mwe_headwords(headwords: list[tuple[str]], separator="_") -> list[list[str]]:
    output = []
    for headword in headwords:
        # Use processed headword (at index 1)
        processed_headword = headword[1]
        if separator in processed_headword:
            output.append(processed_headword.split(separator))

    return output
