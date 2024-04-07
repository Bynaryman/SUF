#!/usr/bin/env python

import pprint

arithmetic_formats= {
    #"ieee754HP": {
    #    "bitwidth": "16",
    #    "category": "IEEE754",
    #    "mantissa_size": "10",
    #    "scale_size": "5",
    #    "flopoco_name": "ieee:5:10"
    #},
    #"bf16": {
    #    "bitwidth": "16",
    #    "category": "BrainFloat",
    #    "mantissa_size": "7",
    #    "scale_size": "8",
    #    "flopoco_name": "ieee:7:8"
    #},
    #"posit16": {
    #    "bitwidth": "16",
    #    "category": "Posit",
    #    "mantissa_size": "11",
    #    "scale_size": "7",
    #    "flopoco_name": "posit:16:2"
    #},
    "posit8": {
        "bitwidth": "8",
        "category": "Posit",
        "mantissa_size": "3",
        "scale_size": "6",
        "flopoco_name": "posit:8:2"

    },
    "posit4": {
        "bitwidth": "4",
        "category": "Posit",
        "mantissa_size": "1",
        "scale_size": "3",
        "flopoco_name": "posit:4:0"
    },
    "e4m3": {
        "bitwidth": "8",
        "category": "Nvidia",
        "mantissa_size": "3",
        "scale_size": "4",
        "flopoco_name": "ieee:4:3"
    },
    "e5m2": {
        "bitwidth": "8",
        "category": "Nvidia",
        "mantissa_size": "2",
        "scale_size": "5",
        "flopoco_name": "ieee:5:2"
    }
}

accumulator_boundaries = [
    {"name": "alpha"}, #8b accum (2,3,-2)
    {"name": "beta"}   #16b accum (5,5,-5)
]

def create_config_entry(base_config, accumulator_name):
    # Define the arithmetic format part of the entry
    arithmetic_format = {
        "bitwidth": base_config["bitwidth"],
        "category": base_config["category"],
        "mantissa_size": base_config["mantissa_size"],
        "scale_size": base_config["scale_size"],
        "flopoco_name": base_config["flopoco_name"]
    }

    # Initialize accumulator configuration with common attributes
    accumulator_config = {
        "name": accumulator_name,
        "msb": 2,  # Default values for "alpha", will be overridden for "beta"
        "lsb": -3,
        "ovf": 2
    }

    # Adjust configuration for accumulator "beta"
    if accumulator_name != "alpha":
        accumulator_config.update({"msb": 5, "lsb": -5, "ovf": 5})

    # Calculate the total width based on MSB, LSB, and OVF
    accumulator_config["total_width"] = (accumulator_config["msb"] - accumulator_config["lsb"] + 1) + accumulator_config["ovf"]

    # Combine arithmetic format and accumulator configuration into a single entry
    entry = {
        "arithmetic_format": arithmetic_format,
        "accumulator_config": accumulator_config
    }

    return entry

total_configs = {}

for base_name, base_config in arithmetic_formats.items():
    for acc in accumulator_boundaries:
        config_key = f"{base_name}_{acc['name']}"
        total_configs[config_key] = create_config_entry(base_config, acc['name'])

if __name__=='__main__':

    # Populate total configurations with entries summarizing arithmetic and accumulator formats
    pprint.pprint(arithmetic_formats)
    pprint.pprint(accumulator_boundaries)
    pprint.pprint(total_configs)
    print("number of computer formats:", len(arithmetic_formats))
    print("number of accumulators per format:", len(accumulator_boundaries))
    print("number of total configurations:", len(accumulator_boundaries)*len(arithmetic_formats))
