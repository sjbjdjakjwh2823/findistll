
import sys
import os
import json
import re
from decimal import Decimal

# Add path to api/services
sys.path.append(os.path.join(os.getcwd(), 'api', 'services'))

from xbrl_semantic_engine import XBRLSemanticEngine, SemanticFact

def verify_final():
    print("Starting Final Verification...")
    
    # 1. Setup Engine
    engine = XBRLSemanticEngine(company_name="NVIDIA", fiscal_year="2022")
    
    # 2. Mock Facts (enough to trigger cross-table analysis)
    facts = []
    
    def make_fact(concept, label, value, hierarchy):
        return SemanticFact(
            concept=concept,
            label=label,
            value=value,
            raw_value=str(value),
            unit='USD',
            period='2022',
            context_ref='ctx',
            decimals='-6',
            is_consolidated=True,
            segment=None,
            hierarchy=hierarchy
        )

    facts = [
        make_fact('Assets', 'Total Assets', Decimal('10000000000'), 'Balance Sheet'),
        make_fact('Liabilities', 'Total Liabilities', Decimal('4000000000'), 'Balance Sheet'),
        make_fact('Equity', 'Total Equity', Decimal('6000000000'), 'Balance Sheet'),
        make_fact('Revenue', 'Revenues', Decimal('5000000000'), 'Income Statement'),
        make_fact('NetIncome', 'Net Income', Decimal('1000000000'), 'Income Statement'),
        make_fact('GrossProfit', 'Gross Profit', Decimal('3000000000'), 'Income Statement'),
        make_fact('OperatingIncome', 'Operating Income', Decimal('2000000000'), 'Income Statement'),
        make_fact('Inventory', 'Inventory', Decimal('500000000'), 'Balance Sheet'),
        make_fact('COGS', 'Cost of Goods Sold', Decimal('2000000000'), 'Income Statement'),
        make_fact('SGA', 'SG&A Expenses', Decimal('1000000000'), 'Income Statement'), # Added for Efficiency
        make_fact('CurrentAssets', 'Current Assets', Decimal('3000000000'), 'Balance Sheet'), # Added for WC
        make_fact('CurrentLiabilities', 'Current Liabilities', Decimal('1000000000'), 'Balance Sheet'), # Added for WC
    ]
    
    # 3. Generate Analysis
    print("Generating Analysis...")
    engine.facts = facts
    # We call internal methods to simulate full process
    fact_dict = engine._build_flexible_fact_dict(facts)
    reasoning_qa = engine._generate_reasoning_qa(facts)
    jsonl = engine._generate_jsonl(facts, reasoning_qa)
    
    print(f"Generated {len(jsonl)} JSONL entries.")
    
    korean_pattern = re.compile(r'[\u3131-\u318E\uAC00-\uD7A3]')
    
    all_passed = True
    
    for i, line in enumerate(jsonl):
        data = json.loads(line)
        instruction = data['instruction']
        output = data['output']
        input_text = data['input']
        
        # Check 1: No Korean
        if korean_pattern.search(line):
            print(f"[FAIL] Line {i+1} contains Korean!")
            print(f"Content: {line[:100]}...")
            all_passed = False
            
        # Check 2: CoT Format (Start with [Definition])
        if not output.strip().startswith("[Definition]"):
            print(f"[FAIL] Line {i+1} does NOT start with [Definition]!")
            print(f"Output start: {output[:50]}...")
            all_passed = False
            
        # Check 3: Headers
        if "컬럼" in input_text or "계정과목" in input_text:
             print(f"[FAIL] Line {i+1} contains Korean Headers!")
             all_passed = False
             
    if all_passed:
        print("\nSUCCESS: All entries are English and use Expert CoT format.")
    else:
        print("\nFAILURE: Some entries failed validation.")

if __name__ == "__main__":
    verify_final()
