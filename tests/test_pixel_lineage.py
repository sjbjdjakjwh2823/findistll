import asyncio
import base64
import os
import sys

import pytest

# Add preciso_work to path
sys.path.append(os.path.abspath("preciso_work"))

from app.services.distill_engine import FinDistillAdapter
from app.services.types import DistillResult

@pytest.mark.asyncio
async def test_lineage_extraction():
    # 1. Create a dummy PDF with specific text
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    text = "Revenue: 100.5 Billion USD"
    page.insert_text((100, 150), text)
    pdf_bytes = doc.write()
    doc.close()

    adapter = FinDistillAdapter()
    
    # Mock document
    document = {
        "filename": "test.pdf",
        "mime_type": "application/pdf",
        "file_bytes": pdf_bytes,
        "content": text
    }

    # Set offline mode to avoid Gemini calls in test, but we want to test coord extraction
    # Actually, we need to mock the facts returned by extraction
    os.environ["DISTILL_OFFLINE"] = "1"
    
    # We'll manually call _enrich_with_source_anchors to test the core logic
    facts = [
        {"label": "Revenue", "value": "100.5", "statement": "Revenue is 100.5B"}
    ]
    
    enriched_facts = adapter._enrich_with_source_anchors(facts, pdf_bytes)
    
    print(f"Enriched Facts: {enriched_facts}")
    
    if enriched_facts and "source_anchor" in enriched_facts[0]:
        anchor = enriched_facts[0]["source_anchor"]
        print(f"SUCCESS: Found anchor at Page {anchor['page']}, Box {anchor['box']}")
        
        # Verify coordinates (should be around 100, 150)
        box = anchor["box"]
        if 90 < box[0] < 110 and 140 < box[1] < 160:
            print("COORDINATES MATCH!")
        else:
            print(f"COORDINATES MISMATCH: Expected near (100, 150), got {box}")
    else:
        print("FAILED: No anchor found")

if __name__ == "__main__":
    asyncio.run(test_lineage_extraction())
