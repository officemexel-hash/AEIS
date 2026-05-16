"""
OpenHands SDK Shim — lightweight adapter for SYLION pipeline.

Replaces the full openhands-ai package (865+ dependencies, Docker, Playwright, etc.)
with a minimal implementation backed by litellm. Provides the same API surface used
by orchestrator.py, pipeline.py, agents/definitions.py, and agents/sdr_agents.py.

This shim implements ONLY the classes and functions actually used by SYLION:
  - LLM (wraps litellm.completion)
  - Conversation (task runner: send_message → run → collect stats)
  - Agent, AgentContext, Tool, Skill (data containers)
  - DelegationVisualizer (no-op visual helper)
  - TerminalTool, FileEditorTool, TaskToolSet (tool name constants)
  - content_to_str (message content normalizer)
  - register_agent (no-op registration)
"""
