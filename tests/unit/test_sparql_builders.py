"""
Unit tests for SPARQL query builders.
"""



class TestBuildPublicFiguresQuery:
    """Test build_public_figures_query method."""
    
    def test_basic_query(self, wiki_service):
        """Test basic query without filters."""
        query = wiki_service.build_public_figures_query()
        
        assert "SELECT DISTINCT" in query
        assert "?person wdt:P31 wd:Q5" in query  # instance of human
        assert "wdt:P569" in query  # date of birth
        assert "ORDER BY ?person" in query
        assert "LIMIT" in query
    
    def test_birthday_filters(self, wiki_service):
        """Test query with birthday filters."""
        query = wiki_service.build_public_figures_query(
            birthday_from="1950-01-01",
            birthday_to="2000-12-31"
        )
        
        assert 'FILTER(?birthDate >= "1950-01-01T00:00:00Z"' in query
        assert 'FILTER(?birthDate <= "2000-12-31T23:59:59Z"' in query
    
    def test_nationality_filter_qid(self, wiki_service):
        """Test nationality filter with QID."""
        query = wiki_service.build_public_figures_query(
            nationality=["Q145"]  # United Kingdom QID
        )
        
        assert "?person wdt:P27 wd:Q145" in query
    
    def test_nationality_filter_name(self, wiki_service):
        """Test nationality filter with name."""
        query = wiki_service.build_public_figures_query(
            nationality=["United Kingdom"],
            lang="en"
        )
        
        assert '?person wdt:P27 ?country' in query
        assert '?country rdfs:label "United Kingdom"@en' in query
    
    def test_profession_filter_qid(self, wiki_service):
        """Test profession filter with QID."""
        query = wiki_service.build_public_figures_query(
            profession=["Q36180"]  # Writer QID
        )
        
        assert "?person wdt:P106 wd:Q36180" in query
    
    def test_profession_filter_name(self, wiki_service):
        """Test profession filter with name."""
        query = wiki_service.build_public_figures_query(
            profession=["writer"],
            lang="en"
        )
        
        assert '?person wdt:P106 ?occupation' in query
        assert '?occupation rdfs:label "writer"@en' in query
    
    def test_multiple_nationalities(self, wiki_service):
        """Test multiple nationality filters."""
        query = wiki_service.build_public_figures_query(
            nationality=["Q145", "Q30"]  # UK and USA
        )
        
        assert "wdt:P27 wd:Q145" in query
        assert "wdt:P27 wd:Q30" in query
    
    def test_keyset_pagination(self, wiki_service):
        """Test keyset pagination with QID."""
        query = wiki_service.build_public_figures_query(
            after_qid="Q100"
        )
        
        assert "BIND(xsd:integer(STRAFTER(STR(?person), \"Q\")) AS ?qidNum)" in query
        assert "FILTER(?qidNum > 100)" in query
    
    def test_offset_pagination(self, wiki_service):
        """Test offset pagination (backward compatibility)."""
        query = wiki_service.build_public_figures_query(
            cursor=50
        )
        
        assert "OFFSET 50" in query
    
    def test_limit(self, wiki_service):
        """Test limit parameter."""
        query = wiki_service.build_public_figures_query(limit=200)
        
        assert "LIMIT 201" in query  # limit + 1 for has_more detection
    
    def test_language_parameter(self, wiki_service):
        """Test language parameter in SERVICE block."""
        query = wiki_service.build_public_figures_query(lang="fr")
        
        assert 'bd:serviceParam wikibase:language "en"' in query or 'wikibase:language "fr"' in query


class TestBuildPublicInstitutionsQuery:
    """Test build_public_institutions_query method."""
    
    def test_basic_query(self, wiki_service):
        """Test basic query without filters."""
        query = wiki_service.build_public_institutions_query()
        
        assert "SELECT DISTINCT" in query
        assert "?institution wdt:P31 ?type" in query
        assert "ORDER BY ?institution" in query
        assert "LIMIT" in query
    
    def test_country_filter_qid(self, wiki_service):
        """Test country filter with QID."""
        query = wiki_service.build_public_institutions_query(
            country="Q145"  # United Kingdom QID
        )
        
        assert "?institution wdt:P17 wd:Q145" in query
    
    def test_country_filter_name(self, wiki_service):
        """Test country filter with name."""
        query = wiki_service.build_public_institutions_query(
            country="United Kingdom",
            lang="en"
        )
        
        assert '?institution wdt:P17 ?country' in query
        assert '?country rdfs:label "United Kingdom"@en' in query
    
    def test_type_filter_mapping(self, wiki_service):
        """Test type filter with mapped type name."""
        query = wiki_service.build_public_institutions_query(
            type=["political_party"]
        )
        
        assert "wdt:P31 wd:Q7278" in query  # political_party mapping
    
    def test_type_filter_qid(self, wiki_service):
        """Test type filter with QID."""
        query = wiki_service.build_public_institutions_query(
            type=["Q7278"]
        )
        
        assert "wdt:P31 wd:Q7278" in query
    
    def test_jurisdiction_filter(self, wiki_service):
        """Test jurisdiction filter."""
        query = wiki_service.build_public_institutions_query(
            jurisdiction="Q145",
            lang="en"
        )
        
        assert "?institution wdt:P1001 wd:Q145" in query
    
    def test_keyset_pagination(self, wiki_service):
        """Test keyset pagination with QID."""
        query = wiki_service.build_public_institutions_query(
            after_qid="Q1000"
        )
        
        assert "BIND(xsd:integer(STRAFTER(STR(?institution), \"Q\")) AS ?qidNum)" in query
        assert "FILTER(?qidNum > 1000)" in query


class TestBuildEntityExpansionQuery:
    """Test build_entity_expansion_query method."""
    
    def test_basic_query(self, wiki_service):
        """Test basic entity expansion query."""
        query = wiki_service.build_entity_expansion_query("Q42", lang="en")
        
        assert "SELECT DISTINCT" in query
        assert "BIND(wd:Q42 AS ?entity)" in query
        assert "?entity wdt:P31 wd:Q5" in query  # instance of human
        assert "OPTIONAL { ?entity wdt:P21 ?gender" in query
        assert "OPTIONAL { ?entity wdt:P27 ?nationality" in query
        assert "OPTIONAL { ?entity wdt:P106 ?profession" in query
        assert "OPTIONAL { ?entity wdt:P856 ?website" in query
        assert "SERVICE wikibase:label" in query
    
    def test_language_parameter(self, wiki_service):
        """Test language parameter in SERVICE block."""
        query = wiki_service.build_entity_expansion_query("Q42", lang="fr")
        
        assert 'bd:serviceParam wikibase:language "fr"' in query


class TestBuildInstitutionExpansionQuery:
    """Test build_institution_expansion_query method."""
    
    def test_basic_query(self, wiki_service):
        """Test basic institution expansion query."""
        query = wiki_service.build_institution_expansion_query("Q123", lang="en")
        
        assert "SELECT DISTINCT" in query
        assert "BIND(wd:Q123 AS ?entity)" in query
        assert "?entity wdt:P31 ?type" in query
        assert "OPTIONAL { ?entity wdt:P17 ?country" in query
        assert "OPTIONAL { ?entity wdt:P856 ?website" in query
        assert "SERVICE wikibase:label" in query
    
    def test_language_parameter(self, wiki_service):
        """Test language parameter."""
        query = wiki_service.build_institution_expansion_query("Q123", lang="de")
        
        assert 'bd:serviceParam wikibase:language "de"' in query


