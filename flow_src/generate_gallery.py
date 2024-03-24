#!/usr/bin/env python

# Author: Ledoux Louis

from scenario import Scenario
from pdk_configs import PDKS
from division_configs import division_configs
import os

# define the actions to perform and their inter dependencies
actions_push = {}
dependencies_push = {}

# todo(lledoux): be careful with this path
COMMAND_TEMPLATE_IMAGE = "make -C /home/lledoux/Documents/PhD/SUF/OpenROAD-flow-scripts/flow/ DESIGN_CONFIG=./designs/{}/divisions/{}/config.mk gui_final"
COMMAND_CP_WITH_NAME = "mv /tmp/tmp.png /home/lledoux/Documents/PhD/gallery/{}_{}.png"

for p in PDKS:
    for dc in division_configs.keys():

        # 1. Create the image as /tmp/tmp.png
        fct1_name = "fct_gds2png_{}_{}".format(p,dc)
        exec(
            'def {}():'.format(fct1_name) +
    		'\n\tos.system("{}")'.format(COMMAND_TEMPLATE_IMAGE.format(p,dc))+
    		'\n\tos.system("{}")'.format(COMMAND_CP_WITH_NAME.format(p,dc))
        )
        actions_push[fct1_name] = eval(fct1_name)
        dependencies_push[fct1_name]=[]

        ## 2. Rename it
        #fct2_name = "fct_rename_{}_{}".format(p,dc)
        #exec(
        #    'def {}():'.format(fct2_name) +
    	#	'\n\tos.system("{}")'.format(COMMAND_CP_WITH_NAME.format(p,dc))
        #)
        #actions_push[fct2_name] = eval(fct2_name)
        #dependencies_push[fct2_name]=[fct1_name]

def GDS_TO_PNG():

    # create the actions dictionary, in this case local actions are the global ones
    actions = actions_push

    # create the dependencies dictionary, in this case local dependencies are the global ones
    dependencies = dependencies_push

    print("================ACTIONS=================")
    print(actions)
    print("==============DEPENDENCIES==============")
    print(dependencies)

    # then create the scenario
    gds2png = Scenario(actions, dependencies, log=True)

    # launch the scenario until it succeed with up to 12 parallel actions
    gds2png.exec_once_sync_parallel(1)

def main():

    # create and play a run
    GDS_TO_PNG()

if __name__ == '__main__':
    main()
