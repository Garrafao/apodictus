import time
from o2c_run import run_outlier2cluster
import pandas as pd
import os
from sklearn.metrics import precision_recall_curve
import numpy as np
import matplotlib.pyplot as plt
import wandb


def run_eval(dictionary, usages, RESULT_DIR, baseline_path="/home/users1/saxjs/BASax/johannes/ba_pipeline/IN/full_tsv_run_pilot_baseline.tsv"):
    full_tsv_run = create_tsv_format_foro2c(dictionary, usages, RESULT_DIR)
    full_tsv_run.to_csv(f"{RESULT_DIR}/full_tsv_run.tsv", sep='\t', index=False)
    
    return calc_eval_metrics(full_tsv_run, RESULT_DIR, baseline_path)
    

###RUN o2c bundles

import time

def create_tsv_format_foro2c(dict_df, usages_df, RESULT_DIR):
    """
    Create TSV format data and run o2c running 1 sense of multiple lemmas at once.
    
    Parameters:
    -----------
    dictionary : string
        path to dictionary file
    usages : string
        path to usages file

    Returns:
    --------
    pandas.DataFrame
        DataFrame containing the dataset
    """
    
    step_sense_path= f"{RESULT_DIR}/sense_step.tsv"
    step_usage_path = f"{RESULT_DIR}/usage_tsv_step.tsv"



    # Remove dictionary entries with no usages
    #print("Removing dictionary entries with no usages... current size:", len(dict_df))
    #dict_df = dict_df[dict_df['sense_id'].isin(usages_df['sense_id_gold'])]
    #print("New dictionary size:", len(dict_df))

    #same columns as usages_df
    full_dataset = pd.DataFrame(columns=usages_df.columns)

    # Iterate over dictionary entries grouped by lemma
    grouped_dict = dict_df.groupby('lemma')
    stop=0
    usages_for_step = pd.DataFrame(columns=usages_df.columns)
    senses_for_step = pd.DataFrame(columns=dict_df.columns)

    #get group with most rows
    max_group_size = grouped_dict.size().max()

    #for lemma, group in grouped_dict:
    #range from 0 to maximum size of grouped_dict
    print("Processing grouped dictionary entries...")
    print(f"maximum size of each group: {max_group_size}")
    for step in range(0,max_group_size):

        # Reset Step DataFrames
        usages_for_step = pd.DataFrame(columns=usages_df.columns)
        senses_for_step = pd.DataFrame(columns=dict_df.columns)
        usages_for_step['tsv_step_sense'] = 0  # Initialize all to 0

        # get row of each group at position step
        for lemma, group in grouped_dict:
            # Check if the current group has enough rows for this step
            if step < len(group):
                sense_id = group.iloc[step]['sense_id']
                usages = usages_df[usages_df['lemma'] == lemma].copy()
                # Keep only the sense at position step
                step_sense = group[group['sense_id'] == sense_id].copy()
                # Create tsv_label column and set it to 0
                usages = usages.copy()
                usages['tsv_label'] = 0  # Initialize all to 0
                usages.loc[usages['sense_id_gold'] == sense_id, 'tsv_label'] = 1

                # add current step sense to output
                usages['tsv_step_sense'] = sense_id
                


                senses_for_step = pd.concat([senses_for_step, step_sense], ignore_index=True)
                usages_for_step = pd.concat([usages_for_step, usages], ignore_index=True)

        usages_for_step.to_csv(f"{RESULT_DIR}/usage_tsv_step.tsv", sep='\t', index=False)
        senses_for_step.to_csv(f"{RESULT_DIR}/sense_step.tsv", sep='\t', index=False)
        

        # start timer
        start_time = time.time()

        print("running step: "+ str(step))    
        #run 02c now
        o2c_output_step = run_outlier2cluster(
                    name="o2c_step",
                    dictionary_s3=step_sense_path,
                    usage_path=step_usage_path,
                    RESULT_DIR=RESULT_DIR)
            
        full_dataset = pd.concat([full_dataset, o2c_output_step], ignore_index=True)
        # end timer
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Processed first '{len(o2c_output_step)}' in {elapsed_time:.2f} seconds.")
        full_dataset.to_csv(f"{RESULT_DIR}/running_tsv_run.tsv", sep='\t')

    return full_dataset


