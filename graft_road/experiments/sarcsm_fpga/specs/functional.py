# Functional specification for the SARSCM FPGA experiment.
#
# Benchmarks are organized as:
# benches/<max_bits>bits/<constants>on<bits>R100/case_XXX/solution.json

BENCH_ROOT = "benches"
PATTERNS = ["**/case_*/solution.json"]
# LIMIT can be set to a small number for quick iterations.
LIMIT = None

# Optional filters for test runs.
# - max_bits: list of bit-width buckets to include (e.g., [6, 8])
# - constants_count: list of counts to include (e.g., [4, 8, 16])
# - case_ids: list of case ids (strings without "case_" prefix)
# - sample_per_bucket: keep at most N per (max_bits, constants_count) bucket
FILTERS = {
    "max_bits": None,
    "constants_count": None,
    "case_ids": None,
    "sample_per_bucket": None,
}
