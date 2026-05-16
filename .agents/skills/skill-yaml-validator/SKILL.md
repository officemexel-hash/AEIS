---
name: skill-yaml-validator
description: Validates skill.yaml manifests against SYLION schema
---

# Skill YAML Validator

## When to use
- After creating or modifying any skill.yaml
- During skill registration

## Inputs
- skill.yaml path

## Outputs
- validation result with errors and warnings

## Checks
- Required fields present
- Type correctness
- Dependency resolution

## Properties
- parallel-safe: true
- idempotent: true
