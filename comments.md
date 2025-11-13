'http://127.0.0.1:8000/v1/public-institutions?country=DEU&type=ministry&lang=en&limit=5'

```json
{
  "data": [
    {
      "id": "Q125548096",
      "entity_kind": "public_institution",
      "name": "germanistique juridique",
      "aliases": [],
      "description": null,
      "founded": null,
      "country": [
        "DEU"
      ],
      "jurisdiction": [],
      "types": [
        "academic discipline"
      ],
      "legal_form": [],
      "headquarters": [],
      "headquarters_coords": [],
      "website": [],
      "official_language": [],
      "logo": [],
      "budget": [],
      "parent_institution": [],
      "sub_institutions": [],
      "sector": [],
      "affiliations": [],
      "accounts": [],
      "updated_at": "2025-11-13T08:31:28.251644+00:00"
    },
    {
      "id": "Q695742",
      "entity_kind": "public_institution",
      "name": "law of Germany",
      "aliases": [],
      "description": "positive law",
      "founded": null,
      "country": [
        "DEU"
      ],
      "jurisdiction": [],
      "types": [
        "positive law",
        "legal system",
        "academic discipline"
      ],
      "legal_form": [],
      "headquarters": [],
      "headquarters_coords": [],
      "website": [],
      "official_language": [],
      "logo": [],
      "budget": [],
      "parent_institution": [],
      "sub_institutions": [],
      "sector": [],
      "affiliations": [],
      "accounts": [],
      "updated_at": "2025-11-13T08:31:33.523719+00:00"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
````

curl -X 'GET' \
  'http://127.0.0.1:8000/v1/public-institutions?country=USA&type=ministry&lang=en&limit=5' \
  -H 'accept: application/json'

```json
{
  "data": [
    {
      "id": "Q1433069",
      "entity_kind": "public_institution",
      "name": "cliometrics",
      "aliases": [],
      "description": "systematic application of economic theory and econometric techniques to the study of history",
      "founded": null,
      "country": [
        "USA"
      ],
      "jurisdiction": [],
      "types": [
        "academic discipline"
      ],
      "legal_form": [],
      "headquarters": [],
      "headquarters_coords": [],
      "website": [],
      "official_language": [],
      "logo": [],
      "budget": [],
      "parent_institution": [
        "economic history"
      ],
      "sub_institutions": [],
      "sector": [],
      "affiliations": [],
      "accounts": [],
      "updated_at": "2025-11-13T09:18:53.951102+00:00"
    },
    {
      "id": "Q1483473",
      "entity_kind": "public_institution",
      "name": "military history of the United States",
      "aliases": [],
      "description": "history of all of the United States military involvements",
      "founded": null,
      "country": [
        "USA"
      ],
      "jurisdiction": [],
      "types": [
        "academic major",
        "academic discipline",
        "military history by country or region"
      ],
      "legal_form": [],
      "headquarters": [],
      "headquarters_coords": [],
      "website": [],
      "official_language": [],
      "logo": [],
      "budget": [],
      "parent_institution": [
        "history of the United States",
        "military history"
      ],
      "sub_institutions": [],
      "sector": [],
      "affiliations": [],
      "accounts": [],
      "updated_at": "2025-11-13T09:19:03.288962+00:00"
    },
    {
      "id": "Q233762",
      "entity_kind": "public_institution",
      "name": "American literature",
      "aliases": [],
      "description": "literature written by Americans or related to the United States",
      "founded": null,
      "country": [
        "USA"
      ],
      "jurisdiction": [],
      "types": [
        "sub-set of literature",
        "academic discipline"
      ],
      "legal_form": [],
      "headquarters": [],
      "headquarters_coords": [],
      "website": [],
      "official_language": [],
      "logo": [],
      "budget": [],
      "parent_institution": [
        "North American literature"
      ],
      "sub_institutions": [],
      "sector": [],
      "affiliations": [],
      "accounts": [],
      "updated_at": "2025-11-13T09:19:06.659136+00:00"
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```


Reason is that type mappings map to wrong Q-ID:
class EntityQID(str, Enum):
    """Common Wikidata entity QIDs."""
    PERSON = "Q5"
    POLITICAL_PARTY = "Q7278"
    GOVERNMENT_AGENCY = "Q327333"
    MUNICIPALITY = "Q15284"
    MEDIA_OUTLET = "Q11019" -> "machine"
    NGO = "Q79913"
    MINISTRY = "Q11862829" -> "academic discipline"