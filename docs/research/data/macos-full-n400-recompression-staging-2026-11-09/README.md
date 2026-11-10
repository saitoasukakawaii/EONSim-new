# Full N400 archive recompression staging

29458 confirmed live after starting single-thread zstd19 staging of completed elastic N400 full archive. Original archive and original manifest SHA verified, free space required above20GiB+original archive bytes+256MiB. Canonical archive and all restoration receipts remain untouched. Stops staging if candidate exceeds original compressed size or shared free space drops below20.5GiB. Geometry chunk migration37578 is independent; no catalog publication occurs here.

On completion helper must verify decoded full tar SHA equality and unchanged original SHA; result is still only a staged candidate. Adoption must update all matching full-archive and materialization receipts transactionally, preserve recovery copies, and validate current catalog before original removal. Actual staging verification/savings not yet available. No new numerical or performance claim; existing storage method reused. No new article, push or PR.
