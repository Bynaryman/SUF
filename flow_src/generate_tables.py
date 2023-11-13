#!/usr/bin/env python

# Author: Ledoux Louis

import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
import math
from mpl_toolkits.axes_grid1 import make_axes_locatable # for the size of colormap
#from matplotlib.ticker import MaxNLocator
from matplotlib.ticker import FuncFormatter
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec
from pdk_configs import PDKS
from division_configs import division_configs
import pprint
import os
import csv
import argparse
import json
from collections import defaultdict # to call append on None value of a key

PATH_UNITS   =  "/home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/logs/{}/{}/base/2_1_floorplan.json"
PATH_RESULTS =  "/home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/logs/{}/{}/base/6_report.json"


# Figure width base on the column width of the Latex document.
fig_width = 252
fig_text_width = 516
fig_text_width_thesis = 473.46

def set_size(width, fraction=1, subplots=(1, 1)):
    """

    :param width:
    :param fraction:
    :return:
    """
    # Width of figure (in pts)
    fig_width_pt = width * fraction

    # Convert from pt to inches.
    inches_per_pt = 1 / 72.27

    # Golden ration to set aesthetic figure height.
    # https://disq.us/p/2940ij3
    golden_ratio = (5 ** (1 / 2) - 1) / 2

    # Figure width in inches
    fig_width_in = fig_width_pt * inches_per_pt
    # Figure height in inches
    #fig_height_in = fig_width_in * golden_ratio * (subplots[0] / subplots[1])

    #if width == fig_text_width:
    #    fig_height_in /= 0.5

    fig_height_in = fig_width_in*1.4
    #fig_height_in /= 1.3

    fig_dim = (fig_width_in, fig_height_in)

    return fig_dim


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

def compute_latency(design_name):
    """Compute the latency for the given design name."""
    config = division_configs.get(design_name, {})

    mantissa_size = int(config.get("mantissa_size", 0))
    adder_size = get_adder_size_from_name(design_name)  # using the previously defined function
    if adder_size is None:
        adder_size = mantissa_size + 4

    # Check for valid values and compute latency, or else return None
    if mantissa_size and adder_size:
        return (mantissa_size + 4) * math.ceil(((mantissa_size + 4) / adder_size))
    else:
        return -1

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
                "count_cell": metrics_data["finish__design__instance__count__stdcell"],
                "latency": compute_latency(arithmetic)
            }

    return data


def data_to_terminal(data, metric, unit):
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

def escape_latex(text):
    """
    Escape unsafe LaTeX characters: # $ % & _ { } ~ ^
    """
    mapping = {
        "#": r"\#",
        "$": r"\$",
        "%": r"\%",
        "&": r"\&",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\^{}",
        "\\": r"\textbackslash{}",
    }
    return "".join(mapping.get(char, char) for char in text)

def data_to_latex(data, metric, unit):
    # Get any key from the dictionary to determine the headers
    first_key = next(iter(data))

    num_columns = len(data[first_key]) + 1

    # Begin the table using the longtable environment combined with tabularx
    latex_str = "\\begin{tabularx}{\\linewidth}{" + "|c" + "|X"*len(data[first_key]) + "|}\n"

    # Caption on top
    latex_str += "\\caption{" + escape_latex(metric.capitalize() + " (" + unit + ") Data") + "}\\\\\n"

    # Header
    latex_str += "\\hline\n"
    latex_str += "Arithmetic & " + " & ".join(escape_latex(node) for node in data[first_key].keys()) + "\\\\ \\hline\n"
    latex_str += "\\endfirsthead\n" # This ends the setup for the first header

    # Set up the headers for subsequent pages, if the table breaks
    latex_str += "\\multicolumn{" + str(num_columns) + "}{c}{{\\tablename\\ \\thetable{} -- continued from previous page}}\\\\\n"
    latex_str += "\\hline\n"
    latex_str += "Arithmetic & " + " & ".join(escape_latex(node) for node in data[first_key].keys()) + "\\\\ \\hline\n"
    latex_str += "\\endhead\n"

    # Rows for each arithmetic type
    for arithmetic, nodes in data.items():
        row = [escape_latex(arithmetic)]
        for process_node in nodes.keys():
            val = escape_latex(str(nodes[process_node][metric]))
            row.append(val)
        latex_str += " & ".join(row) + "\\\\ \\hline\n"

    # End the table
    latex_str += "\\end{tabularx}\n"

    return latex_str

