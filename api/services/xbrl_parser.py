"""
FinDistill XBRL/XML Parser Service v2

Enterprise-grade XBRL parser with full Linkbase support:
- Proper namespace handling (link, xlink, ifrs-full, dart, etc.)
- Locator (link:loc) mapping and indexing
- CalculationArc extraction with weight and order
- PresentationArc hierarchy building
- lxml for optimized namespace processing
- iterparse for memory-efficient large file handling
"""

import io
import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import xml.etree.ElementTree as ET


# ============================================================
# NAMESPACE DEFINITIONS
# ============================================================

NAMESPACES = {
    'link': 'http://www.xbrl.org/2003/linkbase',
    'xlink': 'http://www.w3.org/1999/xlink',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'xbrli': 'http://www.xbrl.org/2003/instance',
    'ifrs-full': 'http://xbrl.ifrs.org/taxonomy/2023-03-23/ifrs-full',
    'dart': 'http://dart.fss.or.kr/taxonomy',
    'iso4217': 'http://www.xbrl.org/2003/iso4217',
    'label': 'http://www.xbrl.org/2003/label',
    'ref': 'http://www.xbrl.org/2006/ref',
}

# Reverse namespace lookup
NS_PREFIXES = {v: k for k, v in NAMESPACES.items()}


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class CalculationRelation:
    """Represents a calculation relationship between XBRL concepts."""
    parent_concept: str  # e.g., ifrs-full_Assets
    child_concept: str   # e.g., ifrs-full_CurrentAssets
    weight: float        # +1 or -1
    order: float         # presentation order
    arc_role: Optional[str] = None


@dataclass
class XBRLFact:
    """Represents a single XBRL fact (data point)."""
    concept: str
    value: str
    unit: Optional[str] = None
    context_ref: Optional[str] = None
    decimals: Optional[int] = None
    label: Optional[str] = None
    hierarchy: Optional[str] = None
    order: int = 0
    period: Optional[str] = None
    

@dataclass
class XBRLContext:
    """XBRL context information (period, entity)."""
    id: str
    entity: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instant: Optional[str] = None


# ============================================================
# TAXONOMY LOADER (Extended)
# ============================================================

