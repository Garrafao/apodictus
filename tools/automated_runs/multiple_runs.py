import argparse
import glob
import logging
import subprocess
from pathlib import Path

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configs', type=str, nargs="+" ,help='One or more paths or glob patterns to configuration files for execution')
    args = parser.parse_args()


    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    config_paths = []
    for config_path in args.configs:
        paths = glob.glob(config_path, recursive=True)
        if not paths:
            logging.warning(f"Specified configuration path or glob pattern: {config_path} did not match any files")
        else:
            config_paths += paths

    for config_path in config_paths:
        subprocess.run(["bash", "../../pipeline/pipeline.sh", Path(config_path).resolve()], check=True)