def data_to_csv(data, metric, unit):
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

#def data_to_plot(data, metric, unit):
#    tech_nodes = list(data[list(data.keys())[0]].keys())
#    designs = list(data.keys())
#
#    bar_width = 0.15
#    n_plots = len(tech_nodes)
#
#    # Setting up the grid for subplots
#    fig, axes = plt.subplots(n_plots, 1, figsize=(15, 5*n_plots))
#
#    for index, tech_node in enumerate(tech_nodes):
#        ax = axes[index] if n_plots > 1 else axes
#        values = [float(data[design][tech_node][metric]) if data[design][tech_node][metric] != 'N/A' else 0 for design in designs]
#        ax.bar(designs, values, width=bar_width, color='blue', alpha=0.7)
#
#        ax.set_ylabel(metric.capitalize())
#        ax.set_title(f'{metric.capitalize()} for {tech_node}')
#        ax.set_xticks(range(len(designs)))
#        ax.set_xticklabels(designs, rotation=45)
#
#    plt.tight_layout()
#    plt.savefig(f"{metric}_per_technode_comparison.pdf", format="pdf", bbox_inches="tight")
#    plt.close()

def data_to_plot(data_dict, metric, unit):
    tech_nodes = list(next(iter(data_dict.values())).keys())  # Extract technology nodes
    num_subplots = len(tech_nodes)

    # Get all unique adder sizes from the data dictionary
    all_sizes = sorted(set(get_adder_size_from_name(design) for design in data_dict if get_adder_size_from_name(design) is not None))
    cmap = plt.get_cmap('viridis')  # Color map for visual consistency
    norm = plt.Normalize(min(all_sizes), max(all_sizes))  # Normalization for color mapping

    fig_dim = set_size(fig_text_width, 1, (5, 1))
    fig, axes = plt.subplots(num_subplots, 1, figsize=fig_dim, dpi=500)
    if num_subplots == 1:
        axes = [axes]  # Ensure axes is iterable for a single subplot case

    for index, (ax, tech_node) in enumerate(zip(axes, tech_nodes)):
        values = [safe_float(data_dict[design][tech_node].get(metric, None)) for design in data_dict]
        adder_sizes = [get_adder_size_from_name(design) for design in data_dict]

        scatter = ax.scatter(adder_sizes, values, c=adder_sizes, cmap=cmap, norm=norm, edgecolor='none')
        ax.set_xscale('log')  # Set logarithmic scale for x-axis

        ax.set_ylabel(f"{tech_node}")
        #ax.set_title(f"{metric.capitalize()} across {tech_node.capitalize()} nodes", fontsize=16)

        if index < num_subplots - 1:
            ax.set_xticklabels([])  # Hide x labels for all but the bottom plot

    # Add a colorbar to relate colors to adder sizes
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])  # Only needed for the colorbar
    fig.colorbar(sm, ax=axes, orientation='vertical', fraction=0.025, pad=0.05, label="Adder Size")

    fig.supxlabel('Adder Size (Bits)')
    #fig.supylabel(f"{metric.capitalize()} ({unit})")

    plt.tight_layout()
    plt.savefig(f"{metric}_across_technodes_comparison.pdf", bbox_inches='tight')
    plt.close(fig)

def format_latex(unit):
    if "^" in unit:
        return f"${unit}$"
    return unit

