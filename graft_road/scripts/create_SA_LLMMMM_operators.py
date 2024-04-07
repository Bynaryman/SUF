#!/usr/bin/env python

# Author: Ledoux Louis
import os
from math import log2,ceil

from libs.scenario import Scenario
from inputs.pdk_configs import PDKS
from inputs.SA_LLMMMM_configs import total_configs
from libs.utils import replace_placeholders
from templates.placeholders import placeholders_config, placeholders_constraint
from config import *

experiment = "sa_llmmmm"

PATH_PLACEHOLDERS_IN       = f"{TEMPLATES_DIR}/{{}}"
PATH_PLACEHOLDERS_OUT      = f"{FLOW_DESIGNS_DIR}/{{}}/{experiment}/{{}}/{{}}"
COMMAND_CREATE_SRC_DIR     = "mkdir -p {}/{}"
COMMAND_CREATE_CFG_DIR     = f"mkdir -p {{}}/{{}}/{experiment}/{{}}"
COMMAND_GENERATE_SA_LLMMMM = "{} {} N={} M={} arithmetic_in={} arithmetic_out=same msb_summand={} lsb_summand={} nb_bits_ovf={} name={} chunk_size={} frequency=200 outputFile={}/{}/{}.vhdl"
COMMAND_TRANSLATION_VH2V   = "python3 {} --input_file {}/{}/{}.vhdl --output_dir {}/{}/"


# steps
# 1. Create src directory
# 2. Create constraint and config directory for each PDK
# 3. Generate the adequate Systolic Array with FloPoCo and put it in corresponding src folder
# 4. Translate generated VHDL into verilog and unflattend modules into subsequent files
# 5. Generate from a template config.mk and constraint.sdc and put it in the corresponding PDK config folder

def main():
    # 1
    for tc in total_configs.keys():
        os.system(COMMAND_CREATE_SRC_DIR.format(FLOW_DESIGNS_SRC_SA_LLMMMM_DIR,tc))

    # 2
    for p in PDKS:
        for tc in total_configs.keys():
            os.system(COMMAND_CREATE_CFG_DIR.format(FLOW_DESIGNS_DIR,p,tc))

    # 3
    for tc in total_configs.keys():
        binary_exec = "SystolicArray"

        # Retrieve the configuration entry for the current key
        entry = total_configs[tc]

        # Extract arithmetic format and accumulator configuration details
        arith_format = entry["arithmetic_format"]
        accum_config = entry["accumulator_config"]

        # Construct the arith_in string based on arithmetic format details
        # This example assumes the format "ieee:exp:mantissa", adjust as necessary
        arith_in = arith_format["flopoco_name"]

        # Extract MSB, LSB, and OVF from the accumulator configuration
        msb = accum_config["msb"]
        lsb = accum_config["lsb"]
        ovf = accum_config["ovf"]
        chunksize = accum_config["total_width"]

        print(COMMAND_GENERATE_SA_LLMMMM.format(

            FLOPOCO_SA_BIN, # which flopoco
            binary_exec, # SystolicArray
            8, # N
            8, # M
            arith_in,
            msb,
            lsb,
            ovf,
            tc,
            chunksize,
            FLOW_DESIGNS_SRC_SA_LLMMMM_DIR,
            tc,
            tc
        ))
        os.system(COMMAND_GENERATE_SA_LLMMMM.format(

            FLOPOCO_SA_BIN, # which flopoco
            binary_exec, # SystolicArray
            8, # N
            8, # M
            arith_in,
            msb,
            lsb,
            ovf,
            tc,
            chunksize,
            FLOW_DESIGNS_SRC_SA_LLMMMM_DIR,
            tc,
            tc
        ))

    # 4
    for tc in total_configs.keys():
        os.system(COMMAND_TRANSLATION_VH2V.format(
            VH2V_BIN,
            FLOW_DESIGNS_SRC_SA_LLMMMM_DIR,
            tc,
            tc,
            FLOW_DESIGNS_SRC_SA_LLMMMM_DIR,
            tc
        ))

    # 5
    for p in PDKS:
        for tc in total_configs.keys():
            replace_placeholders(
                    PATH_PLACEHOLDERS_IN.format("template_config.mk"),
                    PATH_PLACEHOLDERS_OUT.format(p,tc,"config.mk"),
                    placeholders_config[p],
                    {"[[PDK]]":p,"[[DESIGN_NAME]]":tc, "[[EXPERIMENT]]": experiment}
            )
            replace_placeholders(
                    PATH_PLACEHOLDERS_IN.format("template_constraint.sdc"),
                    PATH_PLACEHOLDERS_OUT.format(p,tc,"constraint.sdc"),
                    placeholders_constraint[p],
                    {"[[CURRENT_DESIGN]]":tc}
            )

if __name__ == '__main__':
    main()
