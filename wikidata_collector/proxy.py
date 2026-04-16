"""Proxy rotation and validation for Wikidata requests (no FastAPI dependencies)."""

import logging
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .exceptions import ProxyMisconfigurationError

logger = logging.getLogger(__name__)

# Security: Allowed proxy schemes and blocked hosts for SSRF prevention
ALLOWED_PROXY_SCHEMES = {"http", "https"}
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_internal_host(hostname: str) -> bool:
    """Check if hostname is an internal/private IP address."""
    if hostname in BLOCKED_HOSTS:
        return True
    # Check private IP ranges
    if hostname.startswith("192.168.") or hostname.startswith("10."):
        return True
    # Check 172.16.0.0/12 range (172.16.0.0 - 172.31.255.255)
    if hostname.startswith("172."):
        parts = hostname.split(".")
        if len(parts) >= 2:
            try:
                second_octet = int(parts[1])
                if 16 <= second_octet <= 31:
                    return True
            except ValueError:
                pass
    return False


def validate_proxy_list(proxy_list: List[str]) -> List[str]:
    """Validate a list of proxy URLs and return only valid ones.

    Args:
        proxy_list: List of proxy URLs to validate.

    Returns:
        List of validated proxy URLs (empty entries are silently skipped).

    Raises:
        ProxyMisconfigurationError: If any proxy URL is malformed, has an invalid scheme,
            has no hostname, or targets an internal/private host.
    """
    validated_proxies = []
    for proxy in proxy_list:
        proxy = proxy.strip()
        if not proxy:
            continue

        try:
            parsed = urlparse(proxy)
            # Validate scheme
            if parsed.scheme not in ALLOWED_PROXY_SCHEMES:
                raise ProxyMisconfigurationError(
                    f"Proxy has an invalid or missing scheme (expected 'http' or 'https'): {proxy!r}. "
                    f"Ensure your proxy URL starts with 'http://' or 'https://'."
                )
            # Block internal hosts
            hostname = parsed.hostname
            if not hostname:
                raise ProxyMisconfigurationError(f"Proxy URL has no hostname: {proxy!r}.")
            if _is_internal_host(hostname):
                raise ProxyMisconfigurationError(
                    f"Proxy targets an internal/private host '{hostname}', which is not allowed: {proxy!r}."
                )
            validated_proxies.append(proxy)
        except ProxyMisconfigurationError:
            raise
        except Exception as e:
            raise ProxyMisconfigurationError(
                f"Proxy URL could not be parsed: {proxy!r}. Error: {e}"
            ) from e

    return validated_proxies


class ProxyManager:
    """Manages proxy rotation with failure detection and cooldown."""

    def __init__(
        self,
        proxy_list: Optional[List[str]] = None,
        timeout_per_hop: int = 60,
        cooldown_period: int = 300,
    ):
        """Initialize proxy manager.

        Args:
            proxy_list: List of proxy URLs to use
            timeout_per_hop: Timeout in seconds for each request
            cooldown_period: Cooldown period in seconds for failed proxies
        """
        self.proxies = validate_proxy_list(proxy_list) if proxy_list else []
        self.failed_proxies: Dict[str, float] = {}  # proxy -> failure_time
        self.current_index = 0
        self.cooldown_period = cooldown_period
        self.timeout_per_hop = timeout_per_hop

        if self.proxies:
            logger.info(f"Loaded {len(self.proxies)} validated proxies")

    def get_available_proxies(self, override_proxies: Optional[List[str]] = None) -> List[str]:
        """Get list of available proxies, filtering out failed ones.

        Args:
            override_proxies: Optional list of proxies to use instead of configured ones

        Returns:
            List of available proxy URLs
        """
        # Use override proxies if provided
        if override_proxies:
            return validate_proxy_list(override_proxies)

        # Use configured proxies
        current_time = time.time()
        available = []

        for proxy in self.proxies:
            if proxy in self.failed_proxies:
                # Check if cooldown period has passed
                if current_time - self.failed_proxies[proxy] > self.cooldown_period:
                    del self.failed_proxies[proxy]
                    available.append(proxy)
            else:
                available.append(proxy)

        return available

    def get_next_proxy(self, override_proxies: Optional[List[str]] = None) -> Optional[str]:
        """Get next proxy using round-robin strategy.

        Args:
            override_proxies: Optional list of proxies to use instead of configured ones

        Returns:
            Proxy URL or None if no proxies available
        """
        available_proxies = self.get_available_proxies(override_proxies)

        if not available_proxies:
            return None

        # Round-robin selection
        proxy = available_proxies[self.current_index % len(available_proxies)]
        self.current_index += 1
        return proxy

    def mark_proxy_failed(self, proxy: str):
        """Mark a proxy as failed and record the failure time."""
        self.failed_proxies[proxy] = time.time()
        logger.warning(f"Marked proxy {proxy} as failed")

    def reset_proxy(self, proxy: str) -> None:
        """Clear a proxy's failed status, making it available for selection again.

        Used after a deep-sleep period to allow retrying a single-proxy setup
        whose rotation service may have recovered.

        Args:
            proxy: The proxy URL to reset.
        """
        if proxy in self.failed_proxies:
            del self.failed_proxies[proxy]
            logger.info(f"Reset failed status for proxy {proxy}")

    def get_proxy_dict(self, proxy: str) -> Dict[str, str]:
        """Convert proxy URL to requests proxy dict."""
        if proxy.startswith("http://"):
            return {"http": proxy, "https": proxy}
        elif proxy.startswith("https://"):
            return {"http": proxy, "https": proxy}
        else:
            # Assume HTTP if no protocol specified
            return {"http": f"http://{proxy}", "https": f"http://{proxy}"}
