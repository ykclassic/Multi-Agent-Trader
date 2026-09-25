# Security Model

## Trust zones
1. Browser/UI: untrusted.
2. Application/control plane: authenticated user operations.
3. Intelligence plane: untrusted model outputs.
4. Risk/policy plane: trusted deterministic controls.
5. Execution plane: highly privileged.
6. Venue/broker: external system.

## Secrets
Broker/exchange credentials never enter prompts, browser state or analyst processes. Execution service retrieves scoped secrets from secure secret storage.

## Prompt injection
External news/social text is untrusted. Strip/label instructions from retrieved content and never treat them as system/developer instructions.

## Authorization
Workspace membership and role determine access. RLS protects user-owned records. Execution requires explicit workspace/strategy permission.

## Operational security
Use least privilege, key rotation, audit logs, rate limits, webhook signature validation, encrypted transport, secure secret storage and emergency kill switches.
