# Agent State Schema

The workflow state is append-only by stage.

```text
DecisionState
  run
  market_snapshot
  market_state
  evidence[]
  analyst_reports[]
  research_state
  trade_proposal?
  risk_assessment?
  policy_decision?
  execution_plan?
  final_decision?
```

## Invariants
- Earlier artifacts are immutable.
- Each stage records input state IDs and output artifact IDs.
- State transitions are idempotent.
- A retry must not duplicate orders or evidence.
- Any state used for execution is frozen and content-addressable/versioned.

## Confidence dimensions
Do not expose a single unexplained confidence score. Record:
- data_confidence
- technical_confidence
- macro_confidence
- event_confidence
- execution_confidence
- model_agreement
- unresolved_disagreement

A composite score, if used, is derived by deterministic configuration and is never treated as a probability without calibration evidence.

## Abstention
Agents can return:
- INSUFFICIENT_DATA
- STALE_DATA
- CONFLICTING_EVIDENCE
- OUT_OF_SCOPE
- LOW_CONFIDENCE

Abstention is a valid successful outcome.
