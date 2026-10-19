# Phase 3 — Research Desk Frontend Acceptance

## Routes

- `/dashboard`: authenticated landing page; use the Research Desk link.
- `/research`: authenticated, read-only research history and evidence ledger.
- `/strategies`: strategy registry (not a research execution surface).

## Run-history acceptance checks

1. Sign in using a valid test user and open `/research`.
2. Confirm the page loads the most recent 100 `walk_forward_runs` visible under the signed-in user's workspace RLS.
3. For each row, inspect instrument, asset class/timeframe, effective data window, run status, creation time, run ID, run hash, strategy/algorithm version, fold count, observation count, condition metrics, configuration and summary.
4. For `insufficient_data` records, confirm every stored `summary.coverage_gaps` reason is shown explicitly. Missing reasons must be reported as missing, not inferred.
5. Confirm a run with no folds or observations is never presented as a successful evaluation. A stored `liquidity_shock_proxy` is an OHLCV proxy, not order-book liquidity.

## Evidence-ledger acceptance checks

1. Apply the reviewed `research_evidence_ledger` migration before expecting the evidence query to succeed.
2. Confirm records show evidence ID and type, claim, instrument, source and source version, optional HTTP(S) source URI, occurred/published/received times, freshness, quality, value, and content hash.
3. Confirm each evidence row links to its associated research run.
4. Confirm the empty state says no records are persisted; it must not imply that specialist agents, bull/bear debate, or evidence resolution have executed.
5. Confirm an absent table is shown as a schema/migration prerequisite, not silently treated as a verified empty ledger.
6. Verify users cannot insert, update, or delete evidence through the browser. Evidence writes must be made by a trusted research service only.

## Authorization and deployment checks

- Signed-out users visiting `/research` are redirected to `/auth`.
- Signed-in users only see runs/evidence allowed by workspace RLS. Test with two separate workspaces and confirm no cross-workspace disclosure.
- The evidence table has RLS enabled, an explicit workspace-member SELECT policy, and no client write grants.
- Inspect the deployed build after the migration is applied; verify the production route and browser console.
- Check CI typecheck, lint, build, and deterministic Python tests on the pull request before merging.

## Phase 3 exit gate — what the UI alone does not prove

A visible history page is necessary but not sufficient for Phase 3 completion. The exit gate remains blocked until the implementation and evidence demonstrate:

- Specialist research agents are actually invoked and produce typed, versioned outputs.
- Material claims cite persisted evidence IDs with provenance and point-in-time freshness.
- Bull/bear arguments and explicit disagreement are persisted and inspectable.
- An evidence resolver distinguishes consensus, conflict, unknowns, and source-quality conflicts.
- Runs are reproducible and traceable from source data through agent outputs and final research synthesis.
- Missing/stale data leads to explicit abstention/insufficient-data states, not fabricated conclusions.

No live/paper execution, broker connectivity, or risk-policy promotion is part of this acceptance.
