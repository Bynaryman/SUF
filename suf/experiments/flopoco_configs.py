# Define your flopoco designs here.
# Two accepted formats:
# 1) DESIGNS as a list of tuples: (name, operator, "k=v", ...)
# 2) DESIGNS as a dict: name -> (operator, "k=v", ...) or name -> {"operator":..., "params":{...}}

DESIGNS = [
    ("fp_add16", "FPAdder", "wE=8", "wF=23", "frequency=400"),
    ("fp_mul16", "FPMultiplier", "wE=8", "wF=23", "frequency=400"),
]

