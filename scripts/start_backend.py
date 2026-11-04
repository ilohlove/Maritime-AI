"""Single-worker backend entry point behind an explicitly trusted HTTPS proxy."""

import ipaddress
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import uvicorn
from app.core.config import Settings


def main():
    settings = Settings()
    proxies = os.environ.get("MARITIME_TRUSTED_PROXY_IPS", "")
    if settings.environment == "production" and not proxies:
        raise ValueError(
            "Configure MARITIME_TRUSTED_PROXY_IPS for the actual HTTPS ingress"
        )
    for proxy in proxies.split(","):
        if proxy.strip():
            network = ipaddress.ip_network(proxy.strip(), strict=False)
            if network.prefixlen == 0:
                raise ValueError("Do not trust all addresses for forwarded headers")
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=os.environ.get("MARITIME_BIND_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        workers=1,
        proxy_headers=bool(proxies),
        forwarded_allow_ips=proxies or "",
        server_header=False,
    )


if __name__ == "__main__":
    main()
