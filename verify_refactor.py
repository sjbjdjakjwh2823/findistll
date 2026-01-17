import sys
import os
from decimal import Decimal
from typing import List, Dict

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.services.xbrl_semantic_engine import XBRLSemanticEngine, SemanticFact

def create_mock_facts():
    """Create a list of mock SemanticFact objects."""
    facts = []
    
    # Helper to create fact
    def add_fact(label, concept, value, hierarchy="Balance Sheet"):
        facts.append(SemanticFact(
            concept=concept,
            label=label,
            value=Decimal(value),
            raw_value=str(value),
            unit="KRW",
            period="2023",
            context_ref="ctx_2023",
            decimals=-3,
            hierarchy=hierarchy,
            is_consolidated=True,
            segment=None
        ))

    # Add facts
    add_fact("Total Assets", "us-gaap:Assets", 1000000000000, "Balance Sheet > Assets") # 1T
    add_fact("Total Liabilities", "us-gaap:Liabilities", 400000000000, "Balance Sheet > Liabilities") # 400B
    add_fact("Total Equity", "us-gaap:StockholdersEquity", 600000000000, "Balance Sheet > Equity") # 600B
    add_fact("Current Assets", "us-gaap:AssetsCurrent", 500000000000, "Balance Sheet > Assets") # 500B
    add_fact("Current Liabilities", "us-gaap:LiabilitiesCurrent", 300000000000, "Balance Sheet > Liabilities") # 300B
    
    add_fact("Revenues", "us-gaap:Revenues", 2000000000000, "Income Statement") # 2T
    add_fact("Operating Income", "us-gaap:OperatingIncomeLoss", 300000000000, "Income Statement") # 300B
    add_fact("Net Income", "us-gaap:NetIncomeLoss", 200000000000, "Income Statement") # 200B
    add_fact("Cost of Goods Sold", "us-gaap:CostOfGoodsAndServicesSold", 1200000000000, "Income Statement") # 1.2T
    add_fact("Gross Profit", "us-gaap:GrossProfit", 800000000000, "Income Statement") # 800B
    add_fact("SG&A Expenses", "us-gaap:SellingGeneralAndAdministrativeExpense", 500000000000, "Income Statement") # 500B
    add_fact("R&D Expenses", "us-gaap:ResearchAndDevelopmentExpense", 100000000000, "Income Statement") # 100B
    
    # Add duplicate concept with different label to test deduplication
    add_fact("Sales", "us-gaap:Revenues", 2000000000000, "Income Statement") 

    return facts

def verify_output(qa_pairs: List[Dict]):
    """Verify the generated QA pairs meet the requirements."""
    
    print(f"Generated {len(qa_pairs)} QA pairs.")
    
    errors = []
    
    # Check 1: No Korean characters
    for i, qa in enumerate(qa_pairs):
        q_text = qa.get('question', '')
        r_text = qa.get('response', '')
        
        for char in q_text + r_text:
            if '\u3131' <= char <= '\uD7A3':
                errors.append(f"QA #{i}: Korean character detected: {char}")
                break

    # Check 2: Structure
    for i, qa in enumerate(qa_pairs):
        r_text = qa.get('response', '')
        if "[Definition]" not in r_text:
            errors.append(f"QA #{i}: Missing [Definition] section")
        if "[Symbolic Reasoning]" not in r_text:
            errors.append(f"QA #{i}: Missing [Symbolic Reasoning] section")

    # Check 3: Instruction formatting (No "Find X")
    forbidden_starts = ["Find", "What is", "Show me"]
    for i, qa in enumerate(qa_pairs):
        q_text = qa.get('question', '')
        for start in forbidden_starts:
            if q_text.startswith(start):
                 errors.append(f"QA #{i}: Question starts with forbidden phrase '{start}': {q_text}")

    # Check 4: Financial Performance Summary presence
    summary_found = False
    for qa in qa_pairs:
        if "Financial Performance Summary" in qa.get('question', ''):
            summary_found = True
            r_text = qa.get('response', '')
            if "Total Assets" not in r_text or "Revenues" not in r_text or "Operating Income" not in r_text:
                errors.append(f"Summary found but missing key metrics: {r_text[:100]}...")
            if "System Log" in r_text:
                errors.append("Summary contains 'System Log'")
            break
            
    if not summary_found:
        errors.append("Financial Performance Summary not found in QA pairs")

    # Check 5: Deduplication
    questions = [qa['question'] for qa in qa_pairs]
    if len(questions) != len(set(questions)):
        errors.append("Duplicate questions detected")

    if errors:
        print("\n[FAILED] Verification Failed with errors:")
        for e in errors:
            print(f" - {e}")
        return False
    else:
        print("\n[PASSED] Verification Passed!")
        return True

if __name__ == "__main__":
    engine = XBRLSemanticEngine(company_name="TestCorp", fiscal_year="2023", sic_code="3571")
    facts = create_mock_facts()
    qa_pairs = engine._generate_reasoning_qa(facts)
    
    # Print a few samples
    for idx, qa in enumerate(qa_pairs[:3]):
        print(f"\n--- QA #{idx + 1} ---")
        print(f"Q: {qa['question']}")
        print(f"A snippet: {qa['response'][:100]}...")

    verify_output(qa_pairs)