def data_to_per_plot(data_dict, metric1, metric2, unit1, unit2):
    tech_nodes = list(next(iter(data_dict.values())).keys())
    num_subplots = len(tech_nodes)

    # Define the colormap and normalization for adder sizes
    cmap = plt.get_cmap('viridis')
    all_adder_sizes = sorted(set(get_adder_size_from_name(design) for design in data_dict if get_adder_size_from_name(design) is not None))
    norm = plt.Normalize(min(all_adder_sizes), max(all_adder_sizes))

    fig_dim = set_size(fig_text_width, 1, (5, 1))
    fig, axes = plt.subplots(num_subplots, 1, figsize=fig_dim, dpi=500)
    if num_subplots == 1:
        axes = [axes]

    for index_ax, (ax, tech_node) in enumerate(zip(axes, tech_nodes)):
        for design, tech_data in data_dict.items():
            x_value = safe_float(tech_data[tech_node].get(metric1, None))
            y_value = safe_float(tech_data[tech_node].get(metric2, None))
            if x_value is not None and y_value is not None and y_value != 0:
                value = x_value / y_value
                category = get_category(design)
                marker_shape = category_to_marker.get(category, 'x')
                adder_size = get_adder_size_from_name(design)

                # Use color based on adder size
                if adder_size is None:
                    color = "black"
                else:
                    color = cmap(norm(adder_size))

                ax.scatter(adder_size, value, label=f"{category} {adder_size} bit",
                           marker=marker_shape, color=color, edgecolor='none')



    #for index, (ax, tech_node) in enumerate(zip(axes, tech_nodes)):
    #    #values = [safe_float(data_dict[design][tech_node].get(metric, None)) for design in data_dict]
    #    values = [
    #        safe_float(data_dict[design][tech_node].get(metric1, None)) /
    #        safe_float(data_dict[design][tech_node].get(metric2, 1))
    #        if data_dict[design][tech_node].get(metric1) not in [None, 'N/A'] and
    #           data_dict[design][tech_node].get(metric2) not in [None, 'N/A', 0]
    #        else None
    #        for design in data_dict
    #    ]
    #    adder_sizes = [get_adder_size_from_name(design) for design in data_dict]

    #    scatter = ax.scatter(adder_sizes, values, c=adder_sizes, cmap=cmap, norm=norm, edgecolor='none')
    #    #ax.set_xscale('log')  # Set logarithmic scale for x-axis

    #    ax.set_ylabel(f"{tech_node}")
    #    #ax.set_title(f"{metric.capitalize()} across {tech_node.capitalize()} nodes", fontsize=16)

    #    if index < num_subplots - 1:
    #        ax.set_xticklabels([])  # Hide x labels for all but the bottom plot

    # Add a colorbar to relate colors to adder sizes
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])  # Only needed for the colorbar
    fig.colorbar(sm, ax=axes, orientation='vertical', fraction=0.025, pad=0.05, label="Adder Size")

    fig.supxlabel('Adder Size (Bits)')
    fig.supylabel(rf"$\frac{{{metric1}}}{{{metric2}}} \, \left(\frac{{{unit1}}}{{{unit2}}}\right)$")

    plt.tight_layout()
    plt.savefig(f"{metric1}_per_{metric2}_across_technodes_comparison.pdf", bbox_inches='tight')
    plt.close(fig)

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
    'IEEE754': 's',  # Square
    'Nvidia': 'D',  # Circle
    'BrainFloat': 'p',  # Circle
    # Add other categories and their corresponding markers here.
}

def get_marker(design):
    """Fetch the marker shape based on the design's arithmetic category."""
    config = division_configs.get(design, {})
    category = config.get('category', '')
    return category_to_marker.get(category, '')  # Default to 'x' if category is not recognized.


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

