CONFIG = {
    "model": "google/gemma-3-12b-it",#"google/gemma-3-12b-it", #facebook/opt-125m    
    "cuda_device": "2",#"5,6,7,8",
    "dataset_path": "/home/users1/saxjs/BASax/johannes/scripts/dev3_usage_sample_converted.tsv",#"/home/users1/saxjs/BASax/johannes/eval/pilot_f/pilot_f_usages.tsv", 
    "lemur_definitions_path": "/home/users1/saxjs/BASax/johannes/scripts/dev3_dict_converted.tsv",#"/home/users1/saxjs/BASax/johannes/eval/pilot_f/pilot_f_dict.tsv",
    "wandb": True,
    "use_lemur": False,
    "eval": True,
    "output_file_path": "/home/users1/saxjs/BASax/ba_pipeline/OUTPilot_prompttest_mike/gen_def.tsv",#"/home/users1/saxjs/BASax/ba_pipeline/OUT_FEWS_lem_usages/gen_def.tsv",
    "sampling_params": {
         "temperature": 0.6, #[0,0.5,0.6,1]
        "top_p": 0.1, #[0.1,0.5, 0.9]
        "top_k": 100, #[-1, 50, 100]here
        "seed": 192,
        "presence_penalty": 0.7, #[-2,0,1]
        "frequency_penalty": 0.5, #[0,0.5,1,1.5]
        "max_tokens": 60, #60 davor
        #"repetition_penalty": 0.5, #[0,0.5,1,1.5,2] #greater 1 encourages new tokens
        #"min_tokens": 1,
        #"stop": ["\n"]
    }
}