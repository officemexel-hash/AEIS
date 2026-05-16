---
name: panel-generator
description: Generates complete operator console panels with RBAC
---

# Panel Generator

## When to use
- When creating new operator panels
- During UI sprint

## Inputs
- panel_name, data_endpoints, user_roles, ws_channel

## Outputs
- Page, components, API hooks, RBAC gate, loading/error states

## Safety rules
- Frontend RBAC is UX only, backend enforcement required

## Properties
- parallel-safe: true
- idempotent: true
