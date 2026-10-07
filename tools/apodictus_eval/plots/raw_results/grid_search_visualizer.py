#!/usr/bin/env python3
"""
Interactive visualization tool for grid search results.
Shows precision-coverage and recall-coverage scatterplots with tooltips and cross-plot highlighting.
"""

import glob
import os

# Check for required packages
try:
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px
    import numpy as np
    import dash
    from dash import dcc, html, Input, Output, State, callback
    import dash_bootstrap_components as dbc
    PACKAGES_AVAILABLE = True
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install with: pip install pandas plotly dash dash-bootstrap-components")
    PACKAGES_AVAILABLE = False
    exit(1)


class GridSearchVisualizer:
    def __init__(self, data_dir="."):
        self.data_dir = data_dir
        self.data = {}
        self.weights = []
        self.load_data()
        
    def load_data(self):
        """Load all .raw files and extract unique weights"""
        raw_files = glob.glob(os.path.join(self.data_dir, "*.raw"))
        
        for file_path in raw_files:
            file_name = os.path.basename(file_path).replace('.raw', '')
            try:
                df = pd.read_csv(file_path, sep='\t')
                # Calculate coverage as valid_p_count
                df['coverage'] = df['valid_p_count']
                # Clean precision column (handle empty values)
                df['Precision'] = pd.to_numeric(df['Precision'], errors='coerce').fillna(0)
                df['Recall'] = pd.to_numeric(df['Recall'], errors='coerce').fillna(0)
                
                self.data[file_name] = df
                # Extract unique weights from result_name
                unique_weights = df['result_name'].unique()
                self.weights.extend([w for w in unique_weights if w not in self.weights])
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                
        self.weights = sorted(list(set(self.weights)))
        
    def get_filtered_data(self, weight):
        """Get data filtered by selected weight"""
        filtered_data = {}
        for file_name, df in self.data.items():
            filtered_df = df[df['result_name'] == weight].copy()
            if not filtered_df.empty:
                filtered_data[file_name] = filtered_df
        return filtered_data
    
    def create_scatterplots(self, weight, selected_config=None):
        """Create precision-coverage and recall-coverage scatterplots for each file"""
        filtered_data = self.get_filtered_data(weight)
        
        if not filtered_data:
            return go.Figure()
        
        # Sort files alphabetically by filename
        sorted_files = dict(sorted(filtered_data.items()))
        
        num_files = len(sorted_files)
        # Create subplots: 2 columns (precision, recall) per file
        subplot_titles = []
        for file_name in sorted_files.keys():
            subplot_titles.append(f'{file_name} - Precision vs Coverage')
            subplot_titles.append(f'{file_name} - Recall vs Coverage')
        
        fig = make_subplots(
            rows=num_files, cols=2,
            subplot_titles=subplot_titles,
            vertical_spacing=0.05,
            horizontal_spacing=0.1
        )
        
        colors = px.colors.qualitative.Set1
        
        for i, (file_name, df) in enumerate(sorted_files.items()):
            color = colors[i % len(colors)]
            row = i + 1  # subplot rows are 1-indexed
            
            # Precision vs Coverage
            fig.add_trace(
                go.Scatter(
                    x=df['coverage'],
                    y=df['Precision'],
                    mode='markers',
                    name=file_name,
                    marker=dict(color=color, size=8),
                    text=df.apply(self.create_tooltip, axis=1),
                    hovertemplate='%{text}<extra></extra>',
                    customdata=df.apply(lambda row: f"{row['t1_original']:.6f}_{row['t3_original']:.6f}", axis=1),
                    showlegend=(i == 0)  # Only show legend for first file
                ),
                row=row, col=1
            )
            
            # Recall vs Coverage
            fig.add_trace(
                go.Scatter(
                    x=df['coverage'],
                    y=df['Recall'],
                    mode='markers',
                    name=file_name,
                    marker=dict(color=color, size=8),
                    text=df.apply(self.create_tooltip, axis=1),
                    hovertemplate='%{text}<extra></extra>',
                    customdata=df.apply(lambda row: f"{row['t1_original']:.6f}_{row['t3_original']:.6f}", axis=1),
                    showlegend=False
                ),
                row=row, col=2
            )
        
        # Update layout with proper axis titles for each subplot
        fig.update_layout(
            title=f'Grid Search Results - {weight}',
            height=300 * num_files,  # Adjust height based on number of files
            hovermode='closest'
        )
        
        # Set axis titles for all subplots
        for i in range(num_files):
            row = i + 1
            fig.update_xaxes(title_text='Coverage (valid_p_count)', row=row, col=1)
            fig.update_xaxes(title_text='Coverage (valid_p_count)', row=row, col=2)
            fig.update_yaxes(title_text='Precision', row=row, col=1)
            fig.update_yaxes(title_text='Recall', row=row, col=2)
        
        return fig
    
    def create_tooltip(self, row):
        """Create tooltip text showing ranges"""
        return (f"File: {row.name if hasattr(row, 'name') else 'Unknown'}<br>"
                f"Precision: {row['Precision']:.4f}<br>"
                f"Recall: {row['Recall']:.4f}<br>"
                f"Coverage: {row['coverage']:.4f}<br>"
                f"t1_original: {row['t1_original']:.6f}<br>"
                f"t3_original: {row['t3_original']:.6f}")
    
    def find_matching_points(self, selected_data, weight):
        """Find all points with matching t1_original and t3_original ranges"""
        filtered_data = self.get_filtered_data(weight)
        matching_points = []
        
        for file_name, df in filtered_data.items():
            # Find points with similar t1_original and t3_original values
            for _, row in df.iterrows():
                t1_diff = abs(row['t1_original'] - selected_data['t1_original'])
                t3_diff = abs(row['t3_original'] - selected_data['t3_original'])
                
                # Use small tolerance for floating point comparison
                if t1_diff < 1e-6 and t3_diff < 1e-6:
                    matching_points.append({
                        'file': file_name,
                        'coverage': row['coverage'],
                        'precision': row['Precision'],
                        'recall': row['Recall'],
                        't1_original': row['t1_original'],
                        't3_original': row['t3_original']
                    })
        
        return matching_points
    
    def find_nearest_points(self, selected_data, weight, file_name):
        """Find the nearest points by taking Cartesian product of nearest t1 and t3 values"""
        filtered_data = self.get_filtered_data(weight)
        
        if file_name not in filtered_data:
            return []
        
        df = filtered_data[file_name]
        target_t1 = selected_data['t1_original']
        target_t3 = selected_data['t3_original']
        
        # Get unique t1 and t3 values from this file
        unique_t1 = sorted(df['t1_original'].unique())
        unique_t3 = sorted(df['t3_original'].unique())
        
        # Find nearest smaller and bigger t1 values
        t1_candidates = []
        for t1 in unique_t1:
            if t1 < target_t1:
                t1_candidates.append(('smaller', t1, abs(t1 - target_t1)))
            elif t1 > target_t1:
                t1_candidates.append(('bigger', t1, abs(t1 - target_t1)))
        
        # Find nearest smaller and bigger t3 values
        t3_candidates = []
        for t3 in unique_t3:
            if t3 < target_t3:
                t3_candidates.append(('smaller', t3, abs(t3 - target_t3)))
            elif t3 > target_t3:
                t3_candidates.append(('bigger', t3, abs(t3 - target_t3)))
        
        # Take the closest smaller and bigger for each parameter
        nearest_t1 = {}
        for direction in ['smaller', 'bigger']:
            candidates = [c for c in t1_candidates if c[0] == direction]
            if candidates:
                candidates.sort(key=lambda x: x[2])  # sort by distance
                nearest_t1[direction] = candidates[0][1]
        
        nearest_t3 = {}
        for direction in ['smaller', 'bigger']:
            candidates = [c for c in t3_candidates if c[0] == direction]
            if candidates:
                candidates.sort(key=lambda x: x[2])  # sort by distance
                nearest_t3[direction] = candidates[0][1]
        
        # Always create all 4 combinations of nearest t1 and t3 values
        nearest_points = []
        t1_directions = ['smaller', 'bigger']
        t3_directions = ['smaller', 'bigger']
        
        for t1_dir in t1_directions:
            for t3_dir in t3_directions:
                if t1_dir in nearest_t1 and t3_dir in nearest_t3:
                    t1_val = nearest_t1[t1_dir]
                    t3_val = nearest_t3[t3_dir]
                    
                    # Find the row with this combination
                    matching_rows = df[(df['t1_original'] == t1_val) & (df['t3_original'] == t3_val)]
                    
                    if not matching_rows.empty:
                        row = matching_rows.iloc[0]
                        t1_dist = abs(t1_val - target_t1)
                        t3_dist = abs(t3_val - target_t3)
                        
                        nearest_points.append({
                            'file': file_name,
                            'coverage': row['coverage'],
                            'precision': row['Precision'],
                            'recall': row['Recall'],
                            't1_original': row['t1_original'],
                            't3_original': row['t3_original'],
                            'distance': t1_dist + t3_dist,  # Manhattan distance for display
                            't1_dist': t1_dist,
                            't3_dist': t3_dist,
                            't1_direction': t1_dir,
                            't3_direction': t3_dir
                        })
        
        return nearest_points
    
    def find_points_in_range(self, selected_data, weight):
        """Find all points within the selected range of metrics"""
        filtered_data = self.get_filtered_data(weight)
        matching_points = []
        
        # Extract range from selected data
        if 'x_range' in selected_data and 'y_range' in selected_data:
            # Range selection
            x_min, x_max = selected_data['x_range']
            y_min, y_max = selected_data['y_range']
            is_precision_plot = selected_data.get('plot_type', 'precision') == 'precision'
            
            for file_name, df in filtered_data.items():
                for _, row in df.iterrows():
                    # Check if point is within the selected range
                    if (x_min <= row['coverage'] <= x_max and 
                        ((is_precision_plot and y_min <= row['Precision'] <= y_max) or
                         (not is_precision_plot and y_min <= row['Recall'] <= y_max))):
                        matching_points.append({
                            'file': file_name,
                            'coverage': row['coverage'],
                            'precision': row['Precision'],
                            'recall': row['Recall'],
                            't1_original': row['t1_original'],
                            't3_original': row['t3_original']
                        })
        else:
            # Point selection - use existing logic
            return self.find_matching_points(selected_data, weight)
        
        return matching_points


