# Quickstart: Wikidata Public Entities ETL Package

This quickstart shows how an ETL job can use the library to stream public figures and public
institutions from Wikidata using iterator-based APIs.

## Installation (conceptual)

```bash
pip install wikidata-collector
```

## Basic Usage: Public Figures

### Iterator API (Recommended)

The `iterate_public_figures` method returns normalized `PublicFigure` objects directly:

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
    print(f"{figure.id}: {figure.name}")
    print(f"  Birthday: {figure.birthday}")
    print(f"  Nationalities: {', '.join(figure.nationalities)}")
    print(f"  Professions: {', '.join(figure.professions)}")
```

### Limiting Results with `max_results`

```python
# Fetch only the first 100 matching public figures
for figure in client.iterate_public_figures(
    birthday_from="1950-01-01",
    nationality=["DE"],  # Germany (label/code, not QID)
    max_results=100,
):
    process(figure)
```

### Using Birthday Filters

```python
# Get public figures born between 1980 and 1990
for figure in client.iterate_public_figures(
    birthday_from="1980-01-01",
    birthday_to="1990-12-31",
    lang="en",
):
    print(f"{figure.name} (born {figure.birthday})")
```

### Multiple Nationality Filters

```python
# Get public figures from multiple countries
for figure in client.iterate_public_figures(
    nationality=["US", "United Kingdom", "Germany"],
    lang="en",
):
    print(f"{figure.name} - {', '.join(figure.nationalities)}")
```

## Basic Usage: Public Institutions

### Iterator API (Recommended)

The `iterate_public_institutions` method returns normalized `PublicInstitution` objects directly:

```python
from wikidata_collector import WikidataClient

client = WikidataClient()

# Stream public institutions by founding date and country label/code
for institution in client.iterate_public_institutions(
    founded_from="1990-01-01",
    country=["US"],  # United States (label/code, not QID)
    types=["public broadcaster"],  # Example institution type label
    max_results=50,
    lang="en",
):
    print(f"{institution.id}: {institution.name}")
    print(f"  Founded: {institution.founded}")
    print(f"  Country: {', '.join(institution.country)}")
    print(f"  Types: {', '.join(institution.types)}")
```

## Error Handling

The iterator API raises specific exceptions for invalid inputs:

```python
from wikidata_collector import WikidataClient, InvalidFilterError

client = WikidataClient()

try:
    for figure in client.iterate_public_figures(
        birthday_from="invalid-date",  # Invalid date format
    ):
        process(figure)
except InvalidFilterError as e:
    print(f"Invalid filter: {e}")
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

## Advanced: Combining Filters

```python
# Complex query: German writers born after 1950
for figure in client.iterate_public_figures(
    birthday_from="1950-01-01",
    nationality=["Germany", "DE"],  # Can use labels or ISO codes
    max_results=200,
    lang="en",
):
    print(f"{figure.name} ({figure.id})")
    if figure.professions:
        print(f"  Professions: {', '.join(figure.professions)}")
    if figure.website:
        print(f"  Website: {figure.website[0].url}")
```

This quickstart is illustrative; the exact configuration fields will be finalized during
implementation in alignment with the existing config module and exceptions.
