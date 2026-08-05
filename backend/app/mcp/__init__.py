"""MCP 接入层：官方 mcp SDK FastMCP，业务走 capabilities。"""

from app.mcp.server import main, mcp

__all__ = ["mcp", "main"]