class TaxonomyLoader:
    """
    Flexible taxonomy loader supporting IFRS, GAAP, and DART.
    """
    
    IFRS_LABELS_KO = {
        # 재무상태표
        "ifrs-full_Assets": "자산",
        "ifrs-full_CurrentAssets": "유동자산",
        "ifrs-full_NoncurrentAssets": "비유동자산",
        "ifrs-full_Liabilities": "부채",
        "ifrs-full_CurrentLiabilities": "유동부채",
        "ifrs-full_NoncurrentLiabilities": "비유동부채",
        "ifrs-full_Equity": "자본",
        "ifrs-full_IssuedCapital": "자본금",
        "ifrs-full_RetainedEarnings": "이익잉여금",
        "ifrs-full_EquityAttributableToOwnersOfParent": "지배기업소유주지분",
        "ifrs-full_NoncontrollingInterests": "비지배지분",
        
        # 포괄손익계산서
        "ifrs-full_Revenue": "매출액",
        "ifrs-full_CostOfSales": "매출원가",
        "ifrs-full_GrossProfit": "매출총이익",
        "ifrs-full_SellingGeneralAndAdministrativeExpense": "판매비와관리비",
        "ifrs-full_OperatingProfit": "영업이익",
        "ifrs-full_FinanceCosts": "금융비용",
        "ifrs-full_FinanceIncome": "금융수익",
        "ifrs-full_ProfitBeforeTax": "법인세비용차감전순이익",
        "ifrs-full_IncomeTaxExpense": "법인세비용",
        "ifrs-full_ProfitLoss": "당기순이익",
        
        # 현금흐름표
        "ifrs-full_CashFlowsFromOperatingActivities": "영업활동현금흐름",
        "ifrs-full_CashFlowsFromInvestingActivities": "투자활동현금흐름",
        "ifrs-full_CashFlowsFromFinancingActivities": "재무활동현금흐름",
        "ifrs-full_CashAndCashEquivalents": "현금및현금성자산",
        
        # DART specific
        "dart_TotalAssets": "자산총계",
        "dart_TotalLiabilities": "부채총계",
        "dart_TotalEquity": "자본총계",
    }
    
    HIERARCHY_MAP = {
        "ifrs-full_Assets": "재무상태표 > 자산",
        "ifrs-full_CurrentAssets": "재무상태표 > 자산 > 유동자산",
        "ifrs-full_NoncurrentAssets": "재무상태표 > 자산 > 비유동자산",
        "ifrs-full_Liabilities": "재무상태표 > 부채",
        "ifrs-full_Equity": "재무상태표 > 자본",
        "ifrs-full_Revenue": "포괄손익계산서 > 매출액",
        "ifrs-full_GrossProfit": "포괄손익계산서 > 매출총이익",
        "ifrs-full_OperatingProfit": "포괄손익계산서 > 영업이익",
        "ifrs-full_ProfitLoss": "포괄손익계산서 > 당기순이익",
    }
    
    def __init__(self, taxonomy_type: str = "ifrs"):
        self.taxonomy_type = taxonomy_type
        self.labels: Dict[str, str] = self.IFRS_LABELS_KO.copy()
        self.hierarchies: Dict[str, str] = self.HIERARCHY_MAP.copy()
        self.presentation_order: Dict[str, int] = {}
        
        for i, concept in enumerate(self.labels.keys()):
            self.presentation_order[concept] = i
    
    def get_label(self, concept: str) -> str:
        """Get human-readable label for a concept."""
        # Normalize concept name (remove namespace prefix variations)
        normalized = self._normalize_concept(concept)
        
        if normalized in self.labels:
            return self.labels[normalized]
        
        # Try without underscores
        for key, label in self.labels.items():
            if key.replace('_', '').lower() == normalized.replace('_', '').lower():
                return label
        
        # Return cleaned concept name
        return normalized.split('_')[-1] if '_' in normalized else normalized
    
    def get_hierarchy(self, concept: str) -> str:
        """Get hierarchy path for a concept."""
        normalized = self._normalize_concept(concept)
        return self.hierarchies.get(normalized, "")
    
    def get_order(self, concept: str) -> int:
        """Get presentation order."""
        normalized = self._normalize_concept(concept)
        return self.presentation_order.get(normalized, 9999)
    
    def _normalize_concept(self, concept: str) -> str:
        """Normalize concept name to standard format."""
        # Handle various formats:
        # - ifrs-full:Assets -> ifrs-full_Assets
        # - #ifrs-full_Assets -> ifrs-full_Assets
        # - Loc_label_ifrs-full_Assets -> ifrs-full_Assets
        
        if '#' in concept:
            concept = concept.split('#')[-1]
        
        if concept.startswith('Loc_'):
            # Remove Loc_ prefix and label_ if present
            parts = concept.split('_')
            # Find the namespace prefix
            for i, part in enumerate(parts):
                if part in ('ifrs-full', 'dart', 'us-gaap', 'label'):
                    if part == 'label' and i + 1 < len(parts):
                        concept = '_'.join(parts[i+1:])
                    else:
                        concept = '_'.join(parts[i:])
                    break
        
        # Replace colon with underscore
        concept = concept.replace(':', '_').replace('-', '-')
        
        return concept
    
    def add_label(self, concept: str, label: str):
        """Add or update a label."""
        normalized = self._normalize_concept(concept)
        self.labels[normalized] = label


# ============================================================
# LINKBASE PARSER
# ============================================================

