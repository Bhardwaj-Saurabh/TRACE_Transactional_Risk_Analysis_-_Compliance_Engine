"""
Test script to validate citation relevance logic.

This script tests the citation validation system to ensure:
1. Structuring cases can cite 31 USC 5324
2. Money_Laundering cases without structuring cannot cite 31 USC 5324
3. Money_Laundering cases with structuring can cite 31 USC 5324
4. Sanctions cases cannot cite 31 USC 5324
5. Fraud cases use appropriate citations
"""

import sys
import io
sys.path.append('src')

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from compliance_officer_agent import ComplianceOfficerAgent, TYPOLOGY_CITATION_MAPPING


def test_citation_validation():
    """Test citation validation logic with various scenarios."""

    # Create a mock agent to access validation methods
    class MockAgent:
        def __init__(self):
            # Copy the validation method from ComplianceOfficerAgent
            self._validate_regulatory_citations = ComplianceOfficerAgent._validate_regulatory_citations.__get__(self)

    agent = MockAgent()

    print("=" * 80)
    print("CITATION VALIDATION TEST SUITE")
    print("=" * 80)

    test_results = []

    # Test Case 1: Structuring with 31 USC 5324 (SHOULD PASS)
    print("\n[TEST 1] Structuring case citing 31 USC 5324")
    print("-" * 80)
    result = agent._validate_regulatory_citations(
        citations=["31 CFR 1020.320", "31 USC 5324"],
        classification="Structuring",
        narrative="Four cash deposits of $9,800 each to evade CTR reporting threshold."
    )
    print(f"Classification: Structuring")
    print(f"Citations: ['31 CFR 1020.320', '31 USC 5324']")
    print(f"Narrative: 'Four cash deposits of $9,800 each to evade CTR reporting threshold.'")
    print(f"EXPECTED: Valid (is_valid=True, no prohibited citations)")
    print(f"RESULT: is_valid={result['is_valid']}, prohibited={len(result['prohibited_citations_used'])}")
    if result['is_valid']:
        print("[PASS]")
        test_results.append(("Test 1", True))
    else:
        print(f"[FAIL]: {result['error_message']}")
        test_results.append(("Test 1", False))

    # Test Case 2: Money_Laundering with 31 USC 5324 but NO structuring narrative (SHOULD FAIL)
    print("\n[TEST 2] Money_Laundering citing 31 USC 5324 WITHOUT structuring narrative")
    print("-" * 80)
    result = agent._validate_regulatory_citations(
        citations=["31 CFR 1020.320", "31 USC 5324"],
        classification="Money_Laundering",
        narrative="Large wire transfer followed by rapid outbound transfers indicative of layering."
    )
    print(f"Classification: Money_Laundering")
    print(f"Citations: ['31 CFR 1020.320', '31 USC 5324']")
    print(f"Narrative: 'Large wire transfer followed by rapid outbound transfers indicative of layering.'")
    print(f"EXPECTED: Invalid (is_valid=False, 31 USC 5324 is prohibited)")
    print(f"RESULT: is_valid={result['is_valid']}, prohibited={len(result['prohibited_citations_used'])}")
    if not result['is_valid'] and result['prohibited_citations_used']:
        print("[PASS]")
        test_results.append(("Test 2", True))
        for prohibited in result['prohibited_citations_used']:
            print(f"   Reason: {prohibited['reason']}")
    else:
        print(f"[FAIL]: Should have detected inappropriate citation")
        test_results.append(("Test 2", False))

    # Test Case 3: Money_Laundering with 31 USC 5324 AND structuring narrative (SHOULD PASS)
    print("\n[TEST 3] Money_Laundering citing 31 USC 5324 WITH structuring narrative")
    print("-" * 80)
    result = agent._validate_regulatory_citations(
        citations=["31 CFR 1020.320", "31 USC 5324", "18 USC 1956"],
        classification="Money_Laundering",
        narrative="Wire transfers followed by multiple cash withdrawals under $10,000 to evade CTR reporting."
    )
    print(f"Classification: Money_Laundering")
    print(f"Citations: ['31 CFR 1020.320', '31 USC 5324', '18 USC 1956']")
    print(f"Narrative: 'Wire transfers followed by multiple cash withdrawals under $10,000 to evade CTR reporting.'")
    print(f"EXPECTED: Valid (is_valid=True, structuring keywords present)")
    print(f"RESULT: is_valid={result['is_valid']}, prohibited={len(result['prohibited_citations_used'])}")
    if result['is_valid']:
        print("[PASS]")
        test_results.append(("Test 3", True))
    else:
        print(f"[FAIL]: {result['error_message']}")
        test_results.append(("Test 3", False))
        if result['prohibited_citations_used']:
            for prohibited in result['prohibited_citations_used']:
                print(f"   Reason: {prohibited['reason']}")

    # Test Case 4: Money_Laundering with proper AML citations (SHOULD PASS)
    print("\n[TEST 4] Money_Laundering with proper AML citations")
    print("-" * 80)
    result = agent._validate_regulatory_citations(
        citations=["31 CFR 1020.320", "18 USC 1956", "31 USC 5318"],
        classification="Money_Laundering",
        narrative="Large wire transfer followed by rapid outbound transfers indicative of layering."
    )
    print(f"Classification: Money_Laundering")
    print(f"Citations: ['31 CFR 1020.320', '18 USC 1956', '31 USC 5318']")
    print(f"Narrative: 'Large wire transfer followed by rapid outbound transfers indicative of layering.'")
    print(f"EXPECTED: Valid (is_valid=True, proper AML citations)")
    print(f"RESULT: is_valid={result['is_valid']}, prohibited={len(result['prohibited_citations_used'])}")
    if result['is_valid']:
        print("[PASS]")
        test_results.append(("Test 4", True))
    else:
        print(f"[FAIL]: {result['error_message']}")
        test_results.append(("Test 4", False))

    # Test Case 5: Sanctions with structuring citation (SHOULD FAIL)
    print("\n[TEST 5] Sanctions citing 31 USC 5324 (inappropriate)")
    print("-" * 80)
    result = agent._validate_regulatory_citations(
        citations=["31 CFR 1020.320", "31 USC 5324", "OFAC SDN List"],
        classification="Sanctions",
        narrative="Wire transfer to entity matching OFAC SDN List entry."
    )
    print(f"Classification: Sanctions")
    print(f"Citations: ['31 CFR 1020.320', '31 USC 5324', 'OFAC SDN List']")
    print(f"Narrative: 'Wire transfer to entity matching OFAC SDN List entry.'")
    print(f"EXPECTED: Invalid (is_valid=False, 31 USC 5324 prohibited for Sanctions)")
    print(f"RESULT: is_valid={result['is_valid']}, prohibited={len(result['prohibited_citations_used'])}")
    if not result['is_valid'] and result['prohibited_citations_used']:
        print("[PASS]")
        test_results.append(("Test 5", True))
        for prohibited in result['prohibited_citations_used']:
            print(f"   Reason: {prohibited['reason']}")
    else:
        print(f"[FAIL]: Should have detected inappropriate citation")
        test_results.append(("Test 5", False))

    # Test Case 6: Fraud with appropriate citations (SHOULD PASS)
    print("\n[TEST 6] Fraud with appropriate citations")
    print("-" * 80)
    result = agent._validate_regulatory_citations(
        citations=["31 CFR 1020.320", "FTC Red Flags Rule"],
        classification="Fraud",
        narrative="Account takeover with fraudulent wire transfers to overseas accounts."
    )
    print(f"Classification: Fraud")
    print(f"Citations: ['31 CFR 1020.320', 'FTC Red Flags Rule']")
    print(f"Narrative: 'Account takeover with fraudulent wire transfers to overseas accounts.'")
    print(f"EXPECTED: Valid (is_valid=True, appropriate Fraud citations)")
    print(f"RESULT: is_valid={result['is_valid']}, prohibited={len(result['prohibited_citations_used'])}")
    if result['is_valid']:
        print("[PASS]")
        test_results.append(("Test 6", True))
    else:
        print(f"[FAIL]: {result['error_message']}")
        test_results.append(("Test 6", False))

    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)
    print("\nSummary:")
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    print(f"Tests Passed: {passed}/{total}")
    for test_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test_name}")
    print("\n" + "=" * 80)


def print_citation_mapping():
    """Print the citation mapping for reference."""
    print("\n" + "=" * 80)
    print("TYPOLOGY CITATION MAPPING REFERENCE")
    print("=" * 80)

    for typology, config in TYPOLOGY_CITATION_MAPPING.items():
        print(f"\n{typology}:")
        print(f"  Description: {config['description']}")
        print(f"  Required (any): {config.get('required_any', [])}")
        print(f"  Recommended: {config.get('recommended', [])}")
        print(f"  Prohibited: {config.get('prohibited', [])}")
        if 'conditionally_prohibited' in config:
            print(f"  Conditionally Prohibited:")
            for citation, keywords in config['conditionally_prohibited']:
                print(f"    - {citation} (unless narrative contains: {', '.join(keywords)})")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print_citation_mapping()
    test_citation_validation()
