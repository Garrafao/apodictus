#!/bin/bash
set -euo pipefail  # Exit on error or unintentional usage of unset variables

shopt -s globstar

CONFIG=$1
# current script directory
BASE_DIR="$(dirname "$0")"

set -a       # Automatically export all variables
source $CONFIG
set +a

# clean the result directory to avoid unintentional use of previously computed results
rm -rf "${result_dir}"

if [[ -z ${single_feature_s1:+x} ]]; then
    single_feature_s1=""
fi
if [[ -z ${single_feature_s3:+x} ]]; then
    single_feature_s3=""
fi
if [[ -z ${sources_path:+x} ]]; then
    sources_path=""
fi
if [[ -z ${corpus_path:+x} ]]; then
    corpus_path=""
fi

# Use precomputed usages
if [[ -n ${s0_precomputed:+x} ]]; then
    echo "Skipping usage extraction, taking precomputed usages from ${s0_precomputed}"

    mkdir -p "${result_dir}" "${result_dir}/extracted_usages"
    cp "${s0_precomputed}"/info.tsv $result_dir/extracted_usages/
    for x in "${s0_precomputed}"/**/usages_shuffle.tsv.zst; do
        relative_path="${x#${s0_precomputed}/}" # relative path to file, starting from the given s0_precomputed directory
        d=$result_dir/extracted_usages/$(dirname $relative_path)
        mkdir -p $d
        cp $x $d/usages_shuffle.tsv.zst
    done
else
    # Extract trial_sources, if provided and readable
    if [[ -n ${trial_sources:+x} ]]; then
        if [[ ! -r ${trial_sources} ]]; then
            echo "Trial sources ${trial_sources} not readable."
            exit 1
        fi

        sources_path="$BASE_DIR/data/inputs/trial1/sources.tar"
        mkdir -p "$BASE_DIR/data/inputs/trial1"
        unzstd -f -q ${trial_sources} -o ${sources_path}

        echo "Using trial sources ${trial_sources}, extracted to ${sources_path}"
    fi

    # Extract trial corpus files, if provided and readable
    if [[ -n ${trial_corpus:+x} ]]; then
        if [[ ! -r ${trial_corpus} ]]; then
            echo "Trial corpus ${trial_corpus} not readable."
            exit 1
        fi
        mkdir -p "$BASE_DIR/data/inputs/trial1"
        tar -xf ${trial_corpus} -C "$BASE_DIR/data/inputs/trial1/"
        trial_corpus_folder="$BASE_DIR/data/inputs/trial1/corpus/"

        echo "Using trial corpus ${trial_corpus}, extracted to ${trial_corpus_folder}"

        python "$BASE_DIR/outlier2cluster/o2c/code/extract_usages.py" \
            --context_range "$context_range" \
            --result_dir "$result_dir/extracted_usages" \
            --total_usage_limit "$total_usage_limit" \
            --corpus_filter "$corpus_filter" \
            --headword_files "${headword_files[@]}" \
            --random_state "$random_state" \
            --trial_corpus "$trial_corpus_folder" \
            --sources_path "$sources_path"

        rm ${trial_corpus_folder}/*.txt
        rmdir ${trial_corpus_folder}

    # Run usage extraction on NOW corpus
    else
        echo "Start usage extraction from NOW corpus"

        python "$BASE_DIR/outlier2cluster/o2c/code/extract_usages.py" \
            --context_range "$context_range" \
            --result_dir "$result_dir/extracted_usages" \
            --total_usage_limit "$total_usage_limit" \
            --corpus_filter "$corpus_filter" \
            --headword_files "${headword_files[@]}" \
            --random_state "$random_state" \
            --sources_path "$sources_path" \
            --corpus_path "$corpus_path"
    fi

    # Clean-up, if trial sources were used
    if [[ -n ${trial_sources:+x} ]]; then
        rm ${sources_path}
    fi
fi

echo "Start pipeline step S1"
#source "$BASE_DIR/outlier2cluster/o2c/.venv/bin/activate"

s1_args=(
  --dictionary "$dictionary_s1"
  --usages "$result_dir/extracted_usages/**/*usages_shuffle.tsv.zst"
  --thresh "$threshold_s1"
  --result_dir "$result_dir/s1"
  --context_limit "$max_usage_length_s1"
  --delete_embeddings
)
if [[ -n "${single_feature_s1:-}" ]]; then
  s1_args+=(--single_feature "$single_feature_s1")