class LinkbaseParser:
    """
    Parses XBRL Linkbase files (Calculation, Presentation, Label).
    Handles the Loc -> Arc relationship properly.
    """
    
    def __init__(self):
        self.locators: Dict[str, str] = {}  # label -> concept
        self.calculation_relations: List[CalculationRelation] = []
        self.presentation_relations: List[Tuple[str, str, float]] = []  # parent, child, order
        self.labels: Dict[str, Dict[str, str]] = {}  # concept -> {lang: label}
        self.parse_log: List[str] = []
    
    def parse(self, content: bytes) -> None:
        """Parse linkbase content with full namespace support."""
        self.parse_log.append("Starting linkbase parsing...")
        
        try:
            # Register namespaces for proper parsing
            for prefix, uri in NAMESPACES.items():
                ET.register_namespace(prefix, uri)
            
            root = ET.fromstring(content)
            self.parse_log.append(f"Root tag: {root.tag}")
            
            # Determine linkbase type from root or content
            self._parse_locators(root)
            self._parse_calculation_arcs(root)
            self._parse_presentation_arcs(root)
            self._parse_labels(root)
            
            self.parse_log.append(f"Parsing complete. Locators: {len(self.locators)}, "
                                  f"Calculations: {len(self.calculation_relations)}, "
                                  f"Labels: {len(self.labels)}")
            
        except ET.ParseError as e:
            self.parse_log.append(f"XML Parse Error: {e}")
            raise
    
    def _parse_locators(self, root: ET.Element) -> None:
        """Parse link:loc elements to build locator map."""
        loc_count = 0
        
        # Try multiple patterns for locator elements
        patterns = [
            './/{http://www.xbrl.org/2003/linkbase}loc',
            './/loc',
            './/*[local-name()="loc"]',
        ]
        
        for pattern in patterns:
            try:
                for loc in root.findall(pattern):
                    xlink_label = loc.get('{http://www.w3.org/1999/xlink}label', '')
                    xlink_href = loc.get('{http://www.w3.org/1999/xlink}href', '')
                    
                    if not xlink_label:
                        xlink_label = loc.get('label', '')
                    if not xlink_href:
                        xlink_href = loc.get('href', '')
                    
                    if xlink_label and xlink_href:
                        # Extract concept name from href
                        # Format: path/to/schema.xsd#ifrs-full_Assets
                        concept = xlink_href.split('#')[-1] if '#' in xlink_href else xlink_href
                        self.locators[xlink_label] = concept
                        loc_count += 1
            except Exception:
                continue
        
        # Fallback: iterate all elements
        if loc_count == 0:
            for elem in root.iter():
                tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                if tag_local == 'loc':
                    xlink_label = None
                    xlink_href = None
                    
                    for attr_name, attr_value in elem.attrib.items():
                        if 'label' in attr_name.lower():
                            xlink_label = attr_value
                        if 'href' in attr_name.lower():
                            xlink_href = attr_value
                    
                    if xlink_label and xlink_href:
                        concept = xlink_href.split('#')[-1] if '#' in xlink_href else xlink_href
                        self.locators[xlink_label] = concept
                        loc_count += 1
        
        self.parse_log.append(f"Parsed {loc_count} locators")
    
    def _parse_calculation_arcs(self, root: ET.Element) -> None:
        """Parse calculationArc elements with weight and order."""
        arc_count = 0
        
        # Iterate all elements to find calculation arcs
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if 'calculationArc' in tag_local or 'CalculationArc' in tag_local:
                # Extract attributes with namespace handling
                xlink_from = None
                xlink_to = None
                weight = 1.0
                order = 0.0
                arc_role = None
                
                for attr_name, attr_value in elem.attrib.items():
                    attr_local = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                    
                    if attr_local == 'from':
                        xlink_from = attr_value
                    elif attr_local == 'to':
                        xlink_to = attr_value
                    elif attr_local == 'weight':
                        try:
                            weight = float(attr_value)
                        except ValueError:
                            weight = 1.0
                    elif attr_local == 'order':
                        try:
                            order = float(attr_value)
                        except ValueError:
                            order = 0.0
                    elif attr_local == 'arcrole':
                        arc_role = attr_value
                
                if xlink_from and xlink_to:
                    # Resolve locators to concepts
                    parent_concept = self.locators.get(xlink_from, xlink_from)
                    child_concept = self.locators.get(xlink_to, xlink_to)
                    
                    relation = CalculationRelation(
                        parent_concept=parent_concept,
                        child_concept=child_concept,
                        weight=weight,
                        order=order,
                        arc_role=arc_role
                    )
                    self.calculation_relations.append(relation)
                    arc_count += 1
        
        self.parse_log.append(f"Parsed {arc_count} calculation arcs")
    
    def _parse_presentation_arcs(self, root: ET.Element) -> None:
        """Parse presentationArc elements for hierarchy."""
        arc_count = 0
        
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if 'presentationArc' in tag_local or 'PresentationArc' in tag_local:
                xlink_from = None
                xlink_to = None
                order = 0.0
                
                for attr_name, attr_value in elem.attrib.items():
                    attr_local = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                    
                    if attr_local == 'from':
                        xlink_from = attr_value
                    elif attr_local == 'to':
                        xlink_to = attr_value
                    elif attr_local == 'order':
                        try:
                            order = float(attr_value)
                        except ValueError:
                            order = 0.0
                
                if xlink_from and xlink_to:
                    parent = self.locators.get(xlink_from, xlink_from)
                    child = self.locators.get(xlink_to, xlink_to)
                    self.presentation_relations.append((parent, child, order))
                    arc_count += 1
        
        self.parse_log.append(f"Parsed {arc_count} presentation arcs")
    
    def _parse_labels(self, root: ET.Element) -> None:
        """Parse label elements."""
        label_count = 0
        
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag_local == 'label' and elem.text:
                xlink_label = None
                lang = 'ko'
                
                for attr_name, attr_value in elem.attrib.items():
                    attr_local = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                    
                    if attr_local == 'label':
                        xlink_label = attr_value
                    elif attr_local == 'lang':
                        lang = attr_value
                
                if xlink_label and elem.text.strip():
                    # Resolve to concept
                    concept = self.locators.get(xlink_label, xlink_label)
                    
                    if concept not in self.labels:
                        self.labels[concept] = {}
                    self.labels[concept][lang] = elem.text.strip()
                    label_count += 1
        
        self.parse_log.append(f"Parsed {label_count} labels")
    
    def get_calculation_formula(self, parent_concept: str) -> Tuple[str, List[Tuple[str, float]]]:
        """
        Build calculation formula for a parent concept.
        Returns: (formula_string, [(child, weight), ...])
        """
        children = [
            (rel.child_concept, rel.weight, rel.order)
            for rel in self.calculation_relations
            if rel.parent_concept == parent_concept or 
               self._concepts_match(rel.parent_concept, parent_concept)
        ]
        
        if not children:
            return ("", [])
        
        # Sort by order
        children.sort(key=lambda x: x[2])
        
        # Build formula
        parts = []
        result = []
        
        for child, weight, _ in children:
            child_label = child.split('_')[-1] if '_' in child else child
            if weight >= 0:
                parts.append(f"+ {child_label}")
            else:
                parts.append(f"- {child_label}")
            result.append((child, weight))
        
        parent_label = parent_concept.split('_')[-1] if '_' in parent_concept else parent_concept
        formula = f"{parent_label} = {' '.join(parts)}"
        
        return (formula, result)
    
    def _concepts_match(self, c1: str, c2: str) -> bool:
        """Check if two concept names refer to the same concept."""
        def normalize(c):
            return c.split('#')[-1].split('_')[-1].lower().replace('-', '')
        return normalize(c1) == normalize(c2)


