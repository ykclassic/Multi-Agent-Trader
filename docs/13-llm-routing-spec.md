# LLM Routing Specification

## Principle
Use the least expensive model that meets the task's reasoning and reliability requirement.

## Routing classes
- Fast: extraction, classification, formatting, routine summaries.
- Standard: analyst interpretation and synthesis.
- Strong reasoning: Bull/Bear, evidence conflict resolution, risk debate and PM.

## Required metadata
Every call records:
model_provider
model
model_version
prompt_version
schema_version
temperature/decoding config
input token count
output token count
latency
cost
tool calls

## Structured output
All decision-relevant responses use JSON-schema constrained outputs. Free-form prose is presentation-only.

## Reliability
Failed/invalid structured outputs are retried with bounded attempts. Repeated failure causes agent abstention, never an execution bypass.
