CONFIG = {
    "model": "google/gemma-3-12b-it", #google/gemma-3-12b-it
    "cuda_device": "0",
    #"dataset_path": "../../../data/dev2/dev2_results/results_06_04/result_s3t_with_defs.tsv", #"IN/result_s3t_with_defs.tsv", 
    #"lemur_definitions_path": "PATH", #path to definitions if not using lemur
    "wandb": False,
    "use_lemur": False,
    "sampling_params": {
        "temperature": 0.5,
        "top_p": 0.95,
        "top_k": 50,
        "max_tokens": 100,
        "presence_penalty": 0.6,
        "frequency_penalty": 0.2,
        "repetition_penalty": 1.1 #1.5 before
    }
}
