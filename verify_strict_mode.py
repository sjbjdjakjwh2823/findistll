
import sys
import os
import json
from decimal import Decimal

# Add path to api/services
sys.path.append(os.path.join(os.getcwd(), 'api', 'services'))

from xbrl_semantic_engine import XBRLSemanticEngine, SemanticFact

def test_strict_mode():
    print("Testing Strict Mode Enforcement...")
    
    engine = XBRLSemanticEngine(company_name="TEST", fiscal_year="2022")
    
    # Inject a fake QA pair with Korean
    qa_pairs = [{
        "question": "What is this?",
        "response": "This is a 테스트 (test).", # Korean content
        "type": "test",
        "concept": "test"
    }]
    
    facts = [] # Empty facts
    
    print("Attempting to generate JSONL with Korean content...")
    try:
        engine._generate_jsonl(facts, qa_pairs)
        print("[FAIL] RuntimeError was NOT raised!")
        sys.exit(1)
    except RuntimeError as e:
        print(f"[SUCCESS] Caught expected error: {e}")
        if "STRICT_V11_MODE VIOLATION" in str(e):
            print("Error message confirmed.")
            sys.exit(0)
        else:
            print(f"[FAIL] Unexpected error message: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Caught unexpected exception type: {type(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_strict_mode()
