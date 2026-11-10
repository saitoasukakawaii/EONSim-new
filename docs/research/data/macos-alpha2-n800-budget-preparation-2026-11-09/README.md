# Alpha2 N800 target family preparation

After original default N400 budget fails, new default-tau target is N800 with matched coarseN800 and fineN1600 controls. No threshold changes or tau-model substitution. Existing fineN800 result retained.

59645 launched fresh coarseN800 from zero, six cycles, every phase, same binary/physics/seed and LU32/chord configuration. Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/run-womersley-alpha2-coarse-n800.py --alpha 2 --n 800`. Controller retains6GiB RSS/20GiB disk/24h bounds. Launch receipt is not completion.

FineN1600 controller prepared but NOT launched: conservative required free42GiB =20GiB floor plus22GiB raw allowance; observed free35.74GiB before coarse launch. Need finish current consumers and archive more completed data before launching. Original failed N400 budget and ongoing tau intervention remain separate evidence.

Update: alpha1 completed-consumer archiving recovered sufficient capacity (42.998GiB observed). FineN1600 is now launched from zero with original six cycles/defaulttau and resource guards. Command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/run-womersley-alpha2-fine-n1600.py --alpha 2 --n 1600`. Execution receipt is startup evidence only, not completion.
