#!/bin/bash

set -euo pipefail

cd tools/automated_runs
rm -rf ../apodictus_eval/results
date; echo "Building predictions ..."; date
python multiple_runs.py --configs "configs/threshold_heatplots/full_run_annotation*/**/config.env"
echo "Now predictions should be in ../apodictus_eval/results/full_run_annotation_*"

cd ../apodictus_eval/eval_scripts
rm -rf ../plots/raw_results/*tsv ../plots/raw_results/*raw
date; echo "Calculating metrics for the grid ..."; date
python repro_threshold_analysis.py --configs "repro_configs/*"

cd ../plots/raw_results
echo "Tables with grid search results should be in `pwd`"
date; echo "Plotting grid search results ..."

rm -rf plot_executed.ipynb interactive_plots.html
jupyter nbconvert --to notebook --execute plot.ipynb --output plot_executed.ipynb
python interactive_plot.py

echo "Find the lineplots from the paper in `pwd`/plot_executed.ipynb and corresponding interactive line plots in `pwd`/interactive_plots.html"

