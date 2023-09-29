#!/usr/bin/env python

# Author: Ledoux Louis

from scenario import Scenario
import os

# define the actions to perform and their inter dependencies
actions_push = {}
dependencies_push = {}

# todo(lledoux): be careful with this path
COMMAND_TEMPLATE_FULL_FLOW = "make -C /home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/ DESIGN_CONFIG=./designs/{}/aes/config.mk"
COMMAND_TEMPLATE_GUI       = "make -C /home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/ DESIGN_CONFIG=./designs/{}/aes/config.mk gui_final"
COMMAND_TEMPLATE_CLEAN     = "make -C /home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/ DESIGN_CONFIG=./designs/{}/aes/config.mk clean_all"

# todo(lledoux): create commands that generates tables(CSV,TXT,TEX) from reports (area, cells, power)

PDKS = ["nangate45","asap7","sky130hd","gf180"]

for p in PDKS:
    fct_name = "fct_rtl2gds_{}".format(p)
    exec(
        'def {}():'.format(fct_name) +
		'\n\tos.system("{}")'.format(COMMAND_TEMPLATE_GUI.format(p))
    )
    actions_push[fct_name] = eval(fct_name)
    dependencies_push[fct_name]=[]

# first attempt to No Human In Loop Register Transfer Level to Graphic Design System
def NHIL_RTL_2_GDS():

    # create the actions dictionary, in this case local actions are the global ones
    actions = actions_push

    # create the dependencies dictionary, in this case local dependencies are the global ones
    dependencies = dependencies_push

    print("================ACTIONS=================")
    print(actions)
    print("==============DEPENDENCIES==============")
    print(dependencies)

    # then create the scenario
    rtl2gds = Scenario(actions, dependencies, log=True)

    # launch the scenario until it succeed with up to 12 parallel actions
    rtl2gds.exec_once_sync_parallel(12)

def main():

    # create and play a run
    NHIL_RTL_2_GDS()

if __name__ == '__main__':
    main()