def refine_axis(ax, data, axis="y", log_scale=False):
    """
    Refines either x-axis or y-axis of a given ax object.

    Parameters:
        ax: The axes object to be refined.
        data: The data that will be plotted on the specified axis (either x or y).
        axis: A string, either "x" or "y", specifying which axis to refine.
        log_scale: A boolean, if True, sets the specified axis to log scale.

    Returns:
        ax: Refined axes object.
    """

    set_limit = ax.set_xlim if axis == "x" else ax.set_ylim
    major_locator = ax.xaxis.set_major_locator if axis == "x" else ax.yaxis.set_major_locator
    minor_locator = ax.xaxis.set_minor_locator if axis == "x" else ax.yaxis.set_minor_locator
    major_formatter = ax.xaxis.set_major_formatter if axis == "x" else ax.yaxis.set_major_formatter

    def custom_formatter(x, _):
        return r'$10^{%d}$' % int(np.log10(x))

    # Set data limit
    filtered_data = [d for d in data if d is not None]
    set_limit(min(filtered_data), max(filtered_data))

    # If log scale is needed
    if log_scale:
        ax.set_xscale("log") if axis == "x" else ax.set_yscale("log")


        # if we need to go less further
        def next_log_value(x, base=10):
            current_power = int(math.floor(math.log(x, base)))
            next_step = int(x / (base ** current_power))
            return (next_step + 3) * (base ** current_power)

        # Custom logic for determining the axis limits and ticks on a log scale
        closest_power = lambda x, base: int(math.floor(math.log(x, base)))
        next_power = lambda x, base: int(math.ceil(math.log(x, base)))

        min_data = min(filtered_data)
        max_data = max(filtered_data)
        upper_bound = next_log_value(max_data)

        min_power = 10**closest_power(min_data, 10)
        max_power = 10**next_power(max_data, 10)

        set_limit(min_power, max_power)
        #set_limit(min_power, upper_bound)
        major_ticks = np.logspace(closest_power(min_data, 10), next_power(max_data, 10), base=10, num=next_power(max_data, 10) - closest_power(min_data, 10) + 1)
        #major_ticks = np.logspace(closest_power(min_data, 10), math.log(upper_bound, 10), base=10, num=int(math.log(upper_bound, 10) - closest_power(min_data, 10) + 1))

        if axis == 'y':
            ax.set_yticks(major_ticks)
        else:
            ax.set_xticks(major_ticks)
        major_locator(ticker.FixedLocator(major_ticks))
        minor_locator(ticker.LogLocator(base=10.0, subs=np.linspace(0.1, 0.9, 9)))
    else:
        # Automated setting of major ticks
        major_locator(ticker.AutoLocator())
        minor_locator(ticker.AutoMinorLocator())

    # Format major tick labels
    #major_formatter(ticker.ScalarFormatter())
    #formatter = ticker.ScalarFormatter(useOffset=False, useMathText=True)
    major_formatter(FuncFormatter(custom_formatter))
    #major_formatter(formatter)

    return ax

def key_to_marker(key):
    marker_dict = {
        "IEEE75464": "h",   # Circle
        "IEEE75432": "o",   # Circle
        "IEEE75416": "s",   # Square
        "Posit32": "^",     # Triangle up
        "Posit16": "v",     # Triangle down
        "Posit8": "<",      # Triangle left
        "BrainFloat16": ">", # Triangle right
    }
    return marker_dict.get(key, "x")  # Default to 'x' if key not found



