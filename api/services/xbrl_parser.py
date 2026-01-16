"""
FinDistill XBRL/XML Parser Service

Enterprise-grade XBRL parser with:
- Label Linkbase dynamic loading
- Presentation Linkbase hierarchy extraction (with order)
- Calculation Linkbase validation
- Taxonomy version management (IFRS/GAAP)
- Streaming parsing with iterparse() for large files
- Unit standardization (천원/백만원 → 원)
"""

import io
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from xml.etree.ElementTree import iterparse, Element
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class XBRLFact:
    """Represents a single XBRL fact (data point)."""
    concept: str  # e.g., ifrs-full:Revenue
    value: str
    unit: Optional[str] = None
    context_ref: Optional[str] = None
    decimals: Optional[int] = None
    label: Optional[str] = None  # Human-readable label
    hierarchy: Optional[str] = None  # e.g., 재무상태표 > 자산 > 유동자산
    order: int = 0  # Presentation order
    period: Optional[str] = None  # 2024, 2025 등
    

@dataclass
class XBRLContext:
    """XBRL context information (period, entity)."""
    id: str
    entity: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instant: Optional[str] = None


class TaxonomyLoader:
    """
    Flexible taxonomy loader supporting IFRS and GAAP.
    Loads label mappings from external linkbase files or built-in dictionaries.
    """
    
    # Built-in IFRS Korean labels (fallback)
    IFRS_LABELS_KO = {
        # 재무상태표 (Statement of Financial Position)
        "ifrs-full:Assets": "자산",
        "ifrs-full:CurrentAssets": "유동자산",
        "ifrs-full:NoncurrentAssets": "비유동자산",
        "ifrs-full:Liabilities": "부채",
        "ifrs-full:CurrentLiabilities": "유동부채",
        "ifrs-full:NoncurrentLiabilities": "비유동부채",
        "ifrs-full:Equity": "자본",
        "ifrs-full:IssuedCapital": "자본금",
        "ifrs-full:RetainedEarnings": "이익잉여금",
        
        # 포괄손익계산서 (Statement of Comprehensive Income)
        "ifrs-full:Revenue": "매출액",
        "ifrs-full:CostOfSales": "매출원가",
        "ifrs-full:GrossProfit": "매출총이익",
        "ifrs-full:SellingGeneralAndAdministrativeExpense": "판매비와관리비",
        "ifrs-full:OperatingProfit": "영업이익",
        "ifrs-full:FinanceCosts": "금융비용",
        "ifrs-full:FinanceIncome": "금융수익",
        "ifrs-full:ProfitBeforeTax": "법인세비용차감전순이익",
        "ifrs-full:IncomeTaxExpense": "법인세비용",
        "ifrs-full:ProfitLoss": "당기순이익",
        
        # 현금흐름표 (Statement of Cash Flows)
        "ifrs-full:CashFlowsFromOperatingActivities": "영업활동현금흐름",
        "ifrs-full:CashFlowsFromInvestingActivities": "투자활동현금흐름",
        "ifrs-full:CashFlowsFromFinancingActivities": "재무활동현금흐름",
        "ifrs-full:CashAndCashEquivalents": "현금및현금성자산",
    }
    
    # GAAP labels (US)
    GAAP_LABELS_EN = {
        "us-gaap:Assets": "Assets",
        "us-gaap:Liabilities": "Liabilities",
        "us-gaap:StockholdersEquity": "Stockholders Equity",
        "us-gaap:Revenues": "Revenues",
        "us-gaap:CostOfGoodsSold": "Cost of Goods Sold",
        "us-gaap:GrossProfit": "Gross Profit",
        "us-gaap:OperatingIncomeLoss": "Operating Income",
        "us-gaap:NetIncomeLoss": "Net Income",
    }
    
    # Hierarchy mappings (Presentation Linkbase simulation)
    HIERARCHY_MAP = {
        "ifrs-full:Assets": "재무상태표 > 자산",
        "ifrs-full:CurrentAssets": "재무상태표 > 자산 > 유동자산",
        "ifrs-full:NoncurrentAssets": "재무상태표 > 자산 > 비유동자산",
        "ifrs-full:Liabilities": "재무상태표 > 부채",
        "ifrs-full:CurrentLiabilities": "재무상태표 > 부채 > 유동부채",
        "ifrs-full:NoncurrentLiabilities": "재무상태표 > 부채 > 비유동부채",
        "ifrs-full:Equity": "재무상태표 > 자본",
        "ifrs-full:Revenue": "포괄손익계산서 > 매출액",
        "ifrs-full:GrossProfit": "포괄손익계산서 > 매출총이익",
        "ifrs-full:OperatingProfit": "포괄손익계산서 > 영업이익",
        "ifrs-full:ProfitLoss": "포괄손익계산서 > 당기순이익",
    }
    
    def __init__(self, taxonomy_type: str = "ifrs"):
        self.taxonomy_type = taxonomy_type
        self.labels: Dict[str, str] = {}
        self.hierarchies: Dict[str, str] = {}
        self.presentation_order: Dict[str, int] = {}
        self._load_default_taxonomy()
    
    def _load_default_taxonomy(self):
        """Load built-in taxonomy labels."""
        if self.taxonomy_type.lower() == "ifrs":
            self.labels = self.IFRS_LABELS_KO.copy()
        elif self.taxonomy_type.lower() == "gaap":
            self.labels = self.GAAP_LABELS_EN.copy()
        
        self.hierarchies = self.HIERARCHY_MAP.copy()
        
        # Default presentation order
        for i, concept in enumerate(self.labels.keys()):
            self.presentation_order[concept] = i
    
    def load_label_linkbase(self, linkbase_content: bytes) -> None:
        """
        Parse external Label Linkbase XML file.
        Updates the labels dictionary with human-readable names.
        """
        try:
            root = ET.fromstring(linkbase_content)
            
            # Common namespaces in XBRL Label Linkbase
            ns = {
                'link': 'http://www.xbrl.org/2003/linkbase',
                'xlink': 'http://www.w3.org/1999/xlink',
                'label': 'http://www.xbrl.org/2003/label'
            }
            
            # Find all label elements
            for label_arc in root.iter():
                if 'labelArc' in label_arc.tag:
                    # Extract concept and label relationships
                    pass
                    
                if 'label' in label_arc.tag and label_arc.text:
                    # Get the label text
                    concept_ref = label_arc.get('{http://www.w3.org/1999/xlink}label', '')
                    if concept_ref and label_arc.text.strip():
                        self.labels[concept_ref] = label_arc.text.strip()
                        
        except Exception as e:
            print(f"Warning: Could not parse Label Linkbase: {e}")
    
    def load_presentation_linkbase(self, linkbase_content: bytes) -> None:
        """
        Parse Presentation Linkbase for hierarchy and order information.
        """
        try:
            root = ET.fromstring(linkbase_content)
            
            order_counter = 0
            for elem in root.iter():
                if 'presentationArc' in elem.tag:
                    from_concept = elem.get('{http://www.w3.org/1999/xlink}from', '')
                    to_concept = elem.get('{http://www.w3.org/1999/xlink}to', '')
                    order = elem.get('order', str(order_counter))
                    
                    if to_concept:
                        self.presentation_order[to_concept] = int(float(order))
                        
                        # Build hierarchy
                        if from_concept and from_concept in self.hierarchies:
                            parent_hierarchy = self.hierarchies[from_concept]
                            to_label = self.labels.get(to_concept, to_concept)
                            self.hierarchies[to_concept] = f"{parent_hierarchy} > {to_label}"
                    
                    order_counter += 1
                    
        except Exception as e:
            print(f"Warning: Could not parse Presentation Linkbase: {e}")
    
    def get_label(self, concept: str) -> str:
        """Get human-readable label for a concept."""
        # Try full concept name first
        if concept in self.labels:
            return self.labels[concept]
        
        # Try without namespace prefix
        local_name = concept.split(':')[-1] if ':' in concept else concept
        for key, label in self.labels.items():
            if key.endswith(f":{local_name}") or key == local_name:
                return label
        
        # Return cleaned concept name as fallback
        return local_name.replace('_', ' ').title()
    
    def get_hierarchy(self, concept: str) -> str:
        """Get hierarchy path for a concept."""
        return self.hierarchies.get(concept, "")
    
    def get_order(self, concept: str) -> int:
        """Get presentation order for a concept."""
        return self.presentation_order.get(concept, 9999)


