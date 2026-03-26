class CloudflareAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Cloudflare API error {status_code}: {message}")
