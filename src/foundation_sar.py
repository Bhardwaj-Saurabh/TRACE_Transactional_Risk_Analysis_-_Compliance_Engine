# Foundation SAR - Core Data Schemas and Utilities

"""
This module contains the foundational components for SAR processing:

1. Pydantic Data Schemas:
   - CustomerData: Customer profile information
   - AccountData: Account details and balances
   - TransactionData: Individual transaction records
   - CaseData: Unified case combining all data sources
   - RiskAnalystOutput: Risk analysis results
   - ComplianceOfficerOutput: Compliance narrative results

2. Utility Classes:
   - ExplainabilityLogger: Audit trail logging
   - DataLoader: Combines fragmented data into case objects
"""

import json
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator
import uuid
import os


# ===== PYDANTIC SCHEMAS =====

class CustomerData(BaseModel):
    """Customer information schema with validation"""
    customer_id: str = Field(..., description="Unique customer identifier like CUST_0001")
    name: str = Field(..., description="Full customer name")
    date_of_birth: str = Field(..., description="Date in YYYY-MM-DD format")
    ssn_last_4: str = Field(..., description="Last 4 digits of SSN")
    address: str = Field(..., description="Full address")
    customer_since: str = Field(..., description="Date in YYYY-MM-DD format")
    risk_rating: Literal['Low', 'Medium', 'High'] = Field(..., description="Risk assessment level")
    phone: Optional[str] = Field(None, description="Phone number")
    occupation: Optional[str] = Field(None, description="Job title")
    annual_income: Optional[int] = Field(None, description="Yearly income")


class AccountData(BaseModel):
    """Account information schema with validation"""
    account_id: str = Field(..., description="Unique account identifier")
    customer_id: str = Field(..., description="Owning customer identifier")
    account_type: str = Field(..., description="Account type e.g. Checking, Savings, Money_Market")
    opening_date: str = Field(..., description="Date in YYYY-MM-DD format")
    current_balance: float = Field(..., description="Current balance")
    average_monthly_balance: float = Field(..., description="Average monthly balance")
    status: str = Field(..., description="Account status e.g. Active, Closed, Suspended")


class TransactionData(BaseModel):
    """Transaction information schema with validation"""
    transaction_id: str = Field(..., description="Unique transaction identifier")
    account_id: str = Field(..., description="Associated account identifier")
    transaction_date: str = Field(..., description="Date in YYYY-MM-DD format")
    transaction_type: str = Field(..., description="Transaction type e.g. Cash_Deposit, Wire_Transfer")
    amount: float = Field(..., description="Transaction amount, negative for withdrawals")
    description: str = Field(..., description="Transaction description")
    counterparty: Optional[str] = Field(None, description="Other party in transaction")
    location: Optional[str] = Field(None, description="Transaction location or branch")
    method: str = Field(..., description="Transaction method e.g. Wire, ACH, ATM, Teller, Cash")


class CaseData(BaseModel):
    """Unified case object combining all data sources"""
    case_id: str = Field(..., description="Unique case identifier")
    customer: CustomerData = Field(..., description="Customer information")
    accounts: List[AccountData] = Field(..., description="List of customer accounts")
    transactions: List[TransactionData] = Field(..., description="List of transactions")
    case_created_at: str = Field(..., description="ISO timestamp of case creation")
    data_sources: Dict[str, str] = Field(..., description="Source tracking metadata")

    @field_validator('transactions')
    @classmethod
    def transactions_not_empty(cls, v):
        if not v:
            raise ValueError("Transactions list cannot be empty")
        return v


class RiskAnalystOutput(BaseModel):
    """Risk Analyst agent structured output"""
    classification: Literal['Structuring', 'Sanctions', 'Fraud', 'Money_Laundering', 'Other'] = Field(..., description="Risk classification")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence between 0.0 and 1.0")
    reasoning: str = Field(..., max_length=500, description="Step-by-step analysis reasoning")
    key_indicators: List[str] = Field(..., description="List of suspicious indicators found")
    risk_level: Literal['Low', 'Medium', 'High', 'Critical'] = Field(..., description="Risk assessment level")


