"""
SAR Validator and Repair Tool

Validates all filed SARs against strict Five W's and citation requirements.
Repairs SARs that have issues and regenerates corrected versions.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime


class SARValidator:
    """Validates SARs against strict Five W's and citation requirements."""

    def __init__(self):
        self.violations = []

    def validate_sar(self, sar_path: Path) -> Tuple[bool, List[str]]:
        """Validate a single SAR file.

        Args:
            sar_path: Path to SAR JSON file

        Returns:
            Tuple of (is_valid, list of violations)
        """
        with open(sar_path, 'r') as f:
            sar = json.load(f)

        violations = []

        # Validate Five W's
        narrative = sar['suspicious_activity']['narrative']
        classification = sar['suspicious_activity']['classification']

        # Check WHO
        if not self._check_who(narrative, sar):
            violations.append("Missing WHO: Customer name and ID not clearly stated")

        # Check WHAT
        if not self._check_what(narrative):
            violations.append("Missing WHAT: Transaction types and amounts not specific enough")

        # Check WHEN
        if not self._check_when(narrative):
            violations.append("Missing WHEN: Date range or time period not specified")

        # Check WHERE - STRICT requirement
        if not self._check_where(narrative):
            violations.append("Missing WHERE: No explicit channel (branch/ATM/online/wire/ACH) or location mentioned")

        # Check WHY
        if not self._check_why(narrative, classification):
            violations.append("Missing WHY: Suspicion basis not clearly explained")

        # Validate citations against typology rules
        citations = sar['regulatory_compliance']['citations']
        citation_violations = self._validate_citations(narrative, classification, citations)
        violations.extend(citation_violations)

        is_valid = len(violations) == 0
        return is_valid, violations

    def _check_who(self, narrative: str, sar: Dict) -> bool:
        """Check WHO element: Customer identification."""
        customer_name = sar['subject_information']['customer_name']
        customer_id = sar['subject_information']['customer_id']

        # Must mention both name and ID
        has_name = customer_name in narrative
        has_id = customer_id in narrative

        return has_name and has_id

    def _check_what(self, narrative: str) -> bool:
        """Check WHAT element: Transaction types and amounts."""
        # Must mention transaction type (cash, wire, ACH, transfer, withdrawal, deposit)
        transaction_types = [
            'cash', 'wire', 'ach', 'transfer', 'withdrawal', 'deposit',
            'check', 'debit', 'credit'
        ]
        has_transaction_type = any(t in narrative.lower() for t in transaction_types)

        # Must mention dollar amounts (look for $ symbol)
        has_amounts = '$' in narrative

        return has_transaction_type and has_amounts

    def _check_when(self, narrative: str) -> bool:
        """Check WHEN element: Time period/dates."""
        # Must mention dates or time period
        # Look for: "between", "from", dates like "2025-", month names, or "during"
        time_patterns = [
            r'\bfrom\b.*\bto\b',  # "from X to Y"
            r'\bbetween\b.*\band\b',  # "between X and Y"
            r'\d{4}-\d{2}-\d{2}',  # Date format YYYY-MM-DD
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)',
            r'\bduring\b',
            r'\bthroughout\b'
        ]

        for pattern in time_patterns:
            if re.search(pattern, narrative, re.IGNORECASE):
                return True

        return False

    def _check_where(self, narrative: str) -> bool:
        """Check WHERE element: STRICT requirement for channel/location.

        MUST explicitly mention at least ONE of:
        - Channel: branch, ATM, online, wire, ACH, mobile, in-person
        - Location: branch name/number, city, ATM location, "via X"
        - Geographic: specific country, region, or jurisdiction
        """
        where_indicators = [
            # Channels
            r'\bbranch\b', r'\batm\b', r'\bonline\b', r'\bwire\b', r'\bach\b',
            r'\bmobile\b', r'\bin-person\b', r'\bvia\b', r'\bthrough\b',
            r'\bover the counter\b', r'\bot', r'\binternational\b',

            # Transaction methods that indicate channel
            r'\bwire transfer', r'\bacr transfer\b', r'\bonline banking\b',
            r'\bmobile banking\b', r'\btelegraphic transfer\b',

            # Location indicators
            r'\bcity\b', r'\bstate\b', r'\bjurisdiction\b', r'\bcountry\b',
            r'\boffice\b', r'\blocation\b',

            # Specific geographic mentions
            r'\b(?:Iran|North Korea|Syria|Cuba|Russia)\b',  # Sanctioned countries
            r'\boffshore\b', r'\boverseas\b', r'\bdomestic\b', r'\bforeign\b'
        ]

        for pattern in where_indicators:
            if re.search(pattern, narrative, re.IGNORECASE):
                return True

        return False

    def _check_why(self, narrative: str, classification: str) -> bool:
        """Check WHY element: Reason for suspicion."""
        # Must mention why it's suspicious
        why_indicators = [
            'suspicious', 'unusual', 'inconsistent', 'evasion', 'avoid',
            'threshold', 'pattern', 'layering', 'structuring', 'sanctions',
            'fraud', 'money laundering', 'violat', 'prohibited',
            'disproportionate', 'suggest', 'indicative', 'concern'
        ]

        has_why = any(ind in narrative.lower() for ind in why_indicators)

        # Classification should be mentioned or implied
        classification_lower = classification.lower().replace('_', ' ')
        has_classification_context = classification_lower in narrative.lower()

        return has_why and has_classification_context

    def _validate_citations(self, narrative: str, classification: str,
                           citations: List[str]) -> List[str]:
        """Validate citations against typology-specific rules.

        Returns:
            List of citation violation messages
        """
        violations = []
        narrative_lower = narrative.lower()

        # Check for 31 USC 5324 (structuring statute) - most common violation
        if '31 USC 5324' in citations or '31 USC 5324' in str(citations):
            # 31 USC 5324 should ONLY be cited for Structuring cases
            if classification != 'Structuring':
                violations.append(
                    f"CRITICAL: 31 USC 5324 cited in {classification} case - "
                    f"this statute is ONLY for Structuring cases"
                )
            else:
                # Even for Structuring, narrative must describe threshold evasion
                structuring_keywords = ['threshold', '$10,000', '10000', 'ctr', 'evade', 'avoid reporting']
                if not any(kw in narrative_lower for kw in structuring_keywords):
                    violations.append(
                        "31 USC 5324 cited but narrative doesn't explicitly describe "
                        "CTR threshold evasion or structuring pattern"
                    )

        # Sanctions-specific validation
        if classification == 'Sanctions':
            # Must cite OFAC authorities
            ofac_citations = ['OFAC', 'Executive Order', 'SDN', 'Sanctions Regulations']
            has_ofac_citation = any(cite in str(citations) for cite in ofac_citations)

            if not has_ofac_citation:
                violations.append(
                    "Sanctions case must cite OFAC authorities (OFAC SDN List, "
                    "Executive Orders, or Sanctions Regulations)"
                )

            # Should NOT cite structuring statutes
            prohibited_for_sanctions = ['31 USC 5324', '31 CFR 1010.314']
            for prohibited in prohibited_for_sanctions:
                if prohibited in str(citations):
                    violations.append(
                        f"Sanctions case should NOT cite {prohibited} (structuring statute)"
                    )

        # Money_Laundering-specific validation
        if classification == 'Money_Laundering':
            # Should cite AML statutes
            aml_citations = ['18 USC 1956', '18 USC 1957', '31 USC 5318']
            has_aml_citation = any(cite in str(citations) for cite in aml_citations)

            # If 31 USC 5324 is cited, narrative must describe structuring
            if '31 USC 5324' in str(citations):
                structuring_described = any(kw in narrative_lower for kw in
                                          ['threshold', '$10,000', 'under $10', 'evade ctr'])
                if not structuring_described:
                    violations.append(
                        "31 USC 5324 cited in Money_Laundering case but narrative doesn't "
                        "describe structuring/threshold evasion - should cite AML statutes instead"
                    )

        # Fraud-specific validation
        if classification == 'Fraud':
            prohibited_for_fraud = ['31 USC 5324', 'OFAC']
            for prohibited in prohibited_for_fraud:
                if prohibited in str(citations):
                    violations.append(
                        f"Fraud case should NOT cite {prohibited}"
                    )

        return violations