# Create Dash app
def create_app():
    visualizer = GridSearchVisualizer()
    
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    
    app.layout = dbc.Container([
        html.H1("Grid Search Results Visualizer", className="my-4"),
        
        dbc.Row([
            dbc.Col([
                html.Label("Select Weight:"),
                dcc.Dropdown(
                    id='weight-dropdown',
                    options=[{'label': w, 'value': w} for w in visualizer.weights],
                    value=visualizer.weights[0] if visualizer.weights else None,
                    clearable=False
                )
            ], width=6)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(
                    id='scatterplots',
                    figure=visualizer.create_scatterplots(
                        visualizer.weights[0] if visualizer.weights else None
                    )
                )
            ])
        ]),
        
        dcc.Store(id='selected-point-store'),
        dcc.Store(id='matching-points-store')
        
    ], fluid=True)
    
    @app.callback(
        Output('scatterplots', 'figure'),
        Input('weight-dropdown', 'value')
    )
    def update_plots(weight):
        return visualizer.create_scatterplots(weight)
    
    @app.callback(
        Output('selected-point-store', 'data'),
        Input('scatterplots', 'clickData'),
        Input('scatterplots', 'selectedData')
    )
    def store_selected_point(clickData, selectedData):
        if selectedData is not None and selectedData.get('points'):
            # Handle range/box selection
            points = selectedData['points']
            if len(points) > 1:
                # Extract range from selected points
                x_values = [p['x'] for p in points]
                y_values = [p['y'] for p in points]
                
                # Determine if this is precision or recall plot based on first point
                first_point = points[0]
                plot_type = 'precision' if first_point['curveNumber'] % 2 == 0 else 'recall'
                
                return {
                    'x_range': [min(x_values), max(x_values)],
                    'y_range': [min(y_values), max(y_values)],
                    'plot_type': plot_type,
                    'selection_type': 'range'
                }
        
        if clickData is not None:
            # Handle point click
            point = clickData['points'][0]
            customdata = point.get('customdata', '')
            if customdata:
                t1_orig, t3_orig = map(float, customdata.split('_'))
                return {
                    't1_original': t1_orig,
                    't3_original': t3_orig,
                    'coverage': point['x'],
                    'precision': point.get('y', 0) if point['curveNumber'] % 2 == 0 else None,
                    'recall': point.get('y', 0) if point['curveNumber'] % 2 == 1 else None,
                    'selection_type': 'point'
                }
        
        return None
    
    @app.callback(
        Output('scatterplots', 'figure', allow_duplicate=True),
        Input('selected-point-store', 'data'),
        State('weight-dropdown', 'value'),
        prevent_initial_call=True
    )
    def highlight_matching_points(selected_point, weight):
        if selected_point is None or weight is None:
            return visualizer.create_scatterplots(weight)
        
        fig = visualizer.create_scatterplots(weight)
        filtered_data = visualizer.get_filtered_data(weight)
        
        # Find matching points based on selection type
        if selected_point.get('selection_type') == 'range':
            matching_points = visualizer.find_points_in_range(selected_point, weight)
        else:
            matching_points = visualizer.find_matching_points(selected_point, weight)
        
        # Group matching points by file
        matching_by_file = {}
        for point in matching_points:
            file_name = point['file']
            if file_name not in matching_by_file:
                matching_by_file[file_name] = []
            matching_by_file[file_name].append(point)
        
        # Get the hyperparameter configurations from the matching points
        hyperparameter_configs = []
        for points in matching_by_file.values():
            for point in points:
                config = (point['t1_original'], point['t3_original'])
                if config not in hyperparameter_configs:
                    hyperparameter_configs.append(config)
        
        if hyperparameter_configs:
            # First, update subplot titles with metrics info
            file_names = list(sorted(filtered_data.keys()))
            for i, file_name in enumerate(file_names):
                row = i + 1
                
                # Find matching points in this file for title metrics
                df = filtered_data[file_name]
                matching_points_in_file = []
                for _, row_data in df.iterrows():
                    config = (row_data['t1_original'], row_data['t3_original'])
                    if config in hyperparameter_configs:
                        matching_points_in_file.append({
                            'coverage': row_data['coverage'],
                            'precision': row_data['Precision'],
                            'recall': row_data['Recall']
                        })
                
                # Update titles based on whether we have matching points
                if matching_points_in_file:
                    avg_precision = sum(p['precision'] for p in matching_points_in_file) / len(matching_points_in_file)
                    avg_recall = sum(p['recall'] for p in matching_points_in_file) / len(matching_points_in_file)
                    avg_coverage = sum(p['coverage'] for p in matching_points_in_file) / len(matching_points_in_file)
                    
                    # Use the first configuration for title display
                    t1, t3 = hyperparameter_configs[0]
                    if len(hyperparameter_configs) > 1:
                        config_suffix = f" (+{len(hyperparameter_configs)-1} more)"
                    else:
                        config_suffix = ""
                    
                    title_text = f'{file_name} - Precision<br>t1_original={t1:.4f}, t3_original={t3:.4f}{config_suffix}, P={avg_precision:.3f}, R={avg_recall:.3f}, C={avg_coverage:.3f}'
                    fig.layout.annotations[row*2-2].text = title_text
                    title_text = f'{file_name} - Recall<br>t1_original={t1:.4f}, t3_original={t3:.4f}{config_suffix}, P={avg_precision:.3f}, R={avg_recall:.3f}, C={avg_coverage:.3f}'
                    fig.layout.annotations[row*2-1].text = title_text
                else:
                    # No matching points in this file - find nearest points for title
                    if selected_point and selected_point.get('selection_type') == 'point':
                        nearest_points = visualizer.find_nearest_points(selected_point, weight, file_name)
                        if nearest_points:
                            # Get unique t1 and t3 values from nearest points
                            t1_values = sorted(list(set(p['t1_original'] for p in nearest_points)))
                            t3_values = sorted(list(set(p['t3_original'] for p in nearest_points)))
                            
                            # Format as "value1/value2" for each parameter
                            t1_str = "/".join(f"{t1:.4f}" for t1 in t1_values)
                            t3_str = "/".join(f"{t3:.4f}" for t3 in t3_values)
                            
                            title_text = f'{file_name} - Precision<br>t1_original={t1_str}, t3_original={t3_str} | Nearest points'
                            fig.layout.annotations[row*2-2].text = title_text
                            title_text = f'{file_name} - Recall<br>t1_original={t1_str}, t3_original={t3_str} | Nearest points'
                            fig.layout.annotations[row*2-1].text = title_text
                        else:
                            # No nearest points found
                            title_text = f'{file_name} - Precision<br>No grid points available'
                            fig.layout.annotations[row*2-2].text = title_text
                            title_text = f'{file_name} - Recall<br>No grid points available'
                            fig.layout.annotations[row*2-1].text = title_text
                    else:
                        # Range selection or no selection
                        config_strs = [f"t1_original={t1:.4f}, t3_original={t3:.4f}" for t1, t3 in hyperparameter_configs]
                        config_info = "; ".join(config_strs[:3])
                        if len(hyperparameter_configs) > 3:
                            config_info += f" (+{len(hyperparameter_configs)-3} more)"
                        title_text = f'{file_name} - Precision<br>{config_info} | No matching points'
                        fig.layout.annotations[row*2-2].text = title_text
                        title_text = f'{file_name} - Recall<br>{config_info} | No matching points'
                        fig.layout.annotations[row*2-1].text = title_text
            
            # Then, add red cross markers for matching points
            for i, file_name in enumerate(file_names):
                row = i + 1  # subplot rows are 1-indexed
                df = filtered_data[file_name]
                
                # Find points in this file with matching hyperparameter configurations
                matching_points_in_file = []
                for _, row_data in df.iterrows():
                    config = (row_data['t1_original'], row_data['t3_original'])
                    if config in hyperparameter_configs:
                        matching_points_in_file.append({
                            'coverage': row_data['coverage'],
                            'precision': row_data['Precision'],
                            'recall': row_data['Recall'],
                            't1_original': row_data['t1_original'],
                            't3_original': row_data['t3_original']
                        })
                
                if matching_points_in_file:
                    # Extract coordinates for this file's matching points
                    precision_x = [p['coverage'] for p in matching_points_in_file]
                    precision_y = [p['precision'] for p in matching_points_in_file]
                    recall_x = [p['coverage'] for p in matching_points_in_file]
                    recall_y = [p['recall'] for p in matching_points_in_file]
                    
                    # Create hover text with metrics
                    precision_hover = [f"t1={p['t1_original']:.4f}<br>t3={p['t3_original']:.4f}<br>Precision={p['precision']:.4f}<br>Coverage={p['coverage']:.4f}" for p in matching_points_in_file]
                    recall_hover = [f"t1={p['t1_original']:.4f}<br>t3={p['t3_original']:.4f}<br>Recall={p['recall']:.4f}<br>Coverage={p['coverage']:.4f}" for p in matching_points_in_file]
                    
                    # Add red crosses for exact matches to precision plot
                    fig.add_trace(
                        go.Scatter(
                            x=precision_x,
                            y=precision_y,
                            mode='markers',
                            marker=dict(color='red', symbol='x', size=12, line=dict(width=2)),
                            name='Exact Match' if i == 0 else None,
                            showlegend=(i == 0),
                            hovertext=precision_hover,
                            hovertemplate='%{hovertext}<extra></extra>'
                        ),
                        row=row, col=1
                    )
                    
                    # Add red crosses for exact matches to recall plot
                    fig.add_trace(
                        go.Scatter(
                            x=recall_x,
                            y=recall_y,
                            mode='markers',
                            marker=dict(color='red', symbol='x', size=12, line=dict(width=2)),
                            name='Exact Match' if i == 0 else None,
                            showlegend=False,
                            hovertext=recall_hover,
                            hovertemplate='%{hovertext}<extra></extra>'
                        ),
                        row=row, col=2
                    )
                else:
                    # No exact matches, find and show nearest 4 points with red circles
                    if selected_point and selected_point.get('selection_type') == 'point':
                        nearest_points = visualizer.find_nearest_points(selected_point, weight, file_name)
                        
                        if nearest_points:
                            # Extract coordinates for nearest points
                            precision_x = [p['coverage'] for p in nearest_points]
                            precision_y = [p['precision'] for p in nearest_points]
                            recall_x = [p['coverage'] for p in nearest_points]
                            recall_y = [p['recall'] for p in nearest_points]
                            
                            # Create hover text with distance and direction info
                            precision_hover = [f"t1={p['t1_original']:.4f} ({p['t1_direction']})<br>t3={p['t3_original']:.4f} ({p['t3_direction']})<br>Precision={p['precision']:.4f}<br>Coverage={p['coverage']:.4f}<br>Distance: {p['distance']:.6f}" for p in nearest_points]
                            recall_hover = [f"t1={p['t1_original']:.4f} ({p['t1_direction']})<br>t3={p['t3_original']:.4f} ({p['t3_direction']})<br>Recall={p['recall']:.4f}<br>Coverage={p['coverage']:.4f}<br>Distance: {p['distance']:.6f}" for p in nearest_points]
                            
                            # Add red circles for nearest points to precision plot
                            fig.add_trace(
                                go.Scatter(
                                    x=precision_x,
                                    y=precision_y,
                                    mode='markers',
                                    marker=dict(color='red', symbol='circle', size=10, line=dict(width=2, color='darkred')),
                                    name='Nearest' if i == 0 else None,
                                    showlegend=(i == 0),
                                    hovertext=precision_hover,
                                    hovertemplate='%{hovertext}<extra></extra>'
                                ),
                                row=row, col=1
                            )
                            
                            # Add red circles for nearest points to recall plot
                            fig.add_trace(
                                go.Scatter(
                                    x=recall_x,
                                    y=recall_y,
                                    mode='markers',
                                    marker=dict(color='red', symbol='circle', size=10, line=dict(width=2, color='darkred')),
                                    name='Nearest' if i == 0 else None,
                                    showlegend=False,
                                    hovertext=recall_hover,
                                    hovertemplate='%{hovertext}<extra></extra>'
                                ),
                                row=row, col=2
                            )
        
        return fig
    
    return app


if __name__ == '__main__':
    if not PACKAGES_AVAILABLE:
        print("Required packages are not available. Please install them first.")
        exit(1)
    
    app = create_app()
    print("Starting Grid Search Visualizer...")
    print("Open http://127.0.0.1:8050 in your browser")
    app.run(debug=True, port=8050)
