#!/usr/bin/env python

# Author: Ledoux Louis

import matplotlib.pyplot as plt
import matplotlib.cm as cm
from pdk_configs import PDKS
from division_configs import division_configs
import pprint
import os
import csv
import argparse
import json

PATH_UNITS   =  "/home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/logs/{}/{}/base/2_1_floorplan.json"
PATH_RESULTS =  "/home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/logs/{}/{}/base/6_report.json"


def adjust_value_based_on_unit(value, unit, is_area=False):
    conversion_dict = {
        # Power units
        "1pW": 1e-12,
        "1nW": 1e-9,
        "1uW": 1e-6,
        "1mW": 1e-3,
        "1W": 1e0,
        # Distance units
        "1pm": 1e-12,
        "1nm": 1e-9,
        "1um": 1e-6,
        "1mm": 1e-3,
        "1m": 1e0,
        # Add more units if required
    }

    multiplier = conversion_dict.get(unit, 1)
    if is_area:
        multiplier = multiplier ** 2

    adjusted_value = value * multiplier
    return "{:.2e}".format(adjusted_value)


def extract_metrics_from_json(metrics_file_path, units_file_path, metrics):
    """Extracts specified metrics from a JSON file and gets their units.

    Args:
        metrics_file_path (str): Path to the JSON file with the metrics.
        units_file_path (str): Path to the JSON file with the units.
        metrics (list): List of metric keys to extract.

    Returns:
        dict: Dictionary with the extracted and normalized metrics.
    """

    result = {}

    if not os.path.exists(metrics_file_path):
        return {metric: "N/A" for metric in metrics}

    with open(units_file_path, 'r') as units_file:
        units_data = json.load(units_file)

    with open(metrics_file_path, 'r') as metrics_file:
        metrics_data = json.load(metrics_file)

    is_area = False
    for metric in metrics:
        value = metrics_data.get(metric, None)
        if "power" in metric:
            unit_key = "run__flow__platform__power_units"
        elif "area" in metric:
            unit_key = "run__flow__platform__distance_units"  # Assuming area is in distance units squared
            is_area = True
        else:
            unit_key = None

        if unit_key:
            unit_value = units_data.get(unit_key, None)
            if unit_value:
                value = adjust_value_based_on_unit(value, unit_value, is_area)
        result[metric] = value

    return result

def populate_data_dict():
    """Populates the data dictionary based on the JSON files."""
    data = {}

    for arithmetic in division_configs.keys():
        data[arithmetic] = {}
        for node in PDKS:
            metrics_file_path = PATH_RESULTS.format(node, arithmetic)
            units_file_path = PATH_UNITS.format(node, arithmetic)

            metrics_data = extract_metrics_from_json(metrics_file_path, units_file_path, ["finish__power__total", "finish__design__die__area", "finish__design__instance__count__stdcell"])

            data[arithmetic][node] = {
                "power": metrics_data["finish__power__total"],
                "area": metrics_data["finish__design__die__area"],
                "count_cell": metrics_data["finish__design__instance__count__stdcell"]
            }

    return data


def data_to_terminal(data, metric):
    # Get any key from the dictionary to determine the number of nodes
    first_key = next(iter(data))

    # Determine the column width based on the largest name
    max_arith_len = max(len(arith) for arith in data.keys())
    max_node_len = max(len(node) for arith in data for node in data[arith].keys())
    column_width = max(max_arith_len, max_node_len, len("Arithmetic"), 10) + 2  # +2 for padding

    terminal_str = "+" + "-"*column_width + "+" + ("-"*column_width + "+")*len(data[first_key]) + "\n"
    terminal_str += "|" + " Arithmetic".center(column_width) + "|"

    # Process node names as column headers
    for node in data[first_key].keys():
        terminal_str += f"{node.center(column_width)}" + "|"
    terminal_str += "\n+" + "-"*column_width + "+" + ("-"*column_width + "+")*len(data[first_key]) + "\n"

    # Rows for each arithmetic type
    for arithmetic, nodes in data.items():
        terminal_str += "|" + arithmetic.center(column_width) + "|"

        # Value for each process node
        for process_node in nodes.keys():
            val = str(nodes[process_node][metric])
            terminal_str += val.center(column_width) + "|"
        terminal_str += "\n"

    terminal_str += "+" + "-"*column_width + "+" + ("-"*column_width + "+")*len(data[first_key]) + "\n"

    return terminal_str

