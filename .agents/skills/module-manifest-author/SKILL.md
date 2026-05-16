---
name: module-manifest-author
description: Creates manifest.yaml for SYLION modules
---

# Module Manifest Author

## When to use
- When scaffolding a new module
- When updating module metadata

## Inputs
- module_id, class, dependencies, events_produced, events_consumed

## Outputs
- manifest.yaml

## Safety rules
- module_id must be unique
- dependencies must exist
- events follow domain.event.action taxonomy

## Properties
- parallel-safe: true
- idempotent: true
