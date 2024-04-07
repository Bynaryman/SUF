#!/usr/bin/env python
from pathlib import Path

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent

# Additional directories relative to the base directory
SCRIPTS_DIR = BASE_DIR / 'scripts'
INPUTS_DIR = BASE_DIR / 'inputs'
TEMPLATES_DIR = BASE_DIR / 'templates'
OUTPUTS_DIR = BASE_DIR / 'outputs'
FLOW_DIR = BASE_DIR.parent / 'OpenROAD-flow-scripts' / 'flow'

# Paths relative to the base directory
FLOW_DESIGNS_SRC_DIVISIONS_DIR = FLOW_DIR  / 'designs' / 'src' / 'divisions'
FLOW_DESIGNS_SRC_SA_LLMMMM_DIR = FLOW_DIR  / 'designs' / 'src' / 'sa_llmmmm'
FLOW_DESIGNS_DIR = FLOW_DIR / 'designs'

# External tools
FLOPOCO_BIN = Path.home() / 'Documents' / 'PhD' / 'flopoco' / 'build' / 'code' / 'FloPoCoBin' / 'flopoco'
# old flopoco mantained separately
FLOPOCO_SA_BIN = Path.home() / 'Documents' / 'PhD' / 'flopoco_SA' / 'build' / 'flopoco'
VH2V_BIN    = BASE_DIR.parent / 'translation_tools' / 'vh2v' / 'vh2v.py'

# Example commands
COMMAND_TEMPLATE_GUI       = f"make -C {FLOW_DIR} DESIGN_CONFIG=./designs/{{}}/aes/config.mk gui_final"
COMMAND_TEMPLATE_CLEAN     = f"make -C {FLOW_DIR} DESIGN_CONFIG=./designs/{{}}/aes/config.mk clean_all"


# Minimalist main to test the paths
if __name__ == '__main__':
    print(BASE_DIR)
    print(FLOW_DIR)
    print(SCRIPTS_DIR)
