---
name: radlnavi-junction-review
description: Prepare, revise and verify RadlNavi large-junction review batches from frozen OSM data and human decisions, including district selection, polygons, entry/exit gates and review galleries.
---

# RadlNavi junction review

Work from the repository root. Read [the workflow and reference lessons](references/workflow.md) before preparing or revising a batch.

Keep geometry approval, technical movement validation and deployment separate. Human confirmation of an image approves its exact geometry, not every legal route or production activation. Preserve explicit exclusions and deferrals. Do not infer additional authorization for commit, push or deployment.

Use the maintained scripts in `docs/large-junction-analysis`:
- Rebuild round 1: `python docs/large-junction-analysis/build_review_images.py`.
- Rebuild BA09: `python docs/large-junction-analysis/prepare_ba09_review.py`.
- Run preflight: `python docs/large-junction-analysis/review_preflight.py`.
- Test preflight: `python -m unittest discover -s docs/large-junction-analysis -p test_review_preflight.py`.
- Render PNGs: `powershell -NoProfile -ExecutionPolicy Bypass -File docs/large-junction-analysis/render_review_images.ps1 -BatchDirectory review-batch-02-ba09-images`.
Use the matching batch name for other rounds. Run offline by default; collect fresh OSM only for a requested refresh/new batch. Existing approvals cannot transfer to changed geometry.

Before asking Thomas to review:
1. Read the current decisions, reference cases and preflight report.
2. Resolve obvious branching/merging problems supported by the directed graph. A merge suggestion alone does not authorize deleting gates.
3. Review the rendered image yourself. Preserve four logical arms, cycling directions and waiting areas; keep adjacent junctions separate.
4. Give one concrete question per unresolved site, with its ID and revision. Do not ask Thomas to trace all route variants during geometry review.

For gate repositioning near a split, merge or adjacent side path, follow the gate-and-boundary correction procedure in [the workflow](references/workflow.md#gate-and-boundary-corrections). Resolve the intended cycling junction and polygon edge together before presenting another image.

Preserve labels of unchanged gates. Record explicit migrations and increment the geometry revision when points or polygon change. Approved geometry is fingerprinted; never regenerate approval hashes just to silence a mismatch.

All numbered sheets belong in `kreuzungspruefung/1-bestaetigt`, `2-offen` or `3-ausgeschlossen`; generators maintain this organization. Metadata stays with its source batch. Report changes, checks, remaining questions and activation status concisely.
