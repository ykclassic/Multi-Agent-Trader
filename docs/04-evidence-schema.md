# Evidence Schema

Evidence is the anti-hallucination backbone.

## Required fields
```json
{
  "evidence_id": "E...",
  "kind": "OBSERVED|CALCULATED|INFERRED",
  "claim": "human-readable claim",
  "value": {},
  "source": "provider",
  "instrument": "canonical instrument",
  "occurred_at": "source time",
  "published_at": "publication time when applicable",
  "received_at": "ingestion time",
  "freshness_ms": 1000,
  "quality_score": 0.98,
  "source_version": "v1",
  "content_hash": "..."
}
```

## Rules
- Material agent claims must cite evidence IDs.
- Evidence is immutable.
- Provider corrections create a new observation/version rather than rewriting history.
- Backtests only expose evidence whose published/occurred time is <= simulated decision time.
- Evidence freshness is evaluated against per-field TTL policy.
- External text is untrusted input and must be sanitized before entering prompts.

## Evidence ledger
Each decision run contains a ledger mapping:
claim -> evidence IDs -> source metadata -> freshness -> quality.
The UI should make this ledger inspectable.
