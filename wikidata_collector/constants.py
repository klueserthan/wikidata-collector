"""Constants for the Wikidata Retriever module."""

# Supported gender mappings (P21 = sex or gender)
# "other" is a sentinel that triggers FILTER NOT EXISTS logic (not male AND not female),
# covering non-binary genders as well as entities with no gender claim.
GENDER_MAPPINGS = {
    "male": "Q6581097",
    "female": "Q6581072",
    "other": "other",
}

# Supported institution type mappings
TYPE_MAPPINGS = {
    "political_party": "Q7278",
    "government_agency": "Q327333",
    "municipality": "Q15284",
    "media_outlet": "Q1193236",
    "ngo": "Q79913",
    "ministry": "Q192350",
}

# TODO: Verify and select
# Supported country mappings
COUNTRY_MAPPINGS = {
    "Germany": "Q183",
    "United States": "Q30",
    "US": "Q30",
    "USA": "Q30",
    "France": "Q142",
    "United Kingdom": "Q145",
    "UK": "Q145",
    "Spain": "Q29",
    "Italy": "Q38",
    "Canada": "Q16",
    "Australia": "Q408",
    "Japan": "Q17",
    "China": "Q148",
    "India": "Q668",
    "Brazil": "Q155",
    "Mexico": "Q96",
    "Russia": "Q159",
    "South Korea": "Q884",
    "Netherlands": "Q55",
    "Switzerland": "Q39",
    "Sweden": "Q34",
    "Norway": "Q20",
    "Denmark": "Q35",
    "Austria": "Q40",
    "Belgium": "Q31",
    "Poland": "Q36",
    "Portugal": "Q45",
    "Greece": "Q41",
    "Ireland": "Q27",
    "New Zealand": "Q664",
    "Argentina": "Q414",
    "Chile": "Q298",
    "Colombia": "Q739",
    "South Africa": "Q258",
}

# TODO: Verify and select
# Supported profession mappings
PROFESSION_MAPPINGS = {
    "politician": "Q82955",
    "actor": "Q33999",
    "actress": "Q33999",
    "musician": "Q639669",
    "singer": "Q177220",
    "writer": "Q36180",
    "author": "Q482980",
    "journalist": "Q1930187",
    "scientist": "Q901",
    "researcher": "Q1650915",
    "athlete": "Q2066131",
    "footballer": "Q937857",
    "basketball player": "Q3665646",
    "tennis player": "Q10833314",
    "director": "Q2526255",
    "film director": "Q2526255",
    "producer": "Q3282637",
    "entrepreneur": "Q131524",
    "businessperson": "Q43845",
    "artist": "Q483501",
    "painter": "Q1028181",
    "sculptor": "Q1281618",
    "photographer": "Q33231",
    "composer": "Q36834",
    "architect": "Q42973",
    "engineer": "Q81096",
    "lawyer": "Q40348",
    "physician": "Q39631",
    "doctor": "Q39631",
    "teacher": "Q37226",
    "professor": "Q121594",
    "chef": "Q3499072",
    "model": "Q4610556",
    "fashion model": "Q4610556",
}
