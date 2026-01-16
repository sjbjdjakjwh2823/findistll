"""
FinDistill Label Linkbase Parser

Enterprise-grade parser for XBRL Label Linkbase (_lab.xml) files.

Features:
- Complete Locator → LabelArc → Label reference chain resolution
- Multi-role label extraction (label, terseLabel, documentation)
- Semantic Q&A generation for AI training
- Namespace-grouped Markdown table output
- Universal compatibility (US-GAAP, IFRS, DART, etc.)
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
import xml.etree.ElementTree as ET


# ============================================================
# NAMESPACES
# ============================================================

XBRL_NAMESPACES = {
    'link': 'http://www.xbrl.org/2003/linkbase',
    'xlink': 'http://www.w3.org/1999/xlink',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'xml': 'http://www.w3.org/XML/1998/namespace',
}

# Label roles in priority order
LABEL_ROLES = {
    'http://www.xbrl.org/2003/role/label': 'label',
    'http://www.xbrl.org/2003/role/terseLabel': 'terseLabel',
    'http://www.xbrl.org/2003/role/verboseLabel': 'verboseLabel',
    'http://www.xbrl.org/2003/role/documentation': 'documentation',
    'http://www.xbrl.org/2003/role/definitionGuidance': 'definitionGuidance',
    'http://www.xbrl.org/2003/role/disclosureGuidance': 'disclosureGuidance',
    'http://www.xbrl.org/2003/role/presentationGuidance': 'presentationGuidance',
    'http://www.xbrl.org/2003/role/totalLabel': 'totalLabel',
    'http://www.xbrl.org/2003/role/periodStartLabel': 'periodStartLabel',
    'http://www.xbrl.org/2003/role/periodEndLabel': 'periodEndLabel',
}


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class LabelEntry:
    """Represents a complete label mapping entry."""
    concept: str  # Original concept name (e.g., us-gaap_Assets)
    namespace: str  # Namespace prefix (e.g., us-gaap, ifrs, dei)
    local_name: str  # Local part (e.g., Assets)
    labels: Dict[str, Dict[str, str]] = field(default_factory=dict)  # {role: {lang: text}}
    raw_xml_loc: str = ""  # Raw XML for locator
    raw_xml_label: str = ""  # Raw XML for label


# ============================================================
# LABEL LINKBASE PARSER
# ============================================================

class LabelLinkbaseParser:
    """
    Parses XBRL Label Linkbase (_lab.xml) files with complete reference chain resolution.
    """
    
    def __init__(self):
        # Locators: xlink:label -> concept href
        self.locators: Dict[str, str] = {}
        
        # Label resources: xlink:label -> {role, lang, text}
        self.label_resources: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        
        # Label arcs: from (locator label) -> to (resource label)
        self.label_arcs: List[Tuple[str, str]] = []
        
        # Final mapped entries
        self.entries: Dict[str, LabelEntry] = {}  # concept -> LabelEntry
        
        # Parse logs
        self.parse_log: List[str] = []
    
    def parse(self, content: bytes) -> Dict[str, Any]:
        """
        Parse label linkbase content with complete reference chain resolution.
        """
        self.parse_log.append(f"Starting label linkbase parsing ({len(content)} bytes)")
        
        try:
            # Register namespaces
            for prefix, uri in XBRL_NAMESPACES.items():
                ET.register_namespace(prefix, uri)
            
            root = ET.fromstring(content)
            self.parse_log.append(f"Root element: {root.tag}")
            
            # Step 1: Parse all locators
            self._parse_locators(root)
            
            # Step 2: Parse all label resources
            self._parse_label_resources(root)
            
            # Step 3: Parse label arcs (connects locators to labels)
            self._parse_label_arcs(root)
            
            # Step 4: Build complete reference chain
            self._build_reference_chain()
            
            self.parse_log.append(
                f"Parse complete: {len(self.locators)} locators, "
                f"{len(self.label_resources)} label resources, "
                f"{len(self.label_arcs)} arcs, "
                f"{len(self.entries)} mapped concepts"
            )
            
            return self._build_result()
            
        except ET.ParseError as e:
            self.parse_log.append(f"XML Parse Error: {e}")
            return self._build_error_result(str(e))
    
    def _parse_locators(self, root: ET.Element) -> None:
        """Parse link:loc elements to build locator map."""
        loc_count = 0
        
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag_local == 'loc':
                xlink_label = self._get_xlink_attr(elem, 'label')
                xlink_href = self._get_xlink_attr(elem, 'href')
                
                if xlink_label and xlink_href:
                    # Extract concept from href: path/schema.xsd#us-gaap_Assets
                    concept = xlink_href.split('#')[-1] if '#' in xlink_href else xlink_href
                    self.locators[xlink_label] = concept
                    loc_count += 1
        
        self.parse_log.append(f"Parsed {loc_count} locators")
    
    def _parse_label_resources(self, root: ET.Element) -> None:
        """Parse link:label elements (the actual text resources)."""
        label_count = 0
        
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag_local == 'label' and elem.text:
                xlink_label = self._get_xlink_attr(elem, 'label')
                xlink_role = self._get_xlink_attr(elem, 'role')
                xml_lang = elem.get('{http://www.w3.org/XML/1998/namespace}lang', 'en')
                
                if not xml_lang:
                    xml_lang = elem.get('lang', 'en')
                
                if xlink_label:
                    role_short = LABEL_ROLES.get(xlink_role, 'label')
                    
                    self.label_resources[xlink_label].append({
                        'role': role_short,
                        'role_uri': xlink_role or '',
                        'lang': xml_lang,
                        'text': elem.text.strip(),
                        'raw_xml': ET.tostring(elem, encoding='unicode')[:500]
                    })
                    label_count += 1
        
        self.parse_log.append(f"Parsed {label_count} label resources")
    
    def _parse_label_arcs(self, root: ET.Element) -> None:
        """Parse link:labelArc elements that connect locators to labels."""
        arc_count = 0
        
        for elem in root.iter():
            tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag_local == 'labelArc':
                xlink_from = self._get_xlink_attr(elem, 'from')
                xlink_to = self._get_xlink_attr(elem, 'to')
                
                if xlink_from and xlink_to:
                    self.label_arcs.append((xlink_from, xlink_to))
                    arc_count += 1
        
        self.parse_log.append(f"Parsed {arc_count} label arcs")
    
    def _build_reference_chain(self) -> None:
        """
        Build complete reference chain: Locator → LabelArc → Label
        """
        # For each arc, connect locator concept to label resource
        for from_label, to_label in self.label_arcs:
            # Get concept from locator
            concept = self.locators.get(from_label)
            if not concept:
                continue
            
            # Get label resources
            label_resources = self.label_resources.get(to_label, [])
            if not label_resources:
                continue
            
            # Create or update entry
            if concept not in self.entries:
                namespace, local_name = self._split_concept(concept)
                self.entries[concept] = LabelEntry(
                    concept=concept,
                    namespace=namespace,
                    local_name=local_name,
                )
            
            entry = self.entries[concept]
            
            # Add labels by role
            for resource in label_resources:
                role = resource['role']
                lang = resource['lang']
                text = resource['text']
                
                if role not in entry.labels:
                    entry.labels[role] = {}
                entry.labels[role][lang] = text
                
                # Store raw XML for first label
                if not entry.raw_xml_label:
                    entry.raw_xml_label = resource.get('raw_xml', '')
        
        # Also handle direct locator-to-label mappings (some files skip arcs)
        if not self.label_arcs:
            self.parse_log.append("No arcs found, attempting direct mapping...")
            self._fallback_direct_mapping()
        
        self.parse_log.append(f"Built {len(self.entries)} concept entries")
    
    def _fallback_direct_mapping(self) -> None:
        """Fallback: try direct locator label matching to resource labels."""
        for loc_label, concept in self.locators.items():
            # Try to find matching label resource
            for res_label, resources in self.label_resources.items():
                # Check if labels are related
                if loc_label in res_label or res_label in loc_label:
                    if concept not in self.entries:
                        namespace, local_name = self._split_concept(concept)
                        self.entries[concept] = LabelEntry(
                            concept=concept,
                            namespace=namespace,
                            local_name=local_name,
                        )
                    
                    entry = self.entries[concept]
                    for resource in resources:
                        role = resource['role']
                        lang = resource['lang']
                        if role not in entry.labels:
                            entry.labels[role] = {}
                        entry.labels[role][lang] = resource['text']
    
    def _split_concept(self, concept: str) -> Tuple[str, str]:
        """Split concept into namespace and local name."""
        if '_' in concept:
            parts = concept.split('_')
            namespace = parts[0]
            local_name = '_'.join(parts[1:])
        elif ':' in concept:
            parts = concept.split(':')
            namespace = parts[0]
            local_name = ':'.join(parts[1:])
        else:
            namespace = 'unknown'
            local_name = concept
        
        return namespace, local_name
    
    def _get_xlink_attr(self, elem: ET.Element, attr: str) -> Optional[str]:
        """Get xlink namespaced attribute."""
        # Try with namespace
        value = elem.get(f'{{http://www.w3.org/1999/xlink}}{attr}')
        if value:
            return value
        
        # Try without namespace (some files)
        return elem.get(attr)
    
    def _build_result(self) -> Dict[str, Any]:
        """Build complete parsing result."""
        # Group entries by namespace
        by_namespace: Dict[str, List[LabelEntry]] = defaultdict(list)
        for entry in self.entries.values():
            by_namespace[entry.namespace].append(entry)
        
        # Build tables
        tables = []
        for namespace, entries in sorted(by_namespace.items()):
            rows = []
            for entry in sorted(entries, key=lambda e: e.local_name):
                label = self._get_preferred_label(entry, 'en')
                doc = self._get_documentation(entry, 'en')
                rows.append([entry.concept, label, doc[:200] + "..." if len(doc) > 200 else doc])
            
            tables.append({
                "name": f"Namespace: {namespace}",
                "headers": ["태그(Concept)", "표준 레이블(Label)", "정의(Documentation)"],
                "rows": rows
            })
        
        # Build facts-like structure for compatibility
        facts = []
        for entry in self.entries.values():
            label = self._get_preferred_label(entry)
            doc = self._get_documentation(entry)
            
            facts.append({
                "concept": entry.concept,
                "namespace": entry.namespace,
                "local_name": entry.local_name,
                "label": label,
                "labels_all": entry.labels,
                "documentation": doc,
            })
        
        return {
            "title": "XBRL Label Linkbase 매핑",
            "summary": self._generate_summary(),
            "tables": tables,
            "facts": facts,
            "key_metrics": {
                "total_concepts": len(self.entries),
                "namespaces": list(by_namespace.keys()),
                "locators_parsed": len(self.locators),
                "labels_parsed": sum(len(v) for v in self.label_resources.values()),
                "arcs_parsed": len(self.label_arcs),
            },
            "parse_log": self.parse_log,
            "metadata": {
                "file_type": "xbrl-label-linkbase",
                "processed_by": "label-linkbase-parser-v1"
            }
        }
    
    def _build_error_result(self, error: str) -> Dict[str, Any]:
        """Build error result with debugging info."""
        return {
            "title": "Label Linkbase 파싱 오류",
            "summary": f"오류: {error}",
            "tables": [],
            "facts": [],
            "key_metrics": {},
            "parse_log": self.parse_log,
            "metadata": {
                "file_type": "xbrl-label-linkbase",
                "error": error,
                "processed_by": "label-linkbase-parser-v1"
            }
        }
    
    def _get_preferred_label(self, entry: LabelEntry, lang: str = 'en') -> str:
        """Get preferred label (standard > terse > verbose)."""
        priority = ['label', 'terseLabel', 'verboseLabel', 'totalLabel']
        
        for role in priority:
            if role in entry.labels:
                # Prefer requested language
                if lang in entry.labels[role]:
                    return entry.labels[role][lang]
                # Fall back to any language
                for text in entry.labels[role].values():
                    return text
        
        return entry.local_name  # Fallback
    
    def _get_documentation(self, entry: LabelEntry, lang: str = 'en') -> str:
        """Get documentation text if available."""
        doc_roles = ['documentation', 'definitionGuidance']
        
        for role in doc_roles:
            if role in entry.labels:
                if lang in entry.labels[role]:
                    return entry.labels[role][lang]
                for text in entry.labels[role].values():
                    return text
        
        return ""
    
    def _generate_summary(self) -> str:
        """Generate parsing summary."""
        if not self.entries:
            return "레이블 매핑 추출 실패. " + "; ".join(self.parse_log[-5:])
        
        ns_counts = defaultdict(int)
        for entry in self.entries.values():
            ns_counts[entry.namespace] += 1
        
        ns_summary = ", ".join(f"{ns}: {count}개" for ns, count in sorted(ns_counts.items()))
        
        return (
            f"Label Linkbase에서 {len(self.entries)}개 개념을 추출했습니다. "
            f"네임스페이스별: {ns_summary}"
        )
    
    def to_jsonl(self, data: Dict[str, Any]) -> str:
        """Generate semantic Q&A JSONL for AI training."""
        lines = []
        
        for fact in data.get("facts", []):
            concept = fact.get("concept", "")
            label = fact.get("label", "")
            doc = fact.get("documentation", "")
            namespace = fact.get("namespace", "")
            
            if not concept or not label:
                continue
            
            # Q1: Tag meaning (forward lookup)
            qa1 = {
                "instruction": f"XBRL 태그 [{concept}]의 공식 회계 명칭과 상세 정의는 무엇인가?",
                "response": (
                    f"XBRL 개념 [{concept}]의 공식 명칭은 '{label}'입니다. "
                    f"{'상세 정의: ' + doc if doc else '별도 정의 정보가 없습니다.'}"
                ),
                "context": [f"<link:loc xlink:href='...#{concept}'/>", f"<link:label>{label}</link:label>"],
                "type": "semantic_lookup",
                "namespace": namespace,
            }
            lines.append(json.dumps(qa1, ensure_ascii=False))
            
            # Q2: Reverse lookup (label to tag)
            qa2 = {
                "instruction": f"회계 보고서에서 '{label}'라고 표기되는 항목의 원천 XBRL 태그는 무엇인가?",
                "response": f"'{label}'의 원천 XBRL 태그는 [{concept}]입니다. (네임스페이스: {namespace})",
                "context": [f"<link:label>{label}</link:label>", f"<concept>{concept}</concept>"],
                "type": "reverse_lookup",
                "namespace": namespace,
            }
            lines.append(json.dumps(qa2, ensure_ascii=False))
            
            # Q3: Documentation explanation (if available)
            if doc:
                qa3 = {
                    "instruction": f"'{label}'의 회계적 정의를 설명해주세요.",
                    "response": doc,
                    "context": [f"<link:label role='documentation'>{doc}</link:label>"],
                    "type": "definition",
                    "concept": concept,
                }
                lines.append(json.dumps(qa3, ensure_ascii=False))
        
        # Summary Q&A
        summary = {
            "instruction": "이 레이블 링크베이스 파일에는 몇 개의 개념이 정의되어 있는가?",
            "response": (
                f"총 {len(data.get('facts', []))}개의 XBRL 개념이 정의되어 있습니다. "
                f"네임스페이스: {', '.join(data.get('key_metrics', {}).get('namespaces', []))}"
            ),
            "type": "summary",
        }
        lines.append(json.dumps(summary, ensure_ascii=False))
        
        return '\n'.join(lines)
    
    def to_markdown(self, data: Dict[str, Any]) -> str:
        """Generate comprehensive markdown with namespace-grouped tables."""
        lines = []
        
        # Title
        title = data.get("title", "Label Linkbase")
        lines.append(f"# {title}")
        lines.append("")
        
        # Summary
        summary = data.get("summary", "")
        if summary:
            lines.append(f"> {summary}")
            lines.append("")
        
        # Key Metrics
        metrics = data.get("key_metrics", {})
        if metrics:
            lines.append("## 📊 파싱 통계")
            lines.append("")
            lines.append(f"- **총 개념 수**: {metrics.get('total_concepts', 0)}")
            lines.append(f"- **로케이터**: {metrics.get('locators_parsed', 0)}")
            lines.append(f"- **레이블 리소스**: {metrics.get('labels_parsed', 0)}")
            lines.append(f"- **레이블 아크**: {metrics.get('arcs_parsed', 0)}")
            lines.append(f"- **네임스페이스**: {', '.join(metrics.get('namespaces', []))}")
            lines.append("")
        
        # Tables by namespace
        tables = data.get("tables", [])
        for table in tables:
            name = table.get("name", "데이터")
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            
            lines.append(f"## {name}")
            lines.append("")
            
            if headers and rows:
                lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                lines.append("|" + "|".join(["------"] * len(headers)) + "|")
                
                for row in rows[:100]:  # Limit for readability
                    formatted_row = []
                    for cell in row:
                        cell_str = str(cell) if cell else ""
                        # Escape pipe characters
                        cell_str = cell_str.replace("|", "\\|")[:80]
                        formatted_row.append(cell_str)
                    lines.append("| " + " | ".join(formatted_row) + " |")
                
                if len(rows) > 100:
                    lines.append("")
                    lines.append(f"*... 및 {len(rows) - 100}개 항목 더 있음*")
            
            lines.append("")
        
        # Metadata
        metadata = data.get("metadata", {})
        if metadata:
            lines.append("---")
            lines.append(f"*파일 타입: {metadata.get('file_type', 'unknown')} | "
                        f"처리: {metadata.get('processed_by', 'unknown')}*")
        
        return '\n'.join(lines)


# Singleton
label_linkbase_parser = LabelLinkbaseParser()
