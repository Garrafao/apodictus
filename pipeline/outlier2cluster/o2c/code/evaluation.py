import logging
import os

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, precision_recall_curve, roc_curve, \
    confusion_matrix, accuracy_score, adjusted_rand_score
import matplotlib.pyplot as plt
import argparse


# takes is_novel prediction (True or False) from results and from gold predictions to evaluate
def novel_sense_evaluate(final_preds_path: str, gold_path: str, wsd_preds_path: str, wsi_preds_path: str, out_dir: str):
    logger = logging.getLogger()
    df_preds = pd.read_csv(final_preds_path, sep='\t')
    df_gold = pd.read_csv(gold_path, sep='\t')

    # merge predictions and gold labels
    df_gold = df_gold.rename(columns={"is_novel": "is_novel_gold"})
    df_gold = df_gold.rename(columns={"sense_id": "sense_id_gold"})
    df_nsd_complete = pd.merge(df_preds[['identifier', 'lemma', 'is_novel', 'sense_id', 'prob']],
                               df_gold[['identifier', 'is_novel_gold', 'sense_id_gold']],
                               on='identifier', how='left')

    # drop rows without gold label
    missing_gold = df_nsd_complete["is_novel_gold"].isna().sum()
    df_nsd_complete = df_nsd_complete.dropna(subset=["is_novel_gold"])
    logger.info(f"Ignore {missing_gold} predictions without respective entry in gold file")

    # calculate performance metrics for is_novel label
    preds = df_nsd_complete["is_novel"]
    gold = df_nsd_complete["is_novel_gold"]
    f1 = f1_score(gold, preds, average="binary", zero_division=0)
    precision = precision_score(gold, preds, average='binary', zero_division=0)
    recall = recall_score(gold, preds, average='binary', zero_division=0)
    accuracy = accuracy_score(gold, preds)
    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(gold, preds, labels=[False, True]).ravel().tolist()

    # Create precision-recall curve plot
    prec_curve, rec_curve, thresholds = precision_recall_curve(gold, df_nsd_complete["prob"])
    plt.figure(figsize=(6, 4))
    plt.plot(rec_curve, prec_curve, marker='.', label="PR Curve")
    plt.title("Precision-Recall Curve for is_novel = True")
    plt.fill_between(rec_curve, prec_curve, step='post', alpha=0.2)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.legend()
    pr_plot_path = f"{out_dir}/precision_recall_curve.png"
    plt.savefig(pr_plot_path, dpi=1000)
    plt.close()

    # create ROC curve plot
    fpr, tpr, thresholds = roc_curve(gold, df_nsd_complete["prob"])
    plt.figure(figsize=(6, 4))
    plt.plot(fpr, tpr, marker='.', label="ROC Curve")
    plt.title("ROC Curve")
    plt.fill_between(fpr, tpr, step='post', alpha=0.2)
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend()
    pr_plot_path = f"{out_dir}/roc_curve.png"
    plt.savefig(pr_plot_path, dpi=1000)
    plt.close()

    # merge all rows with entries that are NOT novel to compare WSD sense assignments for known senses
    df_wsd_preds = pd.read_csv(wsd_preds_path, sep='\t')
    df_wsd_complete = pd.merge(df_wsd_preds[['identifier', 'lemma', 'sense_id']],
                               df_gold[['identifier', 'is_novel_gold', 'sense_id_gold']],
                               on='identifier', how='left')
    df_wsd_complete = df_wsd_complete[df_wsd_complete["is_novel_gold"] == False]

    # calculate wsd accuracy
    wsd_preds = df_wsd_complete["sense_id"]
    wsd_gold = df_wsd_complete["sense_id_gold"]
    wsd_accuracy = accuracy_score(wsd_gold, wsd_preds)

    # calculate average ARI score for evaluation of wsi clustering
    df_wsi_preds = pd.read_csv(wsi_preds_path, sep='\t')
    df_wsi_complete = pd.merge(df_wsi_preds[['identifier', 'lemma', 'sense_id']],
                               df_gold[['identifier', 'sense_id_gold']],
                               on='identifier', how='left')
    ari_scores = []
    for word, group in df_wsi_complete.groupby("lemma"):
        gold = group["sense_id_gold"]
        pred = group["sense_id"]
        ari = adjusted_rand_score(gold, pred)
        ari_scores.append(ari)
    average_ari = np.mean(ari_scores) if ari_scores else float("nan")

    # Write Evaluation to Markdown
    with open(f"{out_dir}/evaluation.md", "w") as f:
        f.write("# Evaluation\n\n")
        f.write(f"## WSD Performance Metrics\n")
        f.write("Accuracy of WSD assignments (ignore usages belonging to a novel sense)\n\n")
        f.write("```\n")
        f.write(f"Accuracy:\t{wsd_accuracy:.4f}\n")
        f.write("```\n")
        f.write(f"## WSI Performance Metrics\n")
        f.write("```\n")
        f.write(f"Avg. ARI score:\t{average_ari:.4f}\n")
        f.write("```\n")
        f.write(f"## NSD Performance Metrics\n")
        f.write(f"Evaluate novel_sense predictions (True/False) for NSD Threshold = {df_preds.iloc[1]['thresh']}\n\n")
        f.write("|          | Positive | Negative |\n")
        f.write("|----------|------------------|----------------------|\n")
        f.write(f"| **True**     | {tp}               | {tn}                  |\n")
        f.write(f"| **False** | {fp}               | {fn}                  |\n\n")
        f.write("```\n")
        f.write(f"Accuracy:\t\t{accuracy:.4f}\n")
        f.write(f"F1 Score (binary):\t{f1:.4f}\n")
        f.write(f"Precision (binary):\t{precision:.4f}\n")
        f.write(f"Recall (binary):\t{recall:.4f}\n")
        f.write("```\n")

        f.write("# Precision-Recall Curve\n")
        f.write(
            "PR-curve using NSD probability and gold labels (see [scikit-learn](https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html))\n\n")
        f.write(f'<img src="precision_recall_curve.png" alt="drawing" width="500"/>\n\n')
        f.write("# ROC Curve\n")
        f.write(
            "ROC-curve using NSD probability and gold labels (see [scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_curve.html))\n\n")
        f.write(f'<img src="roc_curve.png" alt="drawing" width="500"/>')


logging.info("Evaluation results written to '../data/evaluation'")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--predictions', type=str, help='path to the result tsv file',
                        default="../data/results/s1/result.tsv")
    parser.add_argument('--wsd', type=str, help='path to the wsd result file', default="../data/results/s1/wsd.tsv")
    parser.add_argument('--wsi', type=str, help='path to the wsi result file', default="../data/results/s1/wsi.tsv")
    parser.add_argument('--gold', type=str, help='path to the gold tsv file', default="../data/gold_files/gold.tsv")
    parser.add_argument('--run_name', type=str, help='Saves the evaluation results under data/evaluation/<run_name>', default="s1")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    os.makedirs(f"../data/evaluation/{args.run_name}", exist_ok=True)
    logging.info("use predictions at '%s' and gold file at '%s' to create evaluation report in data/evaluation/%s", args.predictions,
                 args.gold, args.run_name)

    novel_sense_evaluate(args.predictions, args.gold, args.wsd, args.wsi, f"../data/evaluation/{args.run_name}")
