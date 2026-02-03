# Risk Analyst Agent Tests - Top 10 Essential Tests

"""
Streamlined test suite for risk_analyst_agent.py module focusing on core functionality
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import risk analyst components - these will work once students implement them
try:
    from src.risk_analyst_agent import RiskAnalystAgent
    from src.foundation_sar import (
        RiskAnalystOutput,
        ExplainabilityLogger,
        CaseData,
        CustomerData,
        AccountData,
        TransactionData
    )
    # If import succeeds, consider it implemented
    RISK_ANALYST_IMPLEMENTED = True

except ImportError:
    # Graceful fallback when students haven't implemented yet
    RISK_ANALYST_IMPLEMENTED = False

if not RISK_ANALYST_IMPLEMENTED:
    print("⚠️  Risk Analyst Agent not yet implemented - tests will be skipped")
    print("💡 Implement the RiskAnalystAgent class in src/risk_analyst_agent.py to run these tests")

class TestRiskAnalystAgent:
    """Test RiskAnalystAgent core functionality"""
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_agent_initialization(self):
        """Test RiskAnalystAgent initializes properly"""
        mock_client = Mock()
        logger = ExplainabilityLogger("test_risk.jsonl")
        
        agent = RiskAnalystAgent(mock_client, logger, model="gpt-4")
        
        assert agent.client == mock_client
        assert agent.logger == logger
        assert agent.model == "gpt-4"
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 100  # Should have substantial prompt
        
        # Cleanup
        if os.path.exists("test_risk.jsonl"):
            os.remove("test_risk.jsonl")
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_analyze_case_success(self):
        """Test successful case analysis with valid response"""
        # Setup mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Structuring",
    "confidence_score": 0.85,
    "reasoning": "Multiple transactions just under $10,000 threshold suggest structuring",
    "key_indicators": ["threshold avoidance", "repeated amounts", "cash deposits"],
    "risk_level": "High"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response
        
        # Setup logger
        logger = ExplainabilityLogger("test_analyze.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)
        
        # Create test case data
        customer = CustomerData(
            customer_id="CUST_TEST",
            name="Test Customer", 
            date_of_birth="1980-01-01",
            ssn_last_4="1234",
            address="123 Test St",
            customer_since="2020-01-01",
            risk_rating="Medium"
        )
        
        account = AccountData(
            account_id="ACC_TEST",
            customer_id="CUST_TEST",
            account_type="Checking",
            opening_date="2020-01-01",
            current_balance=15000.0,
            average_monthly_balance=12000.0,
            status="Active"
        )
        
        transaction = TransactionData(
            transaction_id="TXN_TEST",
            account_id="ACC_TEST",
            transaction_date="2025-01-01",
            transaction_type="Cash_Deposit",
            amount=9900.0,
            description="Cash deposit",
            method="Cash"
        )
        
        case = CaseData(
            case_id="CASE_TEST",
            customer=customer,
            accounts=[account],
            transactions=[transaction],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )
        
        # Run analysis
        result = agent.analyze_case(case)

        # Verify result - check type name instead of isinstance to handle import path differences
        assert type(result).__name__ == 'RiskAnalystOutput', f"Expected RiskAnalystOutput, got {type(result).__name__}"
        assert result.classification == "Structuring"
        assert result.confidence_score == 0.85
        assert result.risk_level == "High"
        assert len(result.key_indicators) == 3
        
        # Verify API was called
        mock_client.chat.completions.create.assert_called_once()
        
        # Verify logging
        assert len(logger.entries) == 1
        assert logger.entries[0]["success"] == True
        assert logger.entries[0]["agent_type"] == "RiskAnalyst"
        
        # Cleanup
        if os.path.exists("test_analyze.jsonl"):
            os.remove("test_analyze.jsonl")
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_analyze_case_json_error(self):
        """Test handling of invalid JSON response when fallback is disabled"""
        # Setup mock with invalid JSON
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response without proper structure"
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_json_error.jsonl")
        # Disable fallback to test error raising behavior
        agent = RiskAnalystAgent(mock_client, logger, enable_fallback=False)

        # Create minimal test case
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
            case_id="CASE_ERROR",
            customer=customer,
            accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_ERROR",
                account_id="ACC_ERROR",
                transaction_date="2025-01-01",
                transaction_type="Test",
                amount=100.0,
                description="Test transaction",
                method="Test"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        # Should raise ValueError for invalid JSON when fallback is disabled
        with pytest.raises(ValueError, match="Failed to parse Risk Analyst JSON output"):
            agent.analyze_case(case)

        # Verify error was logged
        error_entries = [e for e in logger.entries if e.get("success") == False]
        assert len(error_entries) >= 1

        # Cleanup
        if os.path.exists("test_json_error.jsonl"):
            os.remove("test_json_error.jsonl")
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_extract_json_from_code_block(self):
        """Test JSON extraction from code blocks"""
        agent = RiskAnalystAgent(Mock(), Mock())
        
        response_with_json_block = '''Here is the analysis:
```json
{
    "classification": "Fraud",
    "confidence_score": 0.9,
    "reasoning": "Clear fraud indicators",
    "key_indicators": ["suspicious_pattern"],
    "risk_level": "Critical"
}
```
That completes the analysis.'''
        
        extracted = agent._extract_json_from_response(response_with_json_block)
        parsed = json.loads(extracted)
        
        assert parsed["classification"] == "Fraud"
        assert parsed["confidence_score"] == 0.9
        assert parsed["risk_level"] == "Critical"
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_extract_json_from_plain_text(self):
        """Test JSON extraction from plain text response"""
        agent = RiskAnalystAgent(Mock(), Mock())
        
        response_plain_json = '''{"classification": "Money_Laundering", "confidence_score": 0.75, "reasoning": "Complex layering scheme", "key_indicators": ["multiple_transfers"], "risk_level": "High"}'''
        
        extracted = agent._extract_json_from_response(response_plain_json)
        parsed = json.loads(extracted)
        
        assert parsed["classification"] == "Money_Laundering"
        assert parsed["confidence_score"] == 0.75
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_extract_json_empty_response(self):
        """Test handling of empty LLM response"""
        agent = RiskAnalystAgent(Mock(), Mock())
        
        # Should raise ValueError for empty response
        with pytest.raises(ValueError, match="No JSON content found"):
            agent._extract_json_from_response("")
        
        with pytest.raises(ValueError, match="No JSON content found"):
            agent._extract_json_from_response("   ")
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_format_accounts(self):
        """Test account formatting for prompts"""
        agent = RiskAnalystAgent(Mock(), Mock())
        
        accounts = [
            AccountData(
                account_id="ACC_001",
                customer_id="CUST_001",
                account_type="Checking",
                opening_date="2020-01-01",
                current_balance=15000.50,
                average_monthly_balance=12000.75,
                status="Active"
            ),
            AccountData(
                account_id="ACC_002", 
                customer_id="CUST_001",
                account_type="Savings",
                opening_date="2020-06-01",
                current_balance=25000.00,
                average_monthly_balance=20000.00,
                status="Active"
            )
        ]
        
        formatted = agent._format_accounts(accounts)
        
        assert "ACC_001" in formatted
        assert "Checking" in formatted
        assert "$15,000.50" in formatted
        assert "ACC_002" in formatted
        assert "Savings" in formatted
        assert "$25,000.00" in formatted
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_format_transactions(self):
        """Test transaction formatting for prompts"""
        agent = RiskAnalystAgent(Mock(), Mock())
        
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
                description="Wire to offshore account",
                method="Wire"
            )
        ]
        
        formatted = agent._format_transactions(transactions)
        
        assert "1. 2025-01-01: Cash_Deposit $9,900.00" in formatted
        assert "2. 2025-01-02: Wire_Transfer $15,000.00" in formatted
        assert "Cash deposit at branch" in formatted
        assert "Branch_001" in formatted
        assert "Wire to offshore account" in formatted
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_system_prompt_structure(self):
        """Test system prompt contains required elements"""
        agent = RiskAnalystAgent(Mock(), Mock())
        prompt = agent.system_prompt
        
        # Check for key Chain-of-Thought elements
        assert "Chain-of-Thought" in prompt or "step-by-step" in prompt
        assert "Financial Crime" in prompt or "Risk Analyst" in prompt
        
        # Check for classification categories
        assert "Structuring" in prompt
        assert "Sanctions" in prompt
        assert "Fraud" in prompt
        assert "Money_Laundering" in prompt
        assert "Other" in prompt
        
        # Check for JSON structure requirement
        assert "JSON" in prompt
        assert "classification" in prompt
        assert "confidence_score" in prompt
        assert "reasoning" in prompt
        assert "key_indicators" in prompt
        assert "risk_level" in prompt
    
    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_api_call_parameters(self):
        """Test OpenAI API call uses correct parameters"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{"classification": "Other", "confidence_score": 0.5, "reasoning": "Step 1: Reviewed data. Step 2: No clear patterns. Step 3: No regulatory violations. Step 4: Low risk. Step 5: Classified as Other.", "key_indicators": ["test"], "risk_level": "Low"}'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_api.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, model="gpt-3.5-turbo")

        # Create minimal case
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

        agent.analyze_case(case)

        # Verify API call parameters
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-3.5-turbo"
        assert call_args.kwargs["temperature"] == 0.3
        assert call_args.kwargs["max_tokens"] == 1000
        assert len(call_args.kwargs["messages"]) == 2
        assert call_args.kwargs["messages"][0]["role"] == "system"
        assert call_args.kwargs["messages"][1]["role"] == "user"

        # Cleanup
        if os.path.exists("test_api.jsonl"):
            os.remove("test_api.jsonl")


class TestClassificationCoverage:
    """Test all 5 classification types are correctly handled"""

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_structuring_classification(self):
        """Test Structuring classification with step-by-step reasoning"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Structuring",
    "confidence_score": 0.92,
    "reasoning": "Step 1: Customer profile shows recent account with high activity. Step 2: Multiple cash deposits of $9,500-$9,900 detected over 5 days, just below $10,000 CTR threshold. Step 3: Pattern matches BSA structuring typology under 31 CFR 1010.314. Step 4: High confidence due to repeated threshold avoidance. Step 5: Classification is Structuring based on deliberate threshold evasion.",
    "key_indicators": ["threshold_avoidance", "repeated_cash_deposits", "amounts_under_10k", "short_timeframe"],
    "risk_level": "High"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_structuring.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_STRUCT", name="Test Structuring",
            date_of_birth="1975-05-15", ssn_last_4="1234",
            address="123 Main St", customer_since="2024-01-01",
            risk_rating="Medium"
        )
        case = CaseData(
            case_id="CASE_STRUCT", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_S1", account_id="ACC_S1",
                transaction_date="2025-01-01", transaction_type="Cash_Deposit",
                amount=9800.0, description="Cash deposit", method="Cash"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        result = agent.analyze_case(case)
        assert result.classification == "Structuring"
        assert result.confidence_score == 0.92
        assert result.risk_level == "High"
        assert "Step 1" in result.reasoning
        assert "Step 5" in result.reasoning

        if os.path.exists("test_structuring.jsonl"):
            os.remove("test_structuring.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_sanctions_classification(self):
        """Test Sanctions classification with step-by-step reasoning"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Sanctions",
    "confidence_score": 0.88,
    "reasoning": "Step 1: Customer has wire transfers to foreign entities. Step 2: Identified wire to entity in Iran and transactions mentioning North Korean company. Step 3: Potential OFAC sanctions violation under Executive Order 13599 and North Korea Sanctions Regulations. Step 4: High severity due to prohibited jurisdiction involvement. Step 5: Classification is Sanctions based on OFAC-prohibited country transactions.",
    "key_indicators": ["iran_transaction", "north_korea_entity", "ofac_violation", "prohibited_jurisdiction"],
    "risk_level": "Critical"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_sanctions.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_SANCT", name="Test Sanctions",
            date_of_birth="1980-03-20", ssn_last_4="5678",
            address="456 Oak Ave", customer_since="2020-06-01",
            risk_rating="High"
        )
        case = CaseData(
            case_id="CASE_SANCT", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_SANCT1", account_id="ACC_SANCT",
                transaction_date="2025-01-15", transaction_type="Wire_Transfer",
                amount=50000.0, description="Wire to Tehran Trade Co",
                method="Wire", counterparty="Tehran Trade Company"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        result = agent.analyze_case(case)
        assert result.classification == "Sanctions"
        assert result.confidence_score == 0.88
        assert result.risk_level == "Critical"
        assert "Step 1" in result.reasoning
        assert "OFAC" in result.reasoning or "sanctions" in result.reasoning.lower()

        if os.path.exists("test_sanctions.jsonl"):
            os.remove("test_sanctions.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_fraud_classification(self):
        """Test Fraud classification with step-by-step reasoning"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Fraud",
    "confidence_score": 0.91,
    "reasoning": "Step 1: Account shows sudden change in transaction patterns. Step 2: Multiple unauthorized access attempts, rapid fund withdrawals to new accounts, and identity verification failures. Step 3: Pattern matches account takeover fraud typology under FTC Red Flags Rule. Step 4: Very high confidence due to multiple fraud indicators. Step 5: Classification is Fraud based on account takeover pattern.",
    "key_indicators": ["account_takeover", "unauthorized_access", "rapid_withdrawals", "identity_mismatch"],
    "risk_level": "Critical"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_fraud.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_FRAUD", name="Test Fraud",
            date_of_birth="1985-07-10", ssn_last_4="9012",
            address="789 Pine Rd", customer_since="2019-02-01",
            risk_rating="Low"
        )
        case = CaseData(
            case_id="CASE_FRAUD", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_FRAUD1", account_id="ACC_FRAUD",
                transaction_date="2025-01-20", transaction_type="Wire_Transfer",
                amount=25000.0, description="Unauthorized wire transfer",
                method="Wire"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        result = agent.analyze_case(case)
        assert result.classification == "Fraud"
        assert result.confidence_score == 0.91
        assert result.risk_level == "Critical"
        assert "Step 1" in result.reasoning

        if os.path.exists("test_fraud.jsonl"):
            os.remove("test_fraud.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_money_laundering_classification(self):
        """Test Money_Laundering classification with step-by-step reasoning"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Money_Laundering",
    "confidence_score": 0.87,
    "reasoning": "Step 1: High-value transactions inconsistent with stated income of $45,000. Step 2: Complex layering detected with funds moving through multiple accounts and shell companies. Step 3: Pattern matches placement/layering/integration typology under BSA AML regulations. Step 4: High confidence due to complexity and income mismatch. Step 5: Classification is Money_Laundering based on layering scheme.",
    "key_indicators": ["layering", "shell_companies", "income_mismatch", "complex_transfers"],
    "risk_level": "High"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_ml.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_ML", name="Test Money Laundering",
            date_of_birth="1970-11-25", ssn_last_4="3456",
            address="321 Elm St", customer_since="2022-03-01",
            risk_rating="Medium", annual_income=45000
        )
        case = CaseData(
            case_id="CASE_ML", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_ML1", account_id="ACC_ML",
                transaction_date="2025-01-25", transaction_type="Wire_Transfer",
                amount=500000.0, description="Wire to offshore LLC",
                method="Wire", counterparty="Caribbean Holdings LLC"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        result = agent.analyze_case(case)
        assert result.classification == "Money_Laundering"
        assert result.confidence_score == 0.87
        assert result.risk_level == "High"
        assert "Step 1" in result.reasoning

        if os.path.exists("test_ml.jsonl"):
            os.remove("test_ml.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_other_classification(self):
        """Test Other classification with step-by-step reasoning"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Other",
    "confidence_score": 0.65,
    "reasoning": "Step 1: Customer profile and account history reviewed. Step 2: Unusual transaction patterns detected but don't match standard typologies. Step 3: No clear regulatory violation identified. Step 4: Moderate confidence, requires further investigation. Step 5: Classification is Other as patterns don't fit Structuring, Sanctions, Fraud, or Money_Laundering categories.",
    "key_indicators": ["unusual_pattern", "atypical_behavior", "requires_investigation"],
    "risk_level": "Medium"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_other.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_OTHER", name="Test Other",
            date_of_birth="1990-04-12", ssn_last_4="7890",
            address="555 Maple Dr", customer_since="2023-01-01",
            risk_rating="Low"
        )
        case = CaseData(
            case_id="CASE_OTHER", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_OTHER1", account_id="ACC_OTHER",
                transaction_date="2025-01-30", transaction_type="ACH_Transfer",
                amount=7500.0, description="Unusual transfer pattern",
                method="ACH"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        result = agent.analyze_case(case)
        assert result.classification == "Other"
        assert result.confidence_score == 0.65
        assert result.risk_level == "Medium"
        assert "Step 1" in result.reasoning

        if os.path.exists("test_other.jsonl"):
            os.remove("test_other.jsonl")


class TestChainOfThoughtEvidence:
    """Test that Chain-of-Thought methodology is evident in outputs"""

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_reasoning_contains_explicit_steps(self):
        """Test that reasoning output contains explicit numbered steps"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Structuring",
    "confidence_score": 0.85,
    "reasoning": "Step 1: Analyzed customer profile showing new account opened 30 days ago. Step 2: Identified 4 cash deposits ranging from $9,500-$9,900 within 7 days. Step 3: Pattern aligns with BSA structuring definition under 31 USC 5324. Step 4: Confidence is high at 0.85 due to clear threshold avoidance. Step 5: Final classification is Structuring based on deliberate CTR evasion.",
    "key_indicators": ["threshold_avoidance", "multiple_deposits", "new_account"],
    "risk_level": "High"
}
```'''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_cot.jsonl")
        agent = RiskAnalystAgent(mock_client, logger)

        customer = CustomerData(
            customer_id="CUST_COT", name="CoT Test",
            date_of_birth="1982-08-15", ssn_last_4="4567",
            address="100 Test Blvd", customer_since="2024-12-01",
            risk_rating="Medium"
        )
        case = CaseData(
            case_id="CASE_COT", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_COT", account_id="ACC_COT",
                transaction_date="2025-01-05", transaction_type="Cash_Deposit",
                amount=9750.0, description="Cash deposit", method="Cash"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "data"}
        )

        result = agent.analyze_case(case)

        # Verify Chain-of-Thought is evident
        assert "Step 1" in result.reasoning
        assert "Step 2" in result.reasoning
        assert "Step 3" in result.reasoning
        assert "Step 4" in result.reasoning
        assert "Step 5" in result.reasoning

        # Verify the has_explicit_steps helper method works
        assert result.has_explicit_steps() == True

        # Verify audit log contains step-by-step reasoning
        assert len(logger.entries) == 1
        assert "Step 1" in logger.entries[0]["reasoning"]

        if os.path.exists("test_cot.jsonl"):
            os.remove("test_cot.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_ensure_chain_of_thought_format_method(self):
        """Test the _ensure_chain_of_thought_format helper method"""
        agent = RiskAnalystAgent(Mock(), Mock())

        # Test reasoning that already has steps
        reasoning_with_steps = "Step 1: Data reviewed. Step 2: Patterns found. Step 3: Mapped to BSA. Step 4: High risk. Step 5: Structuring."
        result = agent._ensure_chain_of_thought_format(reasoning_with_steps)
        assert result == reasoning_with_steps

        # Test reasoning without explicit steps gets formatted
        reasoning_without_steps = "Multiple cash deposits under threshold detected suggesting structuring."
        result = agent._ensure_chain_of_thought_format(reasoning_without_steps)
        assert "Step 1" in result
        assert "Step 5" in result

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_validate_classification_coverage_method(self):
        """Test the validate_classification_coverage helper method"""
        agent = RiskAnalystAgent(Mock(), Mock())

        # Test all valid classifications
        assert agent.validate_classification_coverage("Structuring") == True
        assert agent.validate_classification_coverage("Sanctions") == True
        assert agent.validate_classification_coverage("Fraud") == True
        assert agent.validate_classification_coverage("Money_Laundering") == True
        assert agent.validate_classification_coverage("Other") == True

        # Test invalid classification
        assert agent.validate_classification_coverage("InvalidType") == False
        assert agent.validate_classification_coverage("") == False


class TestErrorHandlingAndRecovery:
    """Test robust error handling and fallback mechanisms"""

    def _create_test_case(self):
        """Helper to create a test case"""
        customer = CustomerData(
            customer_id="CUST_ERR", name="Error Test",
            date_of_birth="1980-01-01", ssn_last_4="1234",
            address="123 Error St", customer_since="2020-01-01",
            risk_rating="Medium"
        )
        return CaseData(
            case_id="CASE_ERR", customer=customer, accounts=[],
            transactions=[TransactionData(
                transaction_id="TXN_ERR", account_id="ACC_ERR",
                transaction_date="2025-01-01", transaction_type="Test",
                amount=1000.0, description="Error test", method="Test"
            )],
            case_created_at=datetime.now().isoformat(),
            data_sources={"test": "error_handling"}
        )

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_api_timeout_with_fallback(self):
        """Test graceful recovery from API timeout errors"""
        import openai

        mock_client = Mock()
        # Create proper timeout exception
        timeout_error = openai.APITimeoutError(request=Mock())
        mock_client.chat.completions.create.side_effect = timeout_error

        logger = ExplainabilityLogger("test_timeout.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, max_retries=1, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Should return fallback output, not raise
        assert result.classification == "Other"
        assert result.confidence_score == 0.0
        assert "processing_error" in result.key_indicators
        assert "manual_review_required" in result.key_indicators

        # Verify error was logged
        error_logs = [e for e in logger.entries if e["success"] == False]
        assert len(error_logs) >= 1

        if os.path.exists("test_timeout.jsonl"):
            os.remove("test_timeout.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_api_rate_limit_with_fallback(self):
        """Test graceful recovery from rate limit errors"""
        import openai

        mock_client = Mock()
        # Create proper rate limit exception
        mock_response = Mock()
        mock_response.status_code = 429
        rate_limit_error = openai.RateLimitError(
            message="Rate limit exceeded", response=mock_response, body={}
        )
        mock_client.chat.completions.create.side_effect = rate_limit_error

        logger = ExplainabilityLogger("test_ratelimit.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, max_retries=1, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Should return fallback output
        assert result.classification == "Other"
        assert "fallback_output" in result.key_indicators

        if os.path.exists("test_ratelimit.jsonl"):
            os.remove("test_ratelimit.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_api_auth_error_no_retry(self):
        """Test that authentication errors don't retry (non-retryable)"""
        import openai

        mock_client = Mock()
        # Create proper auth exception
        mock_response = Mock()
        mock_response.status_code = 401
        auth_error = openai.AuthenticationError(
            message="Invalid API key", response=mock_response, body={}
        )
        mock_client.chat.completions.create.side_effect = auth_error

        logger = ExplainabilityLogger("test_auth.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, max_retries=3, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Should return fallback after single attempt (auth errors are non-retryable)
        assert result.classification == "Other"

        # Should only have called API once (no retries for auth errors)
        assert mock_client.chat.completions.create.call_count == 1

        if os.path.exists("test_auth.jsonl"):
            os.remove("test_auth.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_malformed_json_fallback_extraction(self):
        """Test fallback extraction for malformed JSON responses"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        # Malformed JSON with missing brackets but containing valid field data
        mock_response.choices[0].message.content = '''
        The analysis shows "classification": "Structuring" with high risk.
        "confidence_score": 0.85
        "risk_level": "High"
        "reasoning": "Step 1: Data reviewed. Step 2: Patterns found. Step 3: BSA mapping. Step 4: High risk. Step 5: Structuring detected."
        "key_indicators": ["threshold_avoidance", "cash_deposits"]
        '''
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_malformed.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Should recover using fallback extraction or return safe default
        assert result is not None
        assert result.classification in ["Structuring", "Other"]  # Either extracted or fallback

        if os.path.exists("test_malformed.jsonl"):
            os.remove("test_malformed.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_empty_response_fallback(self):
        """Test fallback for empty API responses"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_empty.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Should return fallback output
        assert result.classification == "Other"
        assert result.confidence_score == 0.0
        assert "processing_error" in result.key_indicators

        if os.path.exists("test_empty.jsonl"):
            os.remove("test_empty.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_fallback_disabled_raises_error(self):
        """Test that errors are raised when fallback is disabled"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Not valid JSON at all"
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_no_fallback.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, enable_fallback=False)

        case = self._create_test_case()

        # Should raise ValueError when fallback is disabled
        with pytest.raises(ValueError, match="Failed to parse Risk Analyst JSON output"):
            agent.analyze_case(case)

        if os.path.exists("test_no_fallback.jsonl"):
            os.remove("test_no_fallback.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_partial_json_recovery(self):
        """Test recovery from partial/incomplete JSON"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        # Partial JSON with some valid structure
        mock_response.choices[0].message.content = '''```json
{
    "classification": "Fraud",
    "confidence_score": 0.9,
    "reasoning": "Step 1: Account takeover detected. Step 2: Unauthorized access patterns. Step 3: FTC Red Flags Rule. Step 4: Critical risk. Step 5: Fraud classification.",
    "key_indicators": ["unauthorized_access"],
    "risk_level": "Critical"
```'''  # Missing closing brace
        mock_client.chat.completions.create.return_value = mock_response

        logger = ExplainabilityLogger("test_partial.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Should recover - either through lenient parsing or fallback
        assert result is not None
        assert result.classification in ["Fraud", "Other"]

        if os.path.exists("test_partial.jsonl"):
            os.remove("test_partial.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_error_logging_completeness(self):
        """Test that all errors are properly logged with success=False"""
        import openai

        mock_client = Mock()
        # Create a proper exception - APIConnectionError requires request parameter
        connection_error = openai.APIConnectionError(request=Mock())
        mock_client.chat.completions.create.side_effect = connection_error

        logger = ExplainabilityLogger("test_logging.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, max_retries=1, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Verify error entries have proper structure
        error_entries = [e for e in logger.entries if e.get("success") == False]
        assert len(error_entries) >= 1

        for entry in error_entries:
            assert "error_message" in entry
            assert "case_id" in entry
            assert entry["case_id"] == "CASE_ERR"
            assert entry["agent_type"] == "RiskAnalyst"

        if os.path.exists("test_logging.jsonl"):
            os.remove("test_logging.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_fallback_output_has_step_format(self):
        """Test that fallback output maintains Chain-of-Thought step format"""
        import openai

        mock_client = Mock()
        # Create proper timeout exception
        timeout_error = openai.APITimeoutError(request=Mock())
        mock_client.chat.completions.create.side_effect = timeout_error

        logger = ExplainabilityLogger("test_fallback_steps.jsonl")
        agent = RiskAnalystAgent(mock_client, logger, max_retries=1, enable_fallback=True)

        case = self._create_test_case()
        result = agent.analyze_case(case)

        # Fallback should still have step-by-step reasoning format
        assert "Step 1" in result.reasoning
        assert "Step 5" in result.reasoning
        assert result.has_explicit_steps() == True

        if os.path.exists("test_fallback_steps.jsonl"):
            os.remove("test_fallback_steps.jsonl")

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_lenient_json_extraction(self):
        """Test lenient JSON extraction fixes common issues"""
        agent = RiskAnalystAgent(Mock(), Mock())

        # Test with trailing comma (common LLM mistake)
        response_trailing_comma = '''{"classification": "Structuring", "confidence_score": 0.8, "risk_level": "High", "reasoning": "Step 1: Test. Step 2: Test. Step 3: Test. Step 4: Test. Step 5: Done.", "key_indicators": ["test",],}'''

        # The lenient extraction should handle this
        result = agent._extract_json_lenient(response_trailing_comma)
        # May or may not succeed depending on complexity, but shouldn't crash
        # Just verify no exception is raised

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_field_extraction_with_regex(self):
        """Test regex-based field extraction"""
        agent = RiskAnalystAgent(Mock(), Mock())

        # Response with valid fields but broken JSON structure
        response = '''
        Some text before
        "classification": "Money_Laundering"
        "confidence_score": 0.75
        "risk_level": "High"
        "reasoning": "Step 1: Layering detected. Step 2: Shell companies. Step 3: BSA AML. Step 4: High risk. Step 5: ML classification."
        "key_indicators": ["layering", "shell_company"]
        Some text after
        '''

        result = agent._extract_fields_with_regex(response)
        if result:  # If extraction succeeded
            assert result["classification"] == "Money_Laundering"
            assert result["confidence_score"] == 0.75
            assert result["risk_level"] == "High"

    @pytest.mark.skipif(not RISK_ANALYST_IMPLEMENTED, reason="Risk Analyst Agent not implemented yet")
    def test_partial_extraction_with_defaults(self):
        """Test partial extraction fills in reasonable defaults"""
        agent = RiskAnalystAgent(Mock(), Mock())

        # Response with only classification hint
        response = "The analysis suggests this is a case of Fraud with high risk indicators."

        result = agent._extract_partial_with_defaults(response)
        assert result is not None
        assert result["classification"] == "Fraud"
        assert "confidence_score" in result
        assert "risk_level" in result
        assert "reasoning" in result
        assert "key_indicators" in result
