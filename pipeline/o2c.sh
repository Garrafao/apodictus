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

# If specified in configuration clear embeddings before execution, instead of reusing possibly existing embeddings
DELETE_EMBEDDINGS_FLAG=""
if [[ "${delete_embeddings,,}" == "true" ]]; then
    DELETE_EMBEDDINGS_FLAG="--delete_embeddings"
fi


echo "Start Outlier2Cluster execution"
python "$BASE_DIR/outlier2cluster/o2c/code/main.py" \
    --dictionary "$dictionary" \
    --usages "$usages" \
    --thresh "$threshold" \
    --result_dir "$result_dir" \
    --nsd_weights "$model_weights" \
    --context_limit "$max_usage_length" \
    $DELETE_EMBEDDINGS_FLAG

python "$BASE_DIR/outlier2cluster/o2c/code/prob_eval.py" "$result_dir/result_raw.tsv" \
    --output "$result_dir/prob_distribution.png"

python "$BASE_DIR/outlier2cluster/o2c/code/sort_results.py" \
    --info "$usages_info_file" \
    --out "$result_dir/organized_results" \
    --files "$result_dir/unrecorded.tsv" "$result_dir/recorded.tsv" "$result_dir/wsd.tsv" "$result_dir/wsi.tsv" "$BASE_DIR/outlier2cluster/o2c/data/temp/dictionary.tsv"


echo "Outlier2Cluster execution finished successfully."
