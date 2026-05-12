"""
Test suite for Support Triage Agent
Run with: pytest
"""
import pytest
import sys
import os
from pathlib import Path

# Add code directory to path
code_dir = os.path.join(os.path.dirname(__file__), '..', 'code')
sys.path.insert(0, code_dir)

# Import modules to test
from models import (
    SupportTicket, TicketStatus, RequestType, Company,
    UrgencyTier, Sentiment, TriageResult, AgentDecision, CorpusChunk
)


class TestModels:
    """Test Pydantic data models"""
    
    def test_support_ticket_creation(self):
        """Test creating a support ticket"""
        ticket = SupportTicket(
            issue="I lost access to my account",
            subject="Account access lost",
            company="Claude"
        )
        assert ticket.issue == "I lost access to my account"
        assert ticket.subject == "Account access lost"
        assert ticket.company == "Claude"
    
    def test_ticket_status_enum(self):
        """Test TicketStatus enum values"""
        assert TicketStatus.REPLIED.value == "replied"
        assert TicketStatus.ESCALATED.value == "escalated"
    
    def test_request_type_enum(self):
        """Test RequestType enum values"""
        assert RequestType.PRODUCT_ISSUE.value == "product_issue"
        assert RequestType.FEATURE_REQUEST.value == "feature_request"
        assert RequestType.BUG.value == "bug"
        assert RequestType.INVALID.value == "invalid"
    
    def test_company_enum(self):
        """Test Company enum values"""
        assert Company.CLAUDE.value == "Claude"
        assert Company.HACKERRANK.value == "HackerRank"
        assert Company.VISA.value == "Visa"
    
    def test_urgency_tier_enum(self):
        """Test UrgencyTier enum values"""
        assert UrgencyTier.P0_CRITICAL.value == "P0_Critical"
        assert UrgencyTier.P1_HIGH.value == "P1_High"
        assert UrgencyTier.P2_MEDIUM.value == "P2_Medium"
        assert UrgencyTier.P3_LOW.value == "P3_Low"
    
    def test_sentiment_enum(self):
        """Test Sentiment enum values"""
        assert Sentiment.ANGRY.value == "angry"
        assert Sentiment.FRUSTRATED.value == "frustrated"
        assert Sentiment.NEUTRAL.value == "neutral"
        assert Sentiment.POSITIVE.value == "positive"
    
    def test_agent_decision_creation(self):
        """Test creating an agent decision"""
        decision = AgentDecision(
            status="replied",
            product_area="General Support",
            response="Thank you for contacting us",
            justification="Standard support response",
            request_type="product_issue",
            escalation_reason=None
        )
        assert decision.status == "replied"
        assert decision.product_area == "General Support"
        assert decision.escalation_reason is None
    
    def test_triage_result_creation(self):
        """Test creating a triage result"""
        result = TriageResult(
            status=TicketStatus.REPLIED,
            product_area="Claude Support",
            response="Your issue has been noted",
            justification="Processed successfully",
            request_type=RequestType.PRODUCT_ISSUE
        )
        assert result.status == TicketStatus.REPLIED
        assert result.product_area == "Claude Support"
    
    def test_corpus_chunk_creation(self):
        """Test creating a corpus chunk"""
        chunk = CorpusChunk(
            source="Claude",
            url="https://example.com",
            title="How to reset password",
            content="To reset your password, click the forgot password button"
        )
        assert chunk.source == "Claude"
        assert chunk.title == "How to reset password"
        assert len(chunk.full_text) > 0


class TestValidation:
    """Test model validation"""
    
    def test_support_ticket_coerces_none_values(self):
        """Test that SupportTicket coerces None values to empty strings"""
        ticket = SupportTicket(
            issue="Test issue",
            subject=None,
            company=None
        )
        assert ticket.subject == ""
        assert ticket.company == ""
    
    def test_support_ticket_strips_whitespace(self):
        """Test that SupportTicket strips whitespace"""
        ticket = SupportTicket(
            issue="  Test issue  ",
            subject="  Test subject  ",
            company="  Claude  "
        )
        assert ticket.issue == "Test issue"
        assert ticket.subject == "Test subject"
        assert ticket.company == "Claude"
    
    def test_support_ticket_handles_float_company(self):
        """Test that SupportTicket handles float values"""
        ticket = SupportTicket(
            issue="Test",
            company=1.0
        )
        assert ticket.company == ""


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
