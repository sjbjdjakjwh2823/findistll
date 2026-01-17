import asyncio
import json
import os
import sys
from decimal import Decimal

# Add current directory to path
sys.path.append(os.getcwd())

from api.services.ingestion import ingestion_service
from api.services.normalizer import normalizer
from api.services.exporter import exporter

async def reproduce():
    print("--- Full Pipeline Reproduction ---")
    mock_xbrl = b"""<?xml version="1.0" encoding="UTF-8"?>
    <xbrl>
        <context id="c_cy"><period><instant>2024-01-31</instant></period></context>
        <context id="c_py"><period><instant>2023-01-31</instant></period></context>
        <EntityRegistrantName contextRef="c_cy">NVIDIA Corp</EntityRegistrantName>
        <DocumentFiscalYearFocus contextRef="c_cy">2024</DocumentFiscalYearFocus>
        <Revenues contextRef="c_cy" unitRef="USD" decimals="-6">60922000000</Revenues>
        <Revenues contextRef="c_py" unitRef="USD" decimals="-6">26974000000</Revenues>
    </xbrl>
    """
    
    # 1. Ingestion
    print("1. Running Ingestion...")
    extracted_data = await ingestion_service.process_file(mock_xbrl, "test.xml", "application/xml")
    print(f"   - jsonl_data present: {'jsonl_data' in extracted_data}")
    print(f"   - reasoning_qa present: {'reasoning_qa' in extracted_data}")
    
    # 2. Normalization
    print("2. Running Normalization...")
    normalized_data = normalizer.normalize(extracted_data)
    print(f"   - jsonl_data preserved: {'jsonl_data' in normalized_data}")
    print(f"   - reasoning_qa preserved: {'reasoning_qa' in normalized_data}")
    
    # 3. Export
    print("3. Running Export (JSONL)...")
    jsonl_output = exporter.to_jsonl(normalized_data)
    
    print("\n--- Final JSONL Content ---")
    if not jsonl_output:
        print("FAIL: JSONL output is EMPTY!")
    else:
        print(f"SUCCESS: JSONL output has {len(jsonl_output.splitlines())} lines.")
        print("First line preview:")
        print(jsonl_output.splitlines()[0][:100] + "...")

if __name__ == "__main__":
    asyncio.run(reproduce())
