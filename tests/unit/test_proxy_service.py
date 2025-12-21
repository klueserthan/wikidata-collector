"""
Unit tests for wikidata_collector/proxy.py
Focus on proxy URL validation and SSRF prevention
"""

import pytest

from wikidata_collector.exceptions import ProxyMisconfigurationError
from wikidata_collector.proxy import ProxyManager, _is_internal_host, validate_proxy_list


class TestIsInternalHost:
    """Test the _is_internal_host helper function"""

    def test_blocked_localhost_variants(self):
        """Test that localhost variants are blocked"""
        assert _is_internal_host("localhost") is True
        assert _is_internal_host("127.0.0.1") is True
        assert _is_internal_host("0.0.0.0") is True
        assert _is_internal_host("::1") is True

    def test_private_ip_192_168(self):
        """Test that 192.168.x.x addresses are blocked"""
        assert _is_internal_host("192.168.1.1") is True
        assert _is_internal_host("192.168.0.1") is True
        assert _is_internal_host("192.168.255.255") is True

    def test_private_ip_10(self):
        """Test that 10.x.x.x addresses are blocked"""
        assert _is_internal_host("10.0.0.1") is True
        assert _is_internal_host("10.1.1.1") is True
        assert _is_internal_host("10.255.255.255") is True

    def test_private_ip_172_16_to_31(self):
        """Test that 172.16.0.0 - 172.31.255.255 addresses are blocked"""
        assert _is_internal_host("172.16.0.1") is True
        assert _is_internal_host("172.20.0.1") is True
        assert _is_internal_host("172.31.255.255") is True
        # Edge cases - should not be blocked
        assert _is_internal_host("172.15.0.1") is False
        assert _is_internal_host("172.32.0.1") is False

    def test_public_ips(self):
        """Test that public IPs are allowed"""
        assert _is_internal_host("8.8.8.8") is False
        assert _is_internal_host("1.1.1.1") is False
        assert _is_internal_host("example.com") is False
        assert _is_internal_host("proxy.example.com") is False


class TestValidateProxyList:
    """Test the validate_proxy_list function"""

    def test_valid_http_proxies(self):
        """Test that valid HTTP proxies are accepted"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:3128"]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 2
        assert validated == proxies

    def test_valid_https_proxies(self):
        """Test that valid HTTPS proxies are accepted"""
        proxies = ["https://proxy1.example.com:8080"]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 1
        assert validated == proxies

    def test_reject_internal_hosts(self):
        """Test that internal hosts are rejected"""
        proxies = [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://192.168.1.1:8080",
            "http://10.0.0.1:8080",
        ]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 0

    def test_reject_invalid_schemes(self):
        """Test that invalid schemes are rejected"""
        proxies = ["ftp://proxy.example.com:8080", "socks5://proxy.example.com:8080"]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 0

    def test_reject_malformed_urls(self):
        """Test that malformed URLs are rejected"""
        proxies = ["not-a-url", ":/missing-scheme", "http://"]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 0

    def test_mixed_valid_and_invalid(self):
        """Test that only valid proxies are returned from mixed list"""
        proxies = [
            "http://proxy.example.com:8080",  # valid
            "http://localhost:8080",  # invalid - localhost
            "https://proxy2.example.com:3128",  # valid
            "ftp://proxy3.example.com:8080",  # invalid - wrong scheme
        ]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 2
        assert "http://proxy.example.com:8080" in validated
        assert "https://proxy2.example.com:3128" in validated


class TestProxyManagerFallback:
    """Test ProxyManager fallback behavior"""

    def test_fallback_disabled_by_default(self):
        """Test that fallback to direct access is disabled by default"""
        manager = ProxyManager(proxy_list=["http://proxy.example.com:8080"])
        assert manager.fallback_to_direct is False

    def test_fallback_enabled_when_configured(self):
        """Test that fallback can be explicitly enabled"""
        manager = ProxyManager(
            proxy_list=["http://proxy.example.com:8080"], fallback_to_direct=True
        )
        assert manager.fallback_to_direct is True

    def test_fail_closed_when_all_proxies_failed(self):
        """Test that manager raises error when all proxies fail and fallback is disabled"""
        manager = ProxyManager(
            proxy_list=["http://proxy.example.com:8080"], fallback_to_direct=False
        )

        # Mark the only proxy as failed
        manager.mark_proxy_failed("http://proxy.example.com:8080")

        # Should raise ProxyMisconfigurationError
        with pytest.raises(ProxyMisconfigurationError) as exc_info:
            manager.get_next_proxy()

        assert "fallback_to_direct" in str(exc_info.value).lower()

    def test_fallback_to_direct_when_enabled(self):
        """Test that manager returns None (direct access) when fallback is enabled"""
        manager = ProxyManager(
            proxy_list=["http://proxy.example.com:8080"], fallback_to_direct=True
        )

        # Mark the only proxy as failed
        manager.mark_proxy_failed("http://proxy.example.com:8080")

        # Should return None (allowing direct access)
        proxy = manager.get_next_proxy()
        assert proxy is None

    def test_no_proxies_configured_allows_direct(self):
        """Test that no proxies configured allows direct access regardless of fallback setting"""
        manager = ProxyManager(proxy_list=None, fallback_to_direct=False)
        proxy = manager.get_next_proxy()
        assert proxy is None

    def test_multiple_proxies_fail_closed(self):
        """Test fail-closed behavior with multiple proxies"""
        manager = ProxyManager(
            proxy_list=["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"],
            fallback_to_direct=False,
        )

        # Mark all proxies as failed
        manager.mark_proxy_failed("http://proxy1.example.com:8080")
        manager.mark_proxy_failed("http://proxy2.example.com:8080")

        # Should raise ProxyMisconfigurationError
        with pytest.raises(ProxyMisconfigurationError):
            manager.get_next_proxy()

    def test_proxy_cooldown_recovery(self):
        """Test that proxies become available again after cooldown period"""
        manager = ProxyManager(
            proxy_list=["http://proxy.example.com:8080"],
            cooldown_period=0,  # Immediate recovery for testing
            fallback_to_direct=False,
        )

        # Mark proxy as failed
        manager.mark_proxy_failed("http://proxy.example.com:8080")

        # After cooldown (0 seconds), proxy should be available again
        proxy = manager.get_next_proxy()
        assert proxy == "http://proxy.example.com:8080"


class TestProxyManagerRoundRobin:
    """Test ProxyManager round-robin selection"""

    def test_round_robin_selection(self):
        """Test that proxies are selected in round-robin fashion"""
        manager = ProxyManager(
            proxy_list=["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        )

        # Get proxies in sequence
        proxy1 = manager.get_next_proxy()
        proxy2 = manager.get_next_proxy()
        proxy3 = manager.get_next_proxy()

        # Should cycle through proxies
        assert proxy1 == "http://proxy1.example.com:8080"
        assert proxy2 == "http://proxy2.example.com:8080"
        assert proxy3 == "http://proxy1.example.com:8080"  # Back to first

    def test_get_proxy_dict(self):
        """Test conversion of proxy URL to requests proxy dict"""
        manager = ProxyManager()

        # HTTP proxy
        proxy_dict = manager.get_proxy_dict("http://proxy.example.com:8080")
        assert proxy_dict == {
            "http": "http://proxy.example.com:8080",
            "https": "http://proxy.example.com:8080",
        }

        # HTTPS proxy
        proxy_dict = manager.get_proxy_dict("https://proxy.example.com:8080")
        assert proxy_dict == {
            "http": "https://proxy.example.com:8080",
            "https": "https://proxy.example.com:8080",
        }
