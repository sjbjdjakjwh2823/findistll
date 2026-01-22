import xml.etree.ElementTree as ET
import os
import re
from main import Orchestrator

def parse_xbrl(file_path):
    print(f"Parsing XBRL: {file_path}")
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Namespace map
    namespaces = dict([
        node for _, node in ET.iterparse(file_path, events=['start-ns'])
    ])
    
    # Find contexts
    contexts = {}
    for context in root.findall(f"{{{namespaces.get('xbrli', 'http://www.xbrl.org/2003/instance')}}}context"):
        cid = context.get("id")
        
        # Entity
        entity_node = context.find(f".//{{{namespaces.get('xbrli')}}}identifier")
        entity = entity_node.text if entity_node is not None else "Unknown"
        
        # Period
        period_node = context.find(f".//{{{namespaces.get('xbrli')}}}period")
        period = "Unknown"
        if period_node is not None:
            instant = period_node.find(f"{{{namespaces.get('xbrli')}}}instant")
            if instant is not None:
                period = instant.text
            else:
                start = period_node.find(f"{{{namespaces.get('xbrli')}}}startDate")
                end = period_node.find(f"{{{namespaces.get('xbrli')}}}endDate")
                if start is not None and end is not None:
                    period = f"{start.text}/{end.text}"
                    
        contexts[cid] = {"entity": entity, "period": period}
        
    # Find Units
    units = {}
    for unit in root.findall(f"{{{namespaces.get('xbrli')}}}unit"):
        uid = unit.get("id")
        measure = unit.find(f".//{{{namespaces.get('xbrli')}}}measure")
        if measure is not None:
            units[uid] = measure.text
        else:
            units[uid] = "Unknown"

    # Find Facts (Elements with unitRef)
    facts = []
    count = 0
    for child in root:
        unit_ref = child.get("unitRef")
        if unit_ref:
            context_ref = child.get("contextRef")
            value = child.text
            
            # Extract concept name (tag without namespace)
            concept = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            
            # Resolve Context & Unit
            ctx = contexts.get(context_ref, {"entity": "Unknown", "period": "Unknown"})
            unit = units.get(unit_ref, "Unknown")
            
            # Clean Unit (iso4217:KRW -> KRW)
            if ":" in unit:
                unit = unit.split(":")[-1]
                
            # Filter empty values
            if value and value.strip():
                try:
                    val_float = float(value)
                    facts.append({
                        "entity": ctx["entity"],
                        "period": ctx["period"],
                        "concept": concept,
                        "value": val_float,
                        "unit": unit
                    })
                    count += 1
                except ValueError:
                    pass
                    
    print(f"Extracted {count} facts from XBRL.")
    return facts

def test_real_data():
    xbrl_file = r"C:\Users\Administrator\Desktop\[삼성전자]사업보고서_IFRS(원문XBRL)(2025.03.11)\entity00126380_2024-12-31.xbrl"
    
    if not os.path.exists(xbrl_file):
        print("XBRL file not found.")
        return

    data = parse_xbrl(xbrl_file)
    
    if not data:
        print("No data extracted.")
        return
        
    # Sample a bit if too large? No, orchestrator handles it.
    print(f" feeding {len(data)} records to Orchestrator...")
    
    orchestrator = Orchestrator()
    try:
        orchestrator.process_pipeline(data)
    finally:
        orchestrator.shutdown()
        
    print("Real Data Test Complete.")

if __name__ == "__main__":
    test_real_data()