else
  s1_args+=(--nsd_weights "$model_weights_s1")
fi

if [[ -n "${max_prob_s1:-}" ]]; then
  s1_args+=(--max_prob "$max_prob_s1")
fi

python "$BASE_DIR/outlier2cluster/o2c/code/main.py" "${s1_args[@]}"

python "$BASE_DIR/outlier2cluster/o2c/code/prob_eval.py" "$result_dir/s1/result_raw.tsv" \
    --output "$result_dir/s1/prob_distribution.png"

python "$BASE_DIR/outlier2cluster/o2c/code/sort_results.py" \
    --info "$result_dir/extracted_usages/info.tsv" \
    --out "$result_dir/s1/organized_results" \
    --files "$result_dir/s1/unrecorded.tsv" "$result_dir/s1/recorded.tsv" "$result_dir/s1/wsd.tsv" "$result_dir/s1/wsi.tsv" "$BASE_DIR/outlier2cluster/o2c/data/temp/dictionary.tsv"

echo "Start pipeline step S3"
s3_args=(
    --dictionary "$dictionary_s3"
    --usages "$result_dir/s1/unrecorded.tsv"
    --thresh "$threshold_s3"
    --result_dir "$result_dir/s3"
    --context_limit "$max_usage_length_s3"
)
if [[ -n "${single_feature_s3:-}" ]]; then
  s3_args+=(--single_feature "$single_feature_s3")
else
  s3_args+=(--nsd_weights "$model_weights_s3")
fi

if [[ -n "${max_prob_s3:-}" ]]; then
  s3_args+=(--max_prob "$max_prob_s3")
fi

python "$BASE_DIR/outlier2cluster/o2c/code/main.py" "${s3_args[@]}"

python "$BASE_DIR/outlier2cluster/o2c/code/prob_eval.py" "$result_dir/s3/result_raw.tsv" \
    --output "$result_dir/s3/prob_distribution.png"

python "$BASE_DIR/outlier2cluster/o2c/code/sort_results.py" \
    --info "$result_dir/extracted_usages/info.tsv" \
    --out "$result_dir/s3/organized_results" \
    --files "$result_dir/s3/unrecorded.tsv" "$result_dir/s3/recorded.tsv" "$result_dir/s3/wsd.tsv" "$result_dir/s3/wsi.tsv" "$BASE_DIR/outlier2cluster/o2c/data/temp/dictionary.tsv"

python "$BASE_DIR/outlier2cluster/o2c/code/stats.py" \
    --file_s1 "$result_dir/extracted_usages/**/*usages_shuffle.tsv.zst" \
    --file_s1t "$result_dir/s1/unrecorded.tsv" \
    --file_s3t "$result_dir/s3/recorded.tsv" \
    --lemur_file "$dictionary_s3" \
    --dict_file "$dictionary_s1" \
    --info "$result_dir/extracted_usages/info.tsv" \
    --output_dir "$result_dir"


if [[ -n ${dump_improved_defs:-} ]]; then
  ###SDG###
  echo "Start improving sense inventory with SDG"

  #run SDG
  python "$BASE_DIR/sense_definition_generation/sdg2/main.py" \
      --s3in "$result_dir/s3/recorded.tsv" \
      --outpath "$dump_improved_defs" \
      --lemurpath "$dictionary_s3" \
      --config_small "$use_small_config"

  echo "Pipeline completed successfully."
else
  echo "dump_improved_defs is unset or empty, skipping SDG"
fi