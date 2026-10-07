import os
import ray
from config import CONFIG
from prompt_builder_3 import build_prompt_group
from o2c_run import run_outlier2cluster
import pandas as pd
from vllm import LLM, SamplingParams
from sklearn.metrics.cluster import adjusted_rand_score
from sklearn.preprocessing import LabelEncoder

import wandb
#wandb.init(project="ba_pipeline_pilot", tags=["test_gen_def_first","prompt_v4","fill_generated_definition","gen_def_lemur+usages","rag_wn_group","rag_wn_lem"], config=CONFIG, save_code=True)
wandb.init(project="ba_wsi", tags=["nash"],config=CONFIG, save_code=True)

os.environ["CUDA_VISIBLE_DEVICES"] = CONFIG["cuda_device"]

dataset_path=CONFIG["dataset_path"]
#dataset_path="/home/users1/saxjs/BASax/johannes/FEWS/train_fews/FEWS_train_ext_o2c.tsv"
out_path="OUT"
data= pd.read_csv(dataset_path, sep='\t')

dict_path=CONFIG["lemur_definitions_path"]
#dict_path="/home/users1/saxjs/BASax/johannes/FEWS/own_dev_fews/GOLD_FEWS_DEF/sense_inv_lem+notlem.tsv"
dict=pd.read_csv(dict_path, sep='\t')

lemmas=dict['lemma'].unique()
#only use the ones in the dataset
lemmas = [lemma for lemma in lemmas if lemma in data['lemma'].values]

dict2 = pd.DataFrame({
    "lemma": lemmas,
    "gloss": ["placeholder_gloss"for lemma in lemmas] ,
    "identifier": [f"{lemma}_x" for lemma in lemmas],
    "sense_id": [f"{lemma}_x" for lemma in lemmas]
})

outdict_path=f"{out_path}/empty_dict.tsv"
dict2.to_csv(outdict_path, sep='\t', index=False)




dataset=run_outlier2cluster("o2c_wsi", outdict_path, dataset_path, out_path)

#grouped_dataset= dataset.groupby('sense_id')

sampling_params = SamplingParams(**CONFIG["sampling_params"])
llm = LLM(model=CONFIG["model"], tensor_parallel_size=1)



##### generate using assigned usages from O2C#################################################################
wsi_clustered_usages_grouped = dataset.groupby(['sense_id','lemma'])

print(f"Grouped dataset has {len(wsi_clustered_usages_grouped)} groups.")
prompts, sentences= build_prompt_group(wsi_clustered_usages_grouped)
    
# Generate definitions using the model
outputs = llm.generate(prompts, sampling_params)
generated_texts = [o.outputs[0].text for o in outputs]

#remove everything but text and numbers

# create a list with all lemmas from wsi_clustered_usages_grouped
lemmas = [] #wsi_clustered_usages_grouped["lemma"]
sense_ids=[]

for (sense_id, lemma),group in wsi_clustered_usages_grouped:
    lemma_new= lemma.replace("'", "")
    lemmas.append(lemma_new)
    sense_ids.append(str(lemma)+"proposal"+str(sense_id))

unrecorded_senses= pd.DataFrame({
    'lemma': lemmas,
    'sense_id': sense_ids,
    'gloss': generated_texts,
    'identifier': [str(sid) + "id" for sid in sense_ids]
})



unrecorded_senses.to_csv(f"{out_path}/sense_proposals.tsv", sep='\t', index=False)
proposal_path=f"{out_path}/sense_proposals.tsv"

dataset3=run_outlier2cluster("o2c_wsdsdg", proposal_path, dataset_path, out_path)
dataset3=pd.read_csv(f"{out_path}/o2c_wsdsdg/wsd.tsv", sep='\t')

scores=dataset3['sense_id'].to_list()
scores_gold=dataset3['sense_id_gold'].to_list()

# Convert both to integer labels
le1 = LabelEncoder()
le2 = LabelEncoder()

test_encoded = le1.fit_transform(scores)
gold_encoded = le2.fit_transform(scores_gold)

rand_score_wsdsdg=adjusted_rand_score(test_encoded, gold_encoded)
print("Adjusted Rand Index (SDG+WSD):", rand_score_wsdsdg)

#prepend lemma to sense_id
dataset['sense_id'] = [str(lemma) + "_x" for lemma in dataset['lemma']]

scores=dataset['sense_id'].to_list()
scores_gold=dataset['sense_id_gold'].to_list()

# Convert both to integer labels
le3 = LabelEncoder()
le4 = LabelEncoder()

test_encoded = le3.fit_transform(scores)
gold_encoded = le4.fit_transform(scores_gold)

rand_score_wsdsdg=adjusted_rand_score(test_encoded, gold_encoded)
print("Adjusted Rand Index (WSI Model):", rand_score_wsdsdg)

def compute_avg_adjusted_rand_index(wsi_data):
    grouped = wsi_data.groupby('lemma')
    adj_rand_ind_list=[]
    for group_name, group_df in grouped:
        # Get sense ids of each element of the group
        scores = group_df['sense_id'].to_list()
        gold = group_df['sense_id_gold'].to_list()

        # Convert both to integer labels
        le1 = LabelEncoder()
        le2 = LabelEncoder()

        test_encoded = le1.fit_transform(scores)
        gold_encoded = le2.fit_transform(gold)

        rand_score = adjusted_rand_score(test_encoded, gold_encoded)
        adj_rand_ind_list.append(rand_score)
    return sum(adj_rand_ind_list) / len(adj_rand_ind_list)

avg_sdg_wsd = compute_avg_adjusted_rand_index(dataset3)
avg_wsi = compute_avg_adjusted_rand_index(dataset)

print("Average Adjusted Rand Index (SDG+WSD):", avg_sdg_wsd)
print("Average Adjusted Rand Index (WSI Model):", avg_wsi)
