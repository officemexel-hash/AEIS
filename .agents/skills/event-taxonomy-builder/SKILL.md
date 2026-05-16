---
name: event-taxonomy-builder
description: Designs event taxonomy for SYLION modules (domain.event.action format)
---

# Event Taxonomy Builder

## When to use
- When defining new event types
- During manifest creation

## Inputs
- module_id, domain, actions list

## Outputs
- Event definitions in manifest.yaml format

## Safety rules
- Event taxonomy FROZEN after Contract Freeze
- Changing existing events requires D3+

## Properties
- parallel-safe: true
- idempotent: false
