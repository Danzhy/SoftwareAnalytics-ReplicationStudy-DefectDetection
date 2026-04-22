# Exploration of 10 random entries from the oracle

We pulled 10 random entries out of the 1,930 manually validated commits in
`data/detailed-database/overall.json`


Sample is reproducible:

run the random_commits.py file

This gives ids: 
2336,
375,
79,
2733,
1039,
933,
844,
493,
2718,
338

## Data format

Each entry is a JSON object with:

- `id` — running integer the authors use to reference the entry.
- `repository` — `owner/repo` on GitHub.
- `fix` — the bug-fix commit: `fix.commit.{hash, message, author, url}` plus
  `fix.files[]` with per-file `lines_added` / `lines_deleted` (1-based line
  numbers) and `change_type`.
- `bugs` — a list of candidate bug-introducing commits, same
  shape as `fix`.
- `issue_urls` — list of GitHub or tracker issue URLs referenced.
- `earliest_issue_date`, `best_scenario_issue_date` — timestamps used by the
  SZZ variants that filter on issue date; `best_scenario_issue_date` is a
  fallback heuristic and does **not** imply there is a real linked issue.

## The five commits

**id 2336 — `andrewphorn/ClassiCube-Client` — fix `638ece305b`.** Fix message:
"Another bug fix / Fixed a bug introduced in d37442c which was causing the
menu to not show up in singleplayer". The inducing commit `d37442c` is
"Fixes #319 ...". The developer literally names the inducing SHA, `issue_urls` is empty.

**id 375 — `spring/spring` — fix `40cba0e1fc`.** Fix message: *"fix compile
error in spring-mt introduced by 9bd22b4f..."*. The inducing commit is a big
refactor "refactor/unify various frustum-line functions into CCamera" that
touches many files. Seems like a "big refactor broke the build" case. Represents a bug introducing commit.
`issue_urls` empty.

**id 79 — `OpenEmu/OpenEmu-SDK` — fix `356aa8d89b`.** Fix: "Refuse to scale
until 8 samples have been learned", bug: "Automatically learn analog-control
calibration". No SHA reference in the fix message, and both
`earliest_issue_date` and `best_scenario_issue_date` are `null`. Potentially bug introducing, but is not 100% evident just from this metadata.

**id 2733 — `t6x/reaver-wps-fork-t6x` — fix `59d097a327`.** Fix: "add support
for QoS data packets", bug: "association: replay AP 802.11n HT
capabilities". Both touch the same 802.11 code and the fix clearly builds on
the bug commit; however, nothing fix message doesn't point at the SHA.
Potential candidate to be bug-introducin.

**id 1039 — `mapbox/carto` — fix `16db1c5b03`.** Fix message: "fix MSS
standalone renderer, fixing failing error handling tests after f6c07afe...";
inducing commit is "Refine heap performance. Switch back to underscore since
lodash does npm all wrong." Explicit SHA reference in the fix, looks legit.

___
None of the five so far have issues linked.


