import os
import pandas as pd

def run_outlier2cluster(name, dictionary_s3, usage_path, RESULT_DIR,threshold_s3=0.4, max_usage_length_s3=512, BASE_DIR="/home/users1/saxjs/BASax/johannes/autodict/pipeline"):
    """
    Run outlier2cluster analysis for sense definition generation evaluation.
    
    Parameters:
    -----------
    name : str
        Name of the experiment/run
    dictionary_s3 : str
        Path to dictionary file
    usage_path : str
        Path to usage data file
    threshold_s3 : float, default=0.4
        Threshold for outlier2cluster
    max_usage_length_s3 : int, default=512
        Maximum usage length
        
    Returns:
    --------
    pandas.DataFrame
        o2c output results
    """
    
    # Model weights path
    #model_weights_s3 = os.path.join(BASE_DIR, "outlier2cluster/o2c/data/models/NSD/NSD_own_dev.pkl")
    model_weights_s3 = os.path.join(BASE_DIR, "outlier2cluster/o2c/data/models/NSD/NSD_russian.pkl")
    
    result_path = f"{RESULT_DIR}/{name}"
    if os.path.exists(result_path):
        o2c_req = True #True means always run o2c
        print(f"Directory {result_path} already exists")
    else:
        o2c_req = True
        # Create directory if not exists
        os.makedirs(result_path, exist_ok=True)
        print(f"Directory {result_path} created, proceeding with outlier2cluster.")

    # Run outlier2cluster script from the pipeline
    if o2c_req:
        cmd = (
            f'python "{BASE_DIR}/outlier2cluster/o2c/code/main.py" '
            f'--dictionary "{dictionary_s3}" '
            f'--usages "{usage_path}" '
            f'--thresh "{threshold_s3}" '
            f'--result_dir "{result_path}" '
            f'--nsd_weights "{model_weights_s3}" '
            f'--context_limit "{max_usage_length_s3}" '
            f'--delete_embeddings'
        )
        print("Running:", cmd)
        os.system(cmd)

    # Load S3 results
    s3out = pd.read_csv(f"{result_path}/result_raw.tsv", sep='\t')
    return s3out