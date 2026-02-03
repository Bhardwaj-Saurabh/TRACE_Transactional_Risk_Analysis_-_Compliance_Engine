# Foundation SAR Tests - Top 10 Essential Tests

"""
Streamlined test suite for foundation_sar.py module focusing on core functionality
"""

import pytest
import os
from datetime import datetime

# Import foundation components - these will work once students implement them
try:
    from src.foundation_sar import (
        CustomerData,
        AccountData,
        TransactionData,
        CaseData,
        ExplainabilityLogger,
        DataLoader,
        NoTransactionsError
    )
    # If import succeeds, consider it implemented
    FOUNDATION_IMPLEMENTED = True

except ImportError:
    # Graceful fallback when students haven't implemented yet
    FOUNDATION_IMPLEMENTED = False

if not FOUNDATION_IMPLEMENTED:
    print("⚠️  Foundation components not yet implemented - tests will be skipped")
    print("💡 Implement the classes in src/foundation_sar.py to run these tests")

class TestCustomerData:
    """Test CustomerData Pydantic schema"""
    
    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_valid_customer_data(self):
        """Test CustomerData with complete valid inputs"""
        customer_data = {
            "customer_id": "CUST_0001",
            "name": "Allison Hill",
            "date_of_birth": "1958-08-25",
            "ssn_last_4": "2679",
            "address": "600 Jeffery Parkways, New Jamesside, MT 29394",
            "phone": "394.802.6542x351",
            "customer_since": "2016-06-14",
            "risk_rating": "Low",
            "occupation": "Local government officer",
            "annual_income": 48815
        }
        
        customer = CustomerData(**customer_data)
        assert customer.customer_id == "CUST_0001"
        assert customer.name == "Allison Hill"
        assert customer.risk_rating == "Low"
        assert customer.annual_income == 48815

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_customer_risk_rating_validation(self):
        """Test CustomerData risk rating validation"""
        # Test valid risk ratings
        for rating in ["Low", "Medium", "High"]:
            customer = CustomerData(
                customer_id=f"CUST_{rating}",
                name="Test Customer",
                date_of_birth="1980-01-01",
                ssn_last_4="1234",
                address="123 Test St",
                customer_since="2020-01-01",
                risk_rating=rating
            )
            assert customer.risk_rating == rating

class TestAccountData:
    """Test AccountData Pydantic schema"""
    
    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_valid_account_data(self):
        """Test AccountData with valid inputs"""
        account_data = {
            "account_id": "CUST_0001_ACC_1",
            "customer_id": "CUST_0001",
            "account_type": "Checking",
            "opening_date": "2016-06-14",
            "current_balance": 51690.75,
            "average_monthly_balance": 45000.00,
            "status": "Active"
        }
        
        account = AccountData(**account_data)
        assert account.account_id == "CUST_0001_ACC_1"
        assert account.account_type == "Checking"
        assert account.current_balance == 51690.75
        assert account.status == "Active"

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_account_balance_validation(self):
        """Test AccountData balance validation"""
        # Test zero balance
        account = AccountData(
            account_id="ACC_TEST",
            customer_id="CUST_TEST",
            account_type="Checking",
            opening_date="2020-01-01",
            current_balance=0.0,
            average_monthly_balance=0.0,
            status="Active"
        )
        assert account.current_balance == 0.0

class TestTransactionData:
    """Test TransactionData Pydantic schema"""
    
    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_valid_transaction_data(self):
        """Test TransactionData with valid inputs"""
        transaction_data = {
            "transaction_id": "TXN_B24455F3",
            "account_id": "CUST_0001_ACC_1",
            "transaction_date": "2025-01-08",
            "transaction_type": "Online_Transfer",
            "amount": 9900.0,
            "description": "ONLINE TRANSFER TO SAVINGS",
            "counterparty": "WELLS FARGO BANK",
            "location": "ONLINE",
            "method": "ACH"
        }
        
        transaction = TransactionData(**transaction_data)
        assert transaction.transaction_id == "TXN_B24455F3"
        assert transaction.amount == 9900.0
        assert transaction.transaction_type == "Online_Transfer"

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_transaction_amount_validation(self):
        """Test TransactionData amount validation"""
        # Test positive amount
        transaction = TransactionData(
            transaction_id="TXN_TEST",
            account_id="ACC_TEST",
            transaction_date="2025-01-01",
            transaction_type="Deposit",
            amount=100.50,
            description="Test deposit",
            method="ACH"
        )
        assert transaction.amount == 100.50

