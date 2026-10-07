# WIP: Generation of sense proposals (Section6.2)
NB! Generation of sense definitions is work in progress, this README may not fully reflect the latest code in the repository. 

Unrecorded usages identified in S2 are grouped into sense clusters using the Outlier2Cluster (WSI) model. For each resulting cluster, the corresponding usages are passed to a model that generates a sense definition proposal.

**Running the Pipeline**

Before executing the commands below, ensure that your environment has CUDA enabled, as S2 clustering requires GPU support.
```
cd pipeline
bash pipeline.sh config_trial1_skipS0.env
```

You can also directly run the sense-definition generation stage with:
```
python main_new.py \
  --outpath "/pipeline/sense_definition_generation/output/gen_def.tsv" \
  --usages "/pipeline/data/results_dev3_annotations/s1/unrecorded.tsv" \
  --dict "/pipeline/data/inputs/lemur_dictionary.tsv" \
  --o2cmainpath "autodictpipeline"
```
