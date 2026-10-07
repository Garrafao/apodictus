# automated_runs
This script makes it possible to automate the execution of several pipeline runs.


## How to execute

Before execution make sure everything is setup similarly to whats required for a regular pipeline exection (create and activate environment with all requirements installed. See [Root Readme](../../README.md))

For each desired pipeline run prepare a configuration. Then execute the script specifying these configurations as path or glob pattern. E.g:


``python multiple_runs.py --configs "configs/**/config.env"``

(the specified configurations and the command above were used to generate the [results](../apodictus_eval/results) for the generation of threshold heatmaps with [threshold_heatmap.ipybn](../apodictus_eval/README.md))

---
IMPORTANT: Paths of a configuration file are resolved from where the script is executed so make sure relative paths of the specified configuration files resolve correctly