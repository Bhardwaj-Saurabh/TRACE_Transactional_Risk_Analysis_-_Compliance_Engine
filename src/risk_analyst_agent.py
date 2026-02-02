# Risk Analyst Agent - Chain-of-Thought Implementation

"""
Risk Analyst Agent Module

This agent performs suspicious activity classification using Chain-of-Thought reasoning.
It analyzes customer profiles, account behavior, and transaction patterns to identify
potential financial crimes.
"""

import json
import re
import openai
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

try:
    from foundation_sar import (
        RiskAnalystOutput,
        ExplainabilityLogger,
        CaseData
    )
except ImportError:
    from src.foundation_sar import (
        RiskAnalystOutput,
        ExplainabilityLogger,
        CaseData
    )

load_dotenv()


class RiskAnalystAgent:
    """Risk Analyst agent using Chain-of-Thought reasoning."""

    def __init__(self, openai_client, explainability_logger, model="gpt-4"):
        self.client = openai_client
        self.logger = explainability_logger
        self.model = model

        self.system_prompt = """You are a Senior Financial Crime Risk Analyst with extensive experience in Bank Secrecy Act (BSA) compliance and suspicious activity detection.

Use a Chain-of-Thought, step-by-step reasoning approach to analyze the case data provided.

**Analysis Framework (Chain-of-Thought):**

Step 1 - Data Review: Examine the customer profile, account details, and transaction history. Note any anomalies in balances, account age, or customer demographics.

Step 2 - Pattern Recognition: Identify suspicious patterns such as structuring (transactions just under $10,000), rapid movement of funds, unusual counterparties, geographic risk indicators, or activity inconsistent with the customer profile.

Step 3 - Regulatory Mapping: Map identified patterns to known financial crime typologies and relevant regulations (BSA, USA PATRIOT Act, OFAC sanctions).

Step 4 - Risk Quantification: Assess the severity and confidence level based on the strength and number of indicators found.

Step 5 - Classification Decision: Assign a final classification based on the predominant pattern.

**Classification Categories:**
- Structuring: Transactions designed to avoid reporting thresholds (e.g., multiple deposits just under $10,000)
- Sanctions: Potential sanctions violations or transactions involving prohibited parties/jurisdictions
- Fraud: Fraudulent transactions, identity-related crimes, or account takeover patterns
- Money_Laundering: Complex schemes to obscure illicit fund sources through layering or integration
- Other: Suspicious patterns not fitting standard categories

**Output Format:**
You MUST respond with ONLY a JSON object in this exact format:
{
    "classification": "Structuring|Sanctions|Fraud|Money_Laundering|Other",
    "confidence_score": 0.0 to 1.0,
    "reasoning": "Step-by-step reasoning summary (max 500 chars)",
    "key_indicators": ["indicator1", "indicator2"],
    "risk_level": "Low|Medium|High|Critical"
}"""

    def analyze_case(self, case_data) -> RiskAnalystOutput:
        """Perform risk analysis on a case using Chain-of-Thought reasoning."""
        start_time = datetime.now()
        user_prompt = self._format_case_for_prompt(case_data)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            response_content = response.choices[0].message.content
            json_str = self._extract_json_from_response(response_content)
            parsed = json.loads(json_str)
            result = RiskAnalystOutput(**parsed)

            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.log_agent_action(
                agent_type="RiskAnalyst",
                action="analyze_case",
                case_id=case_data.case_id,
                input_data={"customer_id": case_data.customer.customer_id},
                output_data=parsed,
                reasoning=result.reasoning,
                execution_time_ms=execution_time_ms,
                success=True
            )
            return result

        except (json.JSONDecodeError, ValueError) as e:
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.log_agent_action(
                agent_type="RiskAnalyst",
                action="analyze_case",
                case_id=case_data.case_id,
                input_data={"customer_id": case_data.customer.customer_id},
                output_data={},
                reasoning="JSON parsing failed",
                execution_time_ms=execution_time_ms,
                success=False,
                error_message=str(e)
            )
            raise ValueError(f"Failed to parse Risk Analyst JSON output: {e}")

    def _extract_json_from_response(self, response_content: str) -> str:
        """Extract JSON content from LLM response."""
        if not response_content or not response_content.strip():
            raise ValueError("No JSON content found in empty response")

        # Try code block extraction
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try plain JSON extraction
        match = re.search(r'\{.*\}', response_content, re.DOTALL)
        if match:
            return match.group(0).strip()

        raise ValueError("No JSON content found in response")

    def _format_case_for_prompt(self, case_data) -> str:
        """Format case data for the analysis prompt."""
        customer = case_data.customer
        lines = [
            f"Case ID: {case_data.case_id}",
            f"\n--- Customer Profile ---",
            f"Customer ID: {customer.customer_id}",
            f"Name: {customer.name}",
            f"Date of Birth: {customer.date_of_birth}",
            f"Address: {customer.address}",
            f"Customer Since: {customer.customer_since}",
            f"Risk Rating: {customer.risk_rating}",
        ]
        if customer.occupation:
            lines.append(f"Occupation: {customer.occupation}")
        if customer.annual_income:
            lines.append(f"Annual Income: ${customer.annual_income:,}")

        lines.append(f"\n--- Accounts ({len(case_data.accounts)}) ---")
        lines.append(self._format_accounts(case_data.accounts))

        lines.append(f"\n--- Transactions ({len(case_data.transactions)}) ---")
        lines.append(self._format_transactions(case_data.transactions))

        total = sum(t.amount for t in case_data.transactions)
        lines.append(f"\n--- Summary ---")
        lines.append(f"Total transaction volume: ${total:,.2f}")
        lines.append(f"Number of transactions: {len(case_data.transactions)}")

        return "\n".join(lines)

    def _format_accounts(self, accounts) -> str:
        """Format accounts for prompt display."""
        if not accounts:
            return "No accounts on file."
        lines = []
        for acc in accounts:
            lines.append(
                f"  {acc.account_id}: {acc.account_type} | "
                f"Balance: ${acc.current_balance:,.2f} | "
                f"Avg Monthly: ${acc.average_monthly_balance:,.2f} | "
                f"Status: {acc.status}"
            )
        return "\n".join(lines)

    def _format_transactions(self, transactions) -> str:
        """Format transactions for prompt display."""
        if not transactions:
            return "No transactions on file."
        lines = []
        for i, txn in enumerate(transactions, 1):
            line = f"  {i}. {txn.transaction_date}: {txn.transaction_type} ${txn.amount:,.2f}"
            line += f" - {txn.description}"
            if txn.location:
                line += f" (Location: {txn.location})"
            lines.append(line)
        return "\n".join(lines)


# ===== PROMPT ENGINEERING HELPERS =====

def create_chain_of_thought_framework():
    return {
        "step_1": "Data Review - Examine all available information",
        "step_2": "Pattern Recognition - Identify suspicious indicators",
        "step_3": "Regulatory Mapping - Connect to known typologies",
        "step_4": "Risk Quantification - Assess severity level",
        "step_5": "Classification Decision - Determine final category"
    }


def get_classification_categories():
    return {
        "Structuring": "Transactions designed to avoid reporting thresholds",
        "Sanctions": "Potential sanctions violations or prohibited parties",
        "Fraud": "Fraudulent transactions or identity-related crimes",
        "Money_Laundering": "Complex schemes to obscure illicit fund sources",
        "Other": "Suspicious patterns not fitting standard categories"
    }


if __name__ == "__main__":
    print("Risk Analyst Agent Module")
    print("Chain-of-Thought reasoning for suspicious activity classification")
