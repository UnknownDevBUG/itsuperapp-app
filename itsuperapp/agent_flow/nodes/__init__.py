"""Agent Flow node executor modules.

Each module here registers one or more node types via
`itsuperapp.agent_flow.node_registry.node`. Real business node types are
#50's scope ("Core Frappe nodes and run-history hardening"); the modules
in this package exist only to prove the registration/hook-loading pattern
works end to end and to give the registry's own tests something real to
register against.
"""

from __future__ import annotations
