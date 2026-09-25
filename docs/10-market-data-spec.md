# Market Data Specification

## Canonical observation
```typescript
interface MarketObservation {
  instrument: string
  venue?: string
  instrumentType: "spot"|"perpetual"|"future"|"forex"
  timestamp: string
  receivedAt: string
  bid?: number
  ask?: number
  open?: number
  high?: number
  low?: number
  close?: number
  volume?: number
  source: string
  sourceVersion?: string
  qualityScore: number
}
```

## Freshness policy
TTL is field/provider/strategy specific. Example starting defaults:
- top-of-book: 1-2 seconds
- candles: one interval plus grace
- funding/OI: 1-5 minutes
- news: 5 minutes unless event-specific
- sentiment: 10 minutes
- macro regime: 1 hour
- tokenomics/static metadata: 1 day

These are defaults, not trading recommendations.

## Data quality
Score freshness, completeness, latency, source reliability and cross-source agreement.

## Crypto
Support 24/7 venue streams, spot/perpetual/futures, funding, OI, liquidations and on-chain feeds.

## Forex
Support 24/5 sessions, economic calendar, rates/yields, central-bank events and broker pricing.

## Point-in-time rule
No record may be visible to a replay before its source/publication time.
