#!/usr/bin/env python3
import argparse
import pandas as pd


def main(pr_tsv: str, eval_tsv: str) -> None:
    pr = pd.read_csv(pr_tsv, sep="\t")
    eval_df = pd.read_csv(eval_tsv, sep="\t")

    # coverage from pr-table.tsv 
    mask_pred = pr["predicted_lemur_count"] > 0
    mask_in = pr["in_ode"] == True
    mask_out = pr["in_ode"] == False

    in_num = ((mask_pred) & mask_in).sum()
    in_den = mask_in.sum()

    out_num = ((mask_pred) & mask_out).sum()
    out_den = mask_out.sum()

    total_num = mask_pred.sum()
    total_den = len(pr)

    # macroP from eval.tsv (row 0)
    row0 = eval_df.iloc[0]
    macro_total = float(row0["macro_p"])
    macro_in = float(row0["macro_p_in_ode"])
    macro_out = float(row0["macro_p_out_ode"])

    # print table 
    rows = [
        ("out-of-dict", macro_out, f"{out_num}/{out_den}"),
        ("in-dict",    macro_in,  f"{in_num}/{in_den}"),
        ("TOTAL",      macro_total, f"{total_num}/{total_den}"),
    ]

    print("| subset      | macroP | coverage |")
    print("|-------------|--------|---------|")
    for subset, m, cov in rows:
        # {X:<N}: the column X is fixed to a width of N characters
        print(f"| {subset:<11}| {m:.2f} | {cov:<5} |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", default="pr-table.tsv",
                        help="Path to pr-table.tsv")
    parser.add_argument("--eval", default="eval.tsv",
                        help="Path to eval.tsv")
    args = parser.parse_args()
    main(args.pr, args.eval)