def data_to_latex(data, metric):
    # Get any key from the dictionary to determine the headers
    first_key = next(iter(data))

    # Begin the table
    latex_str = "\\begin{table}[h]\n"
    latex_str += "\\centering\n"
    latex_str += "\\begin{tabular}{" + "|c" + "|c"*len(data[first_key]) + "|}\n"
    latex_str += "\\hline\n"

    # Header
    latex_str += "Arithmetic & " + " & ".join(node for node in data[first_key].keys()) + "\\\\ \\hline\n"

    # Rows for each arithmetic type
    for arithmetic, nodes in data.items():
        row = [arithmetic]
        for process_node in nodes.keys():
            val = str(nodes[process_node][metric])
            row.append(val)
        latex_str += " & ".join(row) + "\\\\ \\hline\n"

    # End the table
    latex_str += "\\end{tabular}\n"
    latex_str += "\\caption{" + metric.capitalize() + " Data}\n"
    latex_str += "\\end{table}\n"

    return latex_str

def data_to_csv(data, metric):
    # Get any key from the dictionary to determine the headers
    first_key = next(iter(data))

    # Header
    csv_str = "Arithmetic," + ",".join(node for node in data[first_key].keys()) + "\n"

    # Rows for each arithmetic type
    for arithmetic, nodes in data.items():
        row = [arithmetic]
        for process_node in nodes.keys():
            val = str(nodes[process_node][metric])
            row.append(val)
        csv_str += ",".join(row) + "\n"

    return csv_str

def data_to_plot(data, metric):
    tech_nodes = list(data[list(data.keys())[0]].keys())
    designs = list(data.keys())

    bar_width = 0.15
    n_plots = len(tech_nodes)

    # Setting up the grid for subplots
    fig, axes = plt.subplots(n_plots, 1, figsize=(15, 5*n_plots))

    for index, tech_node in enumerate(tech_nodes):
        ax = axes[index] if n_plots > 1 else axes
        values = [float(data[design][tech_node][metric]) if data[design][tech_node][metric] != 'N/A' else 0 for design in designs]
        ax.bar(designs, values, width=bar_width, color='blue', alpha=0.7)

        ax.set_ylabel(metric.capitalize())
        ax.set_title(f'{metric.capitalize()} for {tech_node}')
        ax.set_xticks(range(len(designs)))
        ax.set_xticklabels(designs, rotation=45)

    plt.tight_layout()
    plt.savefig(f"{metric}_per_technode_comparison.svg", format="svg")
    plt.close()

def get_adder_size(design_name):
    design_info = division_configs.get(design_name)
    if not design_info:
        print(f"Warning: No configuration found for design: {design_name}")
        return None

    if 'adder_size' in design_info:
        return design_info['adder_size']
    elif design_info.get('version') == 'baseline':
        return int(design_info.get('mantissa_size', 0))
    else:
        return None

def safe_float(value):
    try:
        return float(value)
    except ValueError:
        return None

category_to_marker = {
    'Posit': 'o',  # Circle
    'IEEE754': 'd',  # Circle
    'Nvidia': 'x',  # Circle
    'BrainFloat': 'D',  # Circle
    # Add other categories and their corresponding markers here.
}

def get_marker(design):
    """Fetch the marker shape based on the design's arithmetic category."""
    config = division_configs.get(design, {})
    category = config.get('category', '')
    return category_to_marker.get(category, 'x')  # Default to 'x' if category is not recognized.


def get_category(design):
    """Fetch the arithmetic category for the given design."""
    config = division_configs.get(design, {})
    return config.get('category', 'Unknown')

def get_adder_size_from_name(design_name):
    """Extracts adder size from design name."""
    if "serial_adder" in design_name:
        return int(design_name.split('_')[-1])
    else:
        return None