def data_to_versus_plot(data_dict, metric1, metric2, unit1, unit2):
    tech_nodes = list(next(iter(data_dict.values())).keys())  # extract tech nodes
    num_subplots = len(tech_nodes)


    # Get all adder sizes
    all_sizes = [get_adder_size_from_name(design) for design in data_dict.keys()]
    all_sizes = [s for s in all_sizes if s is not None]
    cmap1 = plt.get_cmap('viridis')
    norm1 = plt.Normalize(min(all_sizes), max(all_sizes))

    # Get all computer format widths
    #all_bitwidths = {int(division_configs[config]["bitwidth"]) for config in data_dict.keys()}
    all_bitwidths = {int(division_configs[config]["bitwidth"]) for config in data_dict.keys()}
    #all_bitwidths = {print(config) for config in data_dict.values()}

    #line_cmap = plt.get_cmap('viridis')
    #all_adder_sizes = [size for sublist in adder_sizes.values() for size in sublist]
    #line_norm = mcolors.Normalize(vmin=min(all_adder_sizes), vmax=max(all_adder_sizes))


    fig_dim = set_size(fig_text_width,1,(5,1))
    #fig = plt.figure(constrained_layout=True, figsize=fig_dim, dpi=500)
    fig = plt.figure(constrained_layout=False, figsize=fig_dim, dpi=500)
    gs = GridSpec(num_subplots, 1,figure=fig)

    # Create an initial axis object
    ax_main = fig.add_subplot(gs[0, 0])

    # Create the rest of the axes and share Y with the main axis
    #axes = [ax_main] + [fig.add_subplot(gs[i, 0], sharex=ax_main) for i in range(1, num_subplots)]
    axes = [ax_main] + [fig.add_subplot(gs[i, 0]) for i in range(1, num_subplots)]

    #axes = [fig.add_subplot(gs[i]) for i in range(num_subplots)]

    legend_handles = {}
    family_data = {}

    for index_ax, (ax, tech_node) in enumerate(zip(axes, tech_nodes)):
        x_values = defaultdict(list)
        y_values = defaultdict(list)
        adder_sizes = defaultdict(list)
        for design, tech_data in data_dict.items():
            x_value = safe_float(tech_data[tech_node].get(metric1, None))
            y_value = safe_float(tech_data[tech_node].get(metric2, None))

            category = get_category(design)
            marker_shape = category_to_marker.get(category, 'x')  # Default to 'x' if category is not recognized
            adder_size = get_adder_size_from_name(design)
            computer_format_width = int(division_configs[design]["bitwidth"])

            #color = cmap(norm(adder_size)) if adder_size else 'black'  # default to black if size not found
            print(category,adder_size,computer_format_width)


            #primary_color = cmap1(norm1(adder_size)) if adder_size else 'black'  # colormap 1
            if x_value is not None and y_value is not None:
                key = f"{category}{computer_format_width}"
                x_values[key].append(x_value)
                y_values[key].append(y_value)
                adder_sizes[key].append(adder_size)

            #if x_value is not None and y_value is not None:
            #    scatter = ax.scatter(x_value, y_value, label=category, marker=marker_shape, color=primary_color)
            #    # Keep a reference to each unique category's scatter plot for the legend
            #    legend_handles[category] = scatter


        print(x_values)
        def custom_sort(lst):
            return [lst[0]] + lst[:0:-1]

        for key in x_values:
            x_values[key] = custom_sort(x_values[key])
            y_values[key] = custom_sort(y_values[key])
            adder_sizes[key] = custom_sort(adder_sizes[key])

        for key, (m1, m2, adder_size) in zip(x_values.keys(), zip(x_values.values(), y_values.values(), adder_sizes.values())):
            marker_style = key_to_marker(key)
            for i in range(1, len(m1)):
                line_color = cmap1(norm1(adder_size[i]))
                if i == 1:
                    # Plot the line segment between the first and second point
                    ax.plot(m1[i-1:i+1], m2[i-1:i+1], color=line_color, linestyle='-')
                    # Plot the first marker as a black cross
                    scatter1 = ax.scatter(m1[i-1], m2[i-1], color="black", marker='x', label=key if i == 1 else "")
                    # Plot the second marker with its respective color
                    scatter2= ax.scatter(m1[i], m2[i], color=line_color, marker=marker_style)
                    if key not in legend_handles:
                        legend_handles[key] = scatter2
                else:
                    ax.plot(m1[i-1:i+1], m2[i-1:i+1], color=line_color, linestyle='-', marker=marker_style, markerfacecolor=line_color, markeredgecolor=line_color, label=key if i == 1 else "")


        #ax.set_xlabel(f"{metric1.capitalize()} (Unit)")
        ax.set_ylabel(f"{tech_node}")
        #ax.set_title(f"{metric1.capitalize()} vs {metric2.capitalize()} for {tech_node.capitalize()}", fontsize=16)
        #ax.set_yscale("log")
        ax.set_xscale("log")
        #ax.set_yticklabels([]) # as it is shared we remove labelticks
        if index_ax != len(axes)-1:
            ax.set_xticklabels([]) # as it is shared we remove labelticks
        flattened_values = [item for sublist in y_values.values() for item in sublist]
        #refine_axis(ax,flattened_values,axis="y", log_scale=False)

    # Add a global legend outside of the subplots
    handles = list(legend_handles.values())
    labels = list(legend_handles.keys())

    unit1_latex = format_latex(unit1)
    unit2_latex = format_latex(unit2)

    fig.supxlabel(f"{metric1.capitalize()} ({unit1_latex})")
    fig.supylabel(f"{metric2.capitalize()} ({unit2_latex})")

    # Adjust the legend to be horizontal on top
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=len(labels), fontsize='small', title="Arithmetic Category", fancybox=False, framealpha=1.0, edgecolor="white")

    # Assuming axes[0] is the top subplot
    top_subplot = axes[0]

    # Assuming axes[0] is the top subplot
    #bot_subplot = axes[-1]
    #bot_subplots

    # Use the make_axes_locatable to generate a new axis for the colorbar
    divider = make_axes_locatable(top_subplot)
    cax = divider.append_axes("top", size="5%", pad=0.2)

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap1, norm=norm1)
    sm.set_array([])
    cbar = fig.colorbar(sm, cax=cax, orientation='horizontal', label="Serial Adder size")
    cax.xaxis.set_ticks_position('top')
    cax.xaxis.set_label_position('top')

    plt.tight_layout()
    plt.savefig(f"{metric1}_vs_{metric2}_comparison.pdf", bbox_inches='tight')
    #plt.savefig(f"{metric1}_vs_{metric2}_comparison.pdf")
    plt.close(fig)

