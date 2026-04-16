"""
Unit tests for wikidata_collector/proxy.py
Focus on proxy URL validation and SSRF prevention
"""

import time

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
    """Test proxy list validation"""

    def test_valid_http_proxies(self):
        """Test that valid HTTP proxies are accepted"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 2
        assert validated[0] == "http://proxy1.example.com:8080"
        assert validated[1] == "http://proxy2.example.com:8080"

    def test_valid_https_proxies(self):
        """Test that valid HTTPS proxies are accepted"""
        proxies = ["https://proxy1.example.com:8443", "https://proxy2.example.com:8443"]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 2

    def test_reject_invalid_scheme_raises(self):
        """Test that proxies with invalid schemes raise ProxyMisconfigurationError"""
        with pytest.raises(ProxyMisconfigurationError, match="invalid or missing scheme"):
            validate_proxy_list(["ftp://proxy.example.com:8080"])

    def test_reject_socks_scheme_raises(self):
        """Test that socks5 scheme raises ProxyMisconfigurationError"""
        with pytest.raises(ProxyMisconfigurationError, match="invalid or missing scheme"):
            validate_proxy_list(["socks5://proxy.example.com:1080"])

    def test_reject_internal_host_raises(self):
        """Test that internal host proxies raise ProxyMisconfigurationError"""
        with pytest.raises(ProxyMisconfigurationError, match="internal/private host"):
            validate_proxy_list(["http://localhost:8080"])

    def test_reject_private_ip_raises(self):
        """Test that 192.168.x.x proxies raise ProxyMisconfigurationError"""
        with pytest.raises(ProxyMisconfigurationError, match="internal/private host"):
            validate_proxy_list(["http://192.168.1.1:8080"])

    def test_reject_10_subnet_raises(self):
        """Test that 10.x.x.x proxies raise ProxyMisconfigurationError"""
        with pytest.raises(ProxyMisconfigurationError, match="internal/private host"):
            validate_proxy_list(["http://10.0.0.1:8080"])

    def test_reject_127_loopback_raises(self):
        """Test that 127.0.0.1 proxies raise ProxyMisconfigurationError"""
        with pytest.raises(ProxyMisconfigurationError, match="internal/private host"):
            validate_proxy_list(["http://127.0.0.1:8080"])

    def test_mixed_list_with_invalid_raises(self):
        """Test that a mixed list raises on the first invalid proxy encountered"""
        proxies = [
            "http://valid-proxy.example.com:8080",
            "http://localhost:8080",  # Invalid — raises
            "https://another-valid.example.com:8443",
        ]
        with pytest.raises(ProxyMisconfigurationError):
            validate_proxy_list(proxies)

    def test_malformed_no_scheme_raises(self):
        """Test that a proxy without a scheme (colon-separated format) raises ProxyMisconfigurationError"""
        # e.g. rp.scrapegw.com:6060:user:pass — urlparse parses 'user' as scheme
        with pytest.raises(ProxyMisconfigurationError, match="invalid or missing scheme"):
            validate_proxy_list(["rp.scrapegw.com:6060:9ift2pyrnt4eg2m:zywcm236fqbpjft"])

    def test_empty_and_whitespace_proxies(self):
        """Test that empty strings and whitespace are filtered out"""
        proxies = ["", "  ", "http://valid.example.com:8080", "   "]
        validated = validate_proxy_list(proxies)
        assert len(validated) == 1
        assert validated[0] == "http://valid.example.com:8080"


class TestProxyManager:
    """Test ProxyManager configuration and behavior"""

    def test_initialization_with_valid_proxies(self):
        """Test ProxyManager initialization with valid proxy list"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies)
        assert len(manager.proxies) == 2
        assert manager.current_index == 0
        assert len(manager.failed_proxies) == 0

    def test_initialization_with_invalid_proxies_raises(self):
        """Test ProxyManager raises ProxyMisconfigurationError for invalid proxies during initialization"""
        proxies = [
            "http://valid.example.com:8080",
            "http://localhost:8080",  # Invalid — raises
        ]
        with pytest.raises(ProxyMisconfigurationError, match="internal/private host"):
            ProxyManager(proxy_list=proxies)

    def test_initialization_with_empty_list(self):
        """Test ProxyManager initialization with empty proxy list"""
        manager = ProxyManager(proxy_list=[])
        assert len(manager.proxies) == 0
        assert manager.get_next_proxy() is None

    def test_round_robin_proxy_selection(self):
        """Test that proxies are selected in round-robin fashion"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies)

        # First call returns first proxy
        proxy1 = manager.get_next_proxy()
        assert proxy1 == "http://proxy1.example.com:8080"

        # Second call returns second proxy
        proxy2 = manager.get_next_proxy()
        assert proxy2 == "http://proxy2.example.com:8080"

        # Third call wraps around to first proxy
        proxy3 = manager.get_next_proxy()
        assert proxy3 == "http://proxy1.example.com:8080"

    def test_mark_proxy_failed(self):
        """Test marking a proxy as failed"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies)

        # Mark first proxy as failed
        manager.mark_proxy_failed("http://proxy1.example.com:8080")

        # Verify it's in failed_proxies
        assert "http://proxy1.example.com:8080" in manager.failed_proxies
        assert len(manager.failed_proxies) == 1

    def test_failed_proxy_cooldown(self):
        """Test that failed proxies are excluded during cooldown period"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies, cooldown_period=2)

        # Mark first proxy as failed
        manager.mark_proxy_failed("http://proxy1.example.com:8080")

        # Get available proxies - should only return the second one
        available = manager.get_available_proxies()
        assert len(available) == 1
        assert available[0] == "http://proxy2.example.com:8080"

        # Wait for cooldown to expire
        time.sleep(2.1)

        # Now both should be available again
        available = manager.get_available_proxies()
        assert len(available) == 2

    def test_get_next_proxy_skips_failed(self):
        """Test that get_next_proxy skips failed proxies during cooldown"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies, cooldown_period=10)

        # Mark first proxy as failed
        manager.mark_proxy_failed("http://proxy1.example.com:8080")

        # Get next proxy - should return second one
        proxy = manager.get_next_proxy()
        assert proxy == "http://proxy2.example.com:8080"

        # Get next proxy again - should return second one again (wraps around but skips failed)
        proxy = manager.get_next_proxy()
        assert proxy == "http://proxy2.example.com:8080"

    def test_all_proxies_failed(self):
        """Test behavior when all proxies have failed"""
        proxies = ["http://proxy1.example.com:8080", "http://proxy2.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies, cooldown_period=10)

        # Mark all proxies as failed
        manager.mark_proxy_failed("http://proxy1.example.com:8080")
        manager.mark_proxy_failed("http://proxy2.example.com:8080")

        # Should return None when all proxies are failed
        proxy = manager.get_next_proxy()
        assert proxy is None

    def test_override_proxies(self):
        """Test that override_proxies parameter works correctly"""
        proxies = ["http://proxy1.example.com:8080"]
        manager = ProxyManager(proxy_list=proxies)

        # Use override proxies
        override = ["http://override.example.com:8080", "http://override2.example.com:8080"]
        proxy = manager.get_next_proxy(override_proxies=override)

        # Should return one of the override proxies, not the configured one
        assert proxy in override
        assert proxy != "http://proxy1.example.com:8080"

    def test_get_proxy_dict(self):
        """Test proxy URL to dict conversion"""
        manager = ProxyManager(proxy_list=[])

        # Test HTTP proxy
        proxy_dict = manager.get_proxy_dict("http://proxy.example.com:8080")
        assert proxy_dict == {
            "http": "http://proxy.example.com:8080",
            "https": "http://proxy.example.com:8080",
        }

        # Test HTTPS proxy
        proxy_dict = manager.get_proxy_dict("https://proxy.example.com:8443")
        assert proxy_dict == {
            "http": "https://proxy.example.com:8443",
            "https": "https://proxy.example.com:8443",
        }
