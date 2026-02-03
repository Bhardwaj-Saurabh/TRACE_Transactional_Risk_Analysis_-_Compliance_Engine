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
import math
import pandas as pd
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
import os


# ===== HELPER FUNCTIONS =====

def is_nan(value: Any) -> bool:
    """Check if a value is NaN (handles pandas NaN and float nan)"""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        import pandas as pd
        if pd.isna(value):
            return True
    except (ImportError, TypeError):
        pass
    return False


def validate_date_format(value: str, field_name: str) -> str:
    """Validate that a date string is in YYYY-MM-DD format"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string in YYYY-MM-DD format")

    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, value):
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format, got: {value}")

    # Validate it's a real date
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"{field_name} is not a valid date: {value}")

    return value


# ===== PYDANTIC SCHEMAS =====

class CustomerData(BaseModel):
    """Customer information schema with validation"""
    customer_id: str = Field(..., description="Unique customer identifier like CUST_0001")
    name: str = Field(..., description="Full customer name")
    date_of_birth: str = Field(..., description="Date in YYYY-MM-DD format")
    ssn_last_4: Union[str, int] = Field(..., description="Last 4 digits of SSN")
    address: str = Field(..., description="Full address")
    customer_since: str = Field(..., description="Date in YYYY-MM-DD format")
    risk_rating: Literal['Low', 'Medium', 'High'] = Field(..., description="Risk assessment level")
    phone: Optional[str] = Field(None, description="Phone number")
    occupation: Optional[str] = Field(None, description="Job title")
    annual_income: Optional[int] = Field(None, description="Yearly income")

    @field_validator('ssn_last_4', mode='before')
    @classmethod
    def coerce_ssn_to_str(cls, v):
        """Convert ssn_last_4 to string (handles int from CSV)"""
        if is_nan(v):
            raise ValueError("ssn_last_4 cannot be empty")
        return str(v)

    @field_validator('date_of_birth')
    @classmethod
    def validate_dob_format(cls, v):
        """Validate date_of_birth is in YYYY-MM-DD format"""
        return validate_date_format(v, 'date_of_birth')

    @field_validator('customer_since')
    @classmethod
    def validate_customer_since_format(cls, v):
        """Validate customer_since is in YYYY-MM-DD format"""
        return validate_date_format(v, 'customer_since')

    @field_validator('phone', 'occupation', mode='before')
    @classmethod
    def handle_nan_optional_str(cls, v):
        """Convert NaN values to None for optional string fields"""
        if is_nan(v):
            return None
        return v

    @field_validator('annual_income', mode='before')
    @classmethod
    def handle_nan_optional_int(cls, v):
        """Convert NaN values to None for optional int fields"""
        if is_nan(v):
            return None
        if isinstance(v, float):
            return int(v)
        return v


class AccountData(BaseModel):
    """Account information schema with validation"""
    account_id: str = Field(..., description="Unique account identifier")
    customer_id: str = Field(..., description="Owning customer identifier")
    account_type: str = Field(..., description="Account type e.g. Checking, Savings, Money_Market")
    opening_date: str = Field(..., description="Date in YYYY-MM-DD format")
    current_balance: float = Field(..., description="Current balance")
    average_monthly_balance: float = Field(..., description="Average monthly balance")
    status: str = Field(..., description="Account status e.g. Active, Closed, Suspended")

    @field_validator('opening_date')
    @classmethod
    def validate_opening_date_format(cls, v):
        """Validate opening_date is in YYYY-MM-DD format"""
        return validate_date_format(v, 'opening_date')


class TransactionData(BaseModel):
    """Transaction information schema with validation"""
    transaction_id: str = Field(..., description="Unique transaction identifier")
    account_id: str = Field(..., description="Associated account identifier")
    transaction_date: str = Field(..., description="Date in YYYY-MM-DD format")
    transaction_type: str = Field(..., description="Transaction type e.g. Cash_Deposit, Wire_Transfer")
    amount: float = Field(..., ge=-10000000, le=10000000, description="Transaction amount, negative for withdrawals")
    description: str = Field(..., description="Transaction description")
    counterparty: Optional[str] = Field(None, description="Other party in transaction")
    location: Optional[str] = Field(None, description="Transaction location or branch")
    method: str = Field(..., description="Transaction method e.g. Wire, ACH, ATM, Teller, Cash")

    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date_format(cls, v):
        """Validate transaction_date is in YYYY-MM-DD format"""
        return validate_date_format(v, 'transaction_date')

    @field_validator('counterparty', 'location', mode='before')
    @classmethod
    def handle_nan_optional_fields(cls, v):
        """Convert NaN values to None for optional string fields"""
        if is_nan(v):
            return None
        return v

    @field_validator('amount')
    @classmethod
    def validate_amount_range(cls, v):
        """Validate transaction amount is within expected range"""
        if v < -10000000 or v > 10000000:
            raise ValueError(f"Transaction amount must be between -10,000,000 and 10,000,000, got: {v}")
        return v


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
    """Risk Analyst agent structured output with Chain-of-Thought reasoning"""
    classification: Literal['Structuring', 'Sanctions', 'Fraud', 'Money_Laundering', 'Other'] = Field(..., description="Risk classification")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence between 0.0 and 1.0")
    reasoning: str = Field(..., max_length=2000, description="Step-by-step Chain-of-Thought analysis reasoning with explicit steps")
    key_indicators: List[str] = Field(..., description="List of suspicious indicators found")
    risk_level: Literal['Low', 'Medium', 'High', 'Critical'] = Field(..., description="Risk assessment level")

    @field_validator('reasoning')
    @classmethod
    def validate_chain_of_thought_reasoning(cls, v):
        """Validate that reasoning contains explicit step-by-step Chain-of-Thought analysis"""
        if not v or len(v.strip()) < 50:
            raise ValueError("Reasoning must contain substantive Chain-of-Thought analysis")
        return v

    def has_explicit_steps(self) -> bool:
        """Check if reasoning contains explicit numbered steps"""
        step_patterns = ['Step 1', 'Step 2', 'Step 3', 'Step 4', 'Step 5',
                        'step 1', 'step 2', 'step 3', 'step 4', 'step 5']
        return any(pattern in self.reasoning for pattern in step_patterns)


class ComplianceOfficerOutput(BaseModel):
    """Compliance Officer agent structured output"""
    narrative: str = Field(..., max_length=1000, description="Regulatory narrative text")
    narrative_reasoning: str = Field(..., max_length=500, description="Reasoning for narrative construction")
    regulatory_citations: List[str] = Field(..., description="List of relevant regulations")
    completeness_check: bool = Field(..., description="Whether narrative meets all requirements (model self-reported, not trusted)")
    validation_passed: Optional[bool] = Field(None, description="Whether narrative passed deterministic pre-finalization validation")
    validation_details: Optional[Dict[str, Any]] = Field(None, description="Detailed validation results for audit trail")


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

    def log_human_decision(self, case_id: str, customer_id: str, customer_name: str,
                          decision: str, reviewer_decision: str, reviewer_identity: str,
                          ai_classification: str, ai_confidence: float, ai_risk_level: str,
                          rationale: Optional[str] = None, sar_id: Optional[str] = None,
                          decision_file: str = "workflow_decisions.jsonl"):
        """Log human decision gate outcome in structured format for regulatory examination.
        
        Args:
            case_id: Unique case identifier
            customer_id: Customer identifier
            customer_name: Customer name
            decision: Decision outcome ('PROCEED', 'REJECT', 'ERROR')
            reviewer_decision: Raw reviewer input/decision text
            reviewer_identity: Identity of reviewer (e.g., 'compliance_officer', 'auto_approve')
            ai_classification: AI classification result
            ai_confidence: AI confidence score
            ai_risk_level: AI risk level assessment
            rationale: Optional rationale for decision
            sar_id: SAR ID if SAR was created (for linking)
            decision_file: Path to decision log file
        """
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'case_id': case_id,
            'customer_id': customer_id,
            'customer_name': customer_name,
            'decision': decision,  # 'PROCEED', 'REJECT', 'ERROR'
            'reviewer_decision': reviewer_decision,  # Raw decision text
            'reviewer_identity': reviewer_identity,  # Who made the decision
            'ai_classification': ai_classification,
            'ai_confidence': ai_confidence,
            'ai_risk_level': ai_risk_level,
            'rationale': rationale or f"{decision} decision by {reviewer_identity}",
            'sar_id': sar_id,  # Link to SAR if created
            'log_type': 'human_decision_gate'
        }
        
        # Write immediately to ensure every decision is captured
        if os.path.isabs(decision_file):
            decision_path = decision_file
        else:
            # If log_file has a directory, use that; otherwise use outputs/audit_logs
            log_dir = os.path.dirname(self.log_file)
            if log_dir:
                decision_path = os.path.join(log_dir, decision_file)
            else:
                decision_path = os.path.join("outputs/audit_logs", decision_file)
        
        # Ensure directory exists
        decision_dir = os.path.dirname(decision_path)
        if decision_dir:
            os.makedirs(decision_dir, exist_ok=True)
        
        with open(decision_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        return entry


# ===== DATA LOADER =====

class NoTransactionsError(Exception):
    """Raised when a customer has no transactions and cannot form a valid case.

    This is expected behavior - SAR cases require transaction data to analyze.
    Customers without transactions should be skipped, not treated as errors.
    """
    def __init__(self, customer_id: str, customer_name: str, reason: str = "no_transactions"):
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.reason = reason
        message = f"Cannot create case for {customer_name} ({customer_id}): {reason}"
        super().__init__(message)


class DataLoader:
    """Simple loader that creates case objects from CSV data.

    Handles cases where customers have no transactions gracefully by:
    1. Raising NoTransactionsError for explicit handling
    2. Providing try_create_case_from_data() for Optional returns
    3. Tracking skipped customers in batch processing
    """

    def __init__(self, explainability_logger: ExplainabilityLogger):
        self.logger = explainability_logger

    def create_case_from_data(self,
                              customer_data: Dict,
                              account_data: List[Dict],
                              transaction_data: List[Dict]) -> CaseData:
        """Create a case from customer, account, and transaction data.

        Args:
            customer_data: Customer information dictionary
            account_data: List of all account records
            transaction_data: List of all transaction records

        Returns:
            CaseData object for SAR analysis

        Raises:
            NoTransactionsError: If customer has no transactions (expected for some customers)
            ValidationError: If data fails Pydantic validation
        """
        start_time = datetime.now()
        try:
            case_id = str(uuid.uuid4())
            customer = CustomerData(**customer_data)

            accounts = [AccountData(**acc) for acc in account_data
                        if acc['customer_id'] == customer.customer_id]
            account_ids = {acc.account_id for acc in accounts}

            transactions = [TransactionData(**txn) for txn in transaction_data
                            if txn['account_id'] in account_ids]

            # Pre-check: Raise clear error if no transactions found
            if not transactions:
                execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                self.logger.log_agent_action(
                    agent_type="DataLoader",
                    action="create_case",
                    case_id="SKIPPED",
                    input_data={"customer_id": customer.customer_id},
                    output_data={"accounts": len(accounts), "transactions": 0},
                    reasoning="Customer has no transactions - cannot create SAR case",
                    execution_time_ms=execution_time_ms,
                    success=True,  # This is expected behavior, not an error
                    error_message=None
                )
                raise NoTransactionsError(
                    customer_id=customer.customer_id,
                    customer_name=customer.name,
                    reason="no transactions found for SAR analysis"
                )

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

        except NoTransactionsError:
            # Re-raise without additional logging (already logged above)
            raise

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

    def try_create_case_from_data(self,
                                   customer_data: Dict,
                                   account_data: List[Dict],
                                   transaction_data: List[Dict]) -> Optional[CaseData]:
        """Attempt to create a case, returning None if customer has no transactions.

        This is a convenience method for workflows that expect some customers
        to have no transactions and want to handle them gracefully.

        Args:
            customer_data: Customer information dictionary
            account_data: List of all account records
            transaction_data: List of all transaction records

        Returns:
            CaseData object if successful, None if customer has no transactions

        Raises:
            ValidationError: If data fails Pydantic validation (not for missing transactions)
        """
        try:
            return self.create_case_from_data(customer_data, account_data, transaction_data)
        except NoTransactionsError:
            return None

    def create_cases_from_dataset(self,
                                   customers_df,
                                   accounts_df,
                                   transactions_df) -> Dict[str, Any]:
        """Process entire dataset and create cases for all eligible customers.

        This method handles the full dataset, tracking both successful cases
        and customers who were skipped due to no transactions.

        Args:
            customers_df: DataFrame of customer records
            accounts_df: DataFrame of account records
            transactions_df: DataFrame of transaction records

        Returns:
            Dictionary containing:
                - cases: List of successfully created CaseData objects
                - skipped_customers: List of dicts with customer_id, name, reason
                - statistics: Summary counts
        """
        cases: List[CaseData] = []
        skipped_customers: List[Dict[str, str]] = []

        # Convert DataFrames to list of dicts
        accounts_list = accounts_df.to_dict('records')
        transactions_list = transactions_df.to_dict('records')

        for _, customer_row in customers_df.iterrows():
            customer_data = customer_row.to_dict()
            try:
                case = self.create_case_from_data(
                    customer_data=customer_data,
                    account_data=accounts_list,
                    transaction_data=transactions_list
                )
                cases.append(case)
            except NoTransactionsError as e:
                skipped_customers.append({
                    'customer_id': e.customer_id,
                    'customer_name': e.customer_name,
                    'reason': e.reason
                })

        return {
            'cases': cases,
            'skipped_customers': skipped_customers,
            'statistics': {
                'total_customers': len(customers_df),
                'cases_created': len(cases),
                'customers_skipped': len(skipped_customers),
                'skip_rate': len(skipped_customers) / len(customers_df) if len(customers_df) > 0 else 0
            }
        }


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
