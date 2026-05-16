---
name: skill-executor-implementer
description: Implements Skills Executor service (Plan 18) - sandbox execution, timeout, result capture
---

# Skill Executor Implementer

## When to use
- When building skills execution engine
- Running skill operations

## Inputs
- skill_id, parameters

## Outputs
- Execution result with status, output, metrics

## Safety rules
- Skills run in sandbox
- Timeout enforced
- Resources limited
- Side effects tracked

## Properties
- parallel-safe: true
- idempotent: false
