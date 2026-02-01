import xml.etree.ElementTree as ET
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class LabelManager:
    """
    v14.0 Label Manager
    Parses XBRL label linkbases to resolve concept names to human-readable text.
    """
    def __init__(self, label_content: Optional[bytes] = None):
        self.label_map = {}
        if label_content:
            self._parse_linkbase(label_content)
            
    def _parse_linkbase(self, content: bytes):
        try:
            tree = ET.fromstring(content)
            # Handle XML namespaces - messy but standard in XBRL
            # link:loc -> href -> #ConceptID
            # link:labelArc -> from Loc to Label
            # link:label -> Text
            
            # 1. Map labels by ID first
            # <link:label id="Label_..." ...>Text</link:label>
            label_resource_map = {} 
            for elem in tree.findall(".//{http://www.xbrl.org/2003/linkbase}label"):
                label_id = elem.get("{http://www.w3.org/1999/xlink}label")
                role = elem.get("{http://www.w3.org/1999/xlink}role")
                text = elem.text
                if label_id and text:
                    # Prefer standard label or specific verbose ones
                    # For now just store the first one or override if standard
                    label_resource_map[label_id] = text
                    
            # 2. Map Locators to Label IDs via Arcs
            # <link:loc xlink:href="...#ConceptID" xlink:label="Loc_..." />
            loc_map = {} # LocLabel -> ConceptID
            for elem in tree.findall(".//{http://www.xbrl.org/2003/linkbase}loc"):
                href = elem.get("{http://www.w3.org/1999/xlink}href")
                label = elem.get("{http://www.w3.org/1999/xlink}label")
                if href and label and '#' in href:
                    concept_id = href.split('#')[1]
                    loc_map[label] = concept_id
                    
            # 3. Process Arcs to link ConceptID -> Text
            for elem in tree.findall(".//{http://www.xbrl.org/2003/linkbase}labelArc"):
                from_loc = elem.get("{http://www.w3.org/1999/xlink}from")
                to_label = elem.get("{http://www.w3.org/1999/xlink}to")
                
                if from_loc in loc_map and to_label in label_resource_map:
                    concept_id = loc_map[from_loc]
                    text = label_resource_map[to_label]
                    
                    # Store in main map (normalize keys to avoid namespace prefix issues if possible)
                    self.label_map[concept_id] = text
                    
            logger.info(f"LabelManager: Loaded {len(self.label_map)} labels from linkbase.")
            
        except Exception as e:
            logger.error(f"LabelManager failed to parse linkbase: {e}")

    def get_label(self, tag_name: str) -> Optional[str]:
        # Tag name might be "dart:Revenue" or "ifrs-full:Assets"
        # The linkbase usually maps the ID "dart_Revenue" or just "Assets"
        
        # 1. Try Exact Match (if tag_name matches ID)
        if tag_name in self.label_map:
            return self.label_map[tag_name]
            
        # 2. Try Local Name (split by :)
        if ':' in tag_name:
            local_name = tag_name.split(':')[1]
            if local_name in self.label_map:
                return self.label_map[local_name]
                
            # 3. Try "dart_" + Local Name (common pattern in provided file)
            # entity00126380_2024-12-31_lab-en.xml uses "dart_LentIncome" for "LentIncome"
            # But the Concept ID in schema might be "dart_LentIncome"
            
            # Check if there is a mapping for "dart_" + local_name
            # Wait, the loc map maps href="#dart_LentIncome" -> concept_id="dart_LentIncome"
            # The instance has <dart:LentIncome>.
            # So we need to match "dart:LentIncome" to "dart_LentIncome" OR "LentIncome"
            
            # Let's try constructing common ID patterns
            candidates = [
                local_name,
                f"dart_{local_name}",
                f"ifrs-full_{local_name}",
                f"entity_{local_name}" # generic entity prefix
            ]
            
            for c in candidates:
                if c in self.label_map:
                    return self.label_map[c]
                    
            # 4. Try scanning map keys for partial match (expensive but safer)
            # If map key is "dart_LentIncome" and we have "LentIncome"
            for k in self.label_map:
                if k.endswith(f"_{local_name}") or k == local_name:
                    return self.label_map[k]
                    
        return None

class DimensionManager:
    """
    v14.0 Dimension Manager
    Parses context dimensions to create granular label differentiation.
    """
    @staticmethod
    def extract_dimensions(context_elem: ET.Element) -> Dict[str, str]:
        dims = {}
        # Parse <segment> or <scenario> (Namespaces already stripped by Engine)
        # Look for <explicitMember dimension="...">Member</explicitMember>
        
        # Search for segment/scenario in a namespace-agnostic way (since Engine strips them)
        containers = []
        for tag in ['segment', 'scenario']:
            found = context_elem.find(f".//{tag}")
            if found is not None:
                containers.append(found)
        
        for container in containers:
            for explicit in container.findall(".//explicitMember"):
                dim_raw = explicit.get("dimension")
                mem_raw = explicit.text
                
                if dim_raw and mem_raw:
                    # Clean strings (remove namespaces if present in attributes)
                    dim = dim_raw.split(':')[1] if ':' in dim_raw else dim_raw
                    mem = mem_raw.split(':')[1] if ':' in mem_raw else mem_raw
                    
                    # Filter out generic/default dimensions if needed
                    if "Consolidated" in dim:
                         # Consolidated vs Separate is CRITICAL
                         dims["Scope"] = mem.replace("Member", "")
                    elif "Axis" in dim:
                         # Generic Axis
                         key = dim.replace("Axis", "")
                         val = mem.replace("Member", "")
                         dims[key] = val
                    else:
                         dims[dim] = mem
                         
        return dims

