#!/usr/bin/env python

# Author: Ledoux Louis

from libs.scenario import Scenario
from inputs.pdk_configs import PDKS
from inputs.SA_LLMMMM_configs import total_configs
import os

from config import FLOW_DIR

# define the actions to perform and their inter dependencies
actions_push = {}
dependencies_push = {}

# todo(lledoux): be careful with this path
COMMAND_TEMPLATE_FULL_FLOW = f"make -C {FLOW_DIR} DESIGN_CONFIG=./designs/{{}}/sa_llmmmm/{{}}/config.mk"

for p in PDKS:
    for tc in total_configs.keys():
        fct_name = "fct_rtl2gds_{}_{}".format(p,tc)
        exec(
            'def {}():'.format(fct_name) +
    		'\n\tos.system("{}")'.format(COMMAND_TEMPLATE_FULL_FLOW.format(p,tc))
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
