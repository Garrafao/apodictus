import argparse
import json
import logging
import sys
import regex

import pandas as pd
from bs4 import BeautifulSoup
from pathlib import Path

def extract_ode_dict(paths: list[Path], ignore_posunit_regions: list[str], ignore_sense_regions: list[str], ignore_definition_regions: list[str], extended_dict: bool = False):

    # read relevant information from xml file to python dictionary, also add xref definitions
    entries = extract_entries(paths, ignore_posunit_regions, ignore_sense_regions, ignore_definition_regions)
    add_xref_definition(entries)

    # build dataframe with previously extracted dictionary data
    rows = []
    no_description_counter = 0
    for entry in entries.values():
        headword = entry["headwords"][0] if entry["headwords"] else ""
        for pos_unit in entry["pos_units"].values():
            for sense_hierarchy, sense in pos_unit["senses"].items():
                lex_id = sense["lex_id"]
                source = sense["source"]

                # Get definitions + xref definitions
                defs = sense.get("definitions", [])
                xref_defs = [item for sublist in sense.get("xref_definitions", []) for item in sublist]
                all_defs = defs + xref_defs

                # for the gloss in the final dictionary concatenate all definitions and examples
                examples = sense.get("examples", [])
                if (len(all_defs)) == 0:
                    logging.debug(f"For sense %s of headword %s there exist no gloss. Ignore sense", lex_id, headword)
                    no_description_counter += 1
                    continue
                # remove special characters which can break formatting (control characters)
                all_defs_clean = []
                for definition in all_defs:
                    all_defs_clean.append(regex.sub(r'\p{Cc}+', ' ', definition))
                if extended_dict:
                    # remove special characters which can break formatting (control characters
                    examples_clean = []
                    for example in examples:
                        examples_clean.append(regex.sub(r'\p{Cc}+', ' ', example))
                    rows.append({"lemma": headword.strip(), "sense_id": lex_id, "sense_hierarchy": sense_hierarchy,
                                 "gloss": json.dumps(all_defs_clean, ensure_ascii=False),
                                 "examples": json.dumps(examples_clean, ensure_ascii=False), "source": source})
                else:
                    rows.append({"lemma": headword.strip(), "sense_id": lex_id, "sense_hierarchy": sense_hierarchy,
                                 "gloss": all_defs_clean[0], "source": source})

    logging.info(f"Ignored %s senses because they did not have any definitions", no_description_counter)
    return pd.DataFrame(rows)

# For cross-references to definitions of other senses add these definitions to the sense directly
def add_xref_definition(entries: dict) -> list[tuple[str]]:
    missing_xrefs = []
    for lex_id, entry in entries.items():
        for pos_unit in entry["pos_units"].values():
            for complete_no, sense in pos_unit["senses"].items():
                definition_count = len(sense["definitions"])
                xrefs = sense["xrefs"]
                xrefs_count = len(xrefs)
                if definition_count == 0 and xrefs_count > 0:

                    for xref in xrefs:
                        target_id = xref["target_id"]
                        target = entries.get(target_id, "")
                        definitions = []
                        if target != "":
                            for pos_unit_lookup in target["pos_units"].values():
                                for complete_no_lookup, sense_lookup in pos_unit_lookup["senses"].items():
                                    definitions = sense_lookup["definitions"]
                                    break
                                break

                        if len(definitions) > 0:
                            sense["xref_definitions"] = sense.get("xref_definitions", [])
                            sense["xref_definitions"].append(definitions)
                        else:
                            missing_xrefs.append((sense["lex_id"], f"{entry['headwords'][0]}.{complete_no}", target_id))

    return missing_xrefs

