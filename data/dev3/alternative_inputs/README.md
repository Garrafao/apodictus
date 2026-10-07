# alternative_inputs/

````
📁 full_run_annotation/
├── 📁 alternative_dictionaries/
├── 📁 raw_usages_for_alternative_dictionaries/
````

---

## `alternative_dictionaries/`
Contains dictionaries that can be used as an alternative to the regular dev3 **LEMUR** dictionary. The dictionaries use unrecorded senses which were discovered during dev3 annotation as replacement for the original LEMUR dictionary. 

- `dev3_unrecorded_dictionary.tsv` Alternative LEMUR dictionary that contains all unrecorded senses found during annotation

- `dev3_unrecorded_dictionary_LFS.tsv` Alternative LEMUR dictionary that contains for each headword only the **L**east **F**requent unrecorded **S**ense (LFS)

- `dev3_unrecorded_dictionary_MFS.tsv` Alternative LEMUR dictionary that contains for each headword only the **M**ost **F**requent unrecorded **S**ense (MFS)

---

## `raw_usages_for_alternative_dictionaries/`

Because the alternative dictionaries rely on unrecorded senses found during annotation, headwords where no unrecorded sense was found will consequently have no entry in the resulting dictionary.
So when running the pipeline using the alternative dictionaries, a reduced set of usages has to be used that only includes usages of headwords that have an entry in the alternative dictionary. This folder contains the filtered set of usages. 