import os
import ray
import argparse
from prompt_builder import build_prompt_improve_existing_def, build_prompt_group, build_prompt_lem_group,build_prompt_llm_def_decision
import pandas as pd
from vllm import LLM, SamplingParams


import importlib

def load_config(module_name):
    config_module = importlib.import_module(module_name)
    return config_module.CONFIG

parser = argparse.ArgumentParser()
parser.add_argument('--s3in', type=str, help='file path to S3 output')
parser.add_argument('--outpath', type=str, help='file path to sdg output')
parser.add_argument('--lemurpath', type=str, help='file path to lemur tsv')
# boolean flag for test_config making default version False if not specified
parser.add_argument('--config_small', type=bool, help='Use small config instead of default config', default=False)

args = parser.parse_args()

# Example usage:
# Choose the config module dynamically (e.g., via CLI arg, env var, or config file)
use_small_config = args.config_small  # or use sys.argv/env/config
config_module_name = "config_small" if use_small_config else "config"

CONFIG = load_config(config_module_name)

#use wanb if specified in config
if CONFIG["wandb"]:
    import wandb
    wandb.init(project="ba_pipeline", tags=["lemur1300", "data/dev2/dev2_results/results_06_04"], config=CONFIG, save_code=True)


#set cuda device
os.environ["CUDA_VISIBLE_DEVICES"] = CONFIG["cuda_device"]







sampling_params = SamplingParams(**CONFIG["sampling_params"])
llm = LLM(model=CONFIG["model"])

# load dataset from the specified path
dataset=pd.read_csv(args.s3in, sep='\t')
#cut down to 1000 entries for testing
#dataset = dataset.head(10000)






lemur_definitions= pd.read_csv(args.lemurpath, sep='\t')
print(f"Loaded {len(lemur_definitions)} lemur definitions.")
print(lemur_definitions.head(5))
# cut down to 1000 definitions for testing
#lemur_definitions = lemur_definitions.head(10000)
if 'gloss' in lemur_definitions.columns:
    lemur_definitions.rename(columns={'gloss': 'definition'}, inplace=True)
if 'headword' in lemur_definitions.columns:
    lemur_definitions.rename(columns={'headword': 'lemma'}, inplace=True)



#####shorten lemur entries to found usages#################################################################
#remove all sense_id from lemur_definitions that are not in dataset
lemur_definitions = lemur_definitions[lemur_definitions['sense_id'].isin(dataset['sense_id'])]

###Rewrite Lemur Definitions###################################################################

# build lemur prompts
lemur_prompts = build_prompt_improve_existing_def(lemur_definitions)

# generate definitions using desired model to create new definitions for lemur entries
outputs = llm.generate(lemur_prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]
lemur_definitions.insert(2, 'generated_definition', generated_texts)
# save the lemur definitions with generated definitions to a tsv file
#lemur_definitions.to_csv("OUT/lemur_gen_def.tsv", sep='\t', index=False)
#if CONFIG["wandb"]:
#    wandb.log({"lemur_update": wandb.Table(dataframe=lemur_definitions)})




###Rewrite Lemur using assigned usages from O2C + lemur def #################################################################




grouped_dataset = dataset.groupby('sense_id')
prompts= build_prompt_lem_group(grouped_dataset, lemur_definitions)
print(f"Grouped dataset has {len(grouped_dataset)} groups.")    
# Generate definitions using the model
outputs = llm.generate(prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]
mapped = pd.DataFrame({
    'sense_id': [key for key, _ in grouped_dataset],
    'gen_def_lemur+usages': generated_texts
})

# create 'gen_def_lemur+usages' column in lemur_definitions
lemur_definitions = lemur_definitions.merge(mapped[['sense_id', 'gen_def_lemur+usages']], on='sense_id', how='left')
# save the lemur definitions with generated definitions to a tsv file
#lemur_definitions.to_csv("OUT/lemur_gen_def.tsv", sep='\t', index=False)

