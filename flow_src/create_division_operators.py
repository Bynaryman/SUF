#!/usr/bin/env python

# Author: Ledoux Louis

from scenario import Scenario
from pdk_configs import PDKS
from division_configs import division_configs
from utils import replace_placeholders
from placeholders import placeholders_config, placeholders_constraint
import os

# todo(lledoux): be careful with these paths
PATH_SRC_DESTINATION     = "/home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/designs/src/divisions/"
PATH_CFG_DESTINATION     = "/home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/designs/"
PATH_BIN_FLOPOCO         = "/home/lledoux/Documents/PhD/flopoco/build/code/FloPoCoBin/flopoco"
PATH_TRANSLATION_TOOLS   = "/home/lledoux/Documents/PhD/SUF/translation_tools/vh2v/vh2v.py"
PATH_PLACEHOLDERS_IN     = "/home/lledoux/Documents/PhD/SUF/flow_src/{}"
PATH_PLACEHOLDERS_OUT    = PATH_CFG_DESTINATION + "{}/divisions/{}/{}"
COMMAND_CREATE_SRC_DIR   = "mkdir -p {}{}"
COMMAND_CREATE_CFG_DIR   = "mkdir -p {}{}/divisions/{}"
COMMAND_GENERATE_DIV     = "{} FixDiv ints=1 frac={} iters={} target=ManualPipeline name={} frequency=0 outputFile={}{}/{}.vhdl"
COMMAND_TRANSLATION_VH2V = "python3 {} --input_file {}{}/{}.vhdl --output_dir {}{}/"

# steps
# 1. Create src directory
# 2. Create constraint and config directory for each PDK
# 3. Generate the adequate division with FloPoCo and put it in corresponding src folder
# 4. Translate generated VHDL into verilog and unflattend modules into subsequent files
# 5. Generate from a template config.mk and constraint.sdc and put it in the corresponding PDK config folder

def main():
    # 1
    for dc in division_configs:
        os.system(COMMAND_CREATE_SRC_DIR.format(PATH_SRC_DESTINATION,dc))

    # 2
    for p in PDKS:
        for dc in division_configs:
            os.system(COMMAND_CREATE_CFG_DIR.format(PATH_CFG_DESTINATION,p,dc))

    # 3
    for dc in division_configs:
        os.system(COMMAND_GENERATE_DIV.format(
            PATH_BIN_FLOPOCO,
            23,
            0,
            dc,
            PATH_SRC_DESTINATION,
            dc,
            dc
        ))

    # 4
    for dc in division_configs:
        os.system(COMMAND_TRANSLATION_VH2V.format(
            PATH_TRANSLATION_TOOLS,
            PATH_SRC_DESTINATION,
            dc,
            dc,
            PATH_SRC_DESTINATION,
            dc
        ))

    # 5
    for p in PDKS:
        for dc in division_configs:
            replace_placeholders(
                    PATH_PLACEHOLDERS_IN.format("template_config.mk"),
                    PATH_PLACEHOLDERS_OUT.format(p,dc,"config.mk"),
                    placeholders_config[p],
                    {"[[PDK]]":p,"[[DESIGN_NAME]]":dc}
            )
            replace_placeholders(
                    PATH_PLACEHOLDERS_IN.format("template_constraint.sdc"),
                    PATH_PLACEHOLDERS_OUT.format(p,dc,"constraint.sdc"),
                    placeholders_constraint[p],
                    {"[[CURRENT_DESIGN]]":dc}
            )

if __name__ == '__main__':
    main()
