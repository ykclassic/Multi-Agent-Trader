# Agent Contracts

## Shared contract
Every agent receives a MarketState reference, relevant evidence, portfolio/risk context allowed by policy, task instructions and an output schema.

Every agent must:
- cite evidence IDs for material claims;
- distinguish observation from inference;
- state uncertainty;
- abstain when required data is unavailable or stale;
- never invent prices, balances, orders or events;
- never issue an executable order.

## Agents
### Technical Analyst
Trend, structure, momentum, volatility, support/resistance, multi-timeframe context.

### Macro Analyst
FX rates, inflation, employment, central-bank policy, yields, economic calendar, risk regime; for crypto, relevant macro regime only.

### News/Event Analyst
Entity extraction, event classification, novelty, source quality, expected exposure and time decay.

### Sentiment Analyst
Change and direction of sentiment across approved sources. Separates discussion volume from sentiment direction.

### On-chain Analyst
Crypto-only: exchange flows, whale activity, stablecoins, network activity, protocol metrics and anomalies.

### Derivatives Analyst
Crypto: funding, open interest, basis, liquidations, options IV/skew. FX: derivatives/rates data where available.

### Liquidity/Microstructure Analyst
Spread, depth, imbalance, estimated impact, liquidity concentration and venue divergence.

### Tokenomics/Fundamentals Analyst
Crypto token supply/emissions/unlocks/fees/revenue/staking/treasury. FX fundamental data is handled by Macro Analyst.

### Bull Researcher
Builds the strongest evidence-backed bullish/positive case and explicit invalidations.

### Bear Researcher
Builds the strongest evidence-backed bearish/negative case and explicit invalidations.

### Evidence Resolver / Research Manager
Separates consensus, disagreement, unknowns and evidence-quality conflicts.

### Trader
Produces a structured non-executable trade proposal including entry concept, invalidation, target concept, horizon, thesis and confidence dimensions.

### Risk Debate Agents
Aggressive, Conservative and Neutral agents challenge the proposal qualitatively inside deterministic risk boundaries.

### Portfolio Manager
Synthesizes research and risk into APPROVE, REJECT or DEFER recommendation. It cannot bypass Policy Gate.

## Output envelope
All agent outputs include:
agent_id, agent_version, run_id, market_state_id, evidence_ids, confidence_dimensions, assumptions, invalidations, created_at, schema_version.
