import argparse
import asyncio

import uvicorn

from .server import mcp


async def _serve_http(host: str, port: int, shutdown_timeout: int) -> None:
    app = mcp.streamable_http_app()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        timeout_graceful_shutdown=shutdown_timeout,
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloudflare Crawl API MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for streamable-http transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for streamable-http transport (default: 8000)",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=int,
        default=5,
        help="Seconds to wait for active connections to close on shutdown (default: 5)",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        asyncio.run(_serve_http(args.host, args.port, args.shutdown_timeout))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
