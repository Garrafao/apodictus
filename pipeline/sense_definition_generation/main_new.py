import argparse
import os
import ray
from config import CONFIG
from prompt_builder_3 import build_prompt_improve_existing_def, build_prompt_group, build_prompt_lem_group,build_prompt_llm_def_decision, build_prompt_llm_based_wsd, prompt_builder_wsd
from o2c_run import run_outlier2cluster
import pandas as pd
from vllm import LLM, SamplingParams
from eval_tsv import run_eval
import nltk
nltk.download('wordnet')
if CONFIG["wandb"]:
    import wandb
    #wandb.init(project="ba_pipeline_pilot", tags=["test_gen_def_first","prompt_v4","fill_generated_definition","gen_def_lemur+usages","rag_wn_group","rag_wn_lem"], config=CONFIG, save_code=True)
    wandb.init(project="ba_pipeline_dev3test", tags=["basic"],config=CONFIG, save_code=True)
    #"fill_generated_definition","gen_def_lemur+usages"

parser = argparse.ArgumentParser()
parser.add_argument('--usages', type=str, help='file path to S1 unrecorded tsv')
parser.add_argument('--outpath', type=str, help='file path to sdg output should end with gen_def.tsv')
parser.add_argument('--dict', type=str, help='file path to for example lemur tsv')
# boolean flag for test_config making default version False if not specified
parser.add_argument('--config_small', type=bool, help='Use small config instead of default config', default=False)
parser.add_argument('--o2cmainpath', type=str, help='Run evaluation after sdg', default="/home/users1/saxjs/BASax/johannes/autodict/pipeline")

args = parser.parse_args()


#set cuda device
os.environ["CUDA_VISIBLE_DEVICES"] = CONFIG["cuda_device"]
if not os.path.exists(os.path.dirname(args.outpath)):
    os.makedirs(os.path.dirname(args.outpath))



sampling_params = SamplingParams(**CONFIG["sampling_params"])
llm = LLM(model=CONFIG["model"], tensor_parallel_size=1)

outfolder_path= os.path.dirname(args.outpath)

if False:#CONFIG["sum"]:
    # load dataset from the specified path
    dataset=pd.read_csv(CONFIG["dataset_path"], sep='\t')

    #TEST#####
    #copy context column to context_old
    dataset["context_old"]= dataset["context"].copy()
    prompts = prompt_builder_wsd(dataset)
    outputs = llm.generate(prompts, sampling_params)
    generated_texts = [o.outputs[0].text for o in outputs]
    dataset["context"]=generated_texts
    dataset.to_csv(os.path.join(outfolder_path, "dataset_updated.tsv"), sep='\t', index=False)
    # ATTENTION, REMOVE context_old to context in bottom
    #TEST#####

    #check if dataset contains values in prob column
    print("run o2c clustering")
    name="o2crun"
    # Run o2c and update dataset
    #dataset=run_outlier2cluster(name, CONFIG["lemur_definitions_path"], CONFIG["dataset_path"], outfolder_path)
    dataset=run_outlier2cluster(name, CONFIG["lemur_definitions_path"], os.path.join(outfolder_path, "dataset_updated.tsv"), outfolder_path)
else:
    name="o2crun"
    dataset=run_outlier2cluster(name, args.dict, args.usages, outfolder_path, BASE_DIR=args.o2cmainpath)

if CONFIG["sum"]:
    dataset["context_old"]= dataset["context"].copy()
    prompts = prompt_builder_wsd(dataset)
    outputs = llm.generate(prompts, sampling_params)
    generated_texts = [o.outputs[0].text for o in outputs]
    dataset["context"]=generated_texts
    dataset.to_csv(os.path.join(outfolder_path, "dataset_updated.tsv"), sep='\t', index=False)

###Rewrite Lemur Definitions###################################################################


lemur_definitions= pd.read_csv(args.dict, sep='\t')
print(f"Loaded {len(lemur_definitions)} definitions.")
print(lemur_definitions.head(5))
    


# remove columns
def_columns=["gen_def_lemur+usages","definition","gen_def_usages","generated_definition"]
lemur_definitions.drop(columns=def_columns, inplace=True, errors='ignore')

#rename 'gloss' to 'definition' in lemur_definitions
lemur_definitions.rename(columns={'gloss': 'definition'}, inplace=True)


# build lemur prompts
lemur_prompts = build_prompt_improve_existing_def(lemur_definitions)
print(f"Generated {len(lemur_prompts)} prompts for lemur entries.")

# generate definitions using desired model to create new definitions for lemur entries
outputs = llm.generate(lemur_prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]
print(f"Generated {len(generated_texts)} definitions for lemur entries.")
print(f"Generated definitions like: {generated_texts[0]}")
lemur_definitions.insert(2, 'generated_definition', generated_texts)


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
lemur_definitions = lemur_definitions.merge(mapped_[['sense_id', 'gen_def_usages', 'usages']], on='sense_id', how='left')






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

