---
name: demand-signal-clusterer
description: Implements Demand Signal Analyzer (Plan 20) - collection, clustering, skill demand prediction
---

# Demand Signal Clusterer

## When to use
- When analyzing skill demand
- During skill planning

## Inputs
- signal data, clustering config

## Outputs
- Clustered demand signals
- Skill demand predictions

## Pattern
SQLite-backed, thread-safe access.

## Properties
- parallel-safe: true
- idempotent: true
