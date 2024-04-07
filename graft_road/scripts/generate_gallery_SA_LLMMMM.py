#!/usr/bin/env python

# Author: Ledoux Louis

import os
from libs.scenario import Scenario
from inputs.pdk_configs import PDKS

from inputs.pdk_configs import PDKS
from inputs.SA_LLMMMM_configs import total_configs

from config import FLOW_DIR,OUTPUTS_DIR

# define the actions to perform and their inter dependencies
actions_push = {}
dependencies_push = {}

# todo(lledoux): be careful with this path
COMMAND_TEMPLATE_IMAGE = f"make -C {FLOW_DIR} DESIGN_CONFIG=./designs/{{}}/sa_llmmmm/{{}}/config.mk gui_final"
COMMAND_CP_WITH_NAME = f"mv /tmp/tmp.png {OUTPUTS_DIR}/gallery/{{}}_{{}}.png"

for p in PDKS:
    for tc in total_configs.keys():

        # 1. Create the image as /tmp/tmp.png
        fct1_name = "fct_gds2png_{}_{}".format(p,tc)
        exec(
            'def {}():'.format(fct1_name) +
    		'\n\tos.system("{}")'.format(COMMAND_TEMPLATE_IMAGE.format(p,tc))+
    		'\n\tos.system("{}")'.format(COMMAND_CP_WITH_NAME.format(p,tc))
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
