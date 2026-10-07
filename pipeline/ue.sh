#!/bin/bash
set -euo pipefail  # Exit on error or unintentional usage of unset variables

CONFIG=$1
# current script directory
BASE_DIR="$(dirname "$0")"

set -a       # Automatically export all variables
source $CONFIG
set +a

# clean the result directory to avoid unintentional use of previously computed results
if [[ -d "${result_dir}" ]]; then
    read -p "Result directory ${result_dir} already exists. Remove and start execution? (y/N) " confirm
    if [[ "$confirm" == [yY] ]]; then
        rm -rf "${result_dir}"
    else
        echo "Aborted."
        exit 0
    fi
fi


if [[ -z ${sources_path:+x} ]]; then
    sources_path=""
fi
if [[ -z ${corpus_path:+x} ]]; then
    corpus_path=""
fi

if [[ -z ${s0_precomputed:+x} ]]; then
    if [[ -z ${trial_corpus:+x} ]]; then
        # Run usage-extract step with PyPy environment
        echo "Start usage extraction from NOW corpus"

        python "$BASE_DIR/outlier2cluster/o2c/code/extract_usages.py" \
            --context_range "$context_range" \
            --result_dir "$result_dir" \
            --total_usage_limit "$total_usage_limit" \
            --corpus_filter "$corpus_filter" \
            --headword_files "${headword_files[@]}" \
            --random_state "$random_state" \
            --sources_path "$sources_path" \
            --corpus_path "$corpus_path"
    else
        if [[ ! -f ${trial_corpus} ]]; then
            echo "Trial corpus ${trial_corpus} not found."
            exit
        fi

        tar -xf ${trial_corpus} -C "$BASE_DIR/data/inputs/trial1/"
        trial_corpus_folder="$BASE_DIR/data/inputs/trial1/corpus/"

        echo "Using trial corpus ${trial_corpus}, extracted to ${trial_corpus_folder}"

        python "$BASE_DIR/outlier2cluster/o2c/code/extract_usages.py" \
            --context_range "$context_range" \
            --result_dir "$result_dir" \
            --total_usage_limit "$total_usage_limit" \
            --corpus_filter "$corpus_filter" \
            --headword_files "${headword_files[@]}" \
            --random_state "$random_state" \
            --trial_corpus "$trial_corpus_folder"

        rm ${trial_corpus_folder}/*.txt
        rmdir ${trial_corpus_folder}
    fi
else
    echo "Skipping usage extraction, taking precomputed usages from ${s0_precomputed}"
    mkdir "${result_dir}" "${result_dir}"
    cp "${s0_precomputed}"/info.tsv $result_dir/
    for x in "${s0_precomputed}"/*/biased_sample.tsv.zst; do
      d=$result_dir/$(basename $(dirname $x))
      mkdir $d
      cp $x $d/usages_shuffle.tsv.zst
    done
fi

echo "Usage extraction completed successfully."
