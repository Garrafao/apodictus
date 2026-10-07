import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='Path to the result .tsv file')
    parser.add_argument('--output', help='Output path for plot')

    args = parser.parse_args()
    input_path =args.input_file
    output_path = args.output

    df = pd.read_csv(input_path, sep='\t', dtype={"sense_id": str})
    if not df.empty:
        df['mwe'] = df.lemma.str.contains(r'[- ]')

        sns.histplot(data=df, x='prob', hue='mwe', fill=True, kde=True, bins=40)
        plt.title('Probability Distribution of predictions')
        plt.xlabel('Probability')
        plt.ylabel('Count')

        plt.savefig(output_path)