class TestCaseData:
    """Test CaseData unified schema"""
    
    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_valid_case_creation(self):
        """Test creating a valid case with all components"""
        # Create sample customer
        customer = CustomerData(
            customer_id="CUST_0001",
            name="Test Customer",
            date_of_birth="1980-01-01",
            ssn_last_4="1234",
            address="123 Test St",
            customer_since="2020-01-01",
            risk_rating="Medium",
            annual_income=75000
        )
        
        # Create sample account
        account = AccountData(
            account_id="CUST_0001_ACC_1",
            customer_id="CUST_0001",
            account_type="Checking",
            opening_date="2020-01-01",
            current_balance=10000.0,
            average_monthly_balance=8000.0,
            status="Active"
        )
        
        # Create sample transaction
        transaction = TransactionData(
            transaction_id="TXN_001",
            account_id="CUST_0001_ACC_1",
            transaction_date="2025-01-01",
            transaction_type="Cash_Deposit",
            amount=9900.0,
            description="Cash deposit just under threshold",
            method="Cash"
        )
        
        # Create unified case
        case = CaseData(
            case_id="CASE_001",
            customer=customer,
            accounts=[account],
            transactions=[transaction],
            case_created_at=datetime.now().isoformat(),
            data_sources={
                "customer_source": "test_data",
                "account_source": "test_data", 
                "transaction_source": "test_data"
            }
        )
        
        assert case.case_id == "CASE_001"
        assert case.customer.customer_id == "CUST_0001"
        assert len(case.accounts) == 1
        assert len(case.transactions) == 1

class TestDataLoader:
    """Test DataLoader functionality"""
    
    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_csv_data_loading(self):
        """Test DataLoader can create cases from data"""
        logger = ExplainabilityLogger("test_audit.jsonl")
        loader = DataLoader(logger)
        
        # Sample data with all required fields
        customer_data = {
            "customer_id": "CUST_0001",
            "name": "Test Customer",
            "date_of_birth": "1980-01-01",
            "ssn_last_4": "1234",
            "address": "123 Test St",
            "customer_since": "2020-01-01",
            "risk_rating": "Medium",
            "annual_income": 75000
        }
        
        account_data = [{
            "account_id": "CUST_0001_ACC_1",
            "customer_id": "CUST_0001",
            "account_type": "Checking",
            "opening_date": "2020-01-01",
            "current_balance": 10000.0,
            "average_monthly_balance": 8000.0,
            "status": "Active"
        }]
        
        transaction_data = [{
            "transaction_id": "TXN_001",
            "account_id": "CUST_0001_ACC_1",
            "transaction_date": "2025-01-01",
            "transaction_type": "Cash_Deposit",
            "amount": 9900.0,
            "description": "Test transaction",
            "method": "Cash"
        }]
        
        case = loader.create_case_from_data(customer_data, account_data, transaction_data)
        assert case is not None
        assert case.customer.customer_id == "CUST_0001"
        assert len(case.accounts) == 1
        assert len(case.transactions) == 1
        
        # Cleanup
        if os.path.exists("test_audit.jsonl"):
            os.remove("test_audit.jsonl")

class TestExplainabilityLogger:
    """Test ExplainabilityLogger audit functionality"""
    
    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_log_creation(self):
        """Test ExplainabilityLogger can create log entries"""
        logger = ExplainabilityLogger("test_log.jsonl")
        
        logger.log_agent_action(
            agent_type="TestAgent",
            action="test_action",
            case_id="CASE_001",
            input_data={"test": "input"},
            output_data={"test": "output"},
            reasoning="Test reasoning",
            execution_time_ms=100.0,
            success=True
        )
        
        assert len(logger.entries) == 1
        assert logger.entries[0]["agent_type"] == "TestAgent"
        assert logger.entries[0]["case_id"] == "CASE_001"
        
        # Cleanup
        if os.path.exists("test_log.jsonl"):
            os.remove("test_log.jsonl")

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_log_file_writing(self):
        """Test ExplainabilityLogger writes to file"""
        log_file = "test_file_log.jsonl"
        logger = ExplainabilityLogger(log_file)
        
        # Log multiple entries
        for i in range(3):
            logger.log_agent_action(
                agent_type="TestAgent",
                action=f"test_action_{i}",
                case_id=f"CASE_{i:03d}",
                input_data={"iteration": i},
                output_data={"result": f"output_{i}"},
                reasoning=f"Test reasoning {i}",
                execution_time_ms=50.0 + i,
                success=True
            )
        
        # Check file exists and has content
        assert os.path.exists(log_file)
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 3
        
        # Cleanup
        if os.path.exists(log_file):
            os.remove(log_file)