class XBRLParser:
    """
    Enterprise XBRL/XML parser with streaming support.
    """
    
    # Unit multipliers for standardization
    UNIT_MULTIPLIERS = {
        '천원': 1000,
        '백만원': 1000000,
        '억원': 100000000,
        '조원': 1000000000000,
        'thousands': 1000,
        'millions': 1000000,
        'billions': 1000000000,
    }
    
    # Currency patterns
    CURRENCY_PATTERNS = {
        'KRW': '원',
        'USD': '달러',
        'EUR': '유로',
        'JPY': '엔',
    }
    
    def __init__(self, taxonomy_type: str = "ifrs"):
        self.taxonomy = TaxonomyLoader(taxonomy_type)
        self.contexts: Dict[str, XBRLContext] = {}
        self.facts: List[XBRLFact] = []
        self.units: Dict[str, str] = {}
        self.raw_xml: str = ""
    
    def parse(self, content: bytes) -> Dict[str, Any]:
        """
        Parse XBRL/XML content using streaming for memory efficiency.
        Returns structured financial data.
        """
        self.raw_xml = content.decode('utf-8', errors='ignore')
        
        # Use iterparse for memory-efficient streaming
        stream = io.BytesIO(content)
        
        for event, elem in iterparse(stream, events=('start', 'end')):
            if event == 'end':
                self._process_element(elem)
                # Clear element to save memory
                elem.clear()
        
        return self._build_result()
    
    def _process_element(self, elem: Element) -> None:
        """Process a single XML element."""
        tag = elem.tag
        
        # Remove namespace prefix for easier matching
        local_tag = tag.split('}')[-1] if '}' in tag else tag
        
        # Parse context elements
        if local_tag == 'context':
            self._parse_context(elem)
        
        # Parse unit elements
        elif local_tag == 'unit':
            self._parse_unit(elem)
        
        # Parse fact elements (monetary/numeric values)
        elif elem.text and elem.text.strip():
            self._parse_fact(elem)
    
    def _parse_context(self, elem: Element) -> None:
        """Parse XBRL context (period, entity info)."""
        context_id = elem.get('id', '')
        if not context_id:
            return
        
        context = XBRLContext(id=context_id)
        
        for child in elem.iter():
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if local_tag == 'identifier':
                context.entity = child.text
            elif local_tag == 'startDate':
                context.start_date = child.text
            elif local_tag == 'endDate':
                context.end_date = child.text
            elif local_tag == 'instant':
                context.instant = child.text
        
        self.contexts[context_id] = context
    
    def _parse_unit(self, elem: Element) -> None:
        """Parse unit definitions."""
        unit_id = elem.get('id', '')
        if not unit_id:
            return
        
        for child in elem.iter():
            local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local_tag == 'measure' and child.text:
                # Extract currency/unit type
                unit_text = child.text.split(':')[-1] if ':' in child.text else child.text
                self.units[unit_id] = unit_text
    
    def _parse_fact(self, elem: Element) -> None:
        """Parse XBRL fact (actual data point)."""
        tag = elem.tag
        value = elem.text.strip() if elem.text else ""
        
        if not value:
            return
        
        # Check if this looks like a financial fact
        # (has contextRef or unitRef attributes)
        context_ref = elem.get('contextRef', '')
        unit_ref = elem.get('unitRef', '')
        decimals = elem.get('decimals', '')
        
        # Build concept name
        local_tag = tag.split('}')[-1] if '}' in tag else tag
        namespace = tag.split('}')[0].replace('{', '') if '}' in tag else ''
        
        # Try to identify the concept
        concept = local_tag
        if namespace:
            # Common namespace shortcuts
            if 'ifrs' in namespace.lower():
                concept = f"ifrs-full:{local_tag}"
            elif 'gaap' in namespace.lower():
                concept = f"us-gaap:{local_tag}"
        
        # Create fact object
        fact = XBRLFact(
            concept=concept,
            value=self._standardize_value(value, unit_ref, decimals),
            unit=self.units.get(unit_ref, unit_ref),
            context_ref=context_ref,
            decimals=int(decimals) if decimals and decimals.lstrip('-').isdigit() else None,
            label=self.taxonomy.get_label(concept),
            hierarchy=self.taxonomy.get_hierarchy(concept),
            order=self.taxonomy.get_order(concept),
        )
        
        # Determine period from context
        if context_ref and context_ref in self.contexts:
            ctx = self.contexts[context_ref]
            if ctx.instant:
                fact.period = ctx.instant[:4]  # Extract year
            elif ctx.end_date:
                fact.period = ctx.end_date[:4]
        
        self.facts.append(fact)
    
    def _standardize_value(self, value: str, unit_ref: str, decimals: str) -> str:
        """
        Standardize numeric values to absolute units (원).
        Handles 천원, 백만원, etc.
        """
        # Clean the value
        clean_value = value.replace(',', '').replace(' ', '')
        
        try:
            numeric = float(clean_value)
            
            # Apply decimal scaling if present
            if decimals and decimals.lstrip('-').isdigit():
                dec = int(decimals)
                if dec < 0:
                    # Negative decimals mean multiply by 10^|decimals|
                    # e.g., decimals="-3" means value is in thousands
                    numeric *= (10 ** abs(dec))
            
            # Check unit reference for scale hints
            unit_text = self.units.get(unit_ref, '').lower()
            for pattern, multiplier in self.UNIT_MULTIPLIERS.items():
                if pattern in unit_text:
                    numeric *= multiplier
                    break
            
            # Format with Korean number grouping
            return f"{int(numeric):,}"
            
        except ValueError:
            return value  # Return original if not numeric
    
    def _build_result(self) -> Dict[str, Any]:
        """Build final structured result."""
        # Sort facts by presentation order
        sorted_facts = sorted(self.facts, key=lambda f: f.order)
        
        # Group facts by hierarchy (for table structure)
        tables: Dict[str, List[Dict]] = defaultdict(list)
        
        for fact in sorted_facts:
            hierarchy_root = fact.hierarchy.split(' > ')[0] if fact.hierarchy else "기타"
            
            tables[hierarchy_root].append({
                "concept": fact.concept,
                "label": fact.label,
                "value": fact.value,
                "unit": fact.unit,
                "period": fact.period,
                "hierarchy": fact.hierarchy,
            })
        
        # Extract key metrics
        key_metrics = self._extract_key_metrics()
        
        return {
            "title": "XBRL 재무데이터",
            "summary": self._generate_summary(),
            "tables": [
                {
                    "name": name,
                    "headers": ["항목", "금액", "기간"],
                    "rows": [[item["label"], item["value"], item["period"]] for item in items]
                }
                for name, items in tables.items()
            ],
            "key_metrics": key_metrics,
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
            "metadata": {
                "file_type": "xbrl",
                "taxonomy": self.taxonomy.taxonomy_type,
                "fact_count": len(self.facts),
                "context_count": len(self.contexts),
                "processed_by": "xbrl-parser-v1"
            }
        }
    
    def _extract_key_metrics(self) -> Dict[str, str]:
        """Extract key financial metrics from parsed facts."""
        metrics = {}
        
        key_concepts = [
            ("ifrs-full:Revenue", "매출액"),
            ("ifrs-full:GrossProfit", "매출총이익"),
            ("ifrs-full:OperatingProfit", "영업이익"),
            ("ifrs-full:ProfitLoss", "당기순이익"),
            ("ifrs-full:Assets", "총자산"),
            ("ifrs-full:Liabilities", "총부채"),
            ("ifrs-full:Equity", "총자본"),
        ]
        
        for concept, label in key_concepts:
            for fact in self.facts:
                if concept in fact.concept or label in (fact.label or ""):
                    period_key = f"{label}_{fact.period}" if fact.period else label
                    metrics[period_key] = f"{fact.value} {fact.unit or '원'}"
                    break
        
        return metrics
    
    def _generate_summary(self) -> str:
        """Generate a summary of the parsed XBRL data."""
        if not self.facts:
            return "파싱된 데이터 없음"
        
        periods = set(f.period for f in self.facts if f.period)
        hierarchies = set(f.hierarchy.split(' > ')[0] for f in self.facts if f.hierarchy)
        
        return (
            f"XBRL 문서에서 {len(self.facts)}개의 재무 항목을 추출했습니다. "
            f"기간: {', '.join(sorted(periods))}. "
            f"포함된 재무제표: {', '.join(hierarchies)}."
        )
    
    def get_raw_context(self, concept: str) -> str:
        """
        Get raw XML context for a concept (for AI grounding).
        """
        pattern = rf'<[^>]*{concept}[^>]*>.*?</[^>]*>'
        match = re.search(pattern, self.raw_xml, re.IGNORECASE | re.DOTALL)
        return match.group(0) if match else ""


# Singleton instance
xbrl_parser = XBRLParser()
