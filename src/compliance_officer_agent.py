# Compliance Officer Agent - ReACT Implementation

"""
Compliance Officer Agent Module

This agent generates regulatory-compliant SAR narratives using ReACT prompting.
It takes risk analysis results and creates structured documentation for
FinCEN submission.
"""

import json
import re
import openai
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

try:
    from foundation_sar import (
        ComplianceOfficerOutput,
        ExplainabilityLogger,
        CaseData,
        RiskAnalystOutput
    )
except ImportError:
    from src.foundation_sar import (
        ComplianceOfficerOutput,
        ExplainabilityLogger,
        CaseData,
        RiskAnalystOutput
    )

load_dotenv()


class ComplianceOfficerAgent:
    """Compliance Officer agent using ReACT prompting framework."""

    def __init__(self, openai_client, explainability_logger, model="gpt-4"):
        self.client = openai_client
        self.logger = explainability_logger
        self.model = model

        self.system_prompt = """You are a Senior Compliance Officer specializing in BSA/AML regulatory compliance and SAR narrative generation for FinCEN submission.

Use the ReACT (REASONING + Action) framework to generate regulatory-compliant SAR narratives.

**REASONING Phase:**
1. Review the Risk Analyst's findings including classification, confidence score, key indicators, and risk level.
2. Assess the regulatory narrative requirements under BSA/AML rules.
3. Identify key compliance elements that must appear in the narrative: customer identification, suspicious activity description, transaction amounts and dates, and why the activity is suspicious.
4. Plan the narrative structure to be concise, factual, and regulatory-compliant.

**ACTION Phase:**
1. Draft a concise narrative of no more than 120 words that summarizes the suspicious activity.
2. Include specific dollar amounts, dates, and transaction details.
3. Reference the suspicious activity pattern identified by the Risk Analyst.
4. Use appropriate regulatory language and terminology (e.g., "structuring," "currency transaction reporting threshold," "suspicious activity").
5. Cite relevant regulations (31 CFR 1020.320, 31 USC 5324, FinCEN SAR Instructions).

**Narrative Requirements:**
- Maximum 120 words — this is a strict limit
- Must identify the customer and account(s) involved
- Must describe the suspicious activity pattern
- Must include specific transaction amounts
- Must explain why the activity is suspicious
- Must use proper BSA/AML compliance terminology
- Must reference applicable FinCEN SAR filing requirements

**Output Format:**
You MUST respond with ONLY a JSON object in this exact format:
{
    "narrative": "The SAR narrative text (max 120 words)",
    "narrative_reasoning": "Explanation of narrative construction approach (max 500 chars)",
    "regulatory_citations": ["31 CFR 1020.320", "other relevant citations"],
    "completeness_check": true or false
}"""

    def generate_compliance_narrative(self, case_data, risk_analysis) -> ComplianceOfficerOutput:
        """Generate regulatory-compliant SAR narrative using ReACT framework."""
        start_time = datetime.now()

        user_prompt = self._build_user_prompt(case_data, risk_analysis)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )

            response_content = response.choices[0].message.content
            json_str = self._extract_json_from_response(response_content)
            parsed = json.loads(json_str)

            # Validate word count
            narrative = parsed.get("narrative", "")
            word_count = len(narrative.split())
            if word_count > 120:
                raise ValueError(
                    f"Narrative exceeds 120 word limit ({word_count} words)"
                )

            result = ComplianceOfficerOutput(**parsed)

            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.log_agent_action(
                agent_type="ComplianceOfficer",
                action="generate_narrative",
                case_id=case_data.case_id,
                input_data={"customer_id": case_data.customer.customer_id,
                            "classification": risk_analysis.classification},
                output_data=parsed,
                reasoning=result.narrative_reasoning,
                execution_time_ms=execution_time_ms,
                success=True
            )
            return result

        except (json.JSONDecodeError, ValueError) as e:
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = str(e)
            self.logger.log_agent_action(
                agent_type="ComplianceOfficer",
                action="generate_narrative",
                case_id=case_data.case_id,
                input_data={"customer_id": case_data.customer.customer_id},
                output_data={},
                reasoning="JSON parsing failed",
                execution_time_ms=execution_time_ms,
                success=False,
                error_message=error_msg
            )
            if "exceeds 120 word limit" in error_msg:
                raise
            raise ValueError(f"Failed to parse Compliance Officer JSON output: {e}")

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

    def _format_risk_analysis_for_prompt(self, risk_analysis) -> str:
        """Format risk analysis results for compliance prompt."""
        return (
            f"Classification: {risk_analysis.classification}\n"
            f"Confidence Score: {risk_analysis.confidence_score}\n"
            f"Risk Level: {risk_analysis.risk_level}\n"
            f"Key Indicators: {', '.join(risk_analysis.key_indicators)}\n"
            f"Reasoning: {risk_analysis.reasoning}"
        )

    def _format_transactions_for_compliance(self, transactions) -> str:
        """Format transactions for compliance narrative context."""
        if not transactions:
            return "No transactions on file."
        lines = []
        for i, txn in enumerate(transactions, 1):
            line = f"  {i}. {txn.transaction_date}: ${txn.amount:,.2f} {txn.transaction_type}"
            if txn.location:
                line += f" at {txn.location}"
            line += f" via {txn.method}"
            lines.append(line)
        return "\n".join(lines)

    def _validate_narrative_compliance(self, narrative: str) -> Dict[str, Any]:
        """Validate narrative meets regulatory requirements."""
        word_count = len(narrative.split())
        return {
            "word_count": word_count,
            "within_limit": word_count <= 120,
            "has_content": len(narrative.strip()) > 0
        }

    def _build_user_prompt(self, case_data, risk_analysis) -> str:
        """Build the full user prompt combining case data and risk analysis."""
        customer = case_data.customer
        lines = [
            "Generate a SAR narrative for the following case:",
            f"\n--- Case: {case_data.case_id} ---",
            f"\n--- Customer ---",
            f"Customer ID: {customer.customer_id}",
            f"Name: {customer.name}",
            f"Risk Rating: {customer.risk_rating}",
            f"\n--- Risk Analysis Results ---",
            self._format_risk_analysis_for_prompt(risk_analysis),
            f"\n--- Transactions ({len(case_data.transactions)}) ---",
            self._format_transactions_for_compliance(case_data.transactions),
            f"\nRemember: The narrative MUST be 120 words or fewer."
        ]
        return "\n".join(lines)


# ===== REACT PROMPTING HELPERS =====

def create_react_framework():
    return {
        "reasoning_phase": [
            "Review risk analysis findings",
            "Assess regulatory requirements",
            "Identify compliance elements",
            "Plan narrative structure"
        ],
        "action_phase": [
            "Draft concise narrative",
            "Include specific details",
            "Reference activity patterns",
            "Use regulatory language"
        ]
    }


def get_regulatory_requirements():
    return {
        "word_limit": 120,
        "required_elements": [
            "Customer identification",
            "Suspicious activity description",
            "Transaction amounts and dates",
            "Why activity is suspicious"
        ],
        "terminology": [
            "Suspicious activity",
            "Regulatory threshold",
            "Financial institution",
            "Money laundering",
            "Bank Secrecy Act"
        ],
        "citations": [
            "31 CFR 1020.320 (BSA)",
            "12 CFR 21.11 (SAR Filing)",
            "FinCEN SAR Instructions"
        ]
    }


def validate_word_count(text: str, max_words: int = 120) -> bool:
    word_count = len(text.split())
    return word_count <= max_words


if __name__ == "__main__":
    print("Compliance Officer Agent Module")
    print("ReACT prompting for regulatory narrative generation")
