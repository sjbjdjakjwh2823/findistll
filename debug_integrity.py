import os
import sys
import json
from decimal import Decimal

# Add current directory to path
sys.path.append(os.getcwd())

from api.services.xbrl_semantic_engine import XBRLSemanticEngine, ScaleProcessor

def check_integrity():
    print("--- Integrity Check: Universal CoT Integration ---")
    engine = XBRLSemanticEngine(company_name="NVIDIA Corp", fiscal_year="2024")
    
    # Mock XBRL with Revenues and NetIncome to ensure multiple rows
    mock_xbrl = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl>
        <context id="c_cy"><period><instant>2024-01-31</instant></period></context>
        <context id="c_py"><period><instant>2023-01-31</instant></period></context>
        <Revenues contextRef="c_cy" unitRef="USD" decimals="-6">60922000000</Revenues>
        <Revenues contextRef="c_py" unitRef="USD" decimals="-6">26974000000</Revenues>
        <NetIncomeLoss contextRef="c_cy" unitRef="USD" decimals="-6">29760000000</NetIncomeLoss>
        <NetIncomeLoss contextRef="c_py" unitRef="USD" decimals="-6">4368000000</NetIncomeLoss>
    </xbrl>
    """
    
    result = engine.process_joint(mock_xbrl)
    
    # Log check
    print("\n--- Terminal Log Verification ---")
    # (Logs will be printed to stdout during execution)
    
    # JSONL Inspection
    print("\n--- JSONL Row Inspection ---")
    for i, line in enumerate(result.jsonl_data):
        data = json.loads(line)
        output = data["output"]
        print(f"\n--- Row {i+1} Output ---")
        if i == 2: # Full print for Row 3
             print(output)
        else:
             print(output[:150] + "...")
        
        # Check for [Definition] and LaTeX
        if "[Definition]" not in output:
             print(f"FAIL: Row {i+1} missing [Definition]")
        if "$$Growth =" not in output:
             print(f"FAIL: Row {i+1} missing YoY LaTeX formula")
        if "Prior data missing" in output and i == 1: # Row 2 (Revenues) should have PY
             print(f"FAIL: Row {i+1} has missing PY data when it should be present")

if __name__ == "__main__":
    check_integrity()
