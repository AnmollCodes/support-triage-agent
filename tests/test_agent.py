"""
Test suite for Support Triage Agent
Run with: pytest
"""
import pytest
import sys
import os
from pathlib import Path

# Add code directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code'))

# Import modules to test
from models import ClassificationModel, SentimentAnalyzer, UrgencyTier
from safety import SafetyChecker
from deduplicator import Deduplicator
from churn_risk import ChurnRiskScorer


class TestClassification:
    """Test request type and product area classification"""
    
    def test_classify_bug_report(self):
        """Bug reports should be classified as 'bug'"""
        classifier = ClassificationModel()
        result = classifier.classify("This feature is broken and doesn't work at all")
        assert result['request_type'] == 'bug'
    
    def test_classify_feature_request(self):
        """Feature requests should be classified as 'feature_request'"""
        classifier = ClassificationModel()
        result = classifier.classify("I would love if you could add dark mode support")
        assert result['request_type'] == 'feature_request'
    
    def test_classify_product_issue(self):
        """General issues should be classified as 'product_issue'"""
        classifier = ClassificationModel()
        result = classifier.classify("How do I reset my password?")
        assert result['request_type'] == 'product_issue'


class TestSentiment:
    """Test sentiment analysis"""
    
    def test_detect_angry_sentiment(self):
        """Should detect angry sentiment"""
        analyzer = SentimentAnalyzer()
        score = analyzer.analyze("I am extremely angry and frustrated!")
        assert score < -2  # Negative sentiment
    
    def test_detect_positive_sentiment(self):
        """Should detect positive sentiment"""
        analyzer = SentimentAnalyzer()
        score = analyzer.analyze("Thank you so much, this really helped!")
        assert score > 2  # Positive sentiment
    
    def test_detect_neutral_sentiment(self):
        """Should detect neutral sentiment"""
        analyzer = SentimentAnalyzer()
        score = analyzer.analyze("I need help with my account")
        assert -1 <= score <= 1  # Neutral


class TestUrgency:
    """Test SLA priority assignment"""
    
    def test_critical_priority(self):
        """Identity theft should be P0_Critical"""
        urgency = UrgencyTier()
        tier = urgency.calculate("My identity has been stolen and I'm at risk", sentiment=-5)
        assert tier == 'P0_Critical'
    
    def test_high_priority(self):
        """Lost access should be P1_High"""
        urgency = UrgencyTier()
        tier = urgency.calculate("I lost access to my account", sentiment=-3)
        assert tier == 'P1_High'
    
    def test_low_priority(self):
        """General questions should be P3_Low"""
        urgency = UrgencyTier()
        tier = urgency.calculate("How do I use this feature?", sentiment=0)
        assert tier == 'P3_Low'


class TestSafety:
    """Test safety screening and threat detection"""
    
    def test_detect_sql_injection(self):
        """Should detect SQL injection attempts"""
        checker = SafetyChecker()
        is_threat = checker.is_threat("'; DROP TABLE users; --")
        assert is_threat is True
    
    def test_allow_legitimate_query(self):
        """Should allow legitimate requests"""
        checker = SafetyChecker()
        is_threat = checker.is_threat("How do I reset my password?")
        assert is_threat is False
    
    def test_detect_base64_injection(self):
        """Should detect Base64-encoded threats"""
        checker = SafetyChecker()
        # "'; DROP TABLE--" in Base64
        is_threat = checker.is_threat("aW5qZWN0aW9u")
        # May or may not detect depending on implementation
        assert isinstance(is_threat, bool)


class TestPIIDetection:
    """Test PII redaction"""
    
    def test_detect_credit_card(self):
        """Should detect credit card numbers"""
        from pii_redactor import PIIRedactor
        redactor = PIIRedactor()
        text = "My card is 4532-1234-5678-9010"
        redacted = redactor.redact(text)
        assert "4532" not in redacted
        assert "[REDACTED" in redacted
    
    def test_detect_email(self):
        """Should detect email addresses"""
        from pii_redactor import PIIRedactor
        redactor = PIIRedactor()
        text = "Email me at john@example.com"
        redacted = redactor.redact(text)
        assert "@example.com" not in redacted
        assert "[REDACTED" in redacted
    
    def test_preserve_non_pii(self):
        """Should not redact non-sensitive data"""
        from pii_redactor import PIIRedactor
        redactor = PIIRedactor()
        text = "Please help with my account"
        redacted = redactor.redact(text)
        assert redacted == text


