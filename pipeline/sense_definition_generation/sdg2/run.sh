#!/bin/bash

# Activate virtual environment
source /home/users1/saxjs/BASax/johannes/vllmenv/bin/activate

# Change to the target directory
#cd /home/users1/saxjs/BASax/ba_pipeline || {
#    echo "Directory not found"
#    exit 1
#}

# Create logs directory if it doesn't exist
#mkdir -p logs

# Create a timestamped log file
#LOGFILE="logs/run_$(date +'%Y-%m-%d_%H-%M-%S').log"

# Run the Python script and log output and errors
#python -u main.py 2>&1 | tee "$LOGFILE"
python main.py
