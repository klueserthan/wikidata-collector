# Quickstart: Wikidata Public Entities ETL Package

This quickstart shows how an ETL job can use the library to stream public figures and public
institutions from Wikidata using iterator-based APIs.

## Installation (conceptual)

```bash
pip install wikidata-collector
```

## Basic Usage: Public Figures

```python
from wikidata_collector import WikidataClient

client = WikidataClient(
    # Configuration details (e.g., contact email, proxy endpoint) will be defined
    # in the concrete implementation based on the existing config module.
)

# Stream all public figures born after 1990 with a given nationality label/code
for figure in client.iterate_public_figures(
    birthday_from="1990-01-01",
    nationality=["US"],  # United States (label/code, not QID)
    lang="en",
):
    print(figure.id, figure.name)
```

## Basic Usage: Public Institutions

```python
from wikidata_collector import WikidataClient

client = WikidataClient()

# Stream public institutions by founding date and country label/code
for institution in client.iterate_public_institutions(
    founded_from="1990-01-01",
    country=["US"],  # United States (label/code, not QID)
    types=["public broadcaster"],  # Example institution type label
    lang="en",
):
    print(institution.id, institution.name)
```

## Limiting Results with `max_results`

```python
# Fetch only the first 100 matching public figures
for figure in client.iterate_public_figures(
    birthday_from="1950-01-01",
    nationality=["DE"],  # Germany (label/code, not QID)
    max_results=100,
):
    process(figure)
```

## Proxy and Logging (Conceptual)

```python
from wikidata_collector.config import WikidataCollectorConfig
from wikidata_collector import WikidataClient

config = WikidataCollectorConfig(
    contact_email="your-email@example.com",
    proxy_endpoint="http://proxy:8080",  # optional
    allow_proxy_fallback=False,           # default fail-closed behavior
)

client = WikidataClient(config)

for figure in client.iterate_public_figures(nationality=["US"]):
    # Structured logs emitted by the library can be collected by your logging stack
    handle_figure(figure)
```

This quickstart is illustrative; the exact configuration fields will be finalized during
implementation in alignment with the existing config module and exceptions.
