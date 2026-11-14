# Workflow and reference lessons

## Sources of truth

All repository paths below are relative to the root.
- `docs/large-junction-analysis/review-reference-cases.json`: an expanding set of pinned human decisions (approved geometries and explicit exclusions; current counts are in review-progress.md). These are regression references, not training statistics or movement approvals.
- `review-batch-01-decisions.json` and `review-batch-02-ba09-decisions.json` in the analysis directory: exact revisions, gate migrations, approval provenance and exceptions.
- `junction-review-decisions.json`: wider exclusions; retain them when selecting candidates.
- `review-preflight.json/.md`: current technical suggestions and unresolved questions.
- `review-batch-02-ba09-routes.json` and `review-batch-02-ba09-technical.md`: per-movement results and diagnostic causes; frozen route fixtures and request manifest make them reproducible.
- `backend/src/big_junctions.json`: actual branch activation, reviewed arm topology and explicit disabled movements. A proposed catalog is not activation evidence.
- `review-deployment-state.json`: last verified production version/commit and its exact source catalog; never infer live activation from a build start or local file.
- `review-field-tests.json`: human-reported field coverage, tied to geometry revisions and backend version. Many tested relationships does not mean all relationships were ridden.
- `review-supplemental-sites.json`: original pilots and earlier exclusions, included once in overview totals.
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

## Technical lessons from K11-K17

Use the successful BA09 field test as evidence for these reviewed cases, not automatic approval of similar future junctions. Preserve K13 Entry-2 -> Exit-5 and Entry-3 -> Exit-5 as disabled until separately resolved and authorized.

### Classify the instruction separately from matching the ridden path

K13 and K15 have curved/offset approaches. A local tangent can suggest 31-38 degrees for a logical straight crossing, or about 148 degrees for a logical left turn. Do not move correct gates, relabel the instruction from this angle alone or widen global angle tolerances to force acceptance.

Document the four logical arms in clockwise order with their actual entry/exit gate memberships. For reviewed four-arm topology, the production validator can classify left/straight by that order. Local approach/departure vectors, legal directed corridor, gate positions and runtime geometry still determine whether a route matches. Multiple gates and shared two-way points remain allowed. Missing or ambiguous topology must not silently bypass the existing angle checks. Explicit movement exclusions such as K05 override any inferred classification.

### Diagnose failed evidence before rejecting a movement

- Reference sampling: 45 m outside the polygon is a convenient test distance, not a junction acceptance rule. Where a short approach ends at a bend or branch, use an actual legal directed point closer to the gate. The current BA09 helper tries shorter distances down to 12 m, keeping margin above the 10 m runtime direction evidence. Record the chosen distance. Never extrapolate off the graph, cross restrictions or shorten below the runtime evidence requirement merely to obtain a pass.
- Road support: K17 needed inner way 38349617 as continuation of the reviewed Lothstrasse carriageway. Verify the specific connector, its access/oneway tags and connectivity. Include only evidenced internal segments, without adding gates or admitting every nearby road. The graph's cycleway-oriented filter omitting a segment is different from that segment being prohibited for cycling.
- Response format: K15 had an approximately 22 cm terminal-marker offset. Reuse the narrow production handling: final point-like arrive step, zero distance/duration, at most 0.75 m offset. Internal maneuvers and geometry joins stay exact; departure handling stays separately bounded. Do not repair or rewrite the original routing response to make guidance fit.
- Route selection: if the requested real Standard route never traverses the polygon, it is not evidence for the intended movement. Record the exact entry/exit pair and leave it disabled. Do not manufacture a corridor, force another maneuver label or relax the crossing requirement. K13's two retained exclusions are this case.

For each failure record whether it arose during endpoint sampling, snapping, polygon/gate crossing, legal corridor support, classification, response continuity or runtime matching. Resolve reproducible tooling limitations first. Leave unresolved relationships individually disabled so one exception need not block an otherwise verified junction or batch.