class SARRepairer:
    """Repairs SARs with violations."""

    def repair_citations(self, sar: Dict) -> Dict:
        """Repair citations to match classification.

        Args:
            sar: SAR dictionary

        Returns:
            Updated SAR with corrected citations
        """
        classification = sar['suspicious_activity']['classification']
        narrative = sar['suspicious_activity']['narrative']

        # Generate correct citations based on classification
        if classification == 'Structuring':
            new_citations = ['31 CFR 1020.320', '31 USC 5324', 'FinCEN SAR Instructions']

        elif classification == 'Sanctions':
            new_citations = ['31 CFR 1020.320', 'OFAC SDN List', 'FinCEN SAR Instructions']

        elif classification == 'Money_Laundering':
            # Check if narrative describes structuring
            if any(kw in narrative.lower() for kw in ['threshold', 'under $10,000', 'evade ctr']):
                # Include both AML and structuring citations
                new_citations = ['31 CFR 1020.320', '31 USC 5318', '31 USC 5324']
            else:
                # Pure money laundering - use AML statutes only
                new_citations = ['31 CFR 1020.320', '31 USC 5318', '18 USC 1956']

        elif classification == 'Fraud':
            new_citations = ['31 CFR 1020.320', 'FTC Red Flags Rule', 'FinCEN SAR Instructions']

        else:  # Other
            new_citations = ['31 CFR 1020.320', 'FinCEN SAR Instructions', 'BSA']

        sar['regulatory_compliance']['citations'] = new_citations
        return sar

    def enhance_where_element(self, sar: Dict) -> Dict:
        """Enhance narrative to include WHERE element if missing.

        Args:
            sar: SAR dictionary

        Returns:
            Updated SAR with enhanced narrative
        """
        narrative = sar['suspicious_activity']['narrative']
        validator = SARValidator()

        # If WHERE is already present, no need to enhance
        if validator._check_where(narrative):
            return sar

        # Determine appropriate channel based on transaction data or classification
        classification = sar['suspicious_activity']['classification']

        # Infer channel from narrative content
        if 'wire' in narrative.lower():
            channel = 'via wire transfers'
        elif 'cash' in narrative.lower():
            channel = 'at multiple branch locations'
        elif 'atm' in narrative.lower():
            channel = 'via ATM'
        elif 'online' in narrative.lower():
            channel = 'through online banking'
        elif 'transfer' in narrative.lower():
            channel = 'through electronic transfers'
        elif classification == 'Sanctions':
            channel = 'via international wire transfers'
        else:
            channel = 'through various banking channels'

        # Insert WHERE element into narrative
        # Find a good insertion point (after describing the transactions)
        sentences = narrative.split('. ')

        # Usually insert after first or second sentence
        if len(sentences) >= 2:
            # Insert channel info after describing the transactions
            enhanced = f"{sentences[0]}. {sentences[1]} {channel}. {'. '.join(sentences[2:])}"
        else:
            # Append to end
            enhanced = f"{narrative.rstrip('.')} {channel}."

        # Update narrative and word count
        sar['suspicious_activity']['narrative'] = enhanced
        sar['suspicious_activity']['narrative_word_count'] = len(enhanced.split())

        return sar


