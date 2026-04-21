# SZZ replication (ICSE 2021)



# 3. Setup Instructions

All commands below assume you are running from the project root, e.g.:

```bash
cd "/path/to/<project_root>"
```

## Prerequisites

- macOS or Linux (tested on macOS 25.4).
- Python 3.10.x (project tested with 3.10.19).
- Git 2.23 or newer on `PATH`.
- Ruby 
- `srcml` on `PATH` (<https://www.srcml.org>). PySZZ v2 (a tool to run SZZ algorithms) checks for it at startup even for variants that don't use it.
- A GitHub personal access token with read-only repo scope. It goes into a `.env` file and is used by the cloning scripts to avoid the 60 req/h anonymous rate limit.
- Around 50 GB of free disk space if you plan to run the full clone of all 951 repositories. Running only the subset clone needs much less.

## One-time setup

```bash
python3.10 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root containing your GitHub token:

```
GITHUB_TOKEN=<your_token>
```

The `cloned/` folder is gitignored (see [.gitignore](.gitignore)) and you do not need to create it by hand. Both `repo_cloner.py` and `subset_repo_cloner.py` create it on first run. If a previous partial run left stale folders inside it, `subset_repo_cloner.py` will `rm -rf` and re-clone each repo in its subset anyway.

## Getting the repositories

There are two paths. Most people should take Path B.

**Path A (full clone, ~4 hours, ~48 GB).** This clones every repository referenced in [data/json-input-raw/bugfix_commits_all.json](data/json-input-raw/bugfix_commits_all.json), filters down to those that cloned successfully, samples 10 entries with seed 42, and re-clones that sample with an attached HEAD:

```bash
python scripts/repo_cloner.py
python scripts/commits_filter.py \
  --input  data/json-input-raw/bugfix_commits_all.json \
  --output logs/bugfix_commits_all_filtered.json
python scripts/make_subset.py \
  --input  logs/bugfix_commits_all_filtered.json \
  --output logs/bugfix_commits_subset.json \
  --size 10 --seed 42
python scripts/subset_repo_cloner.py \
  --subset logs/bugfix_commits_subset.json \
  --log    logs/subset_clone_log.csv
```

Repeat the filter / sample / subset-clone trio for the issues-only dataset, swapping the input file:

```bash
python scripts/commits_filter.py \
  --input  data/json-input-raw/bugfix_commits_issues_only.json \
  --output logs/bugfix_commits_issues_only_filtered.json
python scripts/make_subset.py \
  --input  logs/bugfix_commits_issues_only_filtered.json \
  --output logs/bugfix_commits_issues_only_subset.json \
  --size 10 --seed 42
python scripts/subset_repo_cloner.py \
  --subset logs/bugfix_commits_issues_only_subset.json \
  --log    logs/subset_issues_only_clone_log.csv
```

**Path B (recommended, ~10 minutes).** The two subset JSONs are already committed under [logs/bugfix_commits_subset.json](logs/bugfix_commits_subset.json) and [logs/bugfix_commits_issues_only_subset.json](logs/bugfix_commits_issues_only_subset.json). Skip the full clone and just run the two subset clones directly:

```bash
python scripts/subset_repo_cloner.py \
  --subset logs/bugfix_commits_subset.json \
  --log    logs/subset_clone_log.csv
python scripts/subset_repo_cloner.py \
  --subset logs/bugfix_commits_issues_only_subset.json \
  --log    logs/subset_issues_only_clone_log.csv
```

Either way, you end up with partial (blobless) clones in `cloned/<owner>/<repo>/` whose HEAD is attached to a local branch `pyszz-work` at the pinned commit from `analyzed_projects_all.csv`. PySZZ v2 requires the attached HEAD;

## Installing PySZZ v2

PySZZ v2 is not present in this repo — you need to put it under `tools/pyszz_v2-master/`. Either clone the repo indicated in [tools/pyszz.txt](tools/pyszz.txt):

```bash
cd tools
git clone https://github.com/grosa1/pyszz_v2 pyszz_v2-master
cd ..
```

Or download a zip, put it in `tools/`, and unzip it so that the resulting folder is `tools/pyszz_v2-master/` with `main.py` directly inside.

PySZZ has its own Python dependencies but they are already present in the top-level [requirements.txt](requirements.txt), so the `pip install` in the previous section already covers them.

## Running the SZZ variants

All four variants read the same subset JSON. The paths below are given relative to `tools/pyszz_v2-master/`, which is how PySZZ expects to be invoked.

```bash
cd tools/pyszz_v2-master

python3 main.py ../../logs/bugfix_commits_subset.json conf/bszz.yml  ../../cloned
python3 main.py ../../logs/bugfix_commits_subset.json conf/agszz.yml ../../cloned
python3 main.py ../../logs/bugfix_commits_subset.json conf/lszz.yml  ../../cloned
python3 main.py ../../logs/bugfix_commits_subset.json conf/maszz.yml ../../cloned
```

Then do the same against the issues-only subset:

```bash
python3 main.py ../../logs/bugfix_commits_issues_only_subset.json conf/bszz.yml  ../../cloned
python3 main.py ../../logs/bugfix_commits_issues_only_subset.json conf/agszz.yml ../../cloned
python3 main.py ../../logs/bugfix_commits_issues_only_subset.json conf/lszz.yml  ../../cloned
python3 main.py ../../logs/bugfix_commits_issues_only_subset.json conf/maszz.yml ../../cloned

cd ../..
```

Each run writes a timestamped file under `tools/pyszz_v2-master/out/`, e.g. `bic_bszz_1776802225.json`. Eight runs produce eight output files — four per scenario.

## Collecting and renaming the outputs

[scripts/overlap.py](scripts/overlap.py) reads from `data/out/` with a fixed naming template (see its `model_list_*` blocks). Move the eight files from `tools/pyszz_v2-master/out/` into `data/out/` and rename them to:

```
data/out/bic_b_bugfix_commits_all.json
data/out/bic_ag_bugfix_commits_all.json
data/out/bic_l_bugfix_commits_all.json
data/out/bic_ma_bugfix_commits_all.json
data/out/bic_b_bugfix_commits_issues_only.json
data/out/bic_ag_bugfix_commits_issues_only.json
data/out/bic_l_bugfix_commits_issues_only.json
data/out/bic_ma_bugfix_commits_issues_only.json
```

We advise moving and renaming the four files as soon as one scenario (either `all` or `issues_only`) finishes, before starting the next scenario. That way you won't mix the two scenarios up among the timestamped filenames in `tools/pyszz_v2-master/out/`.

## Applying the issue-date filter

scripts/postfilter.rb removes inducing commits whose commit date is after the linked issue date and writes a `.issue-filter.json` sibling next to every input JSON. It takes two arguments: the directory with the SZZ output JSONs and the directory containing the cloned repositories.

```bash
ruby scripts/postfilter.rb data/out/ cloned/
```

Run this once after all eight files are in place and renamed. It creates the eight corresponding `bic_*.issue-filter.json` files in `data/out/`. Files where no entry has an issue date are skipped with a warning, which is expected.

## Generating the metrics and heatmaps

scripts/overlap.py writes its outputs to `out/` and `out/wrong/`. Create those two folders once.

```bash
mkdir -p out/wrong
python scripts/overlap.py
```

For each of the four prefixes (`all-`, `all-filter-`, `issue-only-`, `issue-only-filter-`) the script produces:

- `out/<prefix>recall-precision.csv` — Table VI numbers (Precision, Recall, F1).
- `out/<prefix>overlap_vi_vj.csv` and `out/<prefix>heatmap.pdf` — Fig. 3 / Fig. 4 data.
- `out/<prefix>overlap_vi_but_others.csv` and `out/<prefix>not-identified.csv`.
- `out/wrong/<prefix><model>-wrongly_identified.csv` per model.

## Notes and caveats

We evaluate on a 10-commit subset per scenario rather than the ~847-commit filtered set. The short reason is disk space (~50 GB already spent on partial clones, with limited room for PySZZ's per-commit temporary copies) and wall-clock time (a single SZZ variant over the full set would take several hours to a day, and the study requires running four of them, twice).
