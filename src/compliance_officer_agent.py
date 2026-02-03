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
from typing import Dict, Any, List, Optional
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


# ===== CUSTOM EXCEPTIONS =====

class NarrativeValidationError(Exception):
    """Exception raised when narrative fails pre-finalization validation.

    Contains detailed validation results to enable regeneration or manual review.
    """
    def __init__(self, message: str, validation_result: Dict[str, Any]):
        super().__init__(message)
        self.validation_result = validation_result
        self.missing_elements = validation_result.get("missing_elements", [])
        self.failed_checks = validation_result.get("failed_checks", [])

    def get_failure_summary(self) -> str:
        """Get a human-readable summary of validation failures."""
        failures = []
        if self.missing_elements:
            failures.append(f"Missing narrative elements: {', '.join(self.missing_elements)}")
        if self.failed_checks:
            failures.append(f"Failed checks: {', '.join(self.failed_checks)}")
        return "; ".join(failures) if failures else "Unknown validation failure"


# ===== VALID REGULATORY CITATIONS =====

VALID_REGULATORY_CITATIONS = [
    # BSA/AML Regulations
    "31 CFR 1020.320",
    "31 CFR 1010.314",
    "31 CFR 1010.311",
    "31 CFR 1020.315",
    "31 USC 5324",
    "31 USC 5313",
    "31 USC 5318",
    # SAR Filing Requirements
    "12 CFR 21.11",
    "12 CFR 208.62",
    "12 CFR 353.3",
    # FinCEN Guidance
    "FinCEN SAR Instructions",
    "FinCEN Advisory",
    "FinCEN Guidance",
    # OFAC
    "OFAC SDN List",
    "Executive Order 13599",
    # Other
    "FTC Red Flags Rule",
    "BSA",
    "AML",
]


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
3. Identify key compliance elements using the Five W's framework: WHO, WHAT, WHEN, WHERE, WHY.
4. Plan the narrative structure to be concise, factual, and regulatory-compliant.

**ACTION Phase:**
1. Draft a concise narrative of no more than 120 words that summarizes the suspicious activity.
2. Include specific dollar amounts, dates, transaction locations, and channels.
3. Reference the suspicious activity pattern identified by the Risk Analyst.
4. Use appropriate regulatory language and terminology (e.g., "structuring," "currency transaction reporting threshold," "suspicious activity").
5. Cite relevant regulations (31 CFR 1020.320, 31 USC 5324, FinCEN SAR Instructions).

**Narrative Requirements - The Five W's (ALL REQUIRED):**
The narrative MUST include ALL FIVE elements:

1. **WHO** - Customer identification:
   - Customer name and ID
   - Account number(s) involved

2. **WHAT** - Suspicious activity description:
   - Type of suspicious activity (structuring, money laundering, fraud, etc.)
   - Specific transaction types involved
   - Total amounts and individual transaction amounts

3. **WHEN** - Temporal details:
   - Specific transaction dates
   - Time period/pattern of activity (e.g., "over three consecutive days")

4. **WHERE** - Location/channel information:
   - Transaction locations (branch names, ATM locations, online)
   - Geographic information if relevant
   - Transaction channels/methods (cash, wire, ACH, etc.)

5. **WHY** - Reason for suspicion:
   - Clear explanation of why the activity is suspicious
   - Reference to regulatory thresholds violated
   - Connection to known suspicious patterns

**Additional Requirements:**
- Maximum 120 words — this is a strict limit
- Must use proper BSA/AML compliance terminology
- Must reference applicable FinCEN SAR filing requirements

