"""
Unit Tests for Services
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import (
    GherkinScenario,
    AcceptanceCriteria,
    TestScenario,
    TestStep,
    TestSuite,
    TestScenarioType,
)


class TestGherkinScenario:
    """Tests for GherkinScenario model"""
    
    def test_to_gherkin_text(self):
        """Test Gherkin text generation"""
        scenario = GherkinScenario(
            id="AC-001",
            title="User can login",
            given=["user is on login page"],
            when=["user enters credentials", "user clicks login"],
            then=["user sees dashboard"],
            tags=["smoke", "positive"]
        )
        
        text = scenario.to_gherkin_text()
        
        assert "@smoke @positive" in text
        assert "Scenario: User can login" in text
        assert "Given user is on login page" in text
        assert "When user enters credentials" in text
        assert "Then user sees dashboard" in text
    
    def test_scenario_outline_with_examples(self):
        """Test Scenario Outline with examples"""
        scenario = GherkinScenario(
            id="AC-002",
            title="Login with different roles",
            given=["user has <role> account"],
            when=["user logs in"],
            then=["user sees <dashboard>"],
            tags=["data-driven"],
            examples={
                "role": ["admin", "user"],
                "dashboard": ["admin panel", "user home"]
            }
        )
        
        text = scenario.to_gherkin_text()
        
        assert "Examples:" in text
        assert "| role | dashboard |" in text
        assert "| admin | admin panel |" in text


class TestAcceptanceCriteria:
    """Tests for AcceptanceCriteria model"""
    
    def test_to_gherkin_full_feature(self):
        """Test full feature file generation"""
        criteria = AcceptanceCriteria(
            story_key="PROJ-123",
            feature_name="User Authentication",
            background={"given": ["application is running"]},
            scenarios=[
                GherkinScenario(
                    id="AC-001",
                    title="Successful login",
                    given=["user has account"],
                    when=["user logs in"],
                    then=["user is authenticated"],
                    tags=["positive"]
                )
            ],
            llm_provider="gemini"
        )
        
        text = criteria.to_gherkin_text()
        
        assert "Feature: User Authentication" in text
        assert "Background:" in text
        assert "Given application is running" in text
        assert "Scenario: Successful login" in text


class TestTestSuite:
    """Tests for TestSuite model"""
    
    def test_counts_calculated(self):
        """Test that scenario counts are calculated"""
        suite = TestSuite(
            story_key="PROJ-123",
            suite_name="Test Suite",
            scenarios=[
                TestScenario(
                    id="TS-001", title="Positive test", description="",
                    type=TestScenarioType.POSITIVE, steps=[
                        TestStep(order=1, action="do", expected_result="done")
                    ],
                    acceptance_criteria_ref="AC-001"
                ),
                TestScenario(
                    id="TS-002", title="Negative test", description="",
                    type=TestScenarioType.NEGATIVE, steps=[
                        TestStep(order=1, action="do", expected_result="error")
                    ],
                    acceptance_criteria_ref="AC-001"
                ),
            ],
            llm_provider="gemini"
        )
        
        assert suite.total_scenarios == 2
        assert suite.positive_count == 1
        assert suite.negative_count == 1
        assert suite.edge_case_count == 0


class TestLLMFactory:
    """Tests for LLM Factory"""
    
    @patch('app.llm.factory.settings')
    def test_get_available_providers(self, mock_settings):
        """Test getting available providers"""
        mock_settings.gemini_api_key = "key1"
        mock_settings.claude_api_key = None
        mock_settings.openai_api_key = "key2"
        
        from app.llm.factory import LLMFactory
        
        # Provider availability depends on configured keys
        providers = LLMFactory._providers
        assert "gemini" in providers
        assert "claude" in providers
        assert "openai" in providers


class TestSecurity:
    """Tests for security module"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        from app.core.security import get_password_hash, verify_password
        
        password = "SecurePass123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("WrongPass", hashed)
    
    def test_jwt_token_creation(self):
        """Test JWT token creation and decoding"""
        from app.core.security import create_access_token, decode_token
        
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)
        
        decoded = decode_token(token)
        
        assert decoded is not None
        assert decoded.sub == "user123"
        assert decoded.email == "test@example.com"
