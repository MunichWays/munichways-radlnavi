# Workflow and reference lessons

## Sources of truth

All repository paths below are relative to the root.
- `docs/large-junction-analysis/review-reference-cases.json`: an expanding set of pinned human decisions (approved geometries and explicit exclusions; current counts are in review-progress.md). These are regression references, not training statistics or movement approvals.
- `review-batch-01-decisions.json` and `review-batch-02-ba09-decisions.json` in the analysis directory: exact revisions, gate migrations, approval provenance and exceptions.
- `junction-review-decisions.json`: wider exclusions; retain them when selecting candidates.
- `review-preflight.json/.md`: current technical suggestions and unresolved questions.
- Frozen OSM snapshots are evidence. No fresh network call is necessary for offline reproduction.

## Rules learned from reviewed cases

- K11: two-way cycleways may share entry/exit locations, and an arm can have multiple valid exits. Do not require exactly eight gates. Internal diagonal connections cease to be external gates when the polygon contains their whole connection.
- K12: place an entry upstream of a split and an exit downstream of a merge. The northern split and western merge are different nodes. Do not combine gates merely because their coordinates are close.
- K08/K12: an explicitly reviewed carriageway can supply a shared entry/exit point. This does not license treating every nearby road as a cycleway.
- K13: separate crowded northeastern gates and stop the northern area before the Schulstrasse connection. Adjacent intersections do not become arms of the main junction.
- K15: follow the cycling continuation backwards before Jutastrasse when shortening the exit. Do not move its gate onto a road tagged bicycle=use_sidepath. Thomas clarified southwestern Entry-3 belongs on the residential right-turn carriageway (way 95857037), about 5m before signal node 4669341961. The earlier untagged-footway proposal is superseded; do not carry its access warning forward.
- K17: Thomas excluded the northern side path (Entry-4 / Exit-5); preserve Entry-5 despite the numbering gap.
- K15/K17: explicit cycleway lane tags are relevant. A carriageway centerline does not locate the physical lane. Follow separate cycleways across lane transitions; do not invent a point on an unsupported side.
- K05 field-test correction: the later Zschokkestrasse bend must not produce a left-turn macro from Garmischer Strasse. The withdrawn Exit-4 uses standard guidance for both affected movements. Explicit movement exclusions override angle inference. Thomas subsequently approved replacement geometry v3 for deployment. Its six retained movements are checked against the new polygon with unchanged real route endpoints. The v2 reference remains archived with its original hash.
- K05/K06: keep correction history. An initial acceptance can be superseded by a user correction.
- K07 stays deferred pending its separate OSM recheck. K09 remains permanently excluded.
- A walking section outside the crossing must not suppress otherwise valid crossing guidance. Walking within the crossing/direction evidence remains a negative runtime case.

## Gate and boundary corrections

K17 required repeated southeast shifts of Exit-4 followed by straightening the edge to Entry-3. K15 similarly required moving a gate back towards the main junction to exclude Jutastrasse. Use these as positioning lessons, not fixed distances or a rule that every exit belongs before a split.

- Identify the exact relevant cycling junction in the frozen OSM graph and rendered map, including any nearby side-path node. Interpret the requested compass direction along the actual cycling way. For an exit, distinguish travel direction from the direction of the requested shift: "southeast" can mean moving upstream towards the main junction.
- Place the gate in relation to the intended main crossing and its waiting areas. If a side connection is excluded, choose the boundary that keeps that connection outside while retaining the main crossing. Do not treat the first nearby OSM node as the intended target without checking the rest of the geometry.
- Judge displacement at the image scale. A request to move a point "a whole stretch farther" needs a clearly visible displacement, not another tiny offset. Use a measured, graph-supported position and report the approximate change from the previous revision. If two different junctions remain plausible, ask one specific question identifying them rather than iterating arbitrary offsets.
- Adapt the adjoining polygon edges in the same revision. Prefer a direct segment between neighbouring gates when it preserves all required crossings and waiting areas. Remove obsolete hull vertices and notches left by moving a gate; do not preserve them merely because they were in the old polygon. An explicit request to straighten the boundary must preserve the gate positions.
- Compare all gates before and after: unchanged labels, positions and directions stay unchanged unless the requested scope requires otherwise. Check for extra polygon crossings, self-intersections and unintended inclusion/exclusion of side paths. Render and inspect the actual resulting image before presenting it.
- Preserve the previous approved geometry as a reference, increment the revision and invalidate technical results for changed geometry. Do not transfer approval or activate the revision automatically. Report the actual generated revision; do not invent missing revision numbers from conversational shorthand.

## Conservative automation

Graph proposals use directed OSM connectivity outside the polygon, up to 50 m, respecting oneway:bicycle/access. They suggest inspecting a common node, not approving the merge. Equal coordinates without shared OSM nodes do not prove connectivity. A missing proposal is not evidence that no split/merge exists.

District node grouping is preliminary: equal street-name sets within 80 m. Different-name groups can still be one complex. Candidate nodes and preliminary groups are not a verified count of Munich's large junctions.

## Work assignments, used sequentially by default

Geometry preparation: select new district candidates, resolve graph suggestions and gate/boundary corrections together, render clear drafts and record precise remaining questions. Preserve runtime files.

Geometry verification: check four arms, road side, direction, shared points, waiting areas, polygon continuity and neighbouring junction boundaries. For moved gates, verify the intended node, visible displacement, clean adjoining edges and unchanged other gates. Use fingerprints and references; never approve on behalf of Thomas.

Movement verification, after geometry approval: legal directed entry/exit paths, left/straight classification, real backend route evidence, right-turn controls, walking/access and wrong-exit controls. Shared gates may require multiple movements per arm. Record unsupported movements individually.

Do not launch additional agents just because these roles exist. Delegate only when the user requests it; sequential use reduces duplicated context and usage.

## Measuring whether this helps

For new completed reviews, record `firstPassConfirmed` (true/false/null), `correctionRounds` and correction reason codes in the decision's optional `efficiency` field when the history establishes them. Null means unknown; never infer first-pass success solely from a revision number.

Compare human first-pass geometry acceptance among cases with known outcomes. Count exclusions separately. Record technical false positives and time spent only if measured. The reference cases establish correctness. Record new explicit approvals as additional cases. First-pass acceptance now includes the explicitly recorded K16 outcome; this is not yet a measured speed improvement.
