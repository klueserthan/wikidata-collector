"""Unit tests for WikidataCollectorConfig."""

import pytest

from wikidata_collector import config as config_module
from wikidata_collector.config import WikidataCollectorConfig


@pytest.fixture(autouse=True)
def clean_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every config env var so tests see constructor defaults.

    `WikidataCollectorConfig` reads process env vars, and `load_dotenv` may have
    populated them from a developer's `.env`. Clearing them keeps these tests
    independent of the machine they run on.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    for name in (
        "CONTACT_EMAIL",
        "WIKIDATA_SPARQL_URL",
        "WIKIDATA_ENTITY_API_URL",
        "PROXY_LIST",
        "SPARQL_TIMEOUT_SECONDS",
        "MAX_RETRIES",
        "PROXY_COOLDOWN_SECONDS",
        "DEFAULT_LIMIT",
        "RETRY_MAX_WAIT_SECONDS",
        "RETRY_JITTER_BASE",
        "RETRY_JITTER_INCREMENT",
        "PROXY_DEEP_SLEEP_SECONDS",
        "PROXY_DEEP_SLEEP_MAX_FAILURES",
    ):
        monkeypatch.delenv(name, raising=False)


class TestDefaults:
    """Values a caller gets when nothing is configured."""

    def test_endpoint_defaults_to_public_wikidata(self):
        """The SPARQL and Entity API URLs default to the public endpoints."""
        config = WikidataCollectorConfig()

        assert config.wikidata_sparql_url == "https://query.wikidata.org/sparql"
        assert config.wikidata_entity_api_url == (
            "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        )

    def test_retry_and_pagination_defaults(self):
        """Retry, cooldown, and page-size defaults match the documented values."""
        config = WikidataCollectorConfig()

        assert config.max_retries == 3
        assert config.sparql_timeout_seconds == 60
        assert config.proxy_cooldown_seconds == 300
        assert config.default_limit == 15
        assert config.retry_max_wait_seconds == 10
        assert config.retry_jitter_base == 0.5
        assert config.retry_jitter_increment == 0.2

    def test_deep_sleep_defaults(self):
        """Deep-sleep defaults are 30 minutes across at most three cycles."""
        config = WikidataCollectorConfig()

        assert config.proxy_deep_sleep_seconds == 1800
        assert config.proxy_deep_sleep_max_failures == 3

    def test_proxy_list_defaults_to_empty(self):
        """With no PROXY_LIST set, the collector runs without proxies."""
        assert WikidataCollectorConfig().proxy_list == []


class TestConstructorOverrides:
    """Explicit constructor arguments are honoured when no env var is set."""

    def test_scalar_overrides_are_applied(self):
        """Numeric settings passed to the constructor reach the instance."""
        config = WikidataCollectorConfig(
            sparql_timeout_seconds=7,
            max_retries=9,
            proxy_cooldown_seconds=11,
            default_limit=42,
            retry_max_wait_seconds=13,
            retry_jitter_base=1.5,
            retry_jitter_increment=0.75,
            proxy_deep_sleep_seconds=17,
            proxy_deep_sleep_max_failures=5,
        )

        assert config.sparql_timeout_seconds == 7
        assert config.max_retries == 9
        assert config.proxy_cooldown_seconds == 11
        assert config.default_limit == 42
        assert config.retry_max_wait_seconds == 13
        assert config.retry_jitter_base == 1.5
        assert config.retry_jitter_increment == 0.75
        assert config.proxy_deep_sleep_seconds == 17
        assert config.proxy_deep_sleep_max_failures == 5

    def test_explicit_proxy_list_is_kept_verbatim(self):
        """An explicit proxy_list bypasses PROXY_LIST parsing entirely."""
        proxies = ["http://a.example.com:8080", "http://b.example.com:8080"]

        assert WikidataCollectorConfig(proxy_list=proxies).proxy_list == proxies

    def test_explicit_empty_proxy_list_is_not_treated_as_unset(self, monkeypatch):
        """Passing [] means 'no proxies', even when PROXY_LIST is populated."""
        monkeypatch.setenv("PROXY_LIST", "http://from-env.example.com:8080")

        assert WikidataCollectorConfig(proxy_list=[]).proxy_list == []


class TestEnvironmentFallback:
    """Env vars supply values the caller did not pass."""

    def test_proxy_list_is_parsed_from_comma_separated_env(self, monkeypatch):
        """PROXY_LIST splits on commas and drops blank entries and whitespace."""
        monkeypatch.setenv("PROXY_LIST", " http://a.example.com:8080 ,, http://b.example.com:8080 ")

        assert WikidataCollectorConfig().proxy_list == [
            "http://a.example.com:8080",
            "http://b.example.com:8080",
        ]

    def test_numeric_settings_are_coerced_from_env(self, monkeypatch):
        """Numeric env vars are parsed into ints and floats, not left as strings."""
        monkeypatch.setenv("MAX_RETRIES", "7")
        monkeypatch.setenv("RETRY_JITTER_BASE", "2.25")

        config = WikidataCollectorConfig()

        assert config.max_retries == 7
        assert config.retry_jitter_base == 2.25

    def test_endpoint_urls_are_read_from_env(self, monkeypatch):
        """A self-hosted SPARQL endpoint can be pointed at via env."""
        monkeypatch.setenv("WIKIDATA_SPARQL_URL", "https://sparql.internal.example/query")

        assert WikidataCollectorConfig().wikidata_sparql_url == (
            "https://sparql.internal.example/query"
        )


class TestUserAgent:
    """User-Agent selection, and the cost of building it."""

    def test_contact_email_produces_an_identifying_user_agent(self):
        """A contact email yields the transparent UA Wikidata's policy asks for."""
        user_agent = WikidataCollectorConfig(contact_email="ops@example.com").get_user_agent()

        assert user_agent.startswith("WikidataCollectorModule/")
        assert "https://github.com/klueserthan/wikidata-collector" in user_agent
        assert "ops@example.com" in user_agent

    def test_missing_contact_email_falls_back_to_a_random_user_agent(self, monkeypatch):
        """Without a contact email the collector uses a random browser UA."""
        monkeypatch.setattr(config_module, "_user_agent_pool", None)
        monkeypatch.setattr(
            config_module, "UserAgent", lambda: _FakeUserAgentPool("Mozilla/5.0 (fake)")
        )

        assert WikidataCollectorConfig().get_user_agent() == "Mozilla/5.0 (fake)"

    def test_random_user_agent_pool_is_built_once_per_process(self, monkeypatch):
        """Building the UA pool costs seconds, so it must not happen per request.

        Regression guard: the pool used to be reconstructed on every SPARQL
        request, adding 1.5-5s of CPU to each call.
        """
        constructions: list[int] = []

        def _counting_pool() -> "_FakeUserAgentPool":
            constructions.append(1)
            return _FakeUserAgentPool("Mozilla/5.0 (fake)")

        monkeypatch.setattr(config_module, "_user_agent_pool", None)
        monkeypatch.setattr(config_module, "UserAgent", _counting_pool)

        first = WikidataCollectorConfig()
        second = WikidataCollectorConfig()
        for _ in range(5):
            first.get_user_agent()
            second.get_user_agent()

        assert len(constructions) == 1

    def test_contact_email_path_never_builds_the_pool(self, monkeypatch):
        """A configured contact email must not pay for the random-UA dataset."""

        def _explode() -> "_FakeUserAgentPool":
            raise AssertionError("UserAgent pool must not be built when contact_email is set")

        monkeypatch.setattr(config_module, "_user_agent_pool", None)
        monkeypatch.setattr(config_module, "UserAgent", _explode)

        WikidataCollectorConfig(contact_email="ops@example.com").get_user_agent()


class _FakeUserAgentPool:
    """Stand-in for random_user_agent's UserAgent that returns a fixed string."""

    def __init__(self, user_agent: str):
        """Store the user agent this pool always returns."""
        self._user_agent = user_agent

    def get_random_user_agent(self) -> str:
        """Return the fixed user agent."""
        return self._user_agent