### Complete the batch before proposing activation

Reproduce cached real routes offline. Test the complete proposed catalog, not only each movement in isolation: positive classifications, rejected relationships, right-turn controls, walking sections, ambiguous matches, wrong local directions and unchanged raw route data. Re-run applicable backend and review-tool tests after changing runtime matching. Preserve earlier pilot/K05 regressions. Pin failures that must remain disabled in both the catalog and regression tests.

Keep generators repeatable after activation: replace a batch's existing sites instead of appending duplicates, preserve manual exclusions and require an explicit authorized step to copy proposed data into runtime configuration. Report the number of verified and disabled movements before the user decides to activate/deploy. Do not ask Thomas to recheck sound geometry just because a technical check failed.

### Make release and field status reviewable

- Clearly show individual exclusions in the overview and affected review image, identified by stable Entry/Exit labels. An excluded pair does not make its shared gate or entire junction invalid. Standard guidance remains available for excluded pairs.
- After authorized activation, distinguish branch-ready from live. After deployment, check production version/commit and actual catalog, then refresh the overview. Keep historical live-test reports labelled as historical. A successful build is not a field test, and a reported field test does not replace the production-state check.
- Record Thomas's field-test statement and actual coverage without expanding it to all movements. Bind it to the tested geometry revision; a later geometry change needs fresh technical evidence and cannot inherit field coverage automatically.
- Include numbered cases, original pilots and earlier exclusions once in totals. City-wide candidate-node counts are a search inventory, not a count of distinct eligible junction complexes. Do not use a provisional point count or an old estimate as the denominator of a claimed completion percentage.

## Conservative automation

Graph proposals use directed OSM connectivity outside the polygon, up to 50 m, respecting oneway:bicycle/access. They suggest inspecting a common node, not approving the merge. Equal coordinates without shared OSM nodes do not prove connectivity. A missing proposal is not evidence that no split/merge exists.

District node grouping is preliminary: equal street-name sets within 80 m. Different-name groups can still be one complex. Candidate nodes and preliminary groups are not a verified count of Munich's large junctions.

## Work assignments, used sequentially by default

Geometry preparation: select district candidates, use reviewed regular four-arm patterns where supported, resolve graph suggestions and gate/boundary corrections together, and record logical arms alongside gate labels. Park genuinely ambiguous geometry with a precise reason instead of blocking unrelated candidates. Render clear drafts; preserve runtime files.

Geometry verification: check four arms, road side, direction, shared points, waiting areas, polygon continuity and neighbouring junction boundaries. For moved gates, verify the intended node, visible displacement, clean adjoining edges and unchanged other gates. Use fingerprints and references; never approve on behalf of Thomas.

Movement verification, after geometry approval: complete legal directed entry/exit and whole-catalog checks using the technical lessons above. Separate sampling/format limitations from unsafe routes. Preserve reviewed arm semantics, shared gates and explicit pair exclusions; record actionable causes for remaining failures.

Release/overview maintenance: within the user-authorized scope, prepare only verified movements, preserve disabled pairs and identify branch-ready versus verified-live state. Update counts including supplemental cases and record the actual human field coverage. Never trigger a user-reserved build or deployment.

Do not launch additional agents just because these roles exist. Delegate only when the user requests it; sequential use reduces duplicated context and usage.

## Measuring whether this helps

For new completed reviews, record `firstPassConfirmed` (true/false/null), `correctionRounds` and correction reason codes in the decision's optional `efficiency` field when the history establishes them. Null means unknown; never infer first-pass success solely from a revision number.

Compare human first-pass geometry acceptance among cases with known outcomes. Count exclusions separately. Record technical false positives and time spent only if measured. The reference cases establish correctness. Record new explicit approvals as additional cases. First-pass acceptance now includes the explicitly recorded K16 outcome; this is not yet a measured speed improvement.