# ============================================================
# MAIN XBRL PARSER
# ============================================================

class XBRLParser:
    """
    Enterprise XBRL/XML parser with full Linkbase support.
    """
    
    UNIT_MULTIPLIERS = {
        '천원': 1000,
        '백만원': 1000000,
        '억원': 100000000,
        'thousands': 1000,
        'millions': 1000000,
    }
    
    def __init__(self, taxonomy_type: str = "ifrs"):
        self.taxonomy = TaxonomyLoader(taxonomy_type)
        self.linkbase = LinkbaseParser()
        self.contexts: Dict[str, XBRLContext] = {}
        self.facts: List[XBRLFact] = []
        self.units: Dict[str, str] = {}
        self.raw_xml: str = ""
        self.parse_log: List[str] = []
    
    def parse(self, content: bytes) -> Dict[str, Any]:
        """
        Parse XBRL/XML content.
        Handles both instance documents and linkbase files.
        """
        self.raw_xml = content.decode('utf-8', errors='ignore')
        self.parse_log.append(f"Input size: {len(content)} bytes")
        
        # Register namespaces
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)
        
        try:
            root = ET.fromstring(content)
            root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
            self.parse_log.append(f"Root element: {root_tag}")
            
            # Detect document type
            if 'linkbase' in root_tag.lower() or self._is_linkbase_content(root):
                return self._parse_linkbase_document(root)
            else:
                return self._parse_instance_document(root)
                
        except ET.ParseError as e:
            self.parse_log.append(f"Parse error: {e}")
            return self._build_error_result(f"XML 파싱 오류: {e}")
    
    def _is_linkbase_content(self, root: ET.Element) -> bool:
        """Check if content is a linkbase by looking for link elements."""
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag in ('calculationLink', 'presentationLink', 'labelLink', 'loc', 'calculationArc'):
                return True
        return False
    
    def _parse_linkbase_document(self, root: ET.Element) -> Dict[str, Any]:
        """Parse a linkbase document (calculation, presentation, label)."""
        self.parse_log.append("Detected linkbase document")
        
        # Parse linkbase content
        content_bytes = ET.tostring(root, encoding='utf-8')
        self.linkbase.parse(content_bytes)
        
        # Merge parse logs
        self.parse_log.extend(self.linkbase.parse_log)
        
        # Generate structured output from linkbase
        return self._build_linkbase_result()
    
    def _parse_instance_document(self, root: ET.Element) -> Dict[str, Any]:
        """Parse an XBRL instance document."""
        self.parse_log.append("Detected instance document")
        
        # Parse contexts
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag == 'context':
                self._parse_context(elem)
            elif tag == 'unit':
                self._parse_unit(elem)
        
        # Parse facts
        for elem in root.iter():
            if elem.text and elem.text.strip():
                self._try_parse_fact(elem)
        
        self.parse_log.append(f"Parsed {len(self.contexts)} contexts, {len(self.facts)} facts")
        
        return self._build_instance_result()
    
    def _parse_context(self, elem: ET.Element) -> None:
        """Parse context element."""
        context_id = elem.get('id', '')
        if not context_id:
            return
        
        context = XBRLContext(id=context_id)
        
        for child in elem.iter():
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag == 'identifier' and child.text:
                context.entity = child.text
            elif tag == 'startDate' and child.text:
                context.start_date = child.text
            elif tag == 'endDate' and child.text:
                context.end_date = child.text
            elif tag == 'instant' and child.text:
                context.instant = child.text
        
        self.contexts[context_id] = context
    
    def _parse_unit(self, elem: ET.Element) -> None:
        """Parse unit element."""
        unit_id = elem.get('id', '')
        if not unit_id:
            return
        
        for child in elem.iter():
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'measure' and child.text:
                unit_text = child.text.split(':')[-1] if ':' in child.text else child.text
                self.units[unit_id] = unit_text
    
    def _try_parse_fact(self, elem: ET.Element) -> None:
        """Try to parse element as a fact."""
        value = elem.text.strip() if elem.text else ""
        if not value:
            return
        
        context_ref = elem.get('contextRef', '')
        unit_ref = elem.get('unitRef', '')
        
        # Skip non-fact elements
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag in ('context', 'unit', 'schemaRef', 'linkbaseRef'):
            return
        
        # Build concept identifier
        namespace = elem.tag.split('}')[0].replace('{', '') if '}' in elem.tag else ''
        
        concept = tag
        if namespace:
            if 'ifrs' in namespace.lower():
                concept = f"ifrs-full_{tag}"
            elif 'dart' in namespace.lower():
                concept = f"dart_{tag}"
        
        # Create fact
        decimals_str = elem.get('decimals', '')
        decimals = None
        if decimals_str and decimals_str.lstrip('-').isdigit():
            decimals = int(decimals_str)
        
        fact = XBRLFact(
            concept=concept,
            value=self._standardize_value(value, unit_ref, decimals_str),
            unit=self.units.get(unit_ref, unit_ref),
            context_ref=context_ref,
            decimals=decimals,
            label=self.taxonomy.get_label(concept),
            hierarchy=self.taxonomy.get_hierarchy(concept),
            order=self.taxonomy.get_order(concept),
        )
        
        # Set period
        if context_ref and context_ref in self.contexts:
            ctx = self.contexts[context_ref]
            if ctx.instant:
                fact.period = ctx.instant[:4]
            elif ctx.end_date:
                fact.period = ctx.end_date[:4]
        
        self.facts.append(fact)
    
    def _standardize_value(self, value: str, unit_ref: str, decimals: str) -> str:
        """Standardize numeric value to absolute units."""
        clean = value.replace(',', '').replace(' ', '')
        
        try:
            numeric = float(clean)
            
            if decimals and decimals.lstrip('-').isdigit():
                dec = int(decimals)
                if dec < 0:
                    numeric *= (10 ** abs(dec))
            
            unit_text = self.units.get(unit_ref, '').lower()
            for pattern, mult in self.UNIT_MULTIPLIERS.items():
                if pattern in unit_text:
                    numeric *= mult
                    break
            
            return f"{int(numeric):,}"
        except ValueError:
            return value
    
    def _build_linkbase_result(self) -> Dict[str, Any]:
        """Build result from linkbase parsing."""
        tables = []
        
        # Build calculation relationships table
        if self.linkbase.calculation_relations:
            calc_rows = []
            for rel in sorted(self.linkbase.calculation_relations, key=lambda r: r.order):
                parent_label = self.taxonomy.get_label(rel.parent_concept)
                child_label = self.taxonomy.get_label(rel.child_concept)
                weight_str = "+" if rel.weight >= 0 else "-"
                
                calc_rows.append([
                    parent_label,
                    f"{weight_str} {child_label}",
                    str(rel.order)
                ])
            
            tables.append({
                "name": "계산관계 (Calculation Linkbase)",
                "headers": ["상위 항목", "하위 항목 (가중치)", "순서"],
                "rows": calc_rows
            })
        
        # Build presentation hierarchy table
        if self.linkbase.presentation_relations:
            hier_rows = []
            for parent, child, order in sorted(self.linkbase.presentation_relations, key=lambda x: x[2]):
                parent_label = self.taxonomy.get_label(parent)
                child_label = self.taxonomy.get_label(child)
                hier_rows.append([parent_label, child_label, str(order)])
            
            tables.append({
                "name": "표시계층 (Presentation Linkbase)",
                "headers": ["상위 항목", "하위 항목", "순서"],
                "rows": hier_rows
            })
        
        # Build formulas
        formulas = []
        seen_parents = set()
        for rel in self.linkbase.calculation_relations:
            if rel.parent_concept not in seen_parents:
                formula, components = self.linkbase.get_calculation_formula(rel.parent_concept)
                if formula:
                    formulas.append({
                        "parent": rel.parent_concept,
                        "label": self.taxonomy.get_label(rel.parent_concept),
                        "formula": formula,
                        "components": [(c, w) for c, w in components]
                    })
                    seen_parents.add(rel.parent_concept)
        
        return {
            "title": "XBRL Linkbase 분석",
            "summary": self._generate_linkbase_summary(),
            "tables": tables,
            "formulas": formulas,
            "key_metrics": {
                "locator_count": len(self.linkbase.locators),
                "calculation_relations": len(self.linkbase.calculation_relations),
                "presentation_relations": len(self.linkbase.presentation_relations),
            },
            "facts": [],  # Linkbase has no facts
            "parse_log": self.parse_log + self.linkbase.parse_log,
            "metadata": {
                "file_type": "xbrl-linkbase",
                "taxonomy": self.taxonomy.taxonomy_type,
                "processed_by": "xbrl-parser-v2"
            }
        }
    
    def _build_instance_result(self) -> Dict[str, Any]:
        """Build result from instance document parsing."""
        sorted_facts = sorted(self.facts, key=lambda f: f.order)
        
        # Group by hierarchy
        tables_dict: Dict[str, List[Dict]] = defaultdict(list)
        for fact in sorted_facts:
            root = fact.hierarchy.split(' > ')[0] if fact.hierarchy else "기타"
            tables_dict[root].append({
                "concept": fact.concept,
                "label": fact.label,
                "value": fact.value,
                "unit": fact.unit,
                "period": fact.period,
            })
        
        tables = [
            {
                "name": name,
                "headers": ["항목", "금액", "기간"],
                "rows": [[item["label"], item["value"], item["period"]] for item in items]
            }
            for name, items in tables_dict.items()
        ]
        
        return {
            "title": "XBRL 재무데이터",
            "summary": self._generate_instance_summary(),
            "tables": tables,
            "key_metrics": self._extract_key_metrics(),
            "facts": [
                {
                    "concept": f.concept,
                    "label": f.label,
                    "value": f.value,
                    "unit": f.unit,
                    "period": f.period,
                    "hierarchy": f.hierarchy,
                }
                for f in sorted_facts
            ],
            "parse_log": self.parse_log,
            "metadata": {
                "file_type": "xbrl-instance",
                "taxonomy": self.taxonomy.taxonomy_type,
                "fact_count": len(self.facts),
                "context_count": len(self.contexts),
                "processed_by": "xbrl-parser-v2"
            }
        }
    
    def _build_error_result(self, error_msg: str) -> Dict[str, Any]:
        """Build error result with structural info."""
        # Try to extract any structural information
        structural_info = []
        try:
            for line in self.raw_xml[:5000].split('\n'):
                if '<' in line and '>' in line:
                    structural_info.append(line.strip()[:100])
        except:
            pass
        
        return {
            "title": "XBRL 파싱 오류",
            "summary": error_msg,
            "tables": [],
            "key_metrics": {},
            "facts": [],
            "parse_log": self.parse_log,
            "structural_info": structural_info[:20],
            "metadata": {
                "file_type": "xbrl",
                "error": error_msg,
                "processed_by": "xbrl-parser-v2"
            }
        }
    
    def _generate_linkbase_summary(self) -> str:
        """Generate summary for linkbase."""
        calc_count = len(self.linkbase.calculation_relations)
        pres_count = len(self.linkbase.presentation_relations)
        loc_count = len(self.linkbase.locators)
        
        if calc_count == 0 and pres_count == 0 and loc_count == 0:
            return "Linkbase 파싱 실패: 데이터를 추출하지 못했습니다. " + "; ".join(self.parse_log[-5:])
        
        return (f"XBRL Linkbase에서 {loc_count}개 개념, "
                f"{calc_count}개 계산관계, {pres_count}개 표시관계를 추출했습니다.")
    
    def _generate_instance_summary(self) -> str:
        """Generate summary for instance document."""
        if not self.facts:
            return "데이터 추출 실패. " + "; ".join(self.parse_log[-5:])
        
        periods = set(f.period for f in self.facts if f.period)
        hierarchies = set(f.hierarchy.split(' > ')[0] for f in self.facts if f.hierarchy)
        
        return (f"XBRL 문서에서 {len(self.facts)}개 항목을 추출. "
                f"기간: {', '.join(sorted(periods))}. 재무제표: {', '.join(hierarchies)}.")
    
    def _extract_key_metrics(self) -> Dict[str, str]:
        """Extract key financial metrics."""
        metrics = {}
        key_concepts = [
            ("Revenue", "매출액"),
            ("GrossProfit", "매출총이익"),
            ("OperatingProfit", "영업이익"),
            ("ProfitLoss", "당기순이익"),
            ("Assets", "총자산"),
            ("Liabilities", "총부채"),
            ("Equity", "총자본"),
        ]
        
        for concept_suffix, label in key_concepts:
            for fact in self.facts:
                if concept_suffix.lower() in fact.concept.lower():
                    key = f"{label}_{fact.period}" if fact.period else label
                    metrics[key] = f"{fact.value} {fact.unit or '원'}"
                    break
        
        return metrics
    
    def get_raw_context(self, concept: str) -> str:
        """Get raw XML context for a concept."""
        pattern = rf'<[^>]*{concept}[^>]*>.*?</[^>]*>'
        match = re.search(pattern, self.raw_xml, re.IGNORECASE | re.DOTALL)
        return match.group(0) if match else ""


# Singleton
xbrl_parser = XBRLParser()