**Output Format:**
You MUST respond with ONLY a JSON object in this exact format:
{
    "narrative": "The SAR narrative text (max 120 words) - MUST include all Five W's",
    "narrative_reasoning": "Explanation of narrative construction approach (max 500 chars)",
    "regulatory_citations": ["31 CFR 1020.320", "other relevant citations"],
    "completeness_check": true or false (true ONLY if all Five W's are present)
}"""

    def generate_compliance_narrative(self, case_data, risk_analysis,
                                        max_regeneration_attempts: int = 2,
                                        strict_validation: bool = True) -> ComplianceOfficerOutput:
        """Generate regulatory-compliant SAR narrative using ReACT framework.

        Implements deterministic pre-finalization validation that:
        - Verifies all required SAR narrative elements (Five W's)
        - Validates dollar amounts are included
        - Ensures regulatory citations are valid
        - Blocks finalization when validation fails
        - Optionally attempts regeneration on validation failure

        Args:
            case_data: CaseData object containing customer, account, and transaction info
            risk_analysis: RiskAnalystOutput with classification and indicators
            max_regeneration_attempts: Number of times to retry on validation failure (default 2)
            strict_validation: If True, raises NarrativeValidationError on failure;
                             if False, returns result with validation warnings

        Returns:
            ComplianceOfficerOutput with validated narrative

        Raises:
            NarrativeValidationError: When validation fails after all attempts (if strict_validation=True)
            ValueError: For JSON parsing failures
        """
        start_time = datetime.now()
        user_prompt = self._build_user_prompt(case_data, risk_analysis)

        last_validation_result = None
        attempt = 0

        while attempt <= max_regeneration_attempts:
            try:
                # Build messages with regeneration feedback if applicable
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

                # Add regeneration feedback if this is a retry
                if attempt > 0 and last_validation_result:
                    regeneration_prompt = self._build_regeneration_prompt(last_validation_result)
                    messages.append({"role": "assistant", "content": "I'll regenerate the narrative addressing the validation issues."})
                    messages.append({"role": "user", "content": regeneration_prompt})

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2 + (attempt * 0.1),  # Slightly increase temperature on retries
                    max_tokens=800
                )

                response_content = response.choices[0].message.content
                json_str = self._extract_json_from_response(response_content)
                parsed = json.loads(json_str)

                narrative = parsed.get("narrative", "")
                citations = parsed.get("regulatory_citations", [])
                model_completeness = parsed.get("completeness_check", False)

                # Run pre-finalization validation gate
                validation_result = self._pre_finalization_validation(
                    narrative=narrative,
                    citations=citations,
                    case_data=case_data,
                    model_completeness_check=model_completeness
                )

                if validation_result["can_finalize"]:
                    # Validation passed - create and return result
                    result = ComplianceOfficerOutput(**parsed)

                    execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={
                            "customer_id": case_data.customer.customer_id,
                            "classification": risk_analysis.classification,
                            "attempts": attempt + 1
                        },
                        output_data={
                            **parsed,
                            "validation_passed": True,
                            "validation_details": validation_result
                        },
                        reasoning=result.narrative_reasoning,
                        execution_time_ms=execution_time_ms,
                        success=True
                    )
                    return result

                # Validation failed - store result and potentially retry
                last_validation_result = validation_result

                # Log validation failure
                self.logger.log_agent_action(
                    agent_type="ComplianceOfficer",
                    action="validation_failed",
                    case_id=case_data.case_id,
                    input_data={
                        "customer_id": case_data.customer.customer_id,
                        "attempt": attempt + 1,
                        "max_attempts": max_regeneration_attempts + 1
                    },
                    output_data={
                        "validation_result": validation_result,
                        "narrative_preview": narrative[:100] + "..." if len(narrative) > 100 else narrative
                    },
                    reasoning=f"Validation failed: {'; '.join(validation_result['error_messages'])}",
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    success=False,
                    error_message=f"Failed checks: {', '.join(validation_result['failed_checks'])}"
                )

                attempt += 1

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

        # All attempts exhausted - validation still failing
        if strict_validation and last_validation_result:
            error_message = (
                f"Narrative validation failed after {max_regeneration_attempts + 1} attempts. "
                f"Failed checks: {', '.join(last_validation_result['failed_checks'])}. "
                f"Missing elements: {', '.join(last_validation_result['missing_elements'])}."
            )
            raise NarrativeValidationError(error_message, last_validation_result)

        # If not strict, return with validation warnings (not recommended for production)
        return ComplianceOfficerOutput(**parsed)

    def _build_regeneration_prompt(self, validation_result: Dict[str, Any]) -> str:
        """Build a prompt for regeneration based on validation failures."""
        issues = []

        if "word_count" in validation_result.get("failed_checks", []):
            issues.append(f"- Word count ({validation_result.get('word_count', 'N/A')}) exceeds 120 word limit")

        if validation_result.get("missing_elements"):
            issues.append(f"- Missing required elements: {', '.join(validation_result['missing_elements'])}")

        if "dollar_amounts" in validation_result.get("failed_checks", []):
            issues.append("- Must include specific dollar amounts (e.g., $9,900, $29,500)")

        if "citations" in validation_result.get("failed_checks", []):
            issues.append("- Must include valid regulatory citations (e.g., 31 CFR 1020.320, 31 USC 5324)")

        prompt = (
            "The previous narrative failed validation. Please regenerate addressing these issues:\n"
            + "\n".join(issues)
            + "\n\nGenerate a corrected narrative that passes all validation checks."
        )
        return prompt

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

    def _extract_locations_from_transactions(self, transactions) -> List[str]:
        """Extract unique transaction locations/channels for narrative context."""
        locations = set()
        methods = set()

        for txn in transactions:
            if txn.location:
                locations.add(txn.location)
            if txn.method:
                methods.add(txn.method)

        # Combine locations and methods for comprehensive "where" context
        all_locations = list(locations) + [f"via {m}" for m in methods]
        return all_locations if all_locations else ["location not specified"]

    def _validate_narrative_compliance(self, narrative: str, case_data=None) -> Dict[str, Any]:
        """Validate narrative meets regulatory requirements including Five W's."""
        word_count = len(narrative.split())
        narrative_lower = narrative.lower()

        # Check for presence of Five W's elements
        five_ws = {
            "who": self._check_who_element(narrative, case_data),
            "what": self._check_what_element(narrative_lower),
            "when": self._check_when_element(narrative),
            "where": self._check_where_element(narrative_lower),
            "why": self._check_why_element(narrative_lower)
        }

        all_elements_present = all(five_ws.values())

        return {
            "word_count": word_count,
            "within_limit": word_count <= 120,
            "has_content": len(narrative.strip()) > 0,
            "five_ws": five_ws,
            "five_ws_complete": all_elements_present,
            "missing_elements": [k for k, v in five_ws.items() if not v]
        }

    def _check_who_element(self, narrative: str, case_data=None) -> bool:
        """Check if narrative contains WHO (customer identification)."""
        # Check if case_data customer name appears first (most reliable)
        if case_data and case_data.customer.name.lower() in narrative.lower():
            return True

        # Look for customer identification patterns (case-insensitive)
        who_patterns_insensitive = [
            r'customer\s+[A-Z][a-z]+',  # "Customer John" or "customer john"
            r'account\s+holder',
            r'subject\s+\w+',
            r'individual\s+\w+',
        ]
        for pattern in who_patterns_insensitive:
            if re.search(pattern, narrative, re.IGNORECASE):
                return True

        # Look for ID patterns (case-sensitive)
        who_patterns_sensitive = [
            r'CUST_\d+',  # Customer ID format
            r'[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+\()',  # Name followed by parenthesis like "John Doe ("
        ]
        for pattern in who_patterns_sensitive:
            if re.search(pattern, narrative):
                return True

        # Check for proper name patterns (two capitalized words not at sentence start)
        # Look for names like "John Doe" that appear mid-sentence
        name_pattern = r'(?<=[a-z]\s)[A-Z][a-z]+\s+[A-Z][a-z]+'
        if re.search(name_pattern, narrative):
            return True

        return False

    def _check_what_element(self, narrative_lower: str) -> bool:
        """Check if narrative contains WHAT (activity description)."""
        what_indicators = [
            'deposit', 'withdrawal', 'transfer', 'transaction',
            'structuring', 'money laundering', 'fraud', 'suspicious',
            'cash', 'wire', 'ach', 'payment', 'activity'
        ]
        return any(indicator in narrative_lower for indicator in what_indicators)

    def _check_when_element(self, narrative: str) -> bool:
        """Check if narrative contains WHEN (temporal details)."""
        # Look for date patterns or temporal words
        when_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY
            r'(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'(consecutive|daily|weekly|monthly)\s+(days?|weeks?|months?)',
            r'over\s+(a\s+)?(period|time|span)',
            r'between\s+\w+\s+and\s+\w+',
            r'from\s+\w+\s+to\s+\w+',
            r'\d+\s+(days?|weeks?|months?)',
        ]
        for pattern in when_patterns:
            if re.search(pattern, narrative, re.IGNORECASE):
                return True
        return False

    def _check_where_element(self, narrative_lower: str) -> bool:
        """Check if narrative contains WHERE (location/channel)."""
        where_indicators = [
            'branch', 'atm', 'online', 'location', 'teller',
            'via wire', 'via ach', 'via cash', 'via check',
            'at branch', 'at atm', 'at location',
            'through', 'channel', 'method',
            'domestic', 'international', 'offshore',
            'bank', 'institution', 'account'
        ]
        return any(indicator in narrative_lower for indicator in where_indicators)

    def _check_why_element(self, narrative_lower: str) -> bool:
        """Check if narrative contains WHY (reason for suspicion)."""
        why_indicators = [
            'suspicious', 'evade', 'avoid', 'circumvent',
            'threshold', 'ctr', 'reporting requirement',
            'structuring', 'pattern', 'indicative',
            'suggests', 'appears', 'consistent with',
            'violation', 'regulatory', 'compliance',
            'under $10,000', 'below threshold', 'just under'
        ]
        return any(indicator in narrative_lower for indicator in why_indicators)

    def _check_dollar_amounts(self, narrative: str) -> bool:
        """Check if narrative contains dollar amounts as required for SAR reporting."""
        # Look for dollar amount patterns
        dollar_patterns = [
            r'\$[\d,]+(?:\.\d{2})?',  # $1,234.56 or $1234
            r'\$\d+(?:,\d{3})*',  # $10,000 format
            r'(?:USD|dollars?)\s*[\d,]+',  # USD 1000 or dollars 1000
            r'(?:totaling|total(?:ed)?|amounting to|worth)\s*\$?[\d,]+',  # totaling $X
        ]
        for pattern in dollar_patterns:
            if re.search(pattern, narrative, re.IGNORECASE):
                return True
        return False

    def _validate_regulatory_citations(self, citations: List[str]) -> Dict[str, Any]:
        """Validate regulatory citations are non-empty and contain valid references.

        Args:
            citations: List of regulatory citation strings

        Returns:
            Dictionary with validation results including:
            - is_valid: Whether citations pass validation
            - has_citations: Whether any citations provided
            - valid_citations: List of recognized citations
            - unrecognized_citations: List of unrecognized citations
            - error_message: Description of validation failure (if any)
        """
        result = {
            "is_valid": False,
            "has_citations": False,
            "valid_citations": [],
            "unrecognized_citations": [],
            "error_message": None
        }

        # Check for empty or missing citations
        if not citations:
            result["error_message"] = "No regulatory citations provided"
            return result

        result["has_citations"] = True

        # Validate each citation
        for citation in citations:
            citation_normalized = citation.strip()
            is_recognized = False

            for valid_citation in VALID_REGULATORY_CITATIONS:
                if valid_citation.lower() in citation_normalized.lower():
                    is_recognized = True
                    result["valid_citations"].append(citation_normalized)
                    break

            if not is_recognized:
                result["unrecognized_citations"].append(citation_normalized)

        # Require at least one valid citation
        if result["valid_citations"]:
            result["is_valid"] = True
        else:
            result["error_message"] = "No recognized regulatory citations found"

        return result

    def _pre_finalization_validation(self, narrative: str, citations: List[str],
                                      case_data, model_completeness_check: bool) -> Dict[str, Any]:
        """Deterministic pre-finalization validation gate.

        This method performs comprehensive validation of the SAR narrative
        before it can be finalized/approved. It does NOT trust the model-supplied
        completeness_check flag.

        Required validations:
        1. Word count within 120 word limit
        2. All Five W's present (WHO, WHAT, WHEN, WHERE, WHY)
        3. Dollar amounts included in narrative
        4. Valid regulatory citations provided
        5. Narrative has substantive content

        Args:
            narrative: The generated SAR narrative
            citations: List of regulatory citations
            case_data: Original case data for context
            model_completeness_check: The model's self-reported completeness (not trusted)

        Returns:
            Dictionary with comprehensive validation results
        """
        validation_result = {
            "is_valid": False,
            "can_finalize": False,
            "word_count_valid": False,
            "five_ws_complete": False,
            "has_dollar_amounts": False,
            "citations_valid": False,
            "has_content": False,
            "model_completeness_check": model_completeness_check,
            "missing_elements": [],
            "failed_checks": [],
            "error_messages": []
        }

        # 1. Check word count
        word_count = len(narrative.split())
        validation_result["word_count"] = word_count
        validation_result["word_count_valid"] = word_count <= 120
        if not validation_result["word_count_valid"]:
            validation_result["failed_checks"].append("word_count")
            validation_result["error_messages"].append(
                f"Narrative exceeds 120 word limit ({word_count} words)"
            )

        # 2. Validate Five W's
        five_ws_result = self._validate_narrative_compliance(narrative, case_data)
        validation_result["five_ws"] = five_ws_result["five_ws"]
        validation_result["five_ws_complete"] = five_ws_result["five_ws_complete"]
        validation_result["missing_elements"] = five_ws_result["missing_elements"]

        if not validation_result["five_ws_complete"]:
            validation_result["failed_checks"].append("five_ws")
            validation_result["error_messages"].append(
                f"Missing required narrative elements: {', '.join(five_ws_result['missing_elements'])}"
            )

        # 3. Check for dollar amounts
        validation_result["has_dollar_amounts"] = self._check_dollar_amounts(narrative)
        if not validation_result["has_dollar_amounts"]:
            validation_result["failed_checks"].append("dollar_amounts")
            validation_result["error_messages"].append(
                "Narrative must include specific dollar amounts"
            )

        # 4. Validate regulatory citations
        citations_result = self._validate_regulatory_citations(citations)
        validation_result["citations_valid"] = citations_result["is_valid"]
        validation_result["citations_details"] = citations_result

        if not validation_result["citations_valid"]:
            validation_result["failed_checks"].append("citations")
            validation_result["error_messages"].append(
                citations_result["error_message"] or "Invalid regulatory citations"
            )

        # 5. Check for substantive content
        validation_result["has_content"] = len(narrative.strip()) >= 50
        if not validation_result["has_content"]:
            validation_result["failed_checks"].append("content")
            validation_result["error_messages"].append(
                "Narrative lacks substantive content (minimum 50 characters)"
            )

        # Determine overall validity
        validation_result["is_valid"] = all([
            validation_result["word_count_valid"],
            validation_result["five_ws_complete"],
            validation_result["has_dollar_amounts"],
            validation_result["citations_valid"],
            validation_result["has_content"]
        ])

        # Can only finalize if all checks pass
        validation_result["can_finalize"] = validation_result["is_valid"]

        # Log discrepancy if model said complete but validation failed
        if model_completeness_check and not validation_result["is_valid"]:
            validation_result["model_discrepancy"] = True
            validation_result["error_messages"].append(
                "Model reported completeness_check=true but validation failed"
            )

        return validation_result

    def _build_user_prompt(self, case_data, risk_analysis) -> str:
        """Build the full user prompt combining case data and risk analysis."""
        customer = case_data.customer

        # Extract location/channel information for WHERE element
        locations = self._extract_locations_from_transactions(case_data.transactions)
        location_summary = ", ".join(locations[:5])  # Limit to first 5 for brevity

        # Calculate transaction date range for WHEN element
        dates = [txn.transaction_date for txn in case_data.transactions]
        date_range = f"{min(dates)} to {max(dates)}" if dates else "N/A"

        # Calculate total amount for WHAT element
        total_amount = sum(txn.amount for txn in case_data.transactions)

        lines = [
            "Generate a SAR narrative for the following case:",
            f"\n--- Case: {case_data.case_id} ---",
            f"\n--- WHO (Customer) ---",
            f"Customer ID: {customer.customer_id}",
            f"Name: {customer.name}",
            f"Risk Rating: {customer.risk_rating}",
            f"\n--- WHAT (Activity Summary) ---",
            f"Classification: {risk_analysis.classification}",
            f"Total Amount: ${total_amount:,.2f}",
            f"Number of Transactions: {len(case_data.transactions)}",
            f"\n--- WHEN (Time Period) ---",
            f"Date Range: {date_range}",
            f"\n--- WHERE (Locations/Channels) ---",
            f"Transaction Locations/Methods: {location_summary}",
            f"\n--- WHY (Risk Analysis) ---",
            self._format_risk_analysis_for_prompt(risk_analysis),
            f"\n--- Transaction Details ---",
            self._format_transactions_for_compliance(case_data.transactions),
            f"\n**IMPORTANT**: The narrative MUST:",
            f"1. Be 120 words or fewer",
            f"2. Include ALL Five W's: WHO, WHAT, WHEN, WHERE, WHY",
            f"3. Specifically mention transaction locations/channels for WHERE element"
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
        "five_ws": {
            "who": "Customer identification - name, ID, account numbers",
            "what": "Suspicious activity description - type, amounts, transaction types",
            "when": "Temporal details - dates, time periods, patterns",
            "where": "Location/channel - branch, ATM, online, geographic info, methods",
            "why": "Reason for suspicion - regulatory violations, pattern analysis"
        },
        "required_elements": [
            "WHO: Customer identification",
            "WHAT: Suspicious activity description",
            "WHEN: Transaction dates and time periods",
            "WHERE: Transaction locations and channels",
            "WHY: Explanation of suspicious nature"
        ],
        "terminology": [
            "Suspicious activity",
            "Regulatory threshold",
            "Financial institution",
            "Money laundering",
            "Bank Secrecy Act",
            "Structuring",
            "Currency Transaction Report"
        ],
        "citations": [
            "31 CFR 1020.320 (BSA)",
            "31 USC 5324 (Structuring)",
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
