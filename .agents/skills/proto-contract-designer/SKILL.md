---
name: proto-contract-designer
description: Designs gRPC .proto contract files for SYLION modules
---

# Proto Contract Designer

## When to use
- Before implementing any new module
- When extending existing service definitions
- During Contract Freeze milestone (M0)

## Inputs
- module_id: string
- services: list of service names with RPC methods
- messages: list of message definitions

## Outputs
- .proto file with services, messages, enums

## Safety rules
- NEVER modify frozen contracts without D3+ governance
- Field numbers must be unique within a message
- Never reuse field numbers after removal
- New fields added at the end

## Properties
- parallel-safe: true
- idempotent: false
