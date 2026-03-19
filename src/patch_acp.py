import uvicorn.config
import typing
import acp_sdk.client

# 1. Patch for acp-sdk 1.0.3 + uvicorn 0.32+ compatibility (Server side)
# acp-sdk's Server class references types that were renamed/removed in newer uvicorn.
for attr in ["LoopSetupType", "HTTPProtocolType", "WSProtocolType", "LifespanType", "InterfaceType"]:
    if not hasattr(uvicorn.config, attr):
        setattr(uvicorn.config, attr, typing.Any)

# 2. Patch for acp-sdk 1.0.3 Client (Client side)
# The Client uses content=model.model_dump_json() but doesn't always set Content-Type,
# which can cause 422 errors on the server if it fails to parse the body as JSON.
_original_client_init = acp_sdk.client.Client.__init__

def _patched_client_init(self, *args, **kwargs):
    headers = kwargs.get("headers") or {}
    if isinstance(headers, dict):
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        if "Accept" not in headers:
            headers["Accept"] = "application/json"
    kwargs["headers"] = headers
    _original_client_init(self, *args, **kwargs)

acp_sdk.client.Client.__init__ = _patched_client_init

print("✓ ACP SDK runtime patches applied (uvicorn compatibility + client headers).")