class ComplianceOfficerOutput(BaseModel):
    """Compliance Officer agent structured output"""
    narrative: str = Field(..., max_length=1000, description="Regulatory narrative text")
    narrative_reasoning: str = Field(..., max_length=500, description="Reasoning for narrative construction")
    regulatory_citations: List[str] = Field(..., description="List of relevant regulations")
    completeness_check: bool = Field(..., description="Whether narrative meets all requirements")


# ===== AUDIT LOGGING =====

class ExplainabilityLogger:
    """Simple audit logging for compliance trails"""

    def __init__(self, log_file: str = "sar_audit.jsonl"):
        self.log_file = log_file
        self.entries: List[Dict] = []

    def log_agent_action(self, agent_type: str, action: str, case_id: str,
                         input_data: Dict, output_data: Dict, reasoning: str,
                         execution_time_ms: float, success: bool = True,
                         error_message: Optional[str] = None):
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'case_id': case_id,
            'agent_type': agent_type,
            'action': action,
            'input_summary': str(input_data),
            'output_summary': str(output_data),
            'reasoning': reasoning,
            'execution_time_ms': execution_time_ms,
            'success': success,
            'error_message': error_message
        }
        self.entries.append(entry)
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')


# ===== DATA LOADER =====

class DataLoader:
    """Simple loader that creates case objects from CSV data"""

    def __init__(self, explainability_logger: ExplainabilityLogger):
        self.logger = explainability_logger

    def create_case_from_data(self,
                              customer_data: Dict,
                              account_data: List[Dict],
                              transaction_data: List[Dict]) -> CaseData:
        start_time = datetime.now()
        try:
            case_id = str(uuid.uuid4())
            customer = CustomerData(**customer_data)

            accounts = [AccountData(**acc) for acc in account_data
                        if acc['customer_id'] == customer.customer_id]
            account_ids = {acc.account_id for acc in accounts}

            transactions = [TransactionData(**txn) for txn in transaction_data
                            if txn['account_id'] in account_ids]

            case = CaseData(
                case_id=case_id,
                customer=customer,
                accounts=accounts,
                transactions=transactions,
                case_created_at=datetime.now(timezone.utc).isoformat(),
                data_sources={
                    'customer_source': f"csv_extract_{datetime.now().strftime('%Y%m%d')}",
                    'account_source': f"csv_extract_{datetime.now().strftime('%Y%m%d')}",
                    'transaction_source': f"csv_extract_{datetime.now().strftime('%Y%m%d')}"
                }
            )

            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.log_agent_action(
                agent_type="DataLoader",
                action="create_case",
                case_id=case_id,
                input_data={"customer_id": customer.customer_id},
                output_data={"accounts": len(accounts), "transactions": len(transactions)},
                reasoning="Created unified case from fragmented data sources",
                execution_time_ms=execution_time_ms,
                success=True
            )
            return case

        except Exception as e:
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.log_agent_action(
                agent_type="DataLoader",
                action="create_case",
                case_id="FAILED",
                input_data={"customer_id": customer_data.get("customer_id", "unknown")},
                output_data={},
                reasoning="Case creation failed",
                execution_time_ms=execution_time_ms,
                success=False,
                error_message=str(e)
            )
            raise


# ===== HELPER FUNCTIONS (PROVIDED) =====

def load_csv_data(data_dir: str = "data/") -> tuple:
    """Helper function to load all CSV files"""
    try:
        customers_df = pd.read_csv(f"{data_dir}/customers.csv")
        accounts_df = pd.read_csv(f"{data_dir}/accounts.csv")
        transactions_df = pd.read_csv(f"{data_dir}/transactions.csv")
        return customers_df, accounts_df, transactions_df
    except FileNotFoundError as e:
        raise FileNotFoundError(f"CSV file not found: {e}")
    except Exception as e:
        raise Exception(f"Error loading CSV data: {e}")


if __name__ == "__main__":
    print("Foundation SAR Module")
    print("Core data schemas and utilities for SAR processing")
