# Exploration of 10 random entries from the oracle

We pulled 10 random entries out of the 1,930 manually validated commits in
`data/detailed-database/overall.json`.

Sample is reproducible:

run the `random_commits.py` file

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

## Commit analysis

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

**id 933 — `analogdevicesinc/hdl` — fix `c4c87c7c7a`.** Fix message:
"axi_ad9361: Fix the _hw.tcl script". The inducing commit `48d2c9d` is
"axi_ad9361: Define a MIMO enabled parameter". No explicit SHA reference in the fix message.
`issue_urls` empty.

**id 844 — `NRGI/resourceprojects.org-frontend` — fix `d6b88831b7`.** Fix message:
"Updates payment table on Country page". The inducing commit `652b20e` is
"[#16] Makes data on payments show up". No explicit SHA reference in the fix message.
`issue_urls` empty.

**id 493 — `chadversary/piglit` — fix `7fe770369f`.** Fix message:
"framework/shader_test.py: fix bug from commit 260f211d". The inducing commit `260f211` is
"framework: Use shader_test.py to drive shader tests". The developer explicitly references the inducing SHA in the fix message.
`issue_urls` empty.

**id 2718 — `audacity/audacity` — fix `f9827a57a7`.** Fix message:
"Minor fix for commands for shifting clips using the keyboard." The inducing commit `9da999d` is
"Use OffsetTimeByPixels correctly...". No explicit SHA reference in the fix message.
`issue_urls` empty.

**id 338 — `Khan/analytics` — fix `d36ea213a8`.** Fix message:
"Fix issues with video matrix generation." The inducing commit `0fac10a` is
"Step 1 in import flow for video correlation matrix.". No explicit SHA reference in the fix message.
`issue_urls` empty.

___
Issue links in this sample (`issue_urls`): none (all entries have an empty `issue_urls` list).

Overall, these commits are pretty good for oracle, and are easy to link in between. They show direct correlation between change and the consequent bugs that were introduced and later fixed.
