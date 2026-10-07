### `dev3/`
Contains all data relevant to the dataset dev3. The usages in `raw_usages/` and the dictionaries in `dictionaries/` can be used to run the pipeline on dev3. The annotated usages in `annotated_usages/` can be used for evaluation.

````
📁 full_run_annotation/
├── 📁 annotated_usages/
├── 📁 dictionaries/
├── 📁 filtered_results/
├── 📁 headwords_file/
├── 📁 quality_control/
├── 📁 raw_usages/
├── 📁 alternative_inputs/
````

* annotated_usages: annotated dev3 dataset. See [annotation instructions](annotation_instructions.md) for more information.
* dictionaries: Complete LEMUR and ODE dictionaries for the dev3 dataset (can be used when running the pipeline on dev3 lemmas and usages)
* filtered_results: results produced by the pipeline for dev3
* headwords_file: contains headwords file, listing lemmas of dev3. Can be used as input to the pipeline when running on dev3 data
* quality_control: annotated usages used for quality control of annotations. The same 100 usages of headword `reel` were annotated once by each annotator.
* raw_usages: all usages for which annotations exist. Can be used as reduced input to the pipeline for evaluation purposes on the annotations
* alternative_inputs: Contains several alternative dictionaries and usages based on dev3 that can be used as input to the pipeline and for evaluation.
They use unrecorded senses from the annotation as replacement senses for the real LEMUR senses for their higher frequency in the data. Consequently only target words with at least one unrecorded sense found during annotation can be used, as for the others there would not be a LMEUR sense available. 
See [README](alternative_inputs/README.md)
