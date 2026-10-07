import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import plotly.express as px

# Color mapping from the notebook
colors = px.colors.qualitative.Dark24
color_map = {
    "Own USD Weights": colors[0],
    "Own USD Weights, no S1": colors[0],
    "Russian USD Weights": colors[6],
    "Russian USD Weights, no S1": colors[6],
    "Finnish USD Weights": colors[2],
    "Finnish USD Weights, no S1": colors[2],
    "euclidean": colors[3],
    "euclidean, no S1": colors[3],
    "norm_l1": colors[4],
    "norm_l1, no S1": colors[4],
}

# Result data to plot
results = [
    "in_dict.tsv",
    "out_of_dict.tsv",
    "LFS_in_dict.tsv",
    "LFS_out_of_dict.tsv",
    "MFS_in_dict.tsv",
    "MFS_out_of_dict.tsv"
]

# Labels for plots
column_labels = ["in-dict", "out-of-dict"]
row_labels = ["LEMUR", "LFS", "MFS"]

# Create subplots
fig = make_subplots(
    rows=3,
    cols=2,
    subplot_titles=[f"{r}<br>{c}" for r in row_labels for c in column_labels],
    shared_xaxes=False,
    shared_yaxes=True
)


def add_traces_to_subplot(fig, result_path: str, row: int, col: int):
    """Reads data and adds traces to a specific subplot."""
    try:
        df_result = pd.read_csv(result_path, sep="\t", dtype={"result_name": str})
    except FileNotFoundError:
        print(f"Warning: {result_path} not found. Skipping.")
        return

    models = df_result["result_name"].unique()
    
    for model_name in models:
        per_model_rows = df_result[df_result["result_name"] == model_name]
        
        linestyle = 'solid'
        # Group regular and "no S1" models for legend
        legend_group = model_name.replace(", no S1", "")
        
        # Only show legend for the first trace in a group
        show_legend_for_group = legend_group not in [trace.legendgroup for trace in fig.data]
        
        if "no S1" in model_name:
            linestyle = 'dash'
            # Don't add "no S1" to legend, it's represented by linestyle
            showlegend = False
            name = model_name # Keep name for hover
        else:
            showlegend = show_legend_for_group
            name = legend_group


        fig.add_trace(
            go.Scatter(
                x=per_model_rows["valid_p_count"],
                y=per_model_rows["Precision"],
                mode='lines',
                name=name,
                legendgroup=legend_group,
                line=dict(color=color_map.get(model_name, 'black'), dash=linestyle),
                customdata=per_model_rows[['t1_original', 't3_original', 'Recall']],
                hovertemplate=(
                    '<b>%{full_name}</b><br>' +
                    'Precision: %{y:.3f}<br>' +
                    'Recall: %{customdata[2]:.3f}<br>' +
                    'valid_p_count: %{x}<br>' +
                    't1_original: %{customdata[0]:.3f}<br>' +
                    't3_original: %{customdata[1]:.3f}<br>' +
                    '<extra></extra>'
                ),
                showlegend=showlegend
            ),
            row=row,
            col=col
        )

# Iterate through results and add plots
result_index = 0
for i in range(1, 4):  # Rows
    for j in range(1, 3):  # Cols
        if result_index < len(results):
            add_traces_to_subplot(fig, results[result_index], i, j)
            result_index += 1

# Update layout
fig.update_layout(
    height=1000,
    width=1200,
    title_text="Interactive Precision Plots",
    legend_title_text='Models',
    legend_tracegroupgap=20
)

# Update y-axes titles and range
fig.update_yaxes(title_text="Precision", range=[-0.05, 1.05])
fig.update_xaxes(title_text="valid_p_count")


# Add annotations for row and column headers
fig.layout.annotations = [] # remove default subplot titles

# Column Titles
for j, col_label in enumerate(column_labels):
    fig.add_annotation(
        x=0.22 + j*0.55, # Adjusted for better positioning
        y=1.02,
        xref='paper',
        yref='paper',
        text=f'<b>{col_label}</b>',
        showarrow=False,
        font=dict(size=16)
    )

# Row Titles
for i, row_label in enumerate(row_labels):
     fig.add_annotation(
        x=-0.07,
        y= 0.85 - i*0.33, # Adjusted for better positioning
        xref='paper',
        yref='paper',
        text=f'<b>{row_label}</b>',
        showarrow=False,
        font=dict(size=16),
        textangle=-90
    )


# Save to HTML
fig.write_html("interactive_plots.html")

print("Interactive HTML plot generated: interactive_plots.html")
