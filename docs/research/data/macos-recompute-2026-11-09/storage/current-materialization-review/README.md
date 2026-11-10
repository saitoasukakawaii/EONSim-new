# Current materialization inventory review

53651 completed0. Seven archived studies originally contain40688files;18099current missing materializations exactly equal the union of their explicit, nonoverlapping receipts. No unexplained missing path or unexpected new file. Retained file sizes checked; archive presence/size and manifest/receipt hash bindings checked. Full archive decoding/SHA checks from creation are reused, not claimed rerun here. Catalog records each required restoration command; no data modified.

First read-only attempt9045 failed on a JSON list probe output while assuming every JSON value was a receipt mapping. Failed source retained; second skips non-mapping outputs before receipt key inspection, with original inventory constraints unchanged.

Added Markdown local link review at5a39167 checked290distinct local targets in added lines since snapshot92fef88, none missing. External URLs and unchanged old links were not checked; no numerical test claim.

Command: `python3 build/recompute-20261109/review-materialization-catalog.py`. This is a point-in-time catalog: future restoration/recovery changes must be reconciled again before relying on current-path presence.
