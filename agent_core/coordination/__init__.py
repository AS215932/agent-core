"""LHP-v2 client helpers.

Importing this package requires the optional ``coordination-client`` extra;
the core contracts remain dependency-light.
"""

from agent_core.coordination.auth import LoopRequestSigner, build_signature
from agent_core.coordination.client import CoordinatorClient, CoordinatorError

__all__ = ["CoordinatorClient", "CoordinatorError", "LoopRequestSigner", "build_signature"]
