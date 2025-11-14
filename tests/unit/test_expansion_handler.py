"""
Unit tests for ExpansionHandler.
"""
import pytest
from unittest.mock import Mock, patch

from api.services.expansion_handler import ExpansionHandler
from core.models import PublicFigure, PublicInstitution, SubInstitution
from core.wiki_service import WikiService


class TestExpansionHandler:
    """Tests for ExpansionHandler class."""

    @pytest.fixture
    def wiki_service(self):
        """Mock WikiService."""
        return Mock(spec=WikiService)

    @pytest.fixture
    def expansion_handler(self, wiki_service):
        """Create ExpansionHandler instance."""
        return ExpansionHandler(wiki_service)

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI Request."""
        request = Mock()
        request.headers = {}
        return request

    def test_sub_institutions_expansion_on_public_institution(self, expansion_handler, wiki_service, mock_request):
        """Test that sub_institutions expansion works on PublicInstitution."""
        # Setup
        entity = PublicInstitution(id="Q123", name="Test Institution")
        qid = "Q123"
        lang = "en"
        expand = "sub_institutions"
        ent = {"claims": {}}
        
        # Create a SubInstitution (Note: _id is ignored by Pydantic v2 as private field)
        sub_inst = SubInstitution(_id="Q456", name="Sub Inst")
        wiki_service.expand_sub_institutions.return_value = [sub_inst]
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify
        assert isinstance(result, PublicInstitution)
        assert len(result.sub_institutions) == 1
        assert result.sub_institutions[0].name == "Sub Inst"
        wiki_service.expand_sub_institutions.assert_called_once_with(qid, lang=lang, request=mock_request)

    def test_sub_institutions_expansion_skipped_on_public_figure(self, expansion_handler, wiki_service, mock_request):
        """Test that sub_institutions expansion is skipped for PublicFigure."""
        # Setup
        entity = PublicFigure(id="Q789", name="Test Person")
        qid = "Q789"
        lang = "en"
        expand = "sub_institutions"
        ent = {"claims": {}}
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify - sub_institutions should not be called for PublicFigure
        assert isinstance(result, PublicFigure)
        wiki_service.expand_sub_institutions.assert_not_called()
        # PublicFigure should not have sub_institutions attribute
        assert not hasattr(result, 'sub_institutions')

    @patch('api.utils.entity_utils.EntityTypeDetector')
    def test_affiliations_expansion_filters_none_values(self, mock_detector, expansion_handler, wiki_service, mock_request):
        """Test that affiliations expansion filters out None values from labels."""
        # Setup
        entity = PublicFigure(id="Q789", name="Test Person")
        qid = "Q789"
        lang = "en"
        expand = "affiliations"
        ent = {"claims": {"P102": [{"value": "Q1"}], "P463": [{"value": "Q2"}]}}
        
        # Mock EntityTypeDetector to return QIDs
        mock_detector.extract_qids_from_claims.side_effect = [
            ["Q1"],  # First call for P102
            ["Q2"]   # Second call for P463
        ]
        
        # Mock get_labels_from_qids to return only one label (Q1), Q2 is missing
        wiki_service.get_labels_from_qids.return_value = {
            "Q1": "Democratic Party"
            # Q2 is intentionally missing to test None filtering
        }
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify - should only include Q1, not Q2
        assert isinstance(result, PublicFigure)
        assert len(result.affiliations) == 1
        assert result.affiliations[0] == "Democratic Party"
        assert "Q2" not in result.affiliations
        wiki_service.get_labels_from_qids.assert_called_once()

    @patch('api.utils.entity_utils.EntityTypeDetector')
    def test_affiliations_expansion_all_labels_found(self, mock_detector, expansion_handler, wiki_service, mock_request):
        """Test affiliations expansion when all labels are found."""
        # Setup
        entity = PublicFigure(id="Q789", name="Test Person")
        qid = "Q789"
        lang = "en"
        expand = "affiliations"
        ent = {"claims": {"P102": [{"value": "Q1"}], "P463": [{"value": "Q2"}]}}
        
        # Mock EntityTypeDetector to return QIDs
        mock_detector.extract_qids_from_claims.side_effect = [
            ["Q1"],  # First call for P102
            ["Q2"]   # Second call for P463
        ]
        
        # Mock get_labels_from_qids to return all labels
        wiki_service.get_labels_from_qids.return_value = {
            "Q1": "Democratic Party",
            "Q2": "American Civil Liberties Union"
        }
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify - should include both labels
        assert isinstance(result, PublicFigure)
        assert len(result.affiliations) == 2
        assert result.affiliations[0] == "Democratic Party"
        assert result.affiliations[1] == "American Civil Liberties Union"

    @patch('api.utils.entity_utils.EntityTypeDetector')
    def test_affiliations_expansion_no_qids(self, mock_detector, expansion_handler, wiki_service, mock_request):
        """Test affiliations expansion when no QIDs are found."""
        # Setup
        entity = PublicFigure(id="Q789", name="Test Person")
        qid = "Q789"
        lang = "en"
        expand = "affiliations"
        ent = {"claims": {}}
        
        # Mock EntityTypeDetector to return empty lists
        mock_detector.extract_qids_from_claims.return_value = []
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify - should have empty affiliations list
        assert isinstance(result, PublicFigure)
        assert result.affiliations == []
        wiki_service.get_labels_from_qids.assert_not_called()

    @patch('api.utils.entity_utils.EntityTypeDetector')
    def test_affiliations_expansion_on_institution(self, mock_detector, expansion_handler, wiki_service, mock_request):
        """Test that affiliations expansion works on PublicInstitution too."""
        # Setup
        entity = PublicInstitution(id="Q123", name="Test Institution")
        qid = "Q123"
        lang = "en"
        expand = "affiliations"
        ent = {"claims": {"P463": [{"value": "Q999"}]}}
        
        # Mock EntityTypeDetector
        mock_detector.extract_qids_from_claims.side_effect = [
            [],       # First call for P102
            ["Q999"]  # Second call for P463
        ]
        
        # Mock get_labels_from_qids
        wiki_service.get_labels_from_qids.return_value = {
            "Q999": "International Association"
        }
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify
        assert isinstance(result, PublicInstitution)
        assert len(result.affiliations) == 1
        assert result.affiliations[0] == "International Association"

    def test_multiple_expansions(self, expansion_handler, wiki_service, mock_request):
        """Test applying multiple expansions at once."""
        # Setup
        entity = PublicInstitution(id="Q123", name="Test Institution")
        qid = "Q123"
        lang = "en"
        expand = "sub_institutions, affiliations"
        ent = {"claims": {}}
        
        sub_inst = SubInstitution(_id="Q456", name="Sub Inst")
        wiki_service.expand_sub_institutions.return_value = [sub_inst]
        
        # Execute
        with patch('api.utils.entity_utils.EntityTypeDetector') as mock_detector:
            mock_detector.extract_qids_from_claims.return_value = []
            result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify both expansions were applied
        assert isinstance(result, PublicInstitution)
        assert len(result.sub_institutions) == 1
        assert result.affiliations == []

    def test_no_expansions_requested(self, expansion_handler, wiki_service, mock_request):
        """Test that entity is returned unchanged when no expansions requested."""
        # Setup
        entity = PublicFigure(id="Q789", name="Test Person")
        qid = "Q789"
        lang = "en"
        expand = ""
        ent = {"claims": {}}
        
        # Execute
        result = expansion_handler.apply_expansions(entity, expand, qid, lang, ent, mock_request)
        
        # Verify
        assert isinstance(result, PublicFigure)
        assert result == entity
        wiki_service.expand_sub_institutions.assert_not_called()
        wiki_service.get_labels_from_qids.assert_not_called()
