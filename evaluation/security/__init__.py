"""MCPSEC-style 10-property security evaluation suite.

Each property probes a specific attack surface that an MCP-using agent
must defend against. The PDF (and the original MCPSEC paper) describes
the properties and their OWASP ASI mappings; we encode them as
``SECURITY_PROPERTIES`` for the grader and adapter to consume.

The suite ships with a hermetic ``mock_mcp_server.py`` that simulates
each attack vector in isolation; ``mcp_security_adapter.py`` drives
the actual harness against the mock and grades the output.
"""

from evaluation.security.properties import SECURITY_PROPERTIES, SECURITY_PROPERTY_INDEX

__all__ = ["SECURITY_PROPERTIES", "SECURITY_PROPERTY_INDEX"]
