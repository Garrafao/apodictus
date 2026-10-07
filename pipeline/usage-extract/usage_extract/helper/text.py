import html
import re
from datetime import timedelta
from pathlib import Path
from tarfile import TarInfo

import humanize
from loguru import logger


def naturalsize(size: int) -> str:
    return humanize.naturalsize(size, binary=True)


def precisedelta(duration_in_seconds: float) -> str:
    delta = timedelta(seconds=duration_in_seconds)
    return humanize.precisedelta(delta, minimum_unit="seconds")


def precisedelta_start_stop(start: float, stop: float) -> str:
    delta = timedelta(seconds=stop-start)
    return humanize.precisedelta(delta, minimum_unit="seconds")


def paths_to_name(paths: list[Path]) -> list[str]:
    return [path.name for path in paths]


def tarinfos_to_name(tarinfos: list[TarInfo]) -> list[str]:
    return [tarinfo.name for tarinfo in tarinfos]


def add_suffix_to_filename(path: Path, suffix: str) -> Path:
    return path.parent.joinpath(f"{path.stem}{suffix}{''.join(path.suffixes)}")


def wlp_to_text(wlp: list[list[str]], headword_position, do_cleanup=False) -> tuple[str, str, str]:
    headword_char_position = []
    headword = wlp[headword_position][0]
    marked_headword = "HW_START#" + headword + "#HW_STOP"
    if do_cleanup:
        marked_headword = clean_up_text(marked_headword)

    pos_regex = re.compile(r"^(ge|mcge|xx|zz2|v[bdhm]|.*?_ge)")
    text = ""

    next_no_space = False
    for index, entry in enumerate(wlp):
        word, _, pos = entry
        if index == headword_position:
            word = marked_headword

        if index == 0:
            text += word
        # No space before punctuation
        elif pos == "y":
            text += word
        # No space for apostrophe occurrences like "n't" (as negating part of don't)
        elif "'" in word and pos_regex.match(pos):
            text += word
        elif pos == '"#start':
            text += " " + word
            next_no_space = True
        # No space before end quotation mark or next_no_space which is right after the start of a quote
        elif pos == '"#end' or next_no_space:
            text += word
            next_no_space = False
        else:
            text += " " + word

    if do_cleanup:
        text = clean_up_text(text)

    try:
        position_start = text.index(marked_headword)
        headword_char_position = f"{position_start}:{position_start + len(headword)}"
        indexes_target_sentence = f"0:{len(text)}"
        text = re.sub("HW_START#(.*?)#HW_STOP", "\\1", text)
        return text, headword_char_position, indexes_target_sentence
    except ValueError as error:
        logger.debug(f"'{headword}' '{marked_headword}' '{text}' error: '{error}'")
        raise error


def highlight_headword_in_usage(usage: str, headword_position: str, color="blue"):
    try:
        pos_start = int(headword_position.split(":")[0])
        pos_stop = int(headword_position.split(":")[1])
        return usage[0:pos_start] + f"<{color}>" + usage[pos_start:pos_stop] + f"</{color}>" + usage[pos_stop:]
    except (IndexError, ValueError) as error:
        logger.error(f"Could not highlight headword. ({error})")

    return usage


def clean_up_text(text: str) -> str:
    methods = [
        remove_tags,
        html.unescape,
        remove_now_corpus_toolong,
        remove_tags,
        replace_multi_whitespace,
        fix_parenthesis_whitespace,
        fix_punctuation_whitespace,
        str.strip,
    ]

    for method in methods:
        text = method(text)

    return text


def remove_tags(text: str) -> str:
    return re.sub(r"<\/?[a-z][a-z0-9]*[^<>]*>|<!--.*?-->", "", text)


def remove_now_corpus_toolong(text: str):
    return re.sub(r'(<a\ href=\ "\ https?\ :\ )?\*\*\d+;\d+;TOOLONG(\ \.\.\.)?', "", text)


def replace_multi_whitespace(text: str):
    return re.sub(r"\s+", " ", text)


def fix_punctuation_whitespace(text: str):
    return re.sub(r"\s+(?=[.,!?;:])", "", text)


def fix_parenthesis_whitespace(text: str):
    return re.sub(r"\(\s*(.*?)\s*\)", "(\\1)", text)


def keep_alphanumeric_underscore(text: str):
    return re.sub(r"[^A-Za-z0-9_ ]", "", text)


def remove_to_from_verb_headwords(text: str):
    return re.sub(r"^to\s", "", text)


def space_to_underscore(text: str):
    return text.replace(" ", "_")


def apply(text: str, methods):
    for method in methods:
        text = method(text)
    return text


def mark_quote_pairs(wlp: list[list[str]], quote='"'):
    quote_started = False
    for entry in wlp:
        if entry[2] == quote and entry[0] == quote:
            if not quote_started:
                entry[2] = f"{quote}#start"
            else:
                entry[2] = f"{quote}#end"
            quote_started = not quote_started


def divider(divider_char="-", divider_length=50):
    return divider_char * divider_length


def title_divider(title="", divider_char="#", divider_length=50):
    divider_string = divider_char * divider_length

    if len(title) == 0:
        return divider_string
    else:
        title = f" {title} "

    title_length = len(title)
    padding_length = int((divider_length - title_length) / 2)
    rounding_offset = 1 if (title_length + 2 * padding_length) < divider_length else 0

    if padding_length < 0:
        return divider_string
    else:
        return divider_string[0:padding_length] + title + divider_string[0 : padding_length + rounding_offset]
