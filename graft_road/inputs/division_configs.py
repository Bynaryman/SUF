#!/usr/bin/env python

#division_configs = [
#    "ieee754_QP",
#    "ieee754_DP",
#    "ieee754_SP",
#    "ieee754_HP",
#    "BF16",
#    "posit64",
#    "posit32",
#    "posit16",
#    "posit8",
#    "E4M3",
#    "E5M2"
#]

import pprint

base_configs= {
    # "ieee754QP": {
    #     "bitwidth": "128",
    #     "category": "IEEE754",
    #     "mantissa_size": "112"
    # },
    #"ieee754DP": {
    #    "bitwidth": "64",
    #    "category": "IEEE754",
    #    "mantissa_size": "52"
    #},
     "ieee754SP": {
         "bitwidth": "32",
         "category": "IEEE754",
         "mantissa_size": "200"
     },
    # "ieee754HP": {
    #     "bitwidth": "16",
    #     "category": "IEEE754",
    #     "mantissa_size": "10"
    # },
    # "bf16": {
    #     "bitwidth": "16",
    #     "category": "BrainFloat",
    #     "mantissa_size": "7"
    # },
    # "posit64": {
    #     "bitwidth": "64",
    #     "category": "Posit",
    #     "mantissa_size": "59"
    # },
    # "posit32": {
    #     "bitwidth": "32",
    #     "category": "Posit",
    #     "mantissa_size": "27"
    # },
    # "posit16": {
    #     "bitwidth": "16",
    #     "category": "Posit",
    #     "mantissa_size": "11"
    # },
    # "posit8": {
    #     "bitwidth": "8",
    #     "category": "Posit",
    #     "mantissa_size": "3"
    # },
    # "e4m3": {
    #     "bitwidth": "8",
    #     "category": "Nvidia",
    #     "mantissa_size": "3"
    # },
    # "e5m2": {
    #     "bitwidth": "8",
    #     "category": "Nvidia",
    #     "mantissa_size": "2"
    # }
}


algorithms = [
    #{"name": "NewTon_Raphson", "versions": ["unrolled", "rolled"]},
    #{"name": "Goldschmidt", "versions": ["unrolled", "rolled"]},
    {"name": "Non_Restoring", "versions": ["baseline"]}  # This will be replaced dynamically later
]

def create_config_entry(base_config, algorithm, version=None):
    entry = {
        "bitwidth": base_config["bitwidth"],
        "category": base_config["category"],
        "is_pipelined": True if "unrolled" in algorithm["name"] or (version and "unrolled" in version) else False,
        "mantissa_size": base_config["mantissa_size"],
        "division_algorithm": algorithm["name"]
    }

    if version:
        entry["version"] = version

        # Add 'adder_size' field for Non_Restoring and non-baseline versions
        if algorithm["name"] == "Non_Restoring" and version != "baseline":
            # Assuming adder size is derived from the version name for non-baseline versions.
            # Extracting the size from the version name (e.g., "serial_adder_5" -> 5)
            adder_size = int(version.split("_")[-1])
            entry["adder_size"] = adder_size

    return entry

division_configs = {}

for base_name, base_config in base_configs.items():
    for algorithm in algorithms:
        if algorithm["name"] == "Non_Restoring":
            #algorithm["versions"] = ["baseline"] + [f"serial_adder_{i}" for i in range(1, int(base_config["mantissa_size"]) + 3)] # +4 because adder needs extra bit for GRS
            #algorithm["versions"] = ["baseline"] + [f"serial_adder_{i}" for i in range(1, int(base_config["mantissa_size"]) + 3)] # +4 because adder needs extra bit for GRS
            algorithm["versions"] = ["baseline"] + [f"serial_adder_{i}" for i in [2,int(base_config["mantissa_size"])]]

        for version in algorithm["versions"]:
            key_name = f"{base_name}_{algorithm['name']}_{version}"
            division_configs[key_name] = create_config_entry(base_config, algorithm, version=version)

if __name__=='__main__':
    print("number of division configurations:", len(division_configs))
    pprint.pprint(division_configs)