def calc_eval_metrics_nosuggestions(full_tsv_run,RESULT_DIR,baseline_path, threshold=0.2):
    metric = []

    tsv_run_test=full_tsv_run.copy()
    tsv_run_base=pd.read_csv(baseline_path, sep='\t')

    gold_label = tsv_run_base['tsv_label'].to_list()
    gold_label_2 = tsv_run_test['tsv_label'].to_list()

    scores_base = tsv_run_base['prob'].to_list()
    label_base = [1 if x < threshold else 0 for i, x in enumerate(scores_base)]  # Convert probabilities to binary labels
    scores_base = [1-x for x in scores_base]  # Convert probabilities to binary labels

    scores_test = tsv_run_test['prob'].to_list()
    label_test = [1 if x < threshold else 0 for i, x in enumerate(scores_test)]  # Convert probabilities to binary labels
    scores_test = [1-x for x in scores_test]  # Convert probabilities to binary labels


    
    # Plot Precision-Recall Curve for base run using scores_base
    precision_base, recall_base, thresholds_base = precision_recall_curve(gold_label, scores_base, pos_label=1)
    plt.plot(recall_base, precision_base, marker='.', label='base run (pilot defs)')
    avg_precision_base= sum(precision_base) / len(precision_base)
    print("Average Precision for base run:", avg_precision_base)

    # Plot Precision-Recall Curve for test run using scores_test
    precision_test, recall_test, thresholds_test = precision_recall_curve(gold_label_2, scores_test,  pos_label=1)
    plt.plot(recall_test, precision_test, marker='.', label='test run: (generated defs)')
    avg_precision_test= sum(precision_test) / len(precision_test)
    print("Average Precision for test run:", avg_precision_test)
    metric.append(["full_run", avg_precision_test])
    metric.append(["base_run", avg_precision_base])
    
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Pilot F')
    plt.legend()
    plt.show()
    resultpath= os.path.join(RESULT_DIR, "precision_recall_full.png")
    plt.savefig(resultpath)
    
    metrics = pd.DataFrame(metric, columns=["type", "avg_precision"])

    return metrics