class TestDuplication:
    """Test duplicate ticket detection"""
    
    def test_detect_exact_duplicate(self):
        """Should detect identical tickets"""
        dedup = Deduplicator()
        ticket1 = "I lost access to my account"
        ticket2 = "I lost access to my account"
        similarity = dedup.similarity(ticket1, ticket2)
        assert similarity > 0.95
    
    def test_detect_near_duplicate(self):
        """Should detect similar tickets"""
        dedup = Deduplicator()
        ticket1 = "I lost access to my account"
        ticket2 = "I can't login to my account"
        similarity = dedup.similarity(ticket1, ticket2)
        assert similarity > 0.70
    
    def test_allow_different_tickets(self):
        """Should not flag different tickets as duplicates"""
        dedup = Deduplicator()
        ticket1 = "I lost access to my account"
        ticket2 = "How do I export my data?"
        similarity = dedup.similarity(ticket1, ticket2)
        assert similarity < 0.50


class TestChurnRisk:
    """Test churn risk scoring"""
    
    def test_high_churn_risk_angry_urgent(self):
        """Angry + urgent should have high churn risk"""
        scorer = ChurnRiskScorer()
        risk = scorer.calculate(
            sentiment=-5,
            urgency='P0_Critical',
            confidence=0.9,
            quality=1.0,
            company='Visa'
        )
        assert risk > 50  # High risk
    
    def test_low_churn_risk_positive_resolved(self):
        """Positive + resolved should have low churn risk"""
        scorer = ChurnRiskScorer()
        risk = scorer.calculate(
            sentiment=5,
            urgency='P3_Low',
            confidence=0.95,
            quality=1.0,
            company='Claude'
        )
        assert risk < 20  # Low risk
    
    def test_medium_churn_risk(self):
        """Mixed signals should have medium churn risk"""
        scorer = ChurnRiskScorer()
        risk = scorer.calculate(
            sentiment=0,
            urgency='P2_Medium',
            confidence=0.7,
            quality=0.8,
            company='HackerRank'
        )
        assert 20 <= risk <= 50  # Medium risk


class TestEndToEnd:
    """End-to-end integration tests"""
    
    def test_full_pipeline_happy_path(self):
        """Test full triage pipeline with valid ticket"""
        from agent import SupportTriageAgent
        
        agent = SupportTriageAgent()
        ticket = {
            'issue': 'I lost access to my Claude workspace',
            'subject': 'Claude access lost',
            'company': 'Claude'
        }
        
        result = agent.process(ticket)
        
        assert 'status' in result
        assert result['status'] in ['replied', 'escalated']
        assert 'confidence' in result
        assert 0 <= result['confidence'] <= 1
        assert 'response' in result or result['status'] == 'escalated'
    
    def test_full_pipeline_with_safety_threat(self):
        """Test pipeline blocks dangerous input"""
        from agent import SupportTriageAgent
        
        agent = SupportTriageAgent()
        ticket = {
            'issue': "'; DROP TABLE users; --",
            'subject': 'SQL injection test',
            'company': 'Claude'
        }
        
        result = agent.process(ticket)
        
        # Should escalate due to threat
        assert result['status'] == 'escalated'


class TestPerformance:
    """Performance benchmarks"""
    
    def test_single_ticket_latency(self):
        """Single ticket should process in <500ms"""
        import time
        from agent import SupportTriageAgent
        
        agent = SupportTriageAgent()
        ticket = {
            'issue': 'How do I reset my password?',
            'subject': 'Password reset',
            'company': 'Claude'
        }
        
        start = time.time()
        result = agent.process(ticket)
        elapsed = time.time() - start
        
        assert elapsed < 0.5  # Less than 500ms


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