# read xml and write information to python dictionary
def extract_entries(paths: list[Path], ignore_posunit_region: list[str], ignore_sense_region: list[str], ignore_definition_region: list[str]) -> dict:
    entries = dict()
    pos_units_ignored = 0
    single_senses_ignored = 0
    for path in paths:
        with open(path, "r", encoding="utf-8") as file:
            bs_data = BeautifulSoup(file, "xml")

            # for each entry in the xml file collect important data
            for entry in bs_data.find_all("entry"):
                lex_id = entry["lexid"]
                entry_type = entry["type"]
                current_headwords = [e.text for e in entry.find_all("headword")]
                dict_entry = {"headwords": current_headwords, "type": entry_type, "pos_units": {}}

                # for each entry go through all the pos units
                pos_unit_no = 0
                for pos_unit in entry.find_all("posUnit"):

                    # ignore pos_units if their region is specified in ignore_posunit_region
                    pos_region = pos_unit.get("regionalization", None)
                    if pos_region is not None and pos_region in ignore_posunit_region:
                        pos_units_ignored += 1
                        continue

                    # add pos unit data under the entry
                    pos_unit_no += 1
                    dict_entry["pos_units"][pos_unit_no] = {}
                    pos_tag = pos_unit.find("pos")
                    lexical_category = pos_tag["lexicalCategory"] if pos_tag else None
                    dict_entry["pos_units"][pos_unit_no]["pos"] = lexical_category

                    # for each pos unit go through all the sense groups
                    senses_dict = {}
                    sense_no = 1
                    for sense_group in pos_unit.find_all("senseGroup"):
                        # go through all senses of the sense group
                        subsense_no = 0
                        for sense in sense_group.find_all("sense"):

                            # ignore senses if their region is specified in ignore_sense_region
                            sense_region = sense.get("regionalization", None)
                            if sense_region is not None and sense_region in ignore_sense_region:
                                single_senses_ignored += 1
                                continue

                            # create sense identifier containing information about it's place in the sense hierarchy (main-/sub-sense)
                            # e.g. 1.0, 2.0, 2.1, 2.2, 2.3, 3.0, ...
                            complete_no = f"{lexical_category}:{sense_no}.{subsense_no}"
                            if sense["type"] == "main" and subsense_no == 0:
                                complete_no = f"{lexical_category}:{sense_no}"

                            # get all important sense information
                            sense_lex_id = sense["lexid"]
                            short_definition = ""
                            short_definition_tag = sense.find("shortDefinition")
                            if short_definition_tag:
                                short_definition = short_definition_tag.text
                            definitions = []
                            examples = []
                            for definition in sense.find_all("definition"):
                                definition_region = definition.get("regionalization", None)
                                if definition_region is not None and definition_region in ignore_definition_region:
                                    continue
                                # if multiple spelling variants only keep the british one to prevent duplicates
                                for spelling_variants in definition.find_all("spellingVariants"):
                                    variants = spelling_variants.find_all("spellingVariant")

                                    if len(variants) > 1:
                                        for variant in variants:
                                            if variant.get("regionalization") != "British":
                                                variant.decompose()
                                definitions.append(definition.text)
                            for example in sense.find_all("example"):
                                examples.append(example.text)
                            xref_data = []
                            for xrefs in sense.find_all("xrefs"):
                                for xref in xrefs.find_all("xref"):
                                    xref_data.append({"text": xrefs.text, "type": xref.get("type", ""), "target_id": xref.get("targetId", "")})

                            # add sense to the dictionary
                            senses_dict[complete_no] = {
                                "lex_id": sense_lex_id,
                                "type": sense["type"],
                                "short_definition": short_definition,
                                "definitions": definitions,
                                "examples": examples,
                                "xrefs": xref_data,
                                "source": str(path.name)
                            }
                            subsense_no += 1
                        sense_no += 1
                    dict_entry["pos_units"][pos_unit_no]["senses"] = senses_dict
                entries[lex_id] = dict_entry

    # print useful information
    if pos_units_ignored > 0:
        logging.info(f"Ignored %s entire pos units because region in %s", pos_units_ignored, ignore_posunit_region)
    if single_senses_ignored > 0:
        logging.info(f"Ignored %s individual senses because region in %s", single_senses_ignored, ignore_sense_region)
    return entries



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--log_level', type=str,
                        help='log level: "CRITICAL", "ERROR", "WARNING", "INFO" or "DEBUG"(default)', default="INFO")
    parser.add_argument('--ode_files', type=str, nargs='+', help="path ode xml dictionary file")
    parser.add_argument('--out', type=str, help="output path for resulting dictionary tsv file")
    parser.add_argument('--ignore_sense_regions', type=str, nargs='+', help="senses with specified region values will be ignored", default=["US"])
    parser.add_argument('--ignore_definition_regions', type=str, nargs='+', help="definitions with specified region values will be ignored", default=["US"])
    parser.add_argument('--ignore_posunit_regions', type=str, nargs='+', help="posunits with specified region values will be ignored", default=["US"])
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
    out_path = Path(args.out)

    # check paths
    target_files = []
    for arg in args.ode_files:
        path = Path(arg)
        if not path.exists():
            logging.error("--ode_files path cannot be resolved: %s", str(path))
            sys.exit(1)
        target_files.append(path)

    df_dict = extract_ode_dict(target_files, args.ignore_posunit_regions, args.ignore_sense_regions, args.ignore_definition_regions)

    # add identifier for each row
    df_dict["identifier"] = [f"ode_{i}" for i in range(0, len(df_dict))]

    # reorder columns
    cols = ["identifier", "lemma", "sense_id", "sense_hierarchy", "gloss", "source"]
    df_dict = df_dict[cols]

    # save resulting dictionary
    df_dict.to_csv(out_path, sep="\t", index=False)
    logging.info("successfully created dictionary tsv file at %s", str(out_path))