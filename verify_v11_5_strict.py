import sys
import os
import re
from decimal import Decimal

# Add current directory to path
sys.path.append(os.getcwd())

from api.services.xbrl_semantic_engine import XBRLSemanticEngine, ScaleProcessor, ExpertCoTGenerator

def test_v11_5_operational():
    print("--- Testing Operational Status ---")
    engine = XBRLSemanticEngine(company_name="Antigravity AI", fiscal_year="2025")
    result = engine.process_mock()
    
    if result.success and "OPERATIONAL" in sys.stdout.getvalue() if hasattr(sys.stdout, 'getvalue') else True:
        print("SUCCESS: Engine reported operational status.")
    
    # Check JSONL content
    jsonl = result.jsonl_data[0]
    data = eval(jsonl) # Safe for internal test
    
    output = data["output"]
    print("\n[Output Preview]")
    print(output[:200] + "...")
    
    # Verification Points
    assertions = [
        ("[Definition]" in output, "Mandatory [Definition] block"),
        ("[Synthesis]" in output, "Mandatory [Synthesis] block"),
        ("[Symbolic Reasoning]" in output, "Mandatory [Symbolic Reasoning] block"),
        ("[Professional Insight]" in output, "Mandatory [Professional Insight] block"),
        ("$$Growth =" in output, "LaTeX Growth formula present"),
        ("Analyze the multi-year performance" in data["instruction"], "Correct English instruction"),
        (not re.search(r'[\uAC00-\uD7A3]', output), "No Korean detected")
    ]
    
    for cond, msg in assertions:
        if cond:
            print(f"PASS: {msg}")
        else:
            print(f"FAIL: {msg}")

def test_self_healing():
    print("\n--- Testing Self-Healing Scaling ---")
    # Test with already large value (trillions)
    raw_val = "3253431000000" 
    val, scale = ScaleProcessor.apply_self_healing(raw_val)
    # Expected: 3253.431B
    print(f"Raw: {raw_val} -> Scaled: {val}B ({scale})")
    if val == Decimal("3253.431"):
        print("PASS: Self-healing trillion detection successful.")
    else:
        print(f"FAIL: Expected 3253.431, got {val}")

def test_poison_pill():
    print("\n--- Testing Poison Pill (Korean Detection) ---")
    engine = XBRLSemanticEngine()
    qa_pairs = [{"question": "test", "response": "한국어 포함 텍스트"}]
    try:
        engine._generate_jsonl(qa_pairs)
        print("FAIL: Poison pill did not trigger for Korean text.")
    except RuntimeError as e:
        if str(e) == "KOREAN_DETECTED":
            print("PASS: Poison pill triggered correctly for Korean text.")
        else:
            print(f"FAIL: Wrong error raised: {e}")

if __name__ == "__main__":
    from io import StringIO
    # Capture output for status check
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    
    try:
        test_v11_5_operational()
        test_self_healing()
        test_poison_pill()
    finally:
        sys.stdout = old_stdout
        print(mystdout.getvalue())
