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
    "North Korea Sanctions Regulations",
    "Iran Sanctions",
    # Other
    "FTC Red Flags Rule",
    "BSA",
    "AML",
    "18 USC 1956",
    "18 USC 1957",
]

# ===== TYPOLOGY-SPECIFIC CITATION MAPPING =====
# Maps classification types to their REQUIRED and PROHIBITED citations
# This ensures citations are relevant to the actual suspicious activity type

TYPOLOGY_CITATION_MAPPING = {
    "Structuring": {
        "required_any": [
            # Must cite at least one structuring-specific regulation
            "31 USC 5324",  # Anti-structuring statute
            "31 CFR 1010.314",  # Structuring regulations
        ],
        "recommended": [
            "31 CFR 1020.320",  # SAR filing requirements (always appropriate)
            "FinCEN SAR Instructions",
            "31 USC 5313",  # CTR requirements (structuring evades this)
        ],
        "prohibited": [
            # Don't cite these for structuring cases
            "OFAC SDN List",
            "Executive Order 13599",
            "North Korea Sanctions Regulations",
            "Iran Sanctions",
        ],
        "description": "Structuring involves breaking up transactions to avoid CTR reporting thresholds"
    },
    "Money_Laundering": {
        "required_any": [
            # Must cite at least one money laundering regulation
            "31 USC 5318",  # AML program requirements
            "18 USC 1956",  # Money laundering statute
            "18 USC 1957",  # Monetary transactions with criminally derived property
            "31 CFR 1020.320",  # SAR filing (central to AML)
        ],
        "recommended": [
            "FinCEN SAR Instructions",
            "FinCEN Advisory",
            "BSA",
            "AML",
        ],
        "prohibited": [
            # 31 USC 5324 is structuring-specific - don't use for general ML
            # unless the ML case involves structuring as a component
        ],
        "conditionally_prohibited": [
            # Only use 31 USC 5324 if narrative mentions structuring/threshold avoidance
            ("31 USC 5324", ["structur", "threshold", "under $10,000", "ctr", "currency transaction report"]),
        ],
        "description": "Money laundering involves placement, layering, or integration of illicit funds"
    },
    "Sanctions": {
        "required_any": [
            # Must cite at least one sanctions-related authority
            "OFAC SDN List",
            "Executive Order 13599",
            "North Korea Sanctions Regulations",
            "Iran Sanctions",
        ],
        "recommended": [
            "31 CFR 1020.320",  # SAR filing
            "FinCEN SAR Instructions",
        ],
        "prohibited": [
            # Don't cite structuring statute for sanctions cases
            "31 USC 5324",
            "31 CFR 1010.314",
        ],
        "description": "Sanctions violations involve transactions with prohibited parties/jurisdictions"
    },
    "Fraud": {
        "required_any": [
            # Must cite at least one fraud-related authority
            "FTC Red Flags Rule",
            "31 CFR 1020.320",  # SAR filing
            "FinCEN SAR Instructions",
        ],
        "recommended": [
            "BSA",
            "AML",
        ],
        "prohibited": [
            # Don't cite sanctions regulations for fraud cases
            "OFAC SDN List",
            "Executive Order 13599",
        ],
        "description": "Fraud involves deceptive practices, identity theft, or account takeover"
    },
    "Other": {
        "required_any": [
            # Generic SAR filing authority always required
            "31 CFR 1020.320",
            "FinCEN SAR Instructions",
            "BSA",
        ],
        "recommended": [
            "FinCEN Advisory",
            "AML",
        ],
        "prohibited": [],  # No specific prohibitions for "Other"
        "description": "Suspicious activity not fitting standard typologies"
    }
}


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
5. **CRITICAL: Analyze the classification and narrative content to select ONLY relevant regulatory citations.**

**ACTION Phase:**
1. Draft a concise narrative of no more than 120 words that summarizes the suspicious activity.
2. Include specific dollar amounts, dates, transaction locations, and channels.
3. Reference the suspicious activity pattern identified by the Risk Analyst.
4. Use appropriate regulatory language and terminology (e.g., "structuring," "currency transaction reporting threshold," "suspicious activity").
5. **Select citations that MATCH the specific facts described in your narrative - DO NOT use boilerplate citations.**

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

