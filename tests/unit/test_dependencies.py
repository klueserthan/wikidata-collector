"""
Unit tests for api/dependencies.py module.

Tests the refactored dependency injection pattern using lru_cache
instead of global mutable state.
"""
import pytest
from unittest.mock import Mock, patch

from api.dependencies import get_wiki_service, get_entity_service, get_list_processor
from core.wiki_service import WikiService
from api.services.entity_service import EntityService
from api.services.list_processor import ListProcessor


class TestGetWikiService:
    """Test get_wiki_service singleton behavior."""
    
    def test_returns_wiki_service_instance(self):
        """Test that get_wiki_service returns a WikiService instance."""
        service = get_wiki_service()
        assert isinstance(service, WikiService)
    
    def test_returns_same_instance_on_multiple_calls(self):
        """Test that get_wiki_service returns the same instance (singleton behavior)."""
        # Clear cache to start fresh
        get_wiki_service.cache_clear()
        
        service1 = get_wiki_service()
        service2 = get_wiki_service()
        service3 = get_wiki_service()
        
        # All calls should return the same instance
        assert service1 is service2
        assert service2 is service3
    
    def test_cache_clear_creates_new_instance(self):
        """Test that cache_clear allows creating a new instance."""
        # Get initial instance
        get_wiki_service.cache_clear()
        service1 = get_wiki_service()
        
        # Clear cache and get new instance
        get_wiki_service.cache_clear()
        service2 = get_wiki_service()
        
        # Should be different instances
        assert service1 is not service2
        assert isinstance(service1, WikiService)
        assert isinstance(service2, WikiService)
    
    def test_cache_info_shows_hits_and_misses(self):
        """Test that lru_cache tracking works correctly."""
        get_wiki_service.cache_clear()
        
        # First call should be a cache miss
        service1 = get_wiki_service()
        cache_info = get_wiki_service.cache_info()
        assert cache_info.hits == 0
        assert cache_info.misses == 1
        
        # Second call should be a cache hit
        service2 = get_wiki_service()
        cache_info = get_wiki_service.cache_info()
        assert cache_info.hits == 1
        assert cache_info.misses == 1
        
        # Services should be the same instance
        assert service1 is service2


class TestGetEntityService:
    """Test get_entity_service dependency."""
    
    def test_returns_entity_service_instance(self):
        """Test that get_entity_service returns an EntityService instance."""
        get_wiki_service.cache_clear()
        wiki_service = get_wiki_service()
        entity_service = get_entity_service(wiki_service)
        
        assert isinstance(entity_service, EntityService)
        assert entity_service.wiki_service is wiki_service
    
    def test_creates_new_instance_each_time(self):
        """Test that get_entity_service creates a new instance for each call."""
        get_wiki_service.cache_clear()
        wiki_service = get_wiki_service()
        
        entity_service1 = get_entity_service(wiki_service)
        entity_service2 = get_entity_service(wiki_service)
        
        # Should be different instances (not cached)
        assert entity_service1 is not entity_service2
        
        # But both should use the same wiki_service
        assert entity_service1.wiki_service is entity_service2.wiki_service
        assert entity_service1.wiki_service is wiki_service


class TestGetListProcessor:
    """Test get_list_processor dependency."""
    
    def test_returns_list_processor_instance(self):
        """Test that get_list_processor returns a ListProcessor instance."""
        get_wiki_service.cache_clear()
        wiki_service = get_wiki_service()
        list_processor = get_list_processor(wiki_service)
        
        assert isinstance(list_processor, ListProcessor)
        assert list_processor.wiki_service is wiki_service
    
    def test_creates_new_instance_each_time(self):
        """Test that get_list_processor creates a new instance for each call."""
        get_wiki_service.cache_clear()
        wiki_service = get_wiki_service()
        
        list_processor1 = get_list_processor(wiki_service)
        list_processor2 = get_list_processor(wiki_service)
        
        # Should be different instances (not cached)
        assert list_processor1 is not list_processor2
        
        # But both should use the same wiki_service
        assert list_processor1.wiki_service is list_processor2.wiki_service
        assert list_processor1.wiki_service is wiki_service


class TestThreadSafety:
    """Test thread-safety of the singleton pattern."""
    
    def test_concurrent_access_returns_same_instance(self):
        """Test that concurrent calls to get_wiki_service return the same instance."""
        import concurrent.futures
        
        get_wiki_service.cache_clear()
        
        def get_service():
            return get_wiki_service()
        
        # Create multiple threads accessing the service concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_service) for _ in range(20)]
            services = [f.result() for f in futures]
        
        # All services should be the same instance
        first_service = services[0]
        for service in services[1:]:
            assert service is first_service


class TestDependencyOverride:
    """Test that dependencies can be overridden for testing."""
    
    def test_cache_clear_allows_mock_injection(self):
        """Test that cache_clear can be used to inject mocks for testing."""
        # Clear cache and verify we can inject a mock
        get_wiki_service.cache_clear()
        
        # Create a mock WikiService
        mock_wiki_service = Mock(spec=WikiService)
        mock_wiki_service.test_attribute = "mocked"
        
        # With lru_cache, we can't directly inject the mock, but we can verify
        # that cache_clear allows for fresh instances
        
        # Get a real instance
        real_service1 = get_wiki_service()
        assert isinstance(real_service1, WikiService)
        
        # Clear and get another instance
        get_wiki_service.cache_clear()
        real_service2 = get_wiki_service()
        
        # They should be different instances
        assert real_service1 is not real_service2
        
        # This demonstrates that tests can clear the cache between test cases
        # to ensure isolation, and can use FastAPI's app.dependency_overrides
        # to inject mocks at the framework level
    
    def test_fastapi_dependency_override_pattern(self):
        """Test the recommended pattern for overriding dependencies in FastAPI."""
        from fastapi import FastAPI
        
        app = FastAPI()
        
        # Create a mock WikiService
        mock_wiki_service = Mock(spec=WikiService)
        mock_wiki_service.test_attribute = "mocked"
        
        # This is how you would override the dependency in FastAPI
        app.dependency_overrides[get_wiki_service] = lambda: mock_wiki_service
        
        # Verify the override is set
        assert get_wiki_service in app.dependency_overrides
        override_func = app.dependency_overrides[get_wiki_service]
        result = override_func()
        
        # The override function should return our mock
        assert result is mock_wiki_service
        assert result.test_attribute == "mocked"
        
        # Clean up
        app.dependency_overrides.clear()
        assert get_wiki_service not in app.dependency_overrides
