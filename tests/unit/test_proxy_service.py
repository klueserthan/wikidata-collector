"""
Unit tests for infrastructure/proxy_service.py
Focus on proxy URL validation and SSRF prevention
"""
import pytest
from unittest.mock import Mock
from infrastructure.proxy_service import ProxyManager, _is_internal_host


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


class TestProxyManagerValidation:
    """Test ProxyManager.get_proxies_from_header validation"""
    
    def test_valid_http_proxy(self):
        """Test that valid HTTP proxies are accepted"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://proxy.example.com:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == ['http://proxy.example.com:8080']
    
    def test_valid_https_proxy(self):
        """Test that valid HTTPS proxies are accepted"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'https://secure-proxy.example.com:443'
        
        result = manager.get_proxies_from_header(request)
        assert result == ['https://secure-proxy.example.com:443']
    
    def test_multiple_valid_proxies(self):
        """Test that multiple valid proxies are accepted"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://proxy1.example.com:8080, https://proxy2.example.com:443'
        
        result = manager.get_proxies_from_header(request)
        assert len(result) == 2
        assert 'http://proxy1.example.com:8080' in result
        assert 'https://proxy2.example.com:443' in result
    
    def test_reject_file_scheme(self):
        """Test that file:// URLs are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'file:///etc/passwd'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_ftp_scheme(self):
        """Test that ftp:// URLs are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'ftp://ftp.example.com'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_localhost(self):
        """Test that localhost is rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://localhost:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_127_0_0_1(self):
        """Test that 127.0.0.1 is rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://127.0.0.1:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_192_168_internal(self):
        """Test that 192.168.x.x addresses are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://192.168.1.1:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_10_internal(self):
        """Test that 10.x.x.x addresses are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://10.0.0.1:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_172_16_to_31_internal(self):
        """Test that 172.16-31.x.x addresses are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://172.20.0.1:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_accept_172_outside_private_range(self):
        """Test that 172.x.x.x outside 16-31 range is accepted"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://172.32.0.1:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == ['http://172.32.0.1:8080']
    
    def test_reject_malformed_url(self):
        """Test that malformed URLs are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'not-a-valid-url'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_reject_url_without_hostname(self):
        """Test that URLs without hostname are rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_empty_header(self):
        """Test that empty header returns empty list"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = ''
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_whitespace_only(self):
        """Test that whitespace-only entries are ignored"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = '   ,  , '
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_mixed_valid_and_invalid(self):
        """Test that only valid proxies are returned when mixed"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://valid.example.com:8080, file:///etc/passwd, http://localhost:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == ['http://valid.example.com:8080']
    
    def test_no_header(self):
        """Test when X-Proxy-List header is not present"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = ''
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_ipv6_localhost_rejected(self):
        """Test that IPv6 localhost (::1) is rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://[::1]:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
    
    def test_0_0_0_0_rejected(self):
        """Test that 0.0.0.0 is rejected"""
        manager = ProxyManager()
        request = Mock()
        request.headers.get.return_value = 'http://0.0.0.0:8080'
        
        result = manager.get_proxies_from_header(request)
        assert result == []