**CRITICAL - Typology-Specific Citation Requirements:**

⚠️ VALIDATION FAILURE WARNING: Citing regulations that don't match your narrative will cause validation failure and require regeneration.

**Structuring cases** - Transactions broken into smaller amounts to evade $10,000 CTR threshold:
✅ MUST cite: 31 USC 5324 (anti-structuring statute) OR 31 CFR 1010.314 (structuring regulations)
✅ May cite: 31 CFR 1020.320 (SAR filing), 31 USC 5313 (CTR requirements), FinCEN SAR Instructions
📝 Example: "Four cash deposits of $9,900 each over three days at different branches to avoid CTR reporting."

**Money_Laundering cases** - Layering, integration, or obscuring origin of funds:
✅ MUST cite: 31 USC 5318 (AML program) OR 18 USC 1956 (money laundering) OR 18 USC 1957 (monetary transactions)
✅ May cite: 31 CFR 1020.320 (SAR filing), FinCEN Advisory, FinCEN Guidance, BSA, AML
❌ DO NOT cite: 31 USC 5324 (structuring statute) - ONLY use if narrative explicitly describes structuring/threshold evasion
📝 Example: "Large incoming wire transfer followed by rapid outbound transfers to multiple accounts - indicative of layering."
📝 Example where 31 USC 5324 IS appropriate: "Wire transfers followed by multiple cash withdrawals under $10,000 to evade CTR reporting."

**Sanctions cases** - Transactions involving prohibited parties/jurisdictions:
✅ MUST cite: OFAC SDN List OR Executive Order 13599 OR North Korea Sanctions Regulations OR Iran Sanctions
✅ May cite: 31 CFR 1020.320 (SAR filing), FinCEN SAR Instructions
❌ DO NOT cite: 31 USC 5324 (structuring), 31 CFR 1010.314 (structuring)
📝 Example: "Wire transfer to entity matching OFAC SDN List entry."

**Fraud cases** - Identity theft, account takeover, deceptive practices:
✅ MUST cite: FTC Red Flags Rule OR 31 CFR 1020.320 (SAR filing) OR FinCEN SAR Instructions
✅ May cite: BSA, AML
❌ DO NOT cite: OFAC SDN List, Executive Order 13599, 31 USC 5324 (structuring)
📝 Example: "Account takeover with fraudulent wire transfers to overseas accounts."

**Other cases** - Suspicious activity not fitting standard typologies:
✅ MUST cite: 31 CFR 1020.320 (SAR filing) OR FinCEN SAR Instructions OR BSA
✅ May cite: FinCEN Advisory, AML
📝 Example: "Unusual transaction pattern not consistent with known typologies."

**Citation Selection Checklist (Review Before Finalizing):**
1. ✅ Does your narrative describe structuring? If NO, do not cite 31 USC 5324 or 31 CFR 1010.314
2. ✅ Does your narrative describe layering/wire transfers/fund movement? If YES, cite AML statutes (18 USC 1956/1957, 31 USC 5318)
3. ✅ Does your narrative mention OFAC/sanctions/prohibited parties? If NO, do not cite OFAC authorities
4. ✅ Does your narrative describe fraud/identity theft? If NO, do not cite FTC Red Flags Rule
5. ✅ Always include general SAR filing authority: 31 CFR 1020.320 or FinCEN SAR Instructions

**Additional Requirements:**
- Maximum 120 words — this is a strict limit
- Must use proper BSA/AML compliance terminology
- Must reference applicable FinCEN SAR filing requirements
- Citations must match the facts in your narrative - READ YOUR NARRATIVE and verify citation relevance

