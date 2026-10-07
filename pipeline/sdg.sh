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

echo "Start improving sense inventory with SDG"

#run SDG
python "$BASE_DIR/sense_definition_generation/sdg2/main.py" \
    --s3in "$input" \
    --outpath "$result_dir/lemur1300_updated.tsv" \
    --lemurpath "$dictionary" \
    --config_small "$use_small_config"

echo "Pipeline step S2 execution finished successfully."