class TestNoTransactionsError:
    """Test NoTransactionsError exception for customers without transactions"""

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_no_transactions_error_attributes(self):
        """Test NoTransactionsError captures customer details"""
        error = NoTransactionsError(
            customer_id="CUST_0001",
            customer_name="John Doe",
            reason="no transactions found"
        )
        assert error.customer_id == "CUST_0001"
        assert error.customer_name == "John Doe"
        assert error.reason == "no transactions found"
        assert "CUST_0001" in str(error)
        assert "John Doe" in str(error)

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_dataloader_raises_no_transactions_error(self):
        """Test DataLoader raises NoTransactionsError for customer with no transactions"""
        logger = ExplainabilityLogger("test_no_txn.jsonl")
        loader = DataLoader(logger)

        customer_data = {
            "customer_id": "CUST_NO_TXN",
            "name": "No Transaction Customer",
            "date_of_birth": "1980-01-01",
            "ssn_last_4": "9999",
            "address": "123 Empty St",
            "customer_since": "2020-01-01",
            "risk_rating": "Low",
            "annual_income": 50000
        }

        # Account exists but no transactions
        account_data = [{
            "account_id": "CUST_NO_TXN_ACC_1",
            "customer_id": "CUST_NO_TXN",
            "account_type": "Checking",
            "opening_date": "2020-01-01",
            "current_balance": 1000.0,
            "average_monthly_balance": 1000.0,
            "status": "Active"
        }]

        # Empty transactions list
        transaction_data = []

        with pytest.raises(NoTransactionsError) as exc_info:
            loader.create_case_from_data(customer_data, account_data, transaction_data)

        assert exc_info.value.customer_id == "CUST_NO_TXN"
        assert exc_info.value.customer_name == "No Transaction Customer"

        # Cleanup
        if os.path.exists("test_no_txn.jsonl"):
            os.remove("test_no_txn.jsonl")

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_try_create_case_returns_none_for_no_transactions(self):
        """Test try_create_case_from_data returns None instead of raising"""
        logger = ExplainabilityLogger("test_try_create.jsonl")
        loader = DataLoader(logger)

        customer_data = {
            "customer_id": "CUST_NO_TXN",
            "name": "No Transaction Customer",
            "date_of_birth": "1980-01-01",
            "ssn_last_4": "9999",
            "address": "123 Empty St",
            "customer_since": "2020-01-01",
            "risk_rating": "Low"
        }

        account_data = [{
            "account_id": "CUST_NO_TXN_ACC_1",
            "customer_id": "CUST_NO_TXN",
            "account_type": "Checking",
            "opening_date": "2020-01-01",
            "current_balance": 1000.0,
            "average_monthly_balance": 1000.0,
            "status": "Active"
        }]

        transaction_data = []

        # Should return None, not raise
        result = loader.try_create_case_from_data(customer_data, account_data, transaction_data)
        assert result is None

        # Cleanup
        if os.path.exists("test_try_create.jsonl"):
            os.remove("test_try_create.jsonl")

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_try_create_case_returns_case_when_valid(self):
        """Test try_create_case_from_data returns CaseData when transactions exist"""
        logger = ExplainabilityLogger("test_try_create_valid.jsonl")
        loader = DataLoader(logger)

        customer_data = {
            "customer_id": "CUST_WITH_TXN",
            "name": "Valid Customer",
            "date_of_birth": "1980-01-01",
            "ssn_last_4": "1234",
            "address": "123 Valid St",
            "customer_since": "2020-01-01",
            "risk_rating": "Low"
        }

        account_data = [{
            "account_id": "CUST_WITH_TXN_ACC_1",
            "customer_id": "CUST_WITH_TXN",
            "account_type": "Checking",
            "opening_date": "2020-01-01",
            "current_balance": 5000.0,
            "average_monthly_balance": 4000.0,
            "status": "Active"
        }]

        transaction_data = [{
            "transaction_id": "TXN_001",
            "account_id": "CUST_WITH_TXN_ACC_1",
            "transaction_date": "2025-01-01",
            "transaction_type": "Deposit",
            "amount": 500.0,
            "description": "Test deposit",
            "method": "ACH"
        }]

        result = loader.try_create_case_from_data(customer_data, account_data, transaction_data)
        assert result is not None
        assert isinstance(result, CaseData)
        assert result.customer.customer_id == "CUST_WITH_TXN"

        # Cleanup
        if os.path.exists("test_try_create_valid.jsonl"):
            os.remove("test_try_create_valid.jsonl")