**Output Format:**
You MUST respond with ONLY a JSON object in this exact format:
{
    "narrative": "The SAR narrative text (max 120 words) - MUST include all Five W's",
    "narrative_reasoning": "Explanation of narrative construction approach (max 500 chars)",
    "regulatory_citations": ["citation relevant to classification type", "other relevant citations"],
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

                # Make API call with error handling
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.2 + (attempt * 0.1),  # Slightly increase temperature on retries
                        max_tokens=800
                    )

                    if not response.choices or not response.choices[0].message.content:
                        raise ValueError("Empty response from API")

                    response_content = response.choices[0].message.content
                except openai.RateLimitError as e:
                    error_msg = f"Rate limit exceeded: {e}"
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={"customer_id": case_data.customer.customer_id, "attempt": attempt + 1},
                        output_data={},
                        reasoning="API rate limit exceeded",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        success=False,
                        error_message=error_msg
                    )
                    raise ValueError(error_msg)
                except openai.APITimeoutError as e:
                    error_msg = f"API timeout: {e}"
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={"customer_id": case_data.customer.customer_id, "attempt": attempt + 1},
                        output_data={},
                        reasoning="API timeout",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        success=False,
                        error_message=error_msg
                    )
                    raise ValueError(error_msg)
                except openai.APIConnectionError as e:
                    error_msg = f"API connection error: {e}"
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={"customer_id": case_data.customer.customer_id, "attempt": attempt + 1},
                        output_data={},
                        reasoning="API connection failed",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        success=False,
                        error_message=error_msg
                    )
                    raise ValueError(error_msg)
                except openai.BadRequestError as e:
                    error_msg = f"Bad request: {e}"
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={"customer_id": case_data.customer.customer_id, "attempt": attempt + 1},
                        output_data={},
                        reasoning="API bad request (e.g., insufficient budget)",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        success=False,
                        error_message=error_msg
                    )
                    raise ValueError(error_msg)
                except openai.AuthenticationError as e:
                    error_msg = f"Authentication failed: {e}"
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={"customer_id": case_data.customer.customer_id, "attempt": attempt + 1},
                        output_data={},
                        reasoning="API authentication failed",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        success=False,
                        error_message=error_msg
                    )
                    raise ValueError(error_msg)
                except openai.APIError as e:
                    error_msg = f"OpenAI API error: {e}"
                    self.logger.log_agent_action(
                        agent_type="ComplianceOfficer",
                        action="generate_narrative",
                        case_id=case_data.case_id,
                        input_data={"customer_id": case_data.customer.customer_id, "attempt": attempt + 1},
                        output_data={},
                        reasoning="OpenAI API error",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                        success=False,
                        error_message=error_msg
                    )
                    raise ValueError(error_msg)

                json_str = self._extract_json_from_response(response_content)
                parsed = json.loads(json_str)

                narrative = parsed.get("narrative", "")
                citations = parsed.get("regulatory_citations", [])
                model_completeness = parsed.get("completeness_check", False)

                # Run pre-finalization validation gate (with typology-specific citation validation)
                validation_result = self._pre_finalization_validation(
                    narrative=narrative,
                    citations=citations,
                    case_data=case_data,
                    model_completeness_check=model_completeness,
                    classification=risk_analysis.classification
                )

                if validation_result["can_finalize"]:
                    # Validation passed - create and return result with validation status
                    result = ComplianceOfficerOutput(
                        **parsed,
                        validation_passed=True,
                        validation_details=validation_result
                    )

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

                # Log validation failure with detailed citation information
                citations_details = validation_result.get("citations_details", {})
                log_output = {
                    "validation_result": validation_result,
                    "narrative_preview": narrative[:100] + "..." if len(narrative) > 100 else narrative,
                    "citations_provided": citations,
                    "classification": risk_analysis.classification
                }

                # Add citation-specific debugging info
                if citations_details:
                    log_output["citation_debug"] = {
                        "valid_citations": citations_details.get("valid_citations", []),
                        "relevant_citations": citations_details.get("relevant_citations", []),
                        "prohibited_citations_used": citations_details.get("prohibited_citations_used", []),
                        "unrecognized_citations": citations_details.get("unrecognized_citations", [])
                    }

                self.logger.log_agent_action(
                    agent_type="ComplianceOfficer",
                    action="validation_failed",
                    case_id=case_data.case_id,
                    input_data={
                        "customer_id": case_data.customer.customer_id,
                        "attempt": attempt + 1,
                        "max_attempts": max_regeneration_attempts + 1,
                        "classification": risk_analysis.classification
                    },
                    output_data=log_output,
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
                # Check if this is a word count violation - raise ValueError specifically
                if "exceeds 120 word limit" in error_msg or "word limit" in error_msg.lower():
                    raise ValueError(f"Narrative exceeds 120 word limit")
                raise ValueError(f"Failed to parse Compliance Officer JSON output: {e}")

        # All attempts exhausted - validation still failing
        if strict_validation and last_validation_result:
            # Check if word count is the primary issue - raise ValueError for word count violations
            if "word_count" in last_validation_result.get('failed_checks', []):
                word_count = last_validation_result.get('word_count', 'unknown')
                raise ValueError(f"Narrative exceeds 120 word limit ({word_count} words)")
            
            error_message = (
                f"Narrative validation failed after {max_regeneration_attempts + 1} attempts. "
                f"Failed checks: {', '.join(last_validation_result['failed_checks'])}. "
                f"Missing elements: {', '.join(last_validation_result['missing_elements'])}."
            )
            raise NarrativeValidationError(error_message, last_validation_result)

        # If not strict, return with validation warnings (not recommended for production)
        # Mark validation as failed so SAR creation can block approval
        return ComplianceOfficerOutput(
            **parsed,
            validation_passed=False,
            validation_details=last_validation_result or {}
        )

    def _build_regeneration_prompt(self, validation_result: Dict[str, Any]) -> str:
        """Build a prompt for regeneration based on validation failures."""
        issues = []

        if "word_count" in validation_result.get("failed_checks", []):
            issues.append(f"- Word count ({validation_result.get('word_count', 'N/A')}) exceeds 120 word limit")

        if validation_result.get("missing_elements"):
            issues.append(f"- Missing required elements: {', '.join(validation_result['missing_elements'])}")

        if "dollar_amounts" in validation_result.get("failed_checks", []):
            issues.append("- Must include specific dollar amounts (e.g., $9,900, $29,500)")

        # Enhanced citation failure feedback with specific details
        if "citations" in validation_result.get("failed_checks", []) or "citation_relevance" in validation_result.get("failed_checks", []):
            citations_details = validation_result.get("citations_details", {})

            # Check for prohibited citations (most critical issue)
            if citations_details.get("prohibited_citations_used"):
                issues.append("\n⚠️ CRITICAL CITATION ERRORS:")
                for prohibited in citations_details["prohibited_citations_used"]:
                    issues.append(f"  • {prohibited['reason']}")
                issues.append("\n  ACTION REQUIRED: Remove the inappropriate citations and select citations that match your narrative content.")

            # Check for missing required citations
            elif not citations_details.get("relevant_citations"):
                issues.append(f"- Citations are not relevant to the activity type. You must cite at least one regulation specific to the classification.")

            # Generic citation error
            else:
                issues.append("- Invalid or irrelevant regulatory citations. Review the typology-specific citation requirements.")

        prompt = (
            "The previous narrative FAILED VALIDATION. Please regenerate addressing these issues:\n"
            + "\n".join(issues)
            + "\n\n**IMPORTANT**: Before finalizing, verify that:\n"
            + "1. Your citations match the facts described in your narrative\n"
            + "2. You are NOT citing 31 USC 5324 unless your narrative explicitly describes structuring (transactions under $10,000 to evade CTR)\n"
            + "3. You have at least one citation specific to the classification type\n\n"
            + "Generate a corrected narrative with appropriate citations."
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

    def _get_citation_guidance(self, classification: str) -> str:
        """Get classification-specific citation guidance for the user prompt."""
        guidance_map = {
            "Structuring": """
**CITATION REQUIREMENTS for Structuring**:
✅ MUST cite: 31 USC 5324 (anti-structuring) OR 31 CFR 1010.314
✅ May cite: 31 CFR 1020.320, 31 USC 5313, FinCEN SAR Instructions
📝 Your narrative should describe transactions under $10,000 threshold to evade CTR reporting.""",

            "Money_Laundering": """
**CITATION REQUIREMENTS for Money_Laundering**:
✅ MUST cite: 31 USC 5318 (AML) OR 18 USC 1956 OR 18 USC 1957
✅ May cite: 31 CFR 1020.320, FinCEN Advisory, BSA, AML
❌ DO NOT cite: 31 USC 5324 (structuring) - ONLY use if narrative mentions structuring/threshold evasion
📝 Your narrative should describe layering, integration, or fund movement patterns.""",

            "Sanctions": """
**CITATION REQUIREMENTS for Sanctions**:
✅ MUST cite: OFAC SDN List OR Executive Order 13599 OR sanctions regulations
✅ May cite: 31 CFR 1020.320, FinCEN SAR Instructions
❌ DO NOT cite: 31 USC 5324 (structuring)
📝 Your narrative should describe transactions with prohibited parties/jurisdictions.""",

            "Fraud": """
**CITATION REQUIREMENTS for Fraud**:
✅ MUST cite: FTC Red Flags Rule OR 31 CFR 1020.320 OR FinCEN SAR Instructions
✅ May cite: BSA, AML
❌ DO NOT cite: OFAC authorities, 31 USC 5324 (structuring)
📝 Your narrative should describe identity theft, account takeover, or deceptive practices.""",

            "Other": """
**CITATION REQUIREMENTS for Other**:
✅ MUST cite: 31 CFR 1020.320 OR FinCEN SAR Instructions OR BSA
✅ May cite: FinCEN Advisory, AML
📝 Your narrative should describe suspicious activity not fitting standard typologies."""
        }

        return guidance_map.get(classification, guidance_map["Other"])

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

    def _validate_regulatory_citations(self, citations: List[str],
                                         classification: str = None,
                                         narrative: str = None) -> Dict[str, Any]:
        """Validate regulatory citations are relevant to the specific suspicious activity type.

        This method validates that:
        1. Citations are recognized (in the valid allowlist)
        2. At least one citation is relevant to the classification type
        3. No prohibited citations are used for the classification type
        4. Conditional prohibitions are enforced (e.g., 31 USC 5324 for ML only if structuring mentioned)

        Args:
            citations: List of regulatory citation strings
            classification: The suspicious activity classification (Structuring, Money_Laundering, etc.)
            narrative: The SAR narrative text (for conditional prohibition checks)

        Returns:
            Dictionary with validation results including:
            - is_valid: Whether citations pass validation
            - has_citations: Whether any citations provided
            - valid_citations: List of recognized citations
            - relevant_citations: List of citations relevant to classification
            - unrecognized_citations: List of unrecognized citations
            - prohibited_citations_used: List of citations that shouldn't be used for this type
            - relevance_valid: Whether citations are relevant to classification
            - error_message: Description of validation failure (if any)
        """
        result = {
            "is_valid": False,
            "has_citations": False,
            "valid_citations": [],
            "relevant_citations": [],
            "unrecognized_citations": [],
            "prohibited_citations_used": [],
            "relevance_valid": False,
            "error_message": None
        }

        # Check for empty or missing citations
        if not citations:
            result["error_message"] = "No regulatory citations provided"
            return result

        result["has_citations"] = True

        # Get typology mapping for this classification
        typology_config = TYPOLOGY_CITATION_MAPPING.get(classification, TYPOLOGY_CITATION_MAPPING.get("Other"))
        required_any = typology_config.get("required_any", [])
        prohibited = typology_config.get("prohibited", [])
        conditionally_prohibited = typology_config.get("conditionally_prohibited", [])

        # Validate each citation
        for citation in citations:
            citation_normalized = citation.strip()
            citation_lower = citation_normalized.lower()
            is_recognized = False
            matched_citation = None

            # Check if citation is recognized
            for valid_citation in VALID_REGULATORY_CITATIONS:
                if valid_citation.lower() in citation_lower:
                    is_recognized = True
                    matched_citation = valid_citation
                    result["valid_citations"].append(citation_normalized)
                    break

            if not is_recognized:
                result["unrecognized_citations"].append(citation_normalized)
                continue

            # Check if citation is prohibited for this classification
            is_prohibited = False
            for prohibited_citation in prohibited:
                if prohibited_citation.lower() in citation_lower:
                    is_prohibited = True
                    result["prohibited_citations_used"].append({
                        "citation": citation_normalized,
                        "reason": f"'{prohibited_citation}' is not relevant to {classification} cases"
                    })
                    break

            # Check conditional prohibitions (e.g., 31 USC 5324 for ML)
            if not is_prohibited and narrative:
                narrative_lower = narrative.lower()
                for cond_citation, required_keywords in conditionally_prohibited:
                    if cond_citation.lower() in citation_lower:
                        # Check if any required keyword is in the narrative
                        keyword_found = any(kw.lower() in narrative_lower for kw in required_keywords)
                        if not keyword_found:
                            is_prohibited = True
                            result["prohibited_citations_used"].append({
                                "citation": citation_normalized,
                                "reason": f"'{cond_citation}' should only be used when narrative mentions: {', '.join(required_keywords)}"
                            })
                        break

            # Check if citation is relevant (matches required citations for this type)
            if not is_prohibited:
                for required_citation in required_any:
                    if required_citation.lower() in citation_lower:
                        result["relevant_citations"].append(citation_normalized)
                        break

        # Determine overall validity
        has_required = len(result["relevant_citations"]) > 0
        no_prohibited = len(result["prohibited_citations_used"]) == 0
        has_valid = len(result["valid_citations"]) > 0

        result["relevance_valid"] = has_required and no_prohibited

        if not has_valid:
            result["error_message"] = "No recognized regulatory citations found"
        elif not has_required:
            result["error_message"] = (
                f"Citations missing relevance to {classification} typology. "
                f"Required: at least one of {required_any}"
            )
        elif not no_prohibited:
            prohibited_details = "; ".join([p["reason"] for p in result["prohibited_citations_used"]])
            result["error_message"] = f"Inappropriate citations for {classification}: {prohibited_details}"
        else:
            result["is_valid"] = True

        return result

    def _pre_finalization_validation(self, narrative: str, citations: List[str],
                                      case_data, model_completeness_check: bool,
                                      classification: str = None) -> Dict[str, Any]:
        """Deterministic pre-finalization validation gate.

        This method performs comprehensive validation of the SAR narrative
        before it can be finalized/approved. It does NOT trust the model-supplied
        completeness_check flag.

        Required validations:
        1. Word count within 120 word limit
        2. All Five W's present (WHO, WHAT, WHEN, WHERE, WHY)
        3. Dollar amounts included in narrative
        4. Valid AND RELEVANT regulatory citations provided (typology-specific)
        5. Narrative has substantive content

        Args:
            narrative: The generated SAR narrative
            citations: List of regulatory citations
            case_data: Original case data for context
            model_completeness_check: The model's self-reported completeness (not trusted)
            classification: The suspicious activity classification for citation relevance check

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

        # 4. Validate regulatory citations (including relevance to classification)
        citations_result = self._validate_regulatory_citations(
            citations=citations,
            classification=classification,
            narrative=narrative
        )
        validation_result["citations_valid"] = citations_result["is_valid"]
        validation_result["citations_details"] = citations_result

        if not validation_result["citations_valid"]:
            validation_result["failed_checks"].append("citations")
            validation_result["error_messages"].append(
                citations_result["error_message"] or "Invalid or irrelevant regulatory citations"
            )

        # Check for prohibited citations (separate check for clarity)
        if citations_result.get("prohibited_citations_used"):
            if "citation_relevance" not in validation_result["failed_checks"]:
                validation_result["failed_checks"].append("citation_relevance")
            for prohibited in citations_result["prohibited_citations_used"]:
                validation_result["error_messages"].append(
                    f"Inappropriate citation: {prohibited['reason']}"
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

        # Get citation guidance for this classification
        citation_guidance = self._get_citation_guidance(risk_analysis.classification)

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
            f"\n**IMPORTANT REQUIREMENTS**:",
            f"1. Be 120 words or fewer",
            f"2. Include ALL Five W's: WHO, WHAT, WHEN, WHERE, WHY",
            f"3. Specifically mention transaction locations/channels for WHERE element",
            f"\n{citation_guidance}"
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