def calc_eval_metrics(full_tsv_run,RESULT_DIR,baseline_path, threshold=0.1):
    # Placeholder for evaluation metric calculations
    print("Calculating evaluation metrics...")

    #empty dataframe for metrics
    metric = []

    tsv_run_test=full_tsv_run.copy()
    tsv_run_base=pd.read_csv(baseline_path, sep='\t')

    tsv_run_base_suggested = tsv_run_base[tsv_run_base['tsv_step_sense'].str.contains('-')].copy()

    tsv_run_base_existing = tsv_run_base[~tsv_run_base['tsv_step_sense'].str.contains('-')].copy()

    tsv_run_test_suggested = tsv_run_test[
    tsv_run_test['tsv_step_sense'].str.contains('-')
    ].copy()

    tsv_run_test_existing = tsv_run_test[
    ~tsv_run_test['tsv_step_sense'].str.contains('-')
    ].copy()
    print(f"Test run has {len(tsv_run_test)} rows.")
    print(f"Base run has {len(tsv_run_base)} rows.")
    print(f"Suggested base run has {len(tsv_run_base_suggested)} rows.")
    print(f"Existing base run has {len(tsv_run_base_existing)} rows.")
    print(f"Suggested test run has {len(tsv_run_test_suggested)} rows.")
    print(f"Existing test run has {len(tsv_run_test_existing)} rows.")


    gold_label = tsv_run_base['tsv_label'].to_list()
    gold_label_2 = tsv_run_test['tsv_label'].to_list()
    gold_label_existing_base = tsv_run_base_existing['tsv_label'].to_list()
    gold_label_suggested_base = tsv_run_base_suggested['tsv_label'].to_list()
    gold_label_existing_test = tsv_run_test_existing['tsv_label'].to_list()
    gold_label_suggested_test = tsv_run_test_suggested['tsv_label'].to_list()


    scores_base = tsv_run_base['prob'].to_list()
    label_base = [0 if x > threshold else 1 for x in scores_base]  # Convert probabilities to binary labels
    scores_base = [1-x for x in scores_base]  # Convert probabilities to binary labels

    scores_test = tsv_run_test['prob'].to_list()
    label_test = [0 if x > threshold else 1 for x in scores_test]  # Convert probabilities to binary labels
    scores_test = [1-x for x in scores_test]  # Convert probabilities to binary labels

    scores_base_existing = tsv_run_base_existing['prob'].to_list()
    label_base_existing = [0 if x > threshold else 1 for x in scores_base_existing]  # Convert probabilities to binary labels
    scores_base_existing = [1-x for x in scores_base_existing]  # Convert probabilities to binary labels

    scores_base_suggested= tsv_run_base_suggested['prob'].to_list()
    label_base_suggested = [0 if x > threshold else 1 for x in scores_base_suggested]  # Convert probabilities to binary labels
    scores_base_suggested = [1-x for x in scores_base_suggested]  # Convert probabilities to binary labels

    scores_test_suggested = tsv_run_test_suggested['prob'].to_list()
    label_test_suggested = [0 if x > threshold else 1 for x in scores_test_suggested]  # Convert probabilities to binary labels
    scores_test_suggested = [1-x for x in scores_test_suggested]  # Convert probabilities to binary labels

    scores_test_existing = tsv_run_test_existing['prob'].to_list()
    label_test_existing = [0 if x > threshold else 1 for x in scores_test_existing]  # Convert probabilities to binary labels
    scores_test_existing = [1-x for x in scores_test_existing]  # Convert probabilities to binary labels




    # Plot Precision-Recall Curve for base run using scores_base
    precision_base, recall_base, thresholds_base = precision_recall_curve(gold_label, scores_base, pos_label=1)
    plt.plot(recall_base, precision_base, marker='.', label='base run (pilot defs)')
    avg_precision_base= sum(precision_base) / len(precision_base)
    print("Average Precision for base run:", avg_precision_base)

    # Plot Precision-Recall Curve for test run using scores_test
    precision_test, recall_test, thresholds_test = precision_recall_curve(gold_label_2, scores_test,  pos_label=1)
    plt.plot(recall_test, precision_test, marker='.', label='test run: (generated defs)')
    avg_precision_test= sum(precision_test) / len(precision_test)
    print("Average Precision for test run:", avg_precision_test)
    metric.append(["full_run", avg_precision_test])

    #wandb.log({"pr-full-run" : wandb.plot.pr_curve(gold_label_2, scores_test)})


    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Pilot F')
    plt.legend()
    plt.show()
    resultpath= os.path.join(RESULT_DIR, "precision_recall_full.png")
    plt.savefig(resultpath)

    plt.clf()  # Clear the plot for the next one


    # Plot Precision-Recall Curve for base using scores_base_existing
    precision_test, recall_test, thresholds_test = precision_recall_curve(gold_label_existing_base, scores_base_existing,  pos_label=1)
    plt.plot(recall_test, precision_test, marker='.', label='Existing : base run')

    # Plot Precision-Recall Curve for test run using scores_test_existing
    precision_test, recall_test, thresholds_test = precision_recall_curve(gold_label_existing_test, scores_test_existing,  pos_label=1)
    plt.plot(recall_test, precision_test, marker='.', label='Existing : test run')
    avg_precision_test= sum(precision_test) / len(precision_test)
    metric.append(["existing", avg_precision_test])


    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Pilot F: Existing')
    plt.legend()
    plt.show()
    resultpath= os.path.join(RESULT_DIR, "precision_recall_existing.png")
    plt.savefig(resultpath)
    
    plt.clf()  # Clear the plot for the next one


    # Plot Precision-Recall Curve for base using scores_base_suggested
    precision_test, recall_test, thresholds_test = precision_recall_curve(gold_label_suggested_base, scores_base_suggested,  pos_label=1)
    plt.plot(recall_test, precision_test, marker='.', label='Suggested : base run')

    # Plot Precision-Recall Curve for test run using scores_test_suggested
    precision_test, recall_test, thresholds_test = precision_recall_curve(gold_label_suggested_test, scores_test_suggested,  pos_label=1)
    plt.plot(recall_test, precision_test, marker='.', label='Suggested : test run')
    avg_precision_test= sum(precision_test) / len(precision_test)
    metric.append(["suggested", avg_precision_test])

    
    # plot pr curve for test run using only suggested definitions from annotator
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Pilot F: Suggested')
    plt.legend()
    plt.show()
    #save plot as file
    resultpath= os.path.join(RESULT_DIR, "precision_recall_suggested.png")
    plt.savefig(resultpath)

    plt.clf()  # Clear the plot for the next one
    

    metrics = pd.DataFrame(metric, columns=["type", "avg_precision"])


    #class distrubution for labels
    print("Class distribution for labels in base run:")
    print(pd.Series(label_base).value_counts())

    print("Class distribution for labels in test run:")
    print(pd.Series(label_test).value_counts())

    print("Class distribution for gold labels:")
    print(tsv_run_base['tsv_label'].value_counts())


    

    return metrics