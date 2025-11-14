
import logging
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import Request

from api.config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security: Allowed proxy schemes and blocked hosts for SSRF prevention
ALLOWED_PROXY_SCHEMES = {'http', 'https'}
BLOCKED_HOSTS = {'localhost', '127.0.0.1', '0.0.0.0', '::1'}


def _is_internal_host(hostname: str) -> bool:
    """Check if hostname is an internal/private IP address."""
    if hostname in BLOCKED_HOSTS:
        return True
    # Check private IP ranges
    if hostname.startswith('192.168.') or hostname.startswith('10.'):
        return True
    # Check 172.16.0.0/12 range (172.16.0.0 - 172.31.255.255)
    if hostname.startswith('172.'):
        parts = hostname.split('.')
        if len(parts) >= 2:
            try:
                second_octet = int(parts[1])
                if 16 <= second_octet <= 31:
                    return True
            except ValueError:
                pass
    return False


class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.failed_proxies = {}  # proxy -> failure_time
        self.current_index = 0
        self.cooldown_period = 300  # 5 minutes
        self.timeout_per_hop = config.SPARQL_TIMEOUT_SECONDS
        
        # Load proxies from environment variable
        env_proxies = config.proxy_list_values
        if env_proxies:
            self.proxies = env_proxies
            logger.info(f"Loaded {len(self.proxies)} proxies from environment")
    
    def get_proxies_from_header(self, request: Request) -> List[str]:
        """Get proxy list from X-Proxy-List header with validation."""
        proxy_header = request.headers.get('X-Proxy-List', '')
        if not proxy_header:
            return []
        
        validated_proxies = []
        for proxy in proxy_header.split(','):
            proxy = proxy.strip()
            if not proxy:
                continue
            
            try:
                parsed = urlparse(proxy)
                # Validate scheme
                if parsed.scheme not in ALLOWED_PROXY_SCHEMES:
                    logger.warning(f"Rejected proxy with invalid scheme: {proxy}")
                    continue
                # Block internal hosts
                hostname = parsed.hostname
                if not hostname:
                    logger.warning(f"Rejected proxy with no hostname: {proxy}")
                    continue
                if _is_internal_host(hostname):
                    logger.warning(f"Rejected proxy with internal host: {proxy}")
                    continue
                validated_proxies.append(proxy)
            except Exception as e:
                logger.warning(f"Rejected malformed proxy: {proxy}, error: {e}")
        
        return validated_proxies
    
    def get_available_proxies(self, request: Optional[Request] = None) -> List[str]:
        """Get list of available proxies, filtering out failed ones."""
        # Check for request-specific proxies first
        if request:
            request_proxies = self.get_proxies_from_header(request)
            if request_proxies:
                return request_proxies
        
        # Use environment proxies
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
    
    def get_next_proxy(self, request: Optional[Request] = None) -> Optional[str]:
        """Get next proxy using round-robin strategy."""
        available_proxies = self.get_available_proxies(request)
        
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
    
    def get_proxy_dict(self, proxy: str) -> Dict[str, str]:
        """Convert proxy URL to requests proxy dict."""
        if proxy.startswith('http://'):
            return {'http': proxy, 'https': proxy}
        elif proxy.startswith('https://'):
            return {'http': proxy, 'https': proxy}
        else:
            # Assume HTTP if no protocol specified
            return {'http': f'http://{proxy}', 'https': f'http://{proxy}'}