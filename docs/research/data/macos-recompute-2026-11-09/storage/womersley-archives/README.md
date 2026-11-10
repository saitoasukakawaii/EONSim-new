# Verified full Womersley archives; original files retained

Zstandard1.5.7 level3,1thread,long-distance window27. A32-native-file probe
compared default(.77435) and long-window(.41271) compressed/tar-byte ratios,
fully decoding every member and checking its original SHA. No general ratio
was assumed; completed full studies were then archived and independently read.

Alpha1 session6618 exit0:3250 members,5416751259 logical source bytes,
2021659536 archive bytes. Alpha2 session46312 result is in its receipt.
Every full archive member was decoded and checked against the previously
committed raw manifest (exact inventory, sizes and SHA256), followed by whole
archive SHA256. Inputs have not been removed. Archives stay local under
`build/recompute-20261109/archives`; this evidence is not a raw upload.

Commands: `python3 build/recompute-20261109/probe-native-archive.py` and
`python3 build/recompute-20261109/archive-completed-womersley.py 1` (then2).
Each completed study still has unfinished scientific consumers. Only after
all required comparisons/budgets have completed may redundant materialized
files be removed in a separately verified action, preserving designated
restart states and inputs. Current archives add storage; they do not yet
constitute released disk space.
