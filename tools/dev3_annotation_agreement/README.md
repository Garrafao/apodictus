# annotation_agreement

This script calculates agreement between the annotators of the dev3 annotation. All parameters are specified and notebook just has to be executed.

Cohen's Kappa and Agreement percentage are calculated between each pair of annotators. Additionally, Krippendorff's alpha is calculated between all annotators.

This is done for 4 cases:
- `Subsense-level`: Where all involved annotators annotated a recorded sense calculate agreement metrics based on sense annotations
- `Mainsense-level`: Where all involved annotators annotated a recorded sense calculate agreement metrics based on sense annotations on a main-sense level. (noun:3, noun:3.2, noun:3.5 would all be considered the same)
- `LEMUR Y/N`: Agreement metrics based on whether the annotators annotated a LEMUR sense or not
- `Recorded Y/N`: Agreement metrics based on whether the annotators annotated a recorded sense or not

---
Only the first mentioned sense annotation is used.