class TestBatchCaseCreation:
    """Test batch processing of cases with mixed valid/invalid customers"""

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_create_cases_from_dataset_mixed(self):
        """Test batch creation handles mix of customers with and without transactions"""
        import pandas as pd

        logger = ExplainabilityLogger("test_batch.jsonl")
        loader = DataLoader(logger)

        # Create test DataFrames
        customers_df = pd.DataFrame([
            {
                "customer_id": "CUST_001",
                "name": "With Transactions",
                "date_of_birth": "1980-01-01",
                "ssn_last_4": "1111",
                "address": "123 Valid St",
                "customer_since": "2020-01-01",
                "risk_rating": "Low"
            },
            {
                "customer_id": "CUST_002",
                "name": "Without Transactions",
                "date_of_birth": "1985-06-15",
                "ssn_last_4": "2222",
                "address": "456 Empty St",
                "customer_since": "2021-01-01",
                "risk_rating": "Medium"
            },
            {
                "customer_id": "CUST_003",
                "name": "Also With Transactions",
                "date_of_birth": "1990-12-25",
                "ssn_last_4": "3333",
                "address": "789 Active St",
                "customer_since": "2022-01-01",
                "risk_rating": "High"
            }
        ])

        accounts_df = pd.DataFrame([
            {
                "account_id": "CUST_001_ACC_1",
                "customer_id": "CUST_001",
                "account_type": "Checking",
                "opening_date": "2020-01-01",
                "current_balance": 5000.0,
                "average_monthly_balance": 4000.0,
                "status": "Active"
            },
            {
                "account_id": "CUST_002_ACC_1",
                "customer_id": "CUST_002",
                "account_type": "Savings",
                "opening_date": "2021-01-01",
                "current_balance": 1000.0,
                "average_monthly_balance": 1000.0,
                "status": "Active"
            },
            {
                "account_id": "CUST_003_ACC_1",
                "customer_id": "CUST_003",
                "account_type": "Checking",
                "opening_date": "2022-01-01",
                "current_balance": 10000.0,
                "average_monthly_balance": 8000.0,
                "status": "Active"
            }
        ])

        # Only CUST_001 and CUST_003 have transactions
        transactions_df = pd.DataFrame([
            {
                "transaction_id": "TXN_001",
                "account_id": "CUST_001_ACC_1",
                "transaction_date": "2025-01-01",
                "transaction_type": "Deposit",
                "amount": 500.0,
                "description": "Test deposit",
                "method": "ACH"
            },
            {
                "transaction_id": "TXN_002",
                "account_id": "CUST_003_ACC_1",
                "transaction_date": "2025-01-02",
                "transaction_type": "Wire_Transfer",
                "amount": 9500.0,
                "description": "Large wire",
                "method": "Wire"
            }
        ])

        result = loader.create_cases_from_dataset(customers_df, accounts_df, transactions_df)

        # Check cases created
        assert len(result['cases']) == 2
        case_customer_ids = {c.customer.customer_id for c in result['cases']}
        assert 'CUST_001' in case_customer_ids
        assert 'CUST_003' in case_customer_ids

        # Check skipped customers
        assert len(result['skipped_customers']) == 1
        assert result['skipped_customers'][0]['customer_id'] == 'CUST_002'
        assert result['skipped_customers'][0]['customer_name'] == 'Without Transactions'

        # Check statistics
        assert result['statistics']['total_customers'] == 3
        assert result['statistics']['cases_created'] == 2
        assert result['statistics']['customers_skipped'] == 1
        assert abs(result['statistics']['skip_rate'] - (1/3)) < 0.01

        # Cleanup
        if os.path.exists("test_batch.jsonl"):
            os.remove("test_batch.jsonl")

    @pytest.mark.skipif(not FOUNDATION_IMPLEMENTED, reason="Foundation not implemented yet")
    def test_create_cases_all_skipped(self):
        """Test batch creation when all customers have no transactions"""
        import pandas as pd

        logger = ExplainabilityLogger("test_batch_all_skip.jsonl")
        loader = DataLoader(logger)

        customers_df = pd.DataFrame([
            {
                "customer_id": "CUST_001",
                "name": "Empty Customer 1",
                "date_of_birth": "1980-01-01",
                "ssn_last_4": "1111",
                "address": "123 Empty St",
                "customer_since": "2020-01-01",
                "risk_rating": "Low"
            },
            {
                "customer_id": "CUST_002",
                "name": "Empty Customer 2",
                "date_of_birth": "1985-06-15",
                "ssn_last_4": "2222",
                "address": "456 Empty St",
                "customer_since": "2021-01-01",
                "risk_rating": "Medium"
            }
        ])

        accounts_df = pd.DataFrame([
            {
                "account_id": "CUST_001_ACC_1",
                "customer_id": "CUST_001",
                "account_type": "Checking",
                "opening_date": "2020-01-01",
                "current_balance": 5000.0,
                "average_monthly_balance": 4000.0,
                "status": "Active"
            }
        ])

        # No transactions
        transactions_df = pd.DataFrame(columns=[
            "transaction_id", "account_id", "transaction_date",
            "transaction_type", "amount", "description", "method"
        ])

        result = loader.create_cases_from_dataset(customers_df, accounts_df, transactions_df)

        assert len(result['cases']) == 0
        assert len(result['skipped_customers']) == 2
        assert result['statistics']['skip_rate'] == 1.0

        # Cleanup
        if os.path.exists("test_batch_all_skip.jsonl"):
            os.remove("test_batch_all_skip.jsonl")