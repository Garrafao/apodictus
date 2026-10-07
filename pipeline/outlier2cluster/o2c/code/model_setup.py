import os

import requests
import tarfile
import logging

from tqdm import tqdm

logger = logging.getLogger()
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


# if not already there download pretrained gloss reader model into data/models
def prepare_gloss_reader_FiEnRu():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.abspath(os.path.join(current_dir, '..', 'data', 'models', 'GR_FiEnRu', 'model.safetensors'))

    if os.path.exists(target_path):
        logger.info("Gloss Reader model.safetensors already exists at %s, skip download.", target_path)
        return
    else:
        logger.info("No Gloss Reader model.safetensors found at %s.", target_path)

    models_dir = os.path.join(current_dir, '..', 'data', 'models')
    os.makedirs(models_dir, exist_ok=True)
    GR_url = 'https://zenodo.org/records/13256679/files/GR_FiEnRu.tar.gz'
    archive_path = os.path.join(models_dir, 'GR_FiEnRu.tar.gz')

    logger.info("Start Gloss Reader model.safetensors archive download")
    response = requests.get(GR_url, stream=True)
    if response.status_code != 200:
        logger.error("Download failed: HTTP %s", response.status_code)
        raise Exception(f"Download failed: HTTP {response.status_code}")

    total_size = int(response.headers.get('content-length', 0))
    chunk_size = 8192
    with open(archive_path, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc='Downloading') as pbar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    logger.info("Download complete, extract archive")
    with tarfile.open(archive_path, 'r:gz') as tar:
        tar.extractall(path=models_dir)

    logger.info("Gloss Reader model.safetensors downloaded successfully")

def prepare_gloss_reader_GR():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.abspath(os.path.join(current_dir, '..', 'data', 'models', 'GR', 'model.pt'))

    if os.path.exists(target_path):
        logger.info("Gloss Reader model.pt already exists at %s, skip download.", target_path)
        return
    else:
        logger.info("No Gloss Reader model.pt found at %s.", target_path)

    models_dir = os.path.join(current_dir, '..', 'data', 'models', 'GR')
    os.makedirs(models_dir, exist_ok=True)
    model_url = 'https://zenodo.org/records/10530146/files/best_model.ckpt'

    response = requests.get(model_url, stream=True)
    if response.status_code != 200:
        logger.error("Download failed: HTTP %s", response.status_code)
        raise Exception(f"Download failed: HTTP {response.status_code}")

    total_size = int(response.headers.get('content-length', 0))
    chunk_size = 8192
    with open(target_path, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc='Downloading') as pbar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    logger.info("Gloss Reader model.pt downloaded successfully")