def parse_args():
    parser = argparse.ArgumentParser(description="Generate tables and plots from SUF reports.")
    parser.add_argument('--type', choices=['csv', 'latex', 'terminal', 'plot', 'all'], required=True,
                        help='The type of table output or plot.')
    parser.add_argument('--metric', type=str, required=True,
                        help='The metric to display or compare. For "versus" plots, use the format "metric1VSmetric2". For "ratio" plots, use the format "metric1PERmetric2".')
    return parser.parse_args()

def main():

    args = parse_args()


    metric_units = {
        'power': 'W',
        'area': 'm^{2}',
        'count_cell': 'cells',
        'latency': 'Clock Cycles'
        # Add other metrics and their units if needed.
    }

    # Configurations for publication quality
    tex_fonts = {
        'text.usetex': True,
        'font.family': 'serif',
        'font.serif': ['Times New Roman'] + plt.rcParams['font.serif'],
        'axes.labelsize': 8,
        'font.size': 10,
        'legend.fontsize': 6.0,
        'legend.handlelength': 2.25,
        'legend.columnspacing': 0.5,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'lines.markeredgewidth': 0.3,
        'lines.markersize': 4,
        'lines.linewidth': 1,
        'hatch.linewidth': 0.2,
         #grid
        'grid.color': '#A5A5A5',     # Light gray grid
        'grid.linestyle': '--',      # Dashed grid lines
        'grid.linewidth': 0.3,       # Grid line width
        'axes.grid': True,           # Display grid by default
        'axes.grid.which': 'both'    # Apply to both major and minor grid lines
    }

    plt.style.use('grayscale')
    plt.rcParams.update(tex_fonts)

    if 'VS' in args.metric:
        metric1, metric2 = args.metric.split('VS')
        unit1, unit2 = metric_units.get(metric1, ''), metric_units.get(metric2, '')
        if args.type == 'plot':
            data_dict = populate_data_dict()
            data_to_versus_plot(data_dict, metric1, metric2, unit1, unit2)
            print(f"'{metric1} vs {metric2}' plot saved as {metric1}_vs_{metric2}_comparison.pdf\n")
        else:
            print(f"The metric '{args.metric}' is only valid for the 'plot' type.")
            exit(1)
    elif "PER" in args.metric:
        metric1, metric2 = args.metric.split('PER')
        unit1, unit2 = metric_units.get(metric1, ''), metric_units.get(metric2, '')
        if args.type == 'plot':
            data_dict = populate_data_dict()
            data_to_per_plot(data_dict, metric1, metric2, unit1, unit2)
            print(f"'{metric1} per {metric2}' plot saved as {metric1}_per_{metric2}_comparison.pdf\n")
        else:
            print(f"The metric '{args.metric}' is only valid for the 'plot' type.")
            exit(1)
    else:
        metrics = ['power', 'area', 'count_cell', 'latency'] if args.metric == 'all' else [args.metric]
        table_types = ['csv', 'latex', 'terminal', 'plot'] if args.type == 'all' else [args.type]

        data_dict = populate_data_dict()
        for metric in metrics:
            for table_type in table_types:
                unit = metric_units.get(metric, '')
                if table_type == 'terminal':
                    print(f"Table for {metric} ({unit}) in Terminal Format:\n")
                    print(data_to_terminal(data_dict, metric, unit))
                elif table_type == 'csv':
                    csv_str = data_to_csv(data_dict, metric, unit)
                    with open(f"{metric}_data.csv", 'w') as f:
                        f.write(csv_str)
                    print(f"CSV file for {metric} saved as {metric}_data.csv\n")
                elif table_type == 'latex':
                    latex_str = data_to_latex(data_dict, metric, unit)
                    with open(f"{metric}_data.tex", 'w') as f:
                        f.write(latex_str)
                    print(f"LaTeX file for {metric} saved as {metric}_data.tex\n")
                elif table_type == 'plot':
                    data_to_plot(data_dict, metric, unit)



if __name__ == '__main__':
    main()
