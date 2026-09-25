# Architecture Blueprint

This directory is the implementation contract for the Multi-Agent Trader platform.

## Read in order
1. [System Architecture](00-system-architecture.md)
2. [Domain Model](01-domain-model.md)
3. [Agent Contracts](02-agent-contracts.md)
4. [Agent State](03-agent-state-schema.md)
5. [Evidence](04-evidence-schema.md)
6. [Tool Contracts](05-tool-contracts.md)
7. [Debate Protocol](06-debate-protocol.md)
8. [Risk Engine](07-risk-engine-spec.md)
9. [Policy Engine](08-policy-engine-spec.md)
10. [Execution](09-execution-engine-spec.md)
11. [Market Data](10-market-data-spec.md)
12. [Backtesting](11-backtesting-spec.md)
13. [Strategy](12-strategy-spec.md)
14. [LLM Routing](13-llm-routing-spec.md)
15. [Observability](14-observability-spec.md)
16. [Security](15-security-model.md)
17. [Supabase Schema](16-supabase-schema.md)
18. [API Contracts](17-api-contracts.md)
19. [Events](18-event-schema.md)
20. [Testing](19-testing-strategy.md)
21. [Implementation Principles](20-implementation-principles.md)
22. [Eight-Phase Roadmap](ROADMAP.md)

## Architecture rule
The blueprint intentionally separates intelligence from authority: LLMs produce typed, evidence-grounded reasoning; deterministic quant/risk/policy services calculate and constrain; only the execution service can access broker/exchange credentials.

## Scope
Crypto and forex only. Stocks are excluded.
