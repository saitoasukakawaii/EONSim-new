# Fine N1600 early volume archive re-encoding

Base226ded6. Existing completed N1600 early volume archives only:56chunks/3258members, all bound to the original complete raw manifest. `python3 build/recompute-20261109/review-fine-n1600-early-recompression-catalog.py` exited0 before starting the batch. Three scoped scripts pass AST parsing and reuse the completed final-volume transaction: old/new decoded tar SHA must match; original archive retained until new archive/receipt and scoped catalog publish successfully. Each transaction journals old/new SHA/size and only then removes the old backup. No field values or numeric gates changed.

`python3 build/recompute-20261109/recompress-fine-n1600-early-volumes.py` is running; no total savings or independent post-batch decode claimed yet. Existing global catalogv19 becomes stale as hashes change and must be refreshed after batch completion.
