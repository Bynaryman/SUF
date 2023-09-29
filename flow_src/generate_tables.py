#!/usr/bin/env python

# Author: Ledoux Louis

#from pdk_configs import PDKS
#from division_configs import division_configs
import os
import csv
import argparse

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



def parse_args():
    parser = argparse.ArgumentParser(description="Generate tables from SUF reports.")
    parser.add_argument('--type', choices=['csv', 'latex', 'terminal', 'all'], required=True, help='The type of table output.')
    parser.add_argument('--metric', choices=['power', 'area', 'all'], required=True, help='The metric to display.')
    return parser.parse_args()


def main():

    args = parse_args()

    metrics = ['power', 'area'] if args.metric == 'all' else [args.metric]
    table_types = ['csv', 'latex', 'terminal'] if args.type == 'all' else [args.type]

    fake_data = {
        'arith1': {
            'node1': {'power': 5.43, 'area': 345.21},
            'node2': {'power': 6.87, 'area': 210.67},
            'node3': {'power': 4.89, 'area': 430.32}
        },
        'arith2': {
            'node1': {'power': 7.45, 'area': 290.15},
            'node2': {'power': 5.21, 'area': 310.84},
            'node3': {'power': 6.78, 'area': 405.29}
        },
        'arith3': {
            'node1': {'power': 6.23, 'area': 356.78},
            'node2': {'power': 5.98, 'area': 275.54},
            'node3': {'power': 7.14, 'area': 398.12}
        }
    }

    for metric in metrics:
        for table_type in table_types:
            if table_type == 'terminal':
                print(f"Table for {metric} in Terminal Format:\n")
                print(data_to_terminal(fake_data, metric))
            elif table_type == 'csv':
                csv_str = data_to_csv(fake_data, metric)
                with open(f"{metric}_data.csv", 'w') as f:
                    f.write(csv_str)
                print(f"CSV file for {metric} saved as {metric}_data.csv\n")
            elif table_type == 'latex':
                latex_str = data_to_latex(fake_data, metric)
                with open(f"{metric}_data.tex", 'w') as f:
                    f.write(latex_str)
                print(f"LaTeX file for {metric} saved as {metric}_data.tex\n")



if __name__ == '__main__':
    main()