#if CONFIG["wandb"]:
#    wandb.log({"lemur_update_2": wandb.Table(dataframe=lemur_definitions)})




#####Rewrite Lemur using assigned usages from O2C#################################################################
grouped_dataset = dataset.groupby('sense_id')
print(f"Grouped dataset has {len(grouped_dataset)} groups.")
prompts, sentences= build_prompt_group(grouped_dataset)
    
# Generate definitions using the model
outputs = llm.generate(prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]
mapped_ = pd.DataFrame({
    'sense_id': [key for key, _ in grouped_dataset],
    'gen_def_usages': generated_texts,
    'usages': sentences
})

# create 'gen_def_lemur+usages' column in lemur_definitions
lemur_definitions = lemur_definitions.merge(mapped_[['sense_id', 'gen_def_usages', 'usages']], on='sense_id', how='left')
# save the lemur definitions with generated definitions to a tsv file
#lemur_definitions.to_csv("OUT/lemur_gen_def.tsv", sep='\t', index=False)
#if CONFIG["wandb"]:
#    wandb.log({"lemur_update_3": wandb.Table(dataframe=lemur_definitions)})


########################LLM Select Best Def#################################################################
def_columns=["gen_def_lemur+usages","definition","gen_def_usages","generated_definition"]
prompts = build_prompt_llm_def_decision(dataset, def_columns, lemur_definitions)
outputs = llm.generate(prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]

# create a new DataFrame with generated_texts and dataset
generated_df = pd.DataFrame({
    'sense_id': lemur_definitions['sense_id'],
    'sense_id_llm': generated_texts,
})


#remove lemma and context columns from generated_df
generated_df = generated_df[['sense_id', 'sense_id_llm']]

# map sense_id to sense_id in lemur_definitions and add sense_id_llm as def_llm_chosen
lemur_definitions = lemur_definitions.merge(generated_df[['sense_id', 'sense_id_llm']], on='sense_id', how='left')
lemur_definitions.rename(columns={'sense_id_llm': 'def_llm_chosen'}, inplace=True)


if CONFIG["wandb"]:
    wandb.log({f"lemur_update": wandb.Table(dataframe=lemur_definitions)})

"""

########################LLM Style WSD#################################################################
def_columns=["gen_def_lemur+usages","definition","gen_def_usages","generated_definition"]
prompts = build_prompt_llm_based_wsd(dataset, def_columns, lemur_definitions)
outputs = llm.generate(prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]

# create a new DataFrame with generated_texts and dataset
generated_df = pd.DataFrame({
    'sense_id': dataset['sense_id'],
    'sense_id_llm': generated_texts,
    'lemma': dataset['lemma'],
    'context': dataset['context']  
})
if CONFIG["wandb"]:
    wandb.log({f"llm_wsd_test": wandb.Table(dataframe=generated_df)})

#merge generated_df with dataset
dataset = dataset.merge(generated_df[['sense_id', 'sense_id_llm']], on='sense_id', how='left')
dataset.to_csv("/home/users1/saxjs/BASax/johannes/OUT_Pipeline/lemur1300_wsd.tsv", sep='\t', index=False)

"""

if CONFIG["wandb"]:
    # log only where gen_def_usages is not null or empty or -
    filtered_df = lemur_definitions[lemur_definitions['gen_def_usages'].notnull() & (lemur_definitions['gen_def_usages'] != '') & (lemur_definitions['gen_def_usages'] != '-')]
    print(f"Filtered DataFrame has {len(filtered_df)} rows.")
    # log the filtered DataFrame
    wandb.log({"filtered_by_gen_def_usages": wandb.Table(dataframe=filtered_df)})    

# create directory for output if it does not exist
if not os.path.exists(os.path.dirname(args.outpath)):
    os.makedirs(os.path.dirname(args.outpath))



lemur_definitions.to_csv(args.outpath, sep='\t', index=False)

ray.shutdown()
