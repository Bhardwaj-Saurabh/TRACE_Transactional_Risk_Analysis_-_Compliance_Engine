"""
Tests for Compliance Officer Agent

The Compliance Officer Agent is responsible for generating regulatory-compliant SAR narratives
using the ReACT (Reasoning-Action-Conclusion-Thought) prompting framework. The agent must:
- Generate concise narratives (≤120 words)
- Include proper regulatory citations
- Apply BSA/AML compliance expertise
- Format outputs for FinCEN SAR submission

This test suite validates the compliance narrative generation functionality.
"""

import pytest
import json
import os
from datetime import datetime
from unittest.mock import Mock

# Import source code directly from starter module
try:
    from src.compliance_officer_agent import ComplianceOfficerAgent
    from src.foundation_sar import (
        CustomerData, AccountData, TransactionData, CaseData,
        ComplianceOfficerOutput, RiskAnalystOutput, ExplainabilityLogger
    )
    # If import succeeds, consider it implemented
    COMPLIANCE_OFFICER_IMPLEMENTED = True

except ImportError:
    # If we can't import, mark as not implemented
    COMPLIANCE_OFFICER_IMPLEMENTED = False


class TestComplianceOfficerAgent:
    """Test ComplianceOfficerAgent core functionality"""
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_agent_initialization(self):
        """Test ComplianceOfficerAgent initializes properly"""
        mock_client = Mock()
        logger = ExplainabilityLogger("test_compliance.jsonl")
        
        agent = ComplianceOfficerAgent(mock_client, logger, model="gpt-4")
        
        assert agent.client == mock_client
        assert agent.logger == logger
        assert agent.model == "gpt-4"
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 200  # Should have substantial ReACT prompt
        
        # Cleanup
        if os.path.exists("test_compliance.jsonl"):
            os.remove("test_compliance.jsonl")
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_generate_compliance_narrative_success(self):
        """Test successful narrative generation with valid response"""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "narrative": "Customer John Doe (CUST_001) conducted multiple cash deposits totaling $29,500 at branch locations over three consecutive days. The deposits were structured via cash to avoid the $10,000 CTR threshold, with amounts of $9,900, $9,800, and $9,800. This pattern suggests possible structuring to evade regulatory reporting requirements.",
    "narrative_reasoning": "Focused on quantitative details and temporal pattern to establish structuring case. Used regulatory terminology and specific statute reference.",
    "regulatory_citations": ["31 USC 5324 (Structuring)", "31 CFR 1020.320 (SAR Filing)", "FinCEN SAR Instructions"],
    "completeness_check": true
}
```'''
        mock_client.chat.completions.create.return_value = mock_response
        
        # Setup logger
        logger = ExplainabilityLogger("test_narrative.jsonl")
        agent = ComplianceOfficerAgent(mock_client, logger)
        
        # Create test case data
        customer = CustomerData(
            customer_id="CUST_001",
            name="John Doe",
            date_of_birth="1980-01-01",
            ssn_last_4="1234",
            address="123 Main St",
            customer_since="2020-01-01",
            risk_rating="Medium"
        )
        
        account = AccountData(
            account_id="ACC_001",
            customer_id="CUST_001",
            account_type="Checking",
            opening_date="2020-01-01",
            current_balance=15000.0,
            average_monthly_balance=12000.0,
            status="Active"
        )
        
        transactions = [
            TransactionData(
                transaction_id="TXN_001",
                account_id="ACC_001",
                transaction_date="2025-01-01",
                transaction_type="Cash_Deposit",
                amount=9900.0,
                description="Cash deposit",
                method="Cash"
            ),
            TransactionData(
                transaction_id="TXN_002",
                account_id="ACC_001",
                transaction_date="2025-01-02",
                transaction_type="Cash_Deposit",
                amount=9800.0,
                description="Cash deposit",
                method="Cash"
            )
        ]
        
        case = CaseData(
            case_id="CASE_001",
            customer=customer,
            accounts=[account],
            transactions=transactions,
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )
        
        # Create risk analysis input with Chain-of-Thought reasoning
        risk_analysis = RiskAnalystOutput(
            classification="Structuring",
            confidence_score=0.85,
            reasoning="Step 1: Reviewed customer profile. Step 2: Identified multiple cash deposits under $10,000. Step 3: Pattern matches BSA structuring. Step 4: High confidence. Step 5: Classified as Structuring.",
            key_indicators=["threshold avoidance", "repeated amounts"],
            risk_level="High"
        )
        
        # Run narrative generation
        result = agent.generate_compliance_narrative(case, risk_analysis)

        # Verify result - check type name instead of isinstance to handle import path differences
        assert type(result).__name__ == 'ComplianceOfficerOutput', f"Expected ComplianceOfficerOutput, got {type(result).__name__}"
        assert "John Doe" in result.narrative
        assert "structuring" in result.narrative.lower() or "threshold" in result.narrative.lower()
        assert len(result.narrative.split()) <= 120  # Word count check
        assert result.completeness_check == True
        assert len(result.regulatory_citations) > 0
        
        # Verify API was called
        mock_client.chat.completions.create.assert_called_once()
        
        # Verify logging
        assert len(logger.entries) == 1
        assert logger.entries[0]["success"] == True
        assert logger.entries[0]["agent_type"] == "ComplianceOfficer"
        
        # Cleanup
        if os.path.exists("test_narrative.jsonl"):
            os.remove("test_narrative.jsonl")
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_narrative_word_count_validation(self):
        """Test narrative word count validation (120 word limit)"""
        # Setup mock with overly long narrative
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        # Create a narrative with more than 120 words
        long_narrative = " ".join(["word"] * 150)  # 150 words
        mock_response.choices[0].message.content = f'''{{
    "narrative": "{long_narrative}",
    "narrative_reasoning": "Test reasoning",
    "regulatory_citations": ["31 CFR 1020.320"],
    "completeness_check": true
}}'''
        mock_client.chat.completions.create.return_value = mock_response
        
        logger = ExplainabilityLogger("test_wordcount.jsonl")
        agent = ComplianceOfficerAgent(mock_client, logger)
        
        # Create minimal test data
        customer = CustomerData(
            customer_id="CUST_TEST",
            name="Test Customer",
            date_of_birth="1980-01-01",
            ssn_last_4="1234",
            address="123 Test St",
            customer_since="2020-01-01",
            risk_rating="Low"
        )
        
        case = CaseData(
            case_id="CASE_WORDCOUNT",
            customer=customer,
            accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_TEST",
                account_id="ACC_TEST",
                transaction_date="2025-01-01",
                transaction_type="Test",
                amount=1000.0,
                description="Test transaction",
                method="Test"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )
        
        risk_analysis = RiskAnalystOutput(
            classification="Other",
            confidence_score=0.5,
            reasoning="Step 1: Reviewed test data. Step 2: No clear patterns. Step 3: No regulatory violations. Step 4: Low risk assessed. Step 5: Classified as Other for testing purposes.",
            key_indicators=["test"],
            risk_level="Low"
        )

        # Should raise ValueError for word count violation
        with pytest.raises(ValueError, match="exceeds 120 word limit"):
            agent.generate_compliance_narrative(case, risk_analysis)
        
        # Cleanup
        if os.path.exists("test_wordcount.jsonl"):
            os.remove("test_wordcount.jsonl")
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_json_parsing_error(self):
        """Test handling of invalid JSON response"""
        # Setup mock with invalid JSON
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response without proper structure"
        mock_client.chat.completions.create.return_value = mock_response
        
        logger = ExplainabilityLogger("test_json_error.jsonl")
        agent = ComplianceOfficerAgent(mock_client, logger)
        
        # Create minimal test case
        customer = CustomerData(
            customer_id="CUST_ERROR",
            name="Error Customer",
            date_of_birth="1980-01-01",
            ssn_last_4="1234",
            address="123 Error St",
            customer_since="2020-01-01",
            risk_rating="Low"
        )
        
        case = CaseData(
            case_id="CASE_ERROR",
            customer=customer,
            accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_ERROR",
                account_id="ACC_ERROR",
                transaction_date="2025-01-01",
                transaction_type="Test",
                amount=100.0,
                description="Error test",
                method="Test"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )
        
        risk_analysis = RiskAnalystOutput(
            classification="Other",
            confidence_score=0.3,
            reasoning="Step 1: Reviewed error test data. Step 2: No patterns identified. Step 3: No regulatory concerns. Step 4: Low confidence. Step 5: Classified as Other for error testing.",
            key_indicators=["error"],
            risk_level="Low"
        )

        # Should raise ValueError for invalid JSON
        with pytest.raises(ValueError, match="Failed to parse Compliance Officer JSON output"):
            agent.generate_compliance_narrative(case, risk_analysis)
        
        # Verify error was logged
        assert len(logger.entries) == 1
        assert logger.entries[0]["success"] == False
        assert "JSON parsing failed" in logger.entries[0]["reasoning"]
        
        # Cleanup
        if os.path.exists("test_json_error.jsonl"):
            os.remove("test_json_error.jsonl")
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_extract_json_from_code_block(self):
        """Test JSON extraction from code blocks"""
        agent = ComplianceOfficerAgent(Mock(), Mock())
        
        response_with_json_block = '''Here is the compliance narrative:
```json
{
    "narrative": "Test narrative for compliance validation",
    "narrative_reasoning": "Generated for testing purposes",
    "regulatory_citations": ["31 CFR 1020.320"],
    "completeness_check": true
}
```
This completes the analysis.'''
        
        extracted = agent._extract_json_from_response(response_with_json_block)
        parsed = json.loads(extracted)
        
        assert parsed["narrative"] == "Test narrative for compliance validation"
        assert parsed["completeness_check"] == True
        assert "31 CFR 1020.320" in parsed["regulatory_citations"]
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_extract_json_from_plain_text(self):
        """Test JSON extraction from plain text response"""
        agent = ComplianceOfficerAgent(Mock(), Mock())
        
        response_plain_json = '''{"narrative": "Plain text compliance narrative", "narrative_reasoning": "Simple extraction test", "regulatory_citations": ["BSA Requirements"], "completeness_check": false}'''
        
        extracted = agent._extract_json_from_response(response_plain_json)
        parsed = json.loads(extracted)
        
        assert parsed["narrative"] == "Plain text compliance narrative"
        assert parsed["completeness_check"] == False
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_extract_json_empty_response(self):
        """Test handling of empty LLM response"""
        agent = ComplianceOfficerAgent(Mock(), Mock())
        
        # Should raise ValueError for empty response
        with pytest.raises(ValueError, match="No JSON content found"):
            agent._extract_json_from_response("")
        
        with pytest.raises(ValueError, match="No JSON content found"):
            agent._extract_json_from_response("   ")
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_format_transactions_for_compliance(self):
        """Test transaction formatting for compliance narratives"""
        agent = ComplianceOfficerAgent(Mock(), Mock())
        
        transactions = [
            TransactionData(
                transaction_id="TXN_001",
                account_id="ACC_001",
                transaction_date="2025-01-01",
                transaction_type="Cash_Deposit",
                amount=9900.0,
                description="Cash deposit at branch",
                method="Cash",
                location="Branch_001"
            ),
            TransactionData(
                transaction_id="TXN_002",
                account_id="ACC_001",
                transaction_date="2025-01-02",
                transaction_type="Wire_Transfer",
                amount=15000.0,
                description="Wire to suspicious account",
                method="Wire"
            )
        ]
        
        formatted = agent._format_transactions_for_compliance(transactions)
        
        assert "1. 2025-01-01: $9,900.00 Cash_Deposit" in formatted
        assert "2. 2025-01-02: $15,000.00 Wire_Transfer" in formatted
        assert "at Branch_001" in formatted
        assert "via Wire" in formatted
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_system_prompt_structure(self):
        """Test system prompt contains required ReACT elements"""
        agent = ComplianceOfficerAgent(Mock(), Mock())
        prompt = agent.system_prompt
        
        # Check for ReACT framework elements
        assert "ReACT" in prompt or "REASONING" in prompt
        assert "Compliance Officer" in prompt
        assert "BSA/AML" in prompt
        
        # Check for narrative requirements
        assert "120 words" in prompt or "word limit" in prompt
        assert "FinCEN" in prompt or "SAR" in prompt
        
        # Check for JSON structure requirement
        assert "JSON" in prompt
        assert "narrative" in prompt
        assert "narrative_reasoning" in prompt
        assert "regulatory_citations" in prompt
        assert "completeness_check" in prompt
    
    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_api_call_parameters(self):
        """Test OpenAI API call uses correct parameters"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"narrative": "Test narrative", "narrative_reasoning": "Test", "regulatory_citations": ["Test"], "completeness_check": true}'''
        mock_client.chat.completions.create.return_value = mock_response
        
        logger = ExplainabilityLogger("test_api_compliance.jsonl")
        agent = ComplianceOfficerAgent(mock_client, logger, model="gpt-3.5-turbo")
        
        # Create minimal case and risk analysis
        customer = CustomerData(
            customer_id="CUST_API",
            name="API Test",
            date_of_birth="1990-01-01",
            ssn_last_4="9999",
            address="API Test Address",
            customer_since="2021-01-01",
            risk_rating="Low"
        )
        
        case = CaseData(
            case_id="CASE_API",
            customer=customer,
            accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_API",
                account_id="ACC_API",
                transaction_date="2025-01-01",
                transaction_type="Test",
                amount=1000.0,
                description="API test",
                method="Test"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"api": "test"}
        )
        
        risk_analysis = RiskAnalystOutput(
            classification="Other",
            confidence_score=0.5,
            reasoning="Step 1: Reviewed API test data. Step 2: No suspicious patterns. Step 3: No regulatory mapping needed. Step 4: Low risk quantified. Step 5: Classified as Other for API testing.",
            key_indicators=["test"],
            risk_level="Low"
        )

        agent.generate_compliance_narrative(case, risk_analysis)
        
        # Verify API call parameters
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-3.5-turbo"
        assert call_args.kwargs["temperature"] == 0.2  # Lower temperature for compliance
        assert call_args.kwargs["max_tokens"] == 800
        assert len(call_args.kwargs["messages"]) == 2
        assert call_args.kwargs["messages"][0]["role"] == "system"
        assert call_args.kwargs["messages"][1]["role"] == "user"
        
        # Cleanup
        if os.path.exists("test_api_compliance.jsonl"):
            os.remove("test_api_compliance.jsonl")


class TestFiveWsNarrativeValidation:
    """Test Five W's (who/what/when/where/why) narrative validation"""

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_extract_locations_from_transactions(self):
        """Test location extraction from transactions"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        transactions = [
            TransactionData(
                transaction_id="TXN_001",
                account_id="ACC_001",
                transaction_date="2025-01-01",
                transaction_type="Cash_Deposit",
                amount=9900.0,
                description="Cash deposit",
                method="Cash",
                location="Branch_001"
            ),
            TransactionData(
                transaction_id="TXN_002",
                account_id="ACC_001",
                transaction_date="2025-01-02",
                transaction_type="Wire_Transfer",
                amount=15000.0,
                description="Wire transfer",
                method="Wire",
                location="Online"
            )
        ]

        locations = agent._extract_locations_from_transactions(transactions)

        assert "Branch_001" in locations
        assert "Online" in locations
        assert "via Cash" in locations
        assert "via Wire" in locations

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_extract_locations_empty_transactions(self):
        """Test location extraction with no location data"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        transactions = [
            TransactionData(
                transaction_id="TXN_001",
                account_id="ACC_001",
                transaction_date="2025-01-01",
                transaction_type="Cash_Deposit",
                amount=9900.0,
                description="Cash deposit",
                method="Cash"
            )
        ]

        locations = agent._extract_locations_from_transactions(transactions)
        assert "via Cash" in locations

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_who_element(self):
        """Test WHO element detection in narrative"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Narrative with customer name
        narrative_with_name = "Customer John Doe conducted multiple suspicious transactions."
        assert agent._check_who_element(narrative_with_name, None) == True

        # Narrative with customer ID
        narrative_with_id = "Subject CUST_001 engaged in structuring activity."
        assert agent._check_who_element(narrative_with_id, None) == True

        # Narrative without identification
        narrative_without_who = "Multiple deposits were made."
        assert agent._check_who_element(narrative_without_who, None) == False

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_what_element(self):
        """Test WHAT element detection in narrative"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Narrative with activity description
        narrative_with_what = "The customer made multiple cash deposits totaling $29,500."
        assert agent._check_what_element(narrative_with_what.lower()) == True

        # Narrative with structuring mention
        narrative_structuring = "The pattern suggests structuring to evade reporting."
        assert agent._check_what_element(narrative_structuring.lower()) == True

        # Narrative without activity
        narrative_without_what = "The individual was observed."
        assert agent._check_what_element(narrative_without_what.lower()) == False

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_when_element(self):
        """Test WHEN element detection in narrative"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Narrative with date
        narrative_with_date = "On 2025-01-15, the customer made a deposit."
        assert agent._check_when_element(narrative_with_date) == True

        # Narrative with time period
        narrative_with_period = "Over three consecutive days, deposits were made."
        assert agent._check_when_element(narrative_with_period) == True

        # Narrative without temporal info
        narrative_without_when = "Deposits were made to the account."
        assert agent._check_when_element(narrative_without_when) == False

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_where_element(self):
        """Test WHERE element detection in narrative"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Narrative with branch location
        narrative_with_branch = "Deposits were made at branch locations."
        assert agent._check_where_element(narrative_with_branch.lower()) == True

        # Narrative with method
        narrative_with_method = "Funds were transferred via wire to offshore accounts."
        assert agent._check_where_element(narrative_with_method.lower()) == True

        # Narrative with online
        narrative_online = "Transactions were conducted online through the banking portal."
        assert agent._check_where_element(narrative_online.lower()) == True

        # Narrative without location
        narrative_without_where = "Money was moved repeatedly."
        assert agent._check_where_element(narrative_without_where.lower()) == False

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_why_element(self):
        """Test WHY element detection in narrative"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Narrative with suspicious explanation
        narrative_with_why = "This activity is suspicious as it appears to evade the $10,000 CTR threshold."
        assert agent._check_why_element(narrative_with_why.lower()) == True

        # Narrative with structuring pattern
        narrative_structuring = "The pattern is consistent with structuring violations."
        assert agent._check_why_element(narrative_structuring.lower()) == True

        # Narrative without explanation
        narrative_without_why = "Deposits were made over several days."
        assert agent._check_why_element(narrative_without_why.lower()) == False

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_validate_narrative_with_all_five_ws(self):
        """Test narrative validation with all Five W's present"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        complete_narrative = (
            "Customer John Doe (CUST_001) conducted multiple cash deposits totaling $29,500 "
            "at branch locations over three consecutive days (2025-01-01 to 2025-01-03). "
            "This pattern is suspicious as the amounts appear structured to evade the $10,000 CTR threshold."
        )

        validation = agent._validate_narrative_compliance(complete_narrative)

        assert validation["five_ws"]["who"] == True
        assert validation["five_ws"]["what"] == True
        assert validation["five_ws"]["when"] == True
        assert validation["five_ws"]["where"] == True
        assert validation["five_ws"]["why"] == True
        assert validation["five_ws_complete"] == True
        assert len(validation["missing_elements"]) == 0

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_validate_narrative_missing_where(self):
        """Test narrative validation detects missing WHERE element"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        narrative_missing_where = (
            "Customer John Doe (CUST_001) made cash deposits totaling $29,500 "
            "over three consecutive days (2025-01-01 to 2025-01-03). "
            "This pattern appears to evade the $10,000 CTR threshold."
        )

        validation = agent._validate_narrative_compliance(narrative_missing_where)

        assert validation["five_ws"]["who"] == True
        assert validation["five_ws"]["what"] == True
        assert validation["five_ws"]["when"] == True
        assert validation["five_ws"]["where"] == False  # Missing WHERE
        assert validation["five_ws"]["why"] == True
        assert validation["five_ws_complete"] == False
        assert "where" in validation["missing_elements"]

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_system_prompt_contains_five_ws(self):
        """Test system prompt includes Five W's requirements"""
        agent = ComplianceOfficerAgent(Mock(), Mock())
        prompt = agent.system_prompt

        # Check for Five W's framework
        assert "WHO" in prompt
        assert "WHAT" in prompt
        assert "WHEN" in prompt
        assert "WHERE" in prompt
        assert "WHY" in prompt

        # Check for specific WHERE requirements
        assert "location" in prompt.lower() or "Location" in prompt
        assert "channel" in prompt.lower() or "Channel" in prompt

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_user_prompt_includes_location_context(self):
        """Test user prompt includes location/channel information"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        customer = CustomerData(
            customer_id="CUST_001",
            name="Test Customer",
            date_of_birth="1980-01-01",
            ssn_last_4="1234",
            address="123 Test St",
            customer_since="2020-01-01",
            risk_rating="Medium"
        )

        case = CaseData(
            case_id="CASE_001",
            customer=customer,
            accounts=[],
            transactions=[
                TransactionData(
                    transaction_id="TXN_001",
                    account_id="ACC_001",
                    transaction_date="2025-01-01",
                    transaction_type="Cash_Deposit",
                    amount=9900.0,
                    description="Cash deposit",
                    method="Cash",
                    location="Branch_Downtown"
                )
            ],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        risk_analysis = RiskAnalystOutput(
            classification="Structuring",
            confidence_score=0.85,
            reasoning="Step 1: Reviewed customer profile. Step 2: Identified cash deposits under threshold. Step 3: Pattern matches structuring. Step 4: High confidence. Step 5: Classified as Structuring.",
            key_indicators=["threshold avoidance"],
            risk_level="High"
        )

        prompt = agent._build_user_prompt(case, risk_analysis)

        # Check for Five W's sections in prompt
        assert "WHO" in prompt
        assert "WHAT" in prompt
        assert "WHEN" in prompt
        assert "WHERE" in prompt
        assert "WHY" in prompt

        # Check for location information
        assert "Branch_Downtown" in prompt or "via Cash" in prompt
        assert "Five W's" in prompt


class TestPreFinalizationValidation:
    """Test deterministic pre-finalization validation gate"""

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_dollar_amounts_valid(self):
        """Test dollar amount detection with valid amounts"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Various valid dollar amount formats
        assert agent._check_dollar_amounts("Total deposits of $29,500") == True
        assert agent._check_dollar_amounts("Amount: $9,900.00") == True
        assert agent._check_dollar_amounts("Transactions totaling $10000") == True
        assert agent._check_dollar_amounts("USD 15,000 transferred") == True

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_check_dollar_amounts_invalid(self):
        """Test dollar amount detection fails when no amounts present"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        assert agent._check_dollar_amounts("Multiple large deposits were made") == False
        assert agent._check_dollar_amounts("Suspicious activity detected") == False

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_validate_regulatory_citations_valid(self):
        """Test regulatory citation validation with valid citations"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        citations = ["31 CFR 1020.320", "31 USC 5324", "FinCEN SAR Instructions"]
        result = agent._validate_regulatory_citations(citations)

        assert result["is_valid"] == True
        assert result["has_citations"] == True
        assert len(result["valid_citations"]) >= 1

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_validate_regulatory_citations_empty(self):
        """Test regulatory citation validation fails with empty list"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        result = agent._validate_regulatory_citations([])

        assert result["is_valid"] == False
        assert result["has_citations"] == False
        assert result["error_message"] == "No regulatory citations provided"

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_validate_regulatory_citations_unrecognized(self):
        """Test regulatory citation validation with unrecognized citations"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        citations = ["Made up regulation 123", "Fake law XYZ"]
        result = agent._validate_regulatory_citations(citations)

        assert result["is_valid"] == False
        assert result["has_citations"] == True
        assert len(result["unrecognized_citations"]) == 2

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_pre_finalization_validation_passes(self):
        """Test pre-finalization validation with complete narrative"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        complete_narrative = (
            "Customer John Doe (CUST_001) conducted multiple cash deposits totaling $29,500 "
            "at branch locations over three consecutive days (2025-01-01 to 2025-01-03). "
            "This pattern is suspicious as the amounts appear structured to evade the $10,000 CTR threshold."
        )

        customer = CustomerData(
            customer_id="CUST_001", name="John Doe",
            date_of_birth="1980-01-01", ssn_last_4="1234",
            address="123 Test St", customer_since="2020-01-01",
            risk_rating="Medium"
        )
        case = CaseData(
            case_id="CASE_001", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_001", account_id="ACC_001",
                transaction_date="2025-01-01", transaction_type="Cash_Deposit",
                amount=9900.0, description="Cash deposit", method="Cash"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        citations = ["31 CFR 1020.320", "31 USC 5324"]

        result = agent._pre_finalization_validation(
            narrative=complete_narrative,
            citations=citations,
            case_data=case,
            model_completeness_check=True
        )

        assert result["is_valid"] == True
        assert result["can_finalize"] == True
        assert result["word_count_valid"] == True
        assert result["five_ws_complete"] == True
        assert result["has_dollar_amounts"] == True
        assert result["citations_valid"] == True
        assert len(result["failed_checks"]) == 0

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_pre_finalization_validation_blocks_missing_elements(self):
        """Test pre-finalization validation blocks narrative with missing elements"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        # Narrative missing WHERE and dollar amounts
        incomplete_narrative = (
            "Customer John Doe made deposits over several days. "
            "This pattern appears suspicious."
        )

        customer = CustomerData(
            customer_id="CUST_001", name="John Doe",
            date_of_birth="1980-01-01", ssn_last_4="1234",
            address="123 Test St", customer_since="2020-01-01",
            risk_rating="Medium"
        )
        case = CaseData(
            case_id="CASE_001", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_001", account_id="ACC_001",
                transaction_date="2025-01-01", transaction_type="Cash_Deposit",
                amount=9900.0, description="Cash deposit", method="Cash"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        citations = ["31 CFR 1020.320"]

        result = agent._pre_finalization_validation(
            narrative=incomplete_narrative,
            citations=citations,
            case_data=case,
            model_completeness_check=True  # Model says complete but it's not
        )

        assert result["is_valid"] == False
        assert result["can_finalize"] == False
        assert "dollar_amounts" in result["failed_checks"]
        assert result.get("model_discrepancy") == True  # Model said complete but validation failed

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_pre_finalization_validation_blocks_empty_citations(self):
        """Test pre-finalization validation blocks narrative with empty citations"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        narrative = (
            "Customer John Doe (CUST_001) conducted cash deposits totaling $29,500 "
            "at branch locations over three consecutive days. "
            "This pattern is suspicious as it evades the CTR threshold."
        )

        result = agent._pre_finalization_validation(
            narrative=narrative,
            citations=[],  # Empty citations
            case_data=None,
            model_completeness_check=True
        )

        assert result["is_valid"] == False
        assert result["can_finalize"] == False
        assert "citations" in result["failed_checks"]

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_narrative_validation_error_exception(self):
        """Test NarrativeValidationError contains proper details"""
        try:
            from src.compliance_officer_agent import NarrativeValidationError
        except ImportError:
            from compliance_officer_agent import NarrativeValidationError

        validation_result = {
            "is_valid": False,
            "can_finalize": False,
            "missing_elements": ["where", "when"],
            "failed_checks": ["five_ws", "dollar_amounts"],
            "error_messages": ["Missing where element", "No dollar amounts"]
        }

        error = NarrativeValidationError("Validation failed", validation_result)

        assert error.missing_elements == ["where", "when"]
        assert error.failed_checks == ["five_ws", "dollar_amounts"]
        assert "Missing narrative elements: where, when" in error.get_failure_summary()

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_generate_narrative_with_validation_success(self):
        """Test generate_compliance_narrative succeeds with valid response"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "narrative": "Customer John Doe (CUST_001) conducted multiple cash deposits totaling $29,500 at branch locations over three consecutive days (2025-01-01 to 2025-01-03). This pattern is suspicious as the amounts appear structured to evade the $10,000 CTR threshold under 31 USC 5324.",
    "narrative_reasoning": "Focused on Five W's: WHO (John Doe), WHAT (cash deposits), WHEN (three days), WHERE (branch), WHY (structuring).",
    "regulatory_citations": ["31 CFR 1020.320", "31 USC 5324", "FinCEN SAR Instructions"],
    "completeness_check": true
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_validation_success.jsonl")
        agent = ComplianceOfficerAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_001", name="John Doe",
            date_of_birth="1980-01-01", ssn_last_4="1234",
            address="123 Test St", customer_since="2020-01-01",
            risk_rating="Medium"
        )
        case = CaseData(
            case_id="CASE_001", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_001", account_id="ACC_001",
                transaction_date="2025-01-01", transaction_type="Cash_Deposit",
                amount=9900.0, description="Cash deposit", method="Cash",
                location="Branch_001"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )
        risk_analysis = RiskAnalystOutput(
            classification="Structuring", confidence_score=0.85,
            reasoning="Step 1: Data reviewed. Step 2: Patterns found. Step 3: BSA mapping. Step 4: High risk. Step 5: Structuring.",
            key_indicators=["threshold_avoidance"],
            risk_level="High"
        )

        result = agent.generate_compliance_narrative(case, risk_analysis)

        assert result is not None
        assert "John Doe" in result.narrative
        assert "$29,500" in result.narrative
        assert result.completeness_check == True

        if os.path.exists("test_validation_success.jsonl"):
            os.remove("test_validation_success.jsonl")

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_generate_narrative_raises_on_validation_failure(self):
        """Test generate_compliance_narrative raises NarrativeValidationError when validation fails"""
        try:
            from src.compliance_officer_agent import NarrativeValidationError
        except ImportError:
            from compliance_officer_agent import NarrativeValidationError

        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        # Response missing dollar amounts and WHERE element
        mock_response.choices[0].message.content = '''```json
{
    "narrative": "Customer made some deposits. This is suspicious.",
    "narrative_reasoning": "Brief narrative.",
    "regulatory_citations": [],
    "completeness_check": false
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_validation_failure.jsonl")
        agent = ComplianceOfficerAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_001", name="Test Customer",
            date_of_birth="1980-01-01", ssn_last_4="1234",
            address="123 Test St", customer_since="2020-01-01",
            risk_rating="Medium"
        )
        case = CaseData(
            case_id="CASE_001", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_001", account_id="ACC_001",
                transaction_date="2025-01-01", transaction_type="Cash_Deposit",
                amount=9900.0, description="Cash deposit", method="Cash"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )
        risk_analysis = RiskAnalystOutput(
            classification="Structuring", confidence_score=0.85,
            reasoning="Step 1: Data reviewed. Step 2: Patterns found. Step 3: BSA. Step 4: Risk. Step 5: Done.",
            key_indicators=["test"],
            risk_level="High"
        )

        # Should raise NarrativeValidationError after max attempts
        with pytest.raises(NarrativeValidationError) as exc_info:
            agent.generate_compliance_narrative(case, risk_analysis, max_regeneration_attempts=0)

        assert "validation failed" in str(exc_info.value).lower()
        assert len(exc_info.value.failed_checks) > 0

        if os.path.exists("test_validation_failure.jsonl"):
            os.remove("test_validation_failure.jsonl")

    @pytest.mark.skipif(not COMPLIANCE_OFFICER_IMPLEMENTED, reason="Compliance Officer Agent not implemented yet")
    def test_build_regeneration_prompt(self):
        """Test regeneration prompt includes failure details"""
        agent = ComplianceOfficerAgent(Mock(), Mock())

        validation_result = {
            "word_count": 150,
            "failed_checks": ["word_count", "dollar_amounts", "citations"],
            "missing_elements": ["where"]
        }

        prompt = agent._build_regeneration_prompt(validation_result)

        assert "Word count (150) exceeds 120 word limit" in prompt
        assert "dollar amounts" in prompt
        assert "regulatory citations" in prompt
        assert "Missing required elements: where" in prompt
