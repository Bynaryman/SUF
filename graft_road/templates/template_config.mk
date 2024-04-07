export PLATFORM               = [[PDK]]
export DESIGN_NAME            = [[DESIGN_NAME]]

export VERILOG_FILES          = $(sort $(wildcard ./designs/src/[[EXPERIMENT]]/$(DESIGN_NAME)/*.v))
export SDC_FILE               = ./designs/$(PLATFORM)/[[EXPERIMENT]]/$(DESIGN_NAME)/constraint.sdc

export CORE_UTILIZATION       = [[CORE_UTILIZATION]]
#export SYNTH_HIERARCHICAL = 1
#export ADDER_MAP_FILE :=
#export CORE_ASPECT_RATIO      = 1 1
#export DIE_AREA               = 0 0 16.2 16.2
#export CORE_AREA              = 1.08 1.08 15.12 15.12
#export PLACE_DENSITY          = 0.35
