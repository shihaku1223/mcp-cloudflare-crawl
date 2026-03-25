import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_api_token() -> str:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        raise RuntimeError("CLOUDFLARE_API_TOKEN environment variable is not set")
    return token


def get_account_id() -> str:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not account_id:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID environment variable is not set")
    return account_id


def get_db_path() -> Path:
    raw = os.environ.get("MCP_DB_PATH")
    if raw:
        return Path(raw)
    default = Path.home() / ".local" / "share" / "mcp-cloudflare-crawl" / "jobs.db"
    return default
