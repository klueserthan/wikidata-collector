"""
Unit tests for wikidata_collector/proxy.py
Focus on proxy URL validation and SSRF prevention
"""
from wikidata_collector.proxy import _is_internal_host


class TestIsInternalHost:
    """Test the _is_internal_host helper function"""
    
    def test_blocked_localhost_variants(self):
        """Test that localhost variants are blocked"""
        assert _is_internal_host('localhost') is True
        assert _is_internal_host('127.0.0.1') is True
        assert _is_internal_host('0.0.0.0') is True
        assert _is_internal_host('::1') is True
    
    def test_private_ip_192_168(self):
        """Test that 192.168.x.x addresses are blocked"""
        assert _is_internal_host('192.168.1.1') is True
        assert _is_internal_host('192.168.0.1') is True
        assert _is_internal_host('192.168.255.255') is True
    
    def test_private_ip_10(self):
        """Test that 10.x.x.x addresses are blocked"""
        assert _is_internal_host('10.0.0.1') is True
        assert _is_internal_host('10.1.1.1') is True
        assert _is_internal_host('10.255.255.255') is True
    
    def test_private_ip_172_16_to_31(self):
        """Test that 172.16.0.0 - 172.31.255.255 addresses are blocked"""
        assert _is_internal_host('172.16.0.1') is True
        assert _is_internal_host('172.20.0.1') is True
        assert _is_internal_host('172.31.255.255') is True
        # Edge cases - should not be blocked
        assert _is_internal_host('172.15.0.1') is False
        assert _is_internal_host('172.32.0.1') is False
    
    def test_public_ips(self):
        """Test that public IPs are allowed"""
        assert _is_internal_host('8.8.8.8') is False
        assert _is_internal_host('1.1.1.1') is False
        assert _is_internal_host('example.com') is False
        assert _is_internal_host('proxy.example.com') is False
