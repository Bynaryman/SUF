# Performance specification for the SARSCM FPGA experiment.

PERFORMANCE = {
    "frequency_mhz": 200.0,
    "synthesis_only": True,
    "max_dsp": -1,
    "targets": [
        {
            "name": "vu9p",
            "target": "virtex_ultrascale_plus",
            "part": "xcvu9p-flgb2104-2-e",
        },
        {
            "name": "kintex7",
            "target": "kintex7",
            "part": "xc7k70tfbv484-3",
        },
    ],
}
