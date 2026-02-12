from sdk.preciso_client import PrecisoClient
import json
import time

def run_b2b_pilot():
    print("🚀 Initializing Preciso B2B SDK Pilot Launch...")
    
    # Initialize client (pointing to local dev server)
    client = PrecisoClient(base_url="http://localhost:8000")
    
    print("\n📦 Step 1: Creating Institutional Case...")
    case_title = f"Consumer Test - {time.strftime('%Y-%m-%d %H:%M')}"
    try:
        case_id = client.create_case(case_title)
        print(f"✅ Case Created: {case_id}")
    except Exception as e:
        print(f"❌ Case Creation Failed: {e}")
        return
    
    print("\n📄 Step 2: Ingesting Financial Document...")
    doc_content = """
    Institutional Financial Overview
    Company: Global Tech Corp
    Revenue: 50.5B
    Net Income: 12.2B
    Debt: 5.1B
    Region: Europe
    Metric_NetIncome: 12.2
    """
    try:
        doc_id = client.add_document(case_id, "Q4_Report.txt", doc_content)
        print(f"✅ Document Ingested: {doc_id}")
    except Exception as e:
        print(f"❌ Document Ingestion Failed: {e}")
        return
    
    print("\n🔍 Step 3: Running FinDistill Analysis...")
    try:
        distill = client.distill(case_id)
        print(f"✅ Facts Extracted: {len(distill['facts'])}")
    except Exception as e:
        print(f"❌ Distill Failed: {e}")
        # Continue to see if other parts work
    
    print("\n🧠 Step 4: Generating FinRobot Decision...")
    try:
        decision = client.decide(case_id)
        print(f"✅ Decision: {decision['decision']}")
        print(f"   Rationale: {decision['rationale'][:100]}...")
    except Exception as e:
        print(f"❌ Decision Failed: {e}")
    
    print("\n🔐 Step 5: Verifying Sovereign Data Integrity (ZKP)...")
    try:
        zkp = client.verify_integrity(case_id)
        if zkp['verified']:
            print(f"✅ Integrity Verified via {zkp['method']}")
            if 'commitment' in zkp:
                print(f"   Commitment: {zkp['commitment']}")
        else:
            print("❌ Integrity Compromised!")
    except Exception as e:
        print(f"❌ ZKP Verification Failed: {e}")

    print("\n🌍 Step 6: Checking Global Risk Mapping...")
    try:
        import requests
        res = requests.get(f"http://localhost:8000/graph/global/{case_id}")
        mapping = res.json()
        print(f"✅ Geo-Quant Connections Found: {len(mapping.get('connections', []))}")
        for conn in mapping.get('connections', []):
            print(f"   - {conn['from']} -> {conn['to']} (Intensity: {conn['intensity']:.2f})")
    except Exception as e:
        print(f"❌ Geo-Mapping Failed: {e}")

    print("\n✨ Consumer Journey Simulation Completed.")

if __name__ == "__main__":
    run_b2b_pilot()