lemur_definitions.to_csv(args.outpath, sep='\t', index=False)

if CONFIG["llm_decision"]:
    def_columns=["gen_def_lemur+usages","definition","gen_def_usages","generated_definition"]
    lemur_definitions['gloss'] = ""
    # iterate over each row
    for row in lemur_definitions.itertuples():
        best_column_name= row.def_llm_chosen
        #take whats inside @@ and  ##
        if '@@' in best_column_name and '##' in best_column_name:
            best_column_name= best_column_name.split("@@")[1].split("##")[0].strip()
        else:
            best_column_name="generated_definition"
        print(f"Best column name: {best_column_name}")
        # check def_columns and choose the 1 that matches with string contains
        matched = False
        for col in def_columns:
            if col in str(best_column_name):  # Check if column name is in def_llm_chosen
                lemur_definitions.at[row.Index, 'gloss'] = lemur_definitions.at[row.Index, col]
                matched = True
                break  # Stop after the first match
        if not matched:
            # Fallback if no match is found
            lemur_definitions.at[row.Index, 'gloss'] = "No match found"
else:
    lemur_definitions.rename(columns={'gen_def_lemur+usages': 'gloss'}, inplace=True)
    #lemur_definitions.rename(columns={'definition': 'gloss'}, inplace=True)
    #fill empty rows in gen_def_lemur+usages with entries from generated_definition
    lemur_definitions['gloss'].fillna(lemur_definitions['generated_definition'], inplace=True)

#lemur_definitions.rename(columns={'definition': 'gloss'}, inplace=True)

#remove linebreaks at start of lemur_definitions["gloss"]
#lemur_definitions["gloss"] = lemur_definitions["gloss"].str.lstrip("\n")


lemur_definitions.to_csv(args.outpath, sep='\t', index=False)
dataset=pd.read_csv(args.usages, sep='\t')


if CONFIG["eval"]:
    #run eval script
    print("Running evaluation script...")
    #dataset2=pd.read_csv(CONFIG["dataset_path"], sep='\t')
    metrics=run_eval(lemur_definitions, dataset, outfolder_path)
    metrics.to_csv(f"{outfolder_path}/evaluation_metrics.tsv", sep='\t', index=False)
    #create tsv file from CONFIG
    config_df=pd.DataFrame.from_dict(CONFIG, orient='index', columns=['value'])
    config_df.to_csv(f"{outfolder_path}/config.tsv", sep='\t', index=False)
    if CONFIG["wandb"]:
        #log lemur_definitions in wandb
        wandb.log({"lemur_definitions": lemur_definitions})
        #log metrics in wandb
        if "FEWS" in CONFIG["dataset_path"]:
            print("Logging metrics for FEWS dataset")
            wandb.log({metrics['type'][0]: metrics['avg_precision'][0]})

        else:
            print("Logging metric avg precision: "+ str(metrics['avg_precision'][0]))
            wandb.log({metrics['type'][0]: metrics['avg_precision'][0]})
            wandb.log({metrics['type'][1]: metrics['avg_precision'][1]})
            wandb.log({metrics['type'][2]: metrics['avg_precision'][2]})
            

"""def_columns=["gen_def_lemur+usages","definition","gen_def_usages","generated_definition"]
for name in def_columns:
    #create tsv for each definition column
    if name in lemur_definitions.columns:
        output_tsv= lemur_definitions[['sense_id', name, 'lemma', 'identifier']]
        output_tsv.rename(columns={name: 'gloss'}, inplace=True)
        output_tsv.to_csv(f"OUTFews3/gen_def_{name}.tsv", sep='\t', index=False)"""


#########TRUE UNRECORDED SENSES!!!#################


#generate for wsi clustered found usages
#remove all sense_id columns where sense_id doesnt contains any letter
wsi_clustered_usages = pd.read_csv(os.path.join(outfolder_path, "o2crun/unrecorded.tsv"), sep='\t')
wsi_clustered_usages['sense_id'] = (
    wsi_clustered_usages['lemma'].astype(str) + "_proposal_" + wsi_clustered_usages['sense_id'].astype(str)
)

##### generate using assigned usages from O2C#################################################################
wsi_clustered_usages_grouped = wsi_clustered_usages.groupby('sense_id')

print(f"Grouped dataset has {len(wsi_clustered_usages_grouped)} groups.")
prompts, sentences= build_prompt_group(wsi_clustered_usages_grouped)
    
# Generate definitions using the model
outputs = llm.generate(prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]

unrecorded_senses= pd.DataFrame({
    'sense_id': [key for key, _ in wsi_clustered_usages_grouped],
    'gloss': generated_texts,
    'identifier': [key+"id" for key, _ in wsi_clustered_usages_grouped],
    'evidence': sentences
})
unrecorded_senses.to_csv(f"{outfolder_path}/sense_proposals.tsv", sep='\t', index=False)
if CONFIG["wandb"]:
    wandb.log({"unrecorded_sense_proposals": unrecorded_senses})


ray.shutdown()
