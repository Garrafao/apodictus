#!/bin/bash

# Activate virtual environment
#source /home/users1/saxjs/BASax/johannes/vllmenv/bin/activate
#conda activate autodict_test3
#conda activate autodict
conda activate autodict_test3

# Change to the target directory
#cd /home/users1/saxjs/BASax/johannes/ba_pipeline || {
#    echo "Directory not found"
#    exit 1
#}

# Create logs directory if it doesn't exist
mkdir -p logs

# Create a timestamped log file
LOGFILE="logs/run_$(date +'%Y-%m-%d_%H-%M-%S').log"

# Set CUDA devices
#export CUDA_VISIBLE_DEVICES="6,7,8"
#export VLLM_CONFIGURE_LOGGING=0
#export NCCL_P2P_DISABLE=1

# Run the Python script and log output and errors
python -u main_new.py --gpu-memory-utilization 0.7 2>&1 | tee "$LOGFILE"
#was 8192 model len --gpu-memory-utilization 0.7 --max-model-len 4096