def validate_all_sars(sars_dir: Path) -> Dict[str, Any]:
    """Validate all SARs in directory.

    Args:
        sars_dir: Directory containing SAR JSON files

    Returns:
        Validation report dictionary
    """
    validator = SARValidator()
    results = {
        'total_sars': 0,
        'valid_sars': 0,
        'invalid_sars': 0,
        'violations_by_sar': {},
        'violation_summary': {
            'missing_where': 0,
            'citation_mismatch': 0,
            'missing_other_ws': 0
        }
    }

    sar_files = list(sars_dir.glob('SAR_*.json'))
    results['total_sars'] = len(sar_files)

    for sar_file in sar_files:
        is_valid, violations = validator.validate_sar(sar_file)

        if is_valid:
            results['valid_sars'] += 1
        else:
            results['invalid_sars'] += 1
            results['violations_by_sar'][sar_file.name] = violations

            # Categorize violations
            for violation in violations:
                if 'WHERE' in violation:
                    results['violation_summary']['missing_where'] += 1
                elif 'citation' in violation.lower() or 'USC' in violation:
                    results['violation_summary']['citation_mismatch'] += 1
                else:
                    results['violation_summary']['missing_other_ws'] += 1

    return results


def repair_all_sars(sars_dir: Path, backup: bool = True) -> Dict[str, Any]:
    """Repair all SARs with violations.

    Args:
        sars_dir: Directory containing SAR JSON files
        backup: Whether to create backups before repairing

    Returns:
        Repair report dictionary
    """
    validator = SARValidator()
    repairer = SARRepairer()

    results = {
        'total_processed': 0,
        'repaired': 0,
        'already_valid': 0,
        'repairs_by_sar': {}
    }

    sar_files = list(sars_dir.glob('SAR_*.json'))

    for sar_file in sar_files:
        results['total_processed'] += 1

        # Validate first
        is_valid, violations = validator.validate_sar(sar_file)

        if is_valid:
            results['already_valid'] += 1
            continue

        # Load SAR
        with open(sar_file, 'r') as f:
            sar = json.load(f)

        # Backup if requested
        if backup:
            backup_file = sar_file.with_suffix('.json.bak')
            with open(backup_file, 'w') as f:
                json.dump(sar, f, indent=2)

        repairs_made = []

        # Repair citations if needed
        citation_violations = [v for v in violations if 'citation' in v.lower() or 'USC' in v]
        if citation_violations:
            sar = repairer.repair_citations(sar)
            repairs_made.append('corrected_citations')

        # Enhance WHERE element if needed
        where_violations = [v for v in violations if 'WHERE' in v]
        if where_violations:
            sar = repairer.enhance_where_element(sar)
            repairs_made.append('added_where_element')

        # Update checksum and filing date
        sar['sar_metadata']['document_checksum'] = 'REPAIRED_' + datetime.now().strftime('%Y%m%d_%H%M%S')
        sar['sar_metadata']['last_updated'] = datetime.now().isoformat()
        sar['sar_metadata']['repair_applied'] = True
        sar['sar_metadata']['repairs'] = repairs_made

        # Save repaired SAR
        with open(sar_file, 'w') as f:
            json.dump(sar, f, indent=2)

        results['repaired'] += 1
        results['repairs_by_sar'][sar_file.name] = repairs_made

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python sar_validator_and_repair.py <command> [sars_directory]")
        print("Commands: validate, repair")
        sys.exit(1)

    command = sys.argv[1]
    sars_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("outputs/filed_sars")

    if command == "validate":
        print(f"Validating all SARs in {sars_dir}...")
        results = validate_all_sars(sars_dir)

        print("\n" + "=" * 80)
        print("SAR VALIDATION REPORT")
        print("=" * 80)
        print(f"Total SARs: {results['total_sars']}")
        print(f"Valid SARs: {results['valid_sars']}")
        print(f"Invalid SARs: {results['invalid_sars']}")
        print(f"\nViolation Summary:")
        print(f"  Missing WHERE element: {results['violation_summary']['missing_where']}")
        print(f"  Citation mismatches: {results['violation_summary']['citation_mismatch']}")
        print(f"  Other Five W's issues: {results['violation_summary']['missing_other_ws']}")

        if results['violations_by_sar']:
            print(f"\nDetailed Violations:")
            for sar_name, violations in list(results['violations_by_sar'].items())[:10]:
                print(f"\n{sar_name}:")
                for v in violations:
                    print(f"  - {v}")

            if len(results['violations_by_sar']) > 10:
                print(f"\n... and {len(results['violations_by_sar']) - 10} more SARs with violations")

    elif command == "repair":
        print(f"Repairing all SARs in {sars_dir}...")
        results = repair_all_sars(sars_dir, backup=True)

        print("\n" + "=" * 80)
        print("SAR REPAIR REPORT")
        print("=" * 80)
        print(f"Total Processed: {results['total_processed']}")
        print(f"Already Valid: {results['already_valid']}")
        print(f"Repaired: {results['repaired']}")

        if results['repairs_by_sar']:
            print(f"\nRepairs Applied:")
            for sar_name, repairs in list(results['repairs_by_sar'].items())[:10]:
                print(f"  {sar_name}: {', '.join(repairs)}")

            if len(results['repairs_by_sar']) > 10:
                print(f"  ... and {len(results['repairs_by_sar']) - 10} more SARs repaired")

        # Revalidate after repair
        print("\nRevalidating after repairs...")
        validation_results = validate_all_sars(sars_dir)
        print(f"Valid SARs after repair: {validation_results['valid_sars']}/{validation_results['total_sars']}")
        print(f"Remaining invalid: {validation_results['invalid_sars']}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
