from enum import Enum


class EntityType(str, Enum):
    """Entity type enumeration."""

    PUBLIC_FIGURE = "public_figure"
    PUBLIC_INSTITUTION = "public_institution"


class ExpansionType(str, Enum):
    """Expansion type enumeration."""

    SUB_INSTITUTIONS = "sub_institutions"
    AFFILIATIONS = "affiliations"


class StreamFormat(str, Enum):
    """Stream format enumeration."""

    NDJSON = "ndjson"


class WikidataProperty(str, Enum):
    """Wikidata property IDs."""

    BIRTH_DATE = "P569"
    DEATH_DATE = "P570"
    FOUNDED_DATE = "P571"
    IMAGE = "P18"
    INSTANCE_OF = "P31"
    MEMBER_OF_PARTY = "P102"
    MEMBER_OF = "P463"
    PLACE_OF_BIRTH = "P19"
    PLACE_OF_DEATH = "P20"
    GENDER = "P21"
    NATIONALITY = "P27"
    PROFESSION = "P106"


class EntityQID(str, Enum):
    """Common Wikidata entity QIDs."""

    PERSON = "Q5"
    POLITICAL_PARTY = "Q7278"
    GOVERNMENT_AGENCY = "Q327333"
    MUNICIPALITY = "Q15284"
    MEDIA_OUTLET = "Q1193236"
    NGO = "Q79913"
    MINISTRY = "Q192350"


class ErrorType(str, Enum):
    """Error type enumeration."""

    WDQS_ERROR = "wdqs_error"  # Wikidata Query Service error
    INTERNAL_ERROR = "internal_error"
    ENTITY_EXPAND_ERROR = "entity_expand_error"
