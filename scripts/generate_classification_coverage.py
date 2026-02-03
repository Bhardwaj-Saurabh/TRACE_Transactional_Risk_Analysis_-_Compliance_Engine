#!/usr/bin/env python3
"""
Classification Coverage Generator

This script creates deterministic test scenarios for all 5 SAR classification types
and runs them through the complete workflow to generate artifacts.

Classifications covered:
1. Structuring - Cash deposits just under $10,000 threshold
2. Money_Laundering - Complex layering, shell companies, income mismatch
3. Fraud - Account takeover, unauthorized transfers, identity issues
4. Sanctions - OFAC countries (Iran, North Korea), sanctioned entities
5. Other - Unusual patterns not fitting standard categories

Usage:
    python scripts/generate_classification_coverage.py
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import openai
from foundation_sar import (
    CustomerData, AccountData, TransactionData, CaseData,
    RiskAnalystOutput, ComplianceOfficerOutput,
    ExplainabilityLogger, DataLoader
)
from risk_analyst_agent import RiskAnalystAgent
from compliance_officer_agent import ComplianceOfficerAgent


# ===== TEST SCENARIO DEFINITIONS =====

def create_fraud_test_case():
    """Create a test case with strong Fraud indicators.

    Fraud signals:
    - Account takeover pattern (new device access)
    - Unauthorized wire transfers to unknown accounts
    - Rapid withdrawals after credential change
    - Identity verification failures
    """
    customer = CustomerData(
        customer_id="CUST_FRAUD_TEST",
        name="Marcus Thompson",
        date_of_birth="1978-03-15",
        ssn_last_4="4521",
        address="892 Oak Street, Denver, CO 80205",
        customer_since="2018-05-20",
        risk_rating="Low",  # Was low-risk before incident
        phone="303-555-0147",
        occupation="Software Engineer",
        annual_income=125000
    )

    account = AccountData(
        account_id="CUST_FRAUD_TEST_ACC_1",
        customer_id="CUST_FRAUD_TEST",
        account_type="Checking",
        opening_date="2018-05-20",
        current_balance=2500.00,  # Drastically reduced from normal
        average_monthly_balance=45000.00,  # Was much higher
        status="Suspended"  # Account suspended due to fraud
    )

    # Fraud pattern: Normal activity followed by account takeover
    transactions = [
        # Normal activity pattern
        TransactionData(
            transaction_id="TXN_FRAUD_01",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-01",
            transaction_type="Direct_Deposit",
            amount=5200.00,
            description="Payroll deposit - employer verified",
            method="ACH",
            counterparty="TechCorp Inc Payroll"
        ),
        TransactionData(
            transaction_id="TXN_FRAUD_02",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-05",
            transaction_type="Debit_Purchase",
            amount=-156.78,
            description="Grocery store purchase",
            method="Debit",
            location="Branch_Denver_Main"
        ),
        # FRAUD PATTERN BEGINS - Unauthorized access from new device
        TransactionData(
            transaction_id="TXN_FRAUD_03",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-15",
            transaction_type="Wire_Transfer",
            amount=-15000.00,
            description="UNAUTHORIZED TRANSFER - New device IP flagged - Transfer to unknown external account",
            method="Wire",
            counterparty="Unknown Account 9847362",
            location="Online_Foreign_IP"
        ),
        TransactionData(
            transaction_id="TXN_FRAUD_04",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-15",
            transaction_type="Wire_Transfer",
            amount=-12000.00,
            description="UNAUTHORIZED - Rapid consecutive transfer - credential compromise suspected",
            method="Wire",
            counterparty="Offshore Account XYZ",
            location="Online_Foreign_IP"
        ),
        TransactionData(
            transaction_id="TXN_FRAUD_05",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-15",
            transaction_type="Wire_Transfer",
            amount=-8500.00,
            description="UNAUTHORIZED - Third rapid transfer - account takeover pattern",
            method="Wire",
            counterparty="Unknown Beneficiary",
            location="Online_Foreign_IP"
        ),
        TransactionData(
            transaction_id="TXN_FRAUD_06",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-15",
            transaction_type="ATM_Withdrawal",
            amount=-2000.00,
            description="ATM withdrawal - unusual location - identity verification failed",
            method="ATM",
            location="ATM_Miami_FL"  # Customer lives in Denver
        ),
        TransactionData(
            transaction_id="TXN_FRAUD_07",
            account_id="CUST_FRAUD_TEST_ACC_1",
            transaction_date="2025-07-16",
            transaction_type="Online_Transfer",
            amount=-5000.00,
            description="BLOCKED - Additional unauthorized transfer attempt - account frozen",
            method="Wire",
            counterparty="Blocked Transfer",
            location="Online_Foreign_IP"
        ),
    ]

    case = CaseData(
        case_id=str(uuid.uuid4()),
        customer=customer,
        accounts=[account],
        transactions=transactions,
        case_created_at=datetime.now(timezone.utc).isoformat(),
        data_sources={
            "customer_source": "fraud_test_scenario",
            "account_source": "fraud_test_scenario",
            "transaction_source": "fraud_test_scenario"
        }
    )

    return case


def create_sanctions_test_case():
    """Create a test case with strong Sanctions indicators.

    Sanctions signals:
    - Wire transfers to/from OFAC-sanctioned countries (Iran, North Korea)
    - Counterparties matching SDN (Specially Designated Nationals) patterns
    - Transactions involving sanctioned entities/banks
    """
    customer = CustomerData(
        customer_id="CUST_SANCTIONS_TEST",
        name="Alexander Petrov",
        date_of_birth="1965-11-22",
        ssn_last_4="7834",
        address="1450 International Plaza, Suite 200, New York, NY 10019",
        customer_since="2022-03-15",
        risk_rating="High",
        phone="212-555-0891",
        occupation="Import/Export Business Owner",
        annual_income=450000
    )

    account = AccountData(
        account_id="CUST_SANCTIONS_TEST_ACC_1",
        customer_id="CUST_SANCTIONS_TEST",
        account_type="Business_Checking",
        opening_date="2022-03-15",
        current_balance=285000.00,
        average_monthly_balance=320000.00,
        status="Under_Review"
    )

    # Sanctions pattern: International transfers to OFAC-sanctioned jurisdictions
    transactions = [
        TransactionData(
            transaction_id="TXN_SANCT_01",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-06-01",
            transaction_type="Wire_Transfer",
            amount=75000.00,
            description="Incoming wire - Trade payment - Dubai intermediary",
            method="Wire",
            counterparty="Gulf Trading LLC Dubai",
            location="International_Wire"
        ),
        # SANCTIONS VIOLATION - Transfer to Iran
        TransactionData(
            transaction_id="TXN_SANCT_02",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-06-10",
            transaction_type="Wire_Transfer",
            amount=-50000.00,
            description="Wire transfer to Tehran Trading Company - IRAN - OFAC SANCTIONED COUNTRY",
            method="Wire",
            counterparty="Tehran Trading Company, Tehran, Iran",
            location="International_Wire_Iran"
        ),
        TransactionData(
            transaction_id="TXN_SANCT_03",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-06-15",
            transaction_type="Wire_Transfer",
            amount=-35000.00,
            description="Payment to Bank Melli Iran correspondent - SANCTIONED IRANIAN BANK",
            method="Wire",
            counterparty="Bank Melli Iran via intermediary",
            location="International_Wire"
        ),
        # SANCTIONS VIOLATION - North Korea connection
        TransactionData(
            transaction_id="TXN_SANCT_04",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-06-20",
            transaction_type="Wire_Transfer",
            amount=-28000.00,
            description="Wire to DPRK-affiliated company - North Korea front company - SANCTIONED",
            method="Wire",
            counterparty="Korea Daesong Trading Corporation",
            location="International_Wire_DPRK"
        ),
        TransactionData(
            transaction_id="TXN_SANCT_05",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-06-25",
            transaction_type="Wire_Transfer",
            amount=120000.00,
            description="Incoming from Syria-linked entity - OFAC scrutiny",
            method="Wire",
            counterparty="Damascus Commerce Group",
            location="International_Wire_Syria"
        ),
        TransactionData(
            transaction_id="TXN_SANCT_06",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-07-01",
            transaction_type="Wire_Transfer",
            amount=-45000.00,
            description="Payment to Russian oligarch-linked entity - SDN LIST MATCH SUSPECTED",
            method="Wire",
            counterparty="Vnesheconombank subsidiary",
            location="International_Wire_Russia"
        ),
        TransactionData(
            transaction_id="TXN_SANCT_07",
            account_id="CUST_SANCTIONS_TEST_ACC_1",
            transaction_date="2025-07-05",
            transaction_type="Wire_Transfer",
            amount=-22000.00,
            description="Transfer to Cuba via Panama intermediary - OFAC CUBA SANCTIONS",
            method="Wire",
            counterparty="Havana International Trading via Panama City",
            location="International_Wire_Cuba"
        ),
    ]

    case = CaseData(
        case_id=str(uuid.uuid4()),
        customer=customer,
        accounts=[account],
        transactions=transactions,
        case_created_at=datetime.now(timezone.utc).isoformat(),
        data_sources={
            "customer_source": "sanctions_test_scenario",
            "account_source": "sanctions_test_scenario",
            "transaction_source": "sanctions_test_scenario"
        }
    )

    return case


def create_structuring_test_case():
    """Create a test case with strong Structuring indicators."""
    customer = CustomerData(
        customer_id="CUST_STRUCT_TEST",
        name="Jennifer Walsh",
        date_of_birth="1982-07-14",
        ssn_last_4="3892",
        address="445 Commerce Drive, Phoenix, AZ 85001",
        customer_since="2021-01-15",
        risk_rating="Medium",
        phone="602-555-0234",
        occupation="Restaurant Owner",
        annual_income=95000
    )

    account = AccountData(
        account_id="CUST_STRUCT_TEST_ACC_1",
        customer_id="CUST_STRUCT_TEST",
        account_type="Business_Checking",
        opening_date="2021-01-15",
        current_balance=78500.00,
        average_monthly_balance=65000.00,
        status="Active"
    )

    # Structuring pattern: Multiple cash deposits just under $10,000
    transactions = [
        TransactionData(
            transaction_id="TXN_STRUCT_01",
            account_id="CUST_STRUCT_TEST_ACC_1",
            transaction_date="2025-07-01",
            transaction_type="Cash_Deposit",
            amount=9800.00,
            description="Cash deposit - business receipts",
            method="Cash",
            location="Branch_Phoenix_Main"
        ),
        TransactionData(
            transaction_id="TXN_STRUCT_02",
            account_id="CUST_STRUCT_TEST_ACC_1",
            transaction_date="2025-07-02",
            transaction_type="Cash_Deposit",
            amount=9500.00,
            description="Cash deposit - daily receipts",
            method="Cash",
            location="Branch_Phoenix_West"
        ),
        TransactionData(
            transaction_id="TXN_STRUCT_03",
            account_id="CUST_STRUCT_TEST_ACC_1",
            transaction_date="2025-07-03",
            transaction_type="Cash_Deposit",
            amount=9900.00,
            description="Cash deposit - weekend receipts",
            method="Cash",
            location="Branch_Phoenix_Main"
        ),
        TransactionData(
            transaction_id="TXN_STRUCT_04",
            account_id="CUST_STRUCT_TEST_ACC_1",
            transaction_date="2025-07-05",
            transaction_type="Cash_Deposit",
            amount=9750.00,
            description="Cash deposit - receipts",
            method="Cash",
            location="Branch_Phoenix_East"
        ),
        TransactionData(
            transaction_id="TXN_STRUCT_05",
            account_id="CUST_STRUCT_TEST_ACC_1",
            transaction_date="2025-07-06",
            transaction_type="Cash_Deposit",
            amount=9850.00,
            description="Cash deposit - business cash",
            method="Cash",
            location="Branch_Phoenix_Main"
        ),
        TransactionData(
            transaction_id="TXN_STRUCT_06",
            account_id="CUST_STRUCT_TEST_ACC_1",
            transaction_date="2025-07-07",
            transaction_type="Cash_Deposit",
            amount=9600.00,
            description="Cash deposit",
            method="Cash",
            location="Branch_Phoenix_West"
        ),
    ]

    case = CaseData(
        case_id=str(uuid.uuid4()),
        customer=customer,
        accounts=[account],
        transactions=transactions,
        case_created_at=datetime.now(timezone.utc).isoformat(),
        data_sources={
            "customer_source": "structuring_test_scenario",
            "account_source": "structuring_test_scenario",
            "transaction_source": "structuring_test_scenario"
        }
    )

    return case


def create_money_laundering_test_case():
    """Create a test case with strong Money Laundering indicators."""
    customer = CustomerData(
        customer_id="CUST_ML_TEST",
        name="Robert Chen",
        date_of_birth="1970-04-08",
        ssn_last_4="6147",
        address="8800 Wilshire Blvd, Suite 400, Beverly Hills, CA 90211",
        customer_since="2023-06-01",
        risk_rating="High",
        phone="310-555-0892",
        occupation="Real Estate Investor",
        annual_income=85000  # Low stated income
    )

    account = AccountData(
        account_id="CUST_ML_TEST_ACC_1",
        customer_id="CUST_ML_TEST",
        account_type="Business_Checking",
        opening_date="2023-06-01",
        current_balance=425000.00,  # High balance inconsistent with income
        average_monthly_balance=380000.00,
        status="Active"
    )

    # Money laundering pattern: Layering through multiple transfers and shell companies
    transactions = [
        TransactionData(
            transaction_id="TXN_ML_01",
            account_id="CUST_ML_TEST_ACC_1",
            transaction_date="2025-06-01",
            transaction_type="Wire_Transfer",
            amount=250000.00,
            description="Incoming wire - Source unclear - offshore shell company",
            method="Wire",
            counterparty="Cayman Islands Holdings Ltd",
            location="International_Wire"
        ),
        TransactionData(
            transaction_id="TXN_ML_02",
            account_id="CUST_ML_TEST_ACC_1",
            transaction_date="2025-06-03",
            transaction_type="Wire_Transfer",
            amount=-75000.00,
            description="Wire to Panama shell company - layering",
            method="Wire",
            counterparty="Panama Investments SA",
            location="International_Wire"
        ),
        TransactionData(
            transaction_id="TXN_ML_03",
            account_id="CUST_ML_TEST_ACC_1",
            transaction_date="2025-06-05",
            transaction_type="Wire_Transfer",
            amount=-50000.00,
            description="Transfer to Delaware LLC - no apparent business purpose",
            method="Wire",
            counterparty="Blue Sky Ventures LLC Delaware",
            location="Domestic_Wire"
        ),
        TransactionData(
            transaction_id="TXN_ML_04",
            account_id="CUST_ML_TEST_ACC_1",
            transaction_date="2025-06-10",
            transaction_type="Wire_Transfer",
            amount=180000.00,
            description="Incoming - BVI company - round trip suspected",
            method="Wire",
            counterparty="British Virgin Islands Trust Co",
            location="International_Wire"
        ),
        TransactionData(
            transaction_id="TXN_ML_05",
            account_id="CUST_ML_TEST_ACC_1",
            transaction_date="2025-06-15",
            transaction_type="Wire_Transfer",
            amount=-120000.00,
            description="Real estate purchase - cash equivalent - integration",
            method="Wire",
            counterparty="Luxury Properties LLC",
            location="Domestic_Wire"
        ),
        TransactionData(
            transaction_id="TXN_ML_06",
            account_id="CUST_ML_TEST_ACC_1",
            transaction_date="2025-06-20",
            transaction_type="Check_Deposit",
            amount=95000.00,
            description="Third party check - unknown source - smurfing suspected",
            method="Check",
            counterparty="Unknown Third Party",
            location="Branch_Beverly_Hills"
        ),
    ]

    case = CaseData(
        case_id=str(uuid.uuid4()),
        customer=customer,
        accounts=[account],
        transactions=transactions,
        case_created_at=datetime.now(timezone.utc).isoformat(),
        data_sources={
            "customer_source": "ml_test_scenario",
            "account_source": "ml_test_scenario",
            "transaction_source": "ml_test_scenario"
        }
    )

    return case


def create_other_test_case():
    """Create a test case with suspicious patterns that don't fit standard categories.

    This scenario has unusual activity that warrants SAR filing but doesn't clearly
    fit Structuring, Fraud, Money Laundering, or Sanctions typologies.
    The pattern is suspicious and requires investigation but classification is unclear.
    """
    customer = CustomerData(
        customer_id="CUST_OTHER_TEST",
        name="Kevin O'Brien",
        date_of_birth="1995-09-28",
        ssn_last_4="4182",
        address="3400 University Avenue, Apt 12B, Austin, TX 78705",
        customer_since="2023-01-10",
        risk_rating="Medium",
        phone="512-555-0394",
        occupation="Graduate Student",
        annual_income=28000  # Low student income
    )

    account = AccountData(
        account_id="CUST_OTHER_TEST_ACC_1",
        customer_id="CUST_OTHER_TEST",
        account_type="Checking",
        opening_date="2023-01-10",
        current_balance=4200.00,
        average_monthly_balance=3500.00,
        status="Active"
    )

    # Unusual pattern: Activity inconsistent with stated profile
    # Not structuring (varying amounts, not near threshold)
    # Not fraud (no takeover indicators, authorized access)
    # Not money laundering (no shell companies, no layering)
    # Not sanctions (domestic entities only)
    # But still suspicious due to inconsistencies
    transactions = [
        TransactionData(
            transaction_id="TXN_OTHER_01",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-01",
            transaction_type="ACH_Credit",
            amount=2800.00,
            description="Monthly stipend - university research grant",
            method="ACH",
            counterparty="University of Texas",
            location="Online"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_02",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-05",
            transaction_type="Zelle_Transfer",
            amount=1500.00,
            description="Incoming Zelle - tutor payment - multiple students",
            method="Zelle",
            counterparty="Multiple Personal Contacts",
            location="Mobile"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_03",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-08",
            transaction_type="Zelle_Transfer",
            amount=1200.00,
            description="Incoming Zelle - notes sales to classmates",
            method="Zelle",
            counterparty="Various Students",
            location="Mobile"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_04",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-12",
            transaction_type="ACH_Debit",
            amount=-800.00,
            description="Rent payment - student housing",
            method="ACH",
            counterparty="Campus Housing LLC",
            location="Online"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_05",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-15",
            transaction_type="Zelle_Transfer",
            amount=2200.00,
            description="Incoming Zelle - essay editing services - unusual volume",
            method="Zelle",
            counterparty="Multiple Unknown Senders",
            location="Mobile"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_06",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-18",
            transaction_type="Zelle_Transfer",
            amount=1800.00,
            description="Incoming Zelle - homework help - frequent small payments aggregated",
            method="Zelle",
            counterparty="Anonymous Senders",
            location="Mobile"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_07",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-22",
            transaction_type="ATM_Withdrawal",
            amount=-500.00,
            description="Cash withdrawal - stated purpose: books",
            method="ATM",
            location="ATM_Austin_Campus"
        ),
        TransactionData(
            transaction_id="TXN_OTHER_08",
            account_id="CUST_OTHER_TEST_ACC_1",
            transaction_date="2025-06-25",
            transaction_type="Zelle_Transfer",
            amount=1600.00,
            description="Incoming Zelle - online tutoring payments - suspicious volume for student",
            method="Zelle",
            counterparty="Out of State Contacts",
            location="Mobile"
        ),
    ]

    case = CaseData(
        case_id=str(uuid.uuid4()),
        customer=customer,
        accounts=[account],
        transactions=transactions,
        case_created_at=datetime.now(timezone.utc).isoformat(),
        data_sources={
            "customer_source": "other_test_scenario",
            "account_source": "other_test_scenario",
            "transaction_source": "other_test_scenario"
        }
    )

    return case


# ===== SAR DOCUMENT GENERATION =====

def create_sar_document(case_data, risk_analysis, compliance_review, human_decision_info=None):
    """Create a complete FinCEN-ready SAR document."""
    sar_id = f"SAR_{uuid.uuid4().hex[:12].upper()}"
    filing_date = datetime.now().isoformat()

    content_str = json.dumps({
        'case_id': case_data.case_id,
        'classification': risk_analysis.classification,
        'narrative': compliance_review.narrative
    }, sort_keys=True)
    checksum = hashlib.sha256(content_str.encode()).hexdigest()

    sar_document = {
        'sar_metadata': {
            'sar_id': sar_id,
            'filing_date': filing_date,
            'filing_type': 'Suspicious Activity Report',
            'ai_generated': True,
            'review_status': 'human_approved',
            'document_checksum': checksum,
            'test_scenario': True,
            'classification_coverage_test': risk_analysis.classification
        },
        'subject_information': {
            'customer_name': case_data.customer.name,
            'customer_id': case_data.customer.customer_id,
            'date_of_birth': case_data.customer.date_of_birth,
            'ssn_last_4': case_data.customer.ssn_last_4,
            'address': case_data.customer.address,
            'customer_since': case_data.customer.customer_since,
            'risk_rating': case_data.customer.risk_rating,
            'occupation': case_data.customer.occupation or '',
            'annual_income': case_data.customer.annual_income or 0
        },
        'suspicious_activity': {
            'classification': risk_analysis.classification,
            'risk_level': risk_analysis.risk_level,
            'confidence_score': risk_analysis.confidence_score,
            'narrative': compliance_review.narrative,
            'narrative_word_count': len(compliance_review.narrative.split()),
            'key_indicators': risk_analysis.key_indicators,
            'ai_reasoning': risk_analysis.reasoning
        },
        'regulatory_compliance': {
            'citations': compliance_review.regulatory_citations,
            'completeness_check': compliance_review.completeness_check,
            'narrative_reasoning': compliance_review.narrative_reasoning,
            'compliance_status': 'approved'
        },
        'account_information': [
            {
                'account_id': acc.account_id,
                'account_type': acc.account_type,
                'current_balance': acc.current_balance,
                'status': acc.status
            }
            for acc in case_data.accounts
        ],
        'transaction_summary': {
            'total_transactions': len(case_data.transactions),
            'total_volume': sum(abs(t.amount) for t in case_data.transactions),
            'date_range': {
                'earliest': min(t.transaction_date for t in case_data.transactions),
                'latest': max(t.transaction_date for t in case_data.transactions)
            }
        },
        'audit_trail': {
            'case_id': case_data.case_id,
            'processing_date': filing_date,
            'ai_agents_used': ['RiskAnalyst', 'ComplianceOfficer'],
            'human_reviewer': 'classification_coverage_test',
            'filing_institution': 'TRACE Financial Services',
            'human_decision_gate': {
                'decision_timestamp': filing_date,
                'decision': 'PROCEED',
                'reviewer_identity': 'auto_approve_coverage_test',
                'reviewer_decision': 'yes (classification coverage test)',
                'rationale': f'Auto-approved for classification coverage testing - {risk_analysis.classification}',
                'ai_classification_at_decision': risk_analysis.classification,
                'ai_confidence_at_decision': risk_analysis.confidence_score,
                'ai_risk_level_at_decision': risk_analysis.risk_level,
                'decision_log_reference': f"workflow_decisions.jsonl:case_id={case_data.case_id}"
            }
        }
    }
    return sar_document


def save_sar_document(sar_document, output_dir):
    """Save SAR document to file."""
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"{sar_document['sar_metadata']['sar_id']}.json")
    with open(filename, 'w') as f:
        json.dump(sar_document, f, indent=2)
    return filename


# ===== MAIN WORKFLOW =====

def run_classification_coverage_workflow():
    """Run the complete workflow to generate artifacts for all 5 classifications."""
    print("\n" + "=" * 70)
    print("  🎯 CLASSIFICATION COVERAGE ARTIFACT GENERATOR")
    print("=" * 70)
    print("\nThis script generates SAR artifacts for all 5 classification types:")
    print("  1. Structuring")
    print("  2. Money_Laundering")
    print("  3. Fraud")
    print("  4. Sanctions")
    print("  5. Other")

    # Initialize OpenAI client
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("\n❌ ERROR: OPENAI_API_KEY not found in environment")
        return False

    # Check for Vocareum routing
    base_url = os.getenv('OPENAI_BASE_URL', 'https://openai.vocareum.com/v1')
    client = openai.OpenAI(base_url=base_url, api_key=openai_api_key)
    print(f"\n✅ OpenAI client initialized")
    print(f"   Base URL: {base_url}")

    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, "outputs", "filed_sars")
    audit_log_dir = os.path.join(project_root, "outputs", "audit_logs")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(audit_log_dir, exist_ok=True)

    # Initialize agents
    logger = ExplainabilityLogger(os.path.join(audit_log_dir, "classification_coverage.jsonl"))
    risk_agent = RiskAnalystAgent(client, logger)
    compliance_agent = ComplianceOfficerAgent(client, logger)

    # Define test scenarios with expected classifications
    test_scenarios = [
        ("Fraud", create_fraud_test_case),
        ("Sanctions", create_sanctions_test_case),
        ("Structuring", create_structuring_test_case),
        ("Money_Laundering", create_money_laundering_test_case),
        ("Other", create_other_test_case),
    ]

    results = {
        "successful": [],
        "failed": [],
        "classifications_produced": {}
    }

    for expected_classification, case_factory in test_scenarios:
        print(f"\n{'─' * 60}")
        print(f"  📋 Testing: {expected_classification}")
        print(f"{'─' * 60}")

        try:
            # Create test case
            case_data = case_factory()
            print(f"  Customer: {case_data.customer.name}")
            print(f"  Transactions: {len(case_data.transactions)}")

            # Stage 1: Risk Analysis
            print(f"\n  🔍 [Stage 1] Risk Analysis...")
            risk_analysis = risk_agent.analyze_case(case_data)
            print(f"    Classification: {risk_analysis.classification}")
            print(f"    Confidence: {risk_analysis.confidence_score:.2f}")
            print(f"    Risk Level: {risk_analysis.risk_level}")

            # Log to audit
            logger.log_human_decision(
                case_id=case_data.case_id,
                customer_id=case_data.customer.customer_id,
                customer_name=case_data.customer.name,
                decision='PROCEED',
                reviewer_decision='yes (classification coverage test)',
                reviewer_identity='auto_approve_coverage_test',
                ai_classification=risk_analysis.classification,
                ai_confidence=risk_analysis.confidence_score,
                ai_risk_level=risk_analysis.risk_level,
                rationale=f"Classification coverage test - Expected: {expected_classification}, Got: {risk_analysis.classification}",
                decision_file=os.path.join(audit_log_dir, "workflow_decisions.jsonl")
            )

            # Stage 2: Compliance Narrative
            print(f"\n  📝 [Stage 2] Compliance Narrative Generation...")
            compliance_review = compliance_agent.generate_compliance_narrative(
                case_data, risk_analysis
            )
            print(f"    Narrative ({len(compliance_review.narrative.split())} words)")
            print(f"    Citations: {', '.join(compliance_review.regulatory_citations)}")

            # Generate and save SAR
            sar_document = create_sar_document(case_data, risk_analysis, compliance_review)
            sar_path = save_sar_document(sar_document, output_dir)

            actual_classification = risk_analysis.classification
            results["successful"].append({
                "expected": expected_classification,
                "actual": actual_classification,
                "sar_id": sar_document['sar_metadata']['sar_id'],
                "sar_path": sar_path,
                "match": expected_classification == actual_classification
            })
            results["classifications_produced"][actual_classification] = sar_document['sar_metadata']['sar_id']

            print(f"\n  ✅ SAR Filed: {sar_document['sar_metadata']['sar_id']}")
            if expected_classification != actual_classification:
                print(f"  ⚠️  Note: Expected {expected_classification}, got {actual_classification}")

        except Exception as e:
            print(f"\n  ❌ ERROR: {e}")
            results["failed"].append({
                "expected": expected_classification,
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 70)
    print("  📊 CLASSIFICATION COVERAGE SUMMARY")
    print("=" * 70)

    print(f"\n  Successful: {len(results['successful'])}")
    print(f"  Failed: {len(results['failed'])}")

    print(f"\n  Classifications Produced:")
    for cls, sar_id in results["classifications_produced"].items():
        print(f"    ✅ {cls}: {sar_id}")

    # Check for missing classifications
    all_classifications = {"Structuring", "Sanctions", "Fraud", "Money_Laundering", "Other"}
    produced = set(results["classifications_produced"].keys())
    missing = all_classifications - produced

    if missing:
        print(f"\n  ⚠️  Missing Classifications: {', '.join(missing)}")
        print(f"     These may require adjusted test scenarios or multiple runs")
    else:
        print(f"\n  🎉 ALL 5 CLASSIFICATIONS COVERED!")

    print(f"\n  📄 SAR documents saved to: {output_dir}")
    print(f"  📊 Audit logs saved to: {audit_log_dir}")

    return len(missing) == 0


if __name__ == "__main__":
    success = run_classification_coverage_workflow()
    sys.exit(0 if success else 1)