def data_to_versus_plot(data_dict, metric1, metric2):
    tech_nodes = ['asap7', 'gf180', 'nangate45', 'sky130hd', 'sky130hs']
    num_subplots = len(tech_nodes)


    # Get all adder sizes
    all_sizes = [get_adder_size_from_name(design) for design in data_dict.keys()]
    all_sizes = [s for s in all_sizes if s is not None]
    cmap = plt.get_cmap('viridis')
    norm = plt.Normalize(min(all_sizes), max(all_sizes))
    fig, axes = plt.subplots(ncols=num_subplots, figsize=(10*num_subplots, 6))

    legend_handles = {}
    for ax, tech_node in zip(axes, tech_nodes):
        for design, values in data_dict.items():
            if tech_node in values:
                x_val = values[tech_node].get(metric1, None)
                y_val = values[tech_node].get(metric2, None)
                marker_shape = get_marker(design)
                x = safe_float(x_val)
                y = safe_float(y_val)
                category = get_category(design)
                marker_shape = category_to_marker.get(category, 'x')  # Default to 'x' if category is not recognized
                adder_size = get_adder_size_from_name(design)
                color = cmap(norm(adder_size)) if adder_size else 'black'  # default to black if size not found

                if x is not None and y is not None:
                    scatter = ax.scatter(x, y, label=category, marker=marker_shape, color=color)
                    # Keep a reference to each unique category's scatter plot for the legend
                    legend_handles[category] = scatter


                ax.set_title(f"{metric1} vs {metric2} for {tech_node}")
                ax.set_xlabel(metric1)
                ax.set_ylabel(metric2)
                ax.grid(True)
    # Add a global legend outside of the subplots
    handles = list(legend_handles.values())
    labels = list(legend_handles.keys())
    fig.legend(handles, labels, loc='upper left', bbox_to_anchor=(1, 0.5), fontsize='small')

    # Add a colorbar for the adder size
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    fig.colorbar(sm, cax=cbar_ax, label='Adder Size')

    plt.tight_layout()
    plt.savefig(f"{metric1}_vs_{metric2}_comparison.svg")

def parse_args():
    parser = argparse.ArgumentParser(description="Generate tables and plots from SUF reports.")
    parser.add_argument('--type', choices=['csv', 'latex', 'terminal', 'plot', 'all'], required=True,
                        help='The type of table output or plot.')
    parser.add_argument('--metric', type=str, required=True,
                        help='The metric to display or compare. For "versus" plots, use the format "metric1VSmetric2".')
    return parser.parse_args()

def main():

    args = parse_args()

    if 'VS' in args.metric:
        metric1, metric2 = args.metric.split('VS')
        if args.type == 'plot':
            data_dict = populate_data_dict()
            #pprint.pprint(data_dict)
            data_to_versus_plot(data_dict, metric1, metric2)
            print(f"'{metric1} vs {metric2}' plot saved as {metric1}_vs_{metric2}_comparison.svg\n")
        else:
            print(f"The metric '{args.metric}' is only valid for the 'plot' type.")
            exit(1)
    else:
        metrics = ['power', 'area', 'count_cell'] if args.metric == 'all' else [args.metric]
        table_types = ['csv', 'latex', 'terminal', 'plot'] if args.type == 'all' else [args.type]

        data_dict = populate_data_dict()
        for metric in metrics:
            for table_type in table_types:
                if table_type == 'terminal':
                    print(f"Table for {metric} in Terminal Format:\n")
                    print(data_to_terminal(data_dict, metric))
                elif table_type == 'csv':
                    csv_str = data_to_csv(data_dict, metric)
                    with open(f"{metric}_data.csv", 'w') as f:
                        f.write(csv_str)
                    print(f"CSV file for {metric} saved as {metric}_data.csv\n")
                elif table_type == 'latex':
                    latex_str = data_to_latex(data_dict, metric)
                    with open(f"{metric}_data.tex", 'w') as f:
                        f.write(latex_str)
                    print(f"LaTeX file for {metric} saved as {metric}_data.tex\n")
                elif table_type == 'plot':
                    data_to_plot(data_dict, metric)



if __name__ == '__main__':
    main()
