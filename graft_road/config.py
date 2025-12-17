#!/usr/bin/env python
import sys

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from suf import FLOW_ROOT, TRANSLATION_ROOT, VH2V_BIN

# Additional directories relative to the base directory
SCRIPTS_DIR = BASE_DIR / 'scripts'
INPUTS_DIR = BASE_DIR / 'inputs'
TEMPLATES_DIR = BASE_DIR / 'templates'
OUTPUTS_DIR = BASE_DIR / 'outputs'
FLOW_DIR = FLOW_ROOT
TRANSLATION_TOOLS_DIR = TRANSLATION_ROOT

# Paths relative to the base directory
FLOW_DESIGNS_SRC_DIVISIONS_DIR = FLOW_DIR  / 'designs' / 'src' / 'divisions'
FLOW_DESIGNS_SRC_SA_LLMMMM_DIR = FLOW_DIR  / 'designs' / 'src' / 'sa_llmmmm'
FLOW_DESIGNS_DIR = FLOW_DIR / 'designs'

# External tools
FLOPOCO_BIN = Path.home() / 'Documents' / 'PhD' / 'flopoco' / 'build' / 'code' / 'FloPoCoBin' / 'flopoco'
FLOPOCO_SA_BIN = Path.home() / 'Documents' / 'PhD' / 'flopoco_SA' / 'build' / 'flopoco'
VH2V_BIN = Path(VH2V_BIN) if VH2V_BIN else None

# Example commands
COMMAND_TEMPLATE_GUI       = f"make -C {FLOW_DIR} DESIGN_CONFIG=./designs/{{}}/aes/config.mk gui_final"
COMMAND_TEMPLATE_CLEAN     = f"make -C {FLOW_DIR} DESIGN_CONFIG=./designs/{{}}/aes/config.mk clean_all"


# Minimalist main to test the paths
if __name__ == '__main__':
    print(BASE_DIR)
    print(FLOW_DIR)
    print(SCRIPTS_DIR)
