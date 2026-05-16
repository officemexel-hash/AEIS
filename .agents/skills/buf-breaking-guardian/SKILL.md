---
name: buf-breaking-guardian
description: Validates proto files for breaking changes using buf conventions
---

# Buf Breaking Guardian

## When to use
- Before merging proto file changes
- During CI/CD pipeline
- After proto-contract-designer creates contracts

## Inputs
- proto_file_paths: list of .proto files
- against: git ref to compare against

## Outputs
- validation report (pass/fail with details)

## Safety rules
- BLOCKS merge on breaking changes to frozen contracts
- Warnings allowed for non-frozen contracts

## Properties
- parallel-safe: true
- idempotent: true
