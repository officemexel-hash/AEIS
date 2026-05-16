---
name: skill-registry-implementer
description: Implements Skills Registry service (Plan 18) - CRUD, lifecycle DRAFT->PUBLISHED->DEPRECATED
---

# Skill Registry Implementer

## When to use
- When building skills infrastructure
- Managing skill lifecycle

## Inputs
- skill definition

## Outputs
- Registry CRUD operations
- Lifecycle state transitions

## Safety rules
- Registry is singleton
- DRAFT->PUBLISHED requires validation
- PUBLISHED->DEPRECATED requires reason

## Properties
- parallel-safe: false
- idempotent: true
