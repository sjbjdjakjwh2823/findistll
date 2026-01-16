"""
FinDistill XBRL AI Training Data Exporter

Enterprise-grade data generator with:
- Reasoning Q&A generation (ratios, growth rates)
- Calculation Linkbase validation
- Financial integrity checks
- PII masking filter
- Dual output: JSONL (Fine-tuning) + Markdown (RAG)
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    """Result of financial validation check."""
    passed: bool
    check_name: str
    expected: Optional[float] = None
    actual: Optional[float] = None
    message: str = ""
    requires_review: bool = False


class FinancialValidator:
    """
    Validates financial data integrity using accounting principles.
    """
    
    def validate_all(self, data: Dict[str, Any]) -> List[ValidationResult]:
        """Run all validation checks."""
        results = []
        
        # Extract metrics for validation
        metrics = self._extract_numeric_metrics(data)
        
        # 1. Balance Sheet equation: Assets = Liabilities + Equity
        results.append(self._check_balance_sheet(metrics))
        
        # 2. Income Statement: Revenue - COGS = Gross Profit
        results.append(self._check_gross_profit(metrics))
        
        # 3. Operating Profit calculation
        results.append(self._check_operating_profit(metrics))
        
        return results
    
    def _extract_numeric_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Extract numeric values from data."""
        metrics = {}
        
        key_metrics = data.get("key_metrics", {})
        for key, value in key_metrics.items():
            try:
                # Remove currency symbols and parse number
                clean = re.sub(r'[^\d.-]', '', str(value).replace(',', ''))
                if clean:
                    metrics[key] = float(clean)
            except (ValueError, TypeError):
                continue
        
        # Also check facts
        for fact in data.get("facts", []):
            label = fact.get("label", "")
            value = fact.get("value", "")
            try:
                clean = re.sub(r'[^\d.-]', '', str(value).replace(',', ''))
                if clean and label:
                    metrics[label] = float(clean)
            except (ValueError, TypeError):
                continue
        
        return metrics
    
    def _check_balance_sheet(self, metrics: Dict[str, float]) -> ValidationResult:
        """Check: Assets = Liabilities + Equity"""
        assets = metrics.get("총자산") or metrics.get("자산")
        liabilities = metrics.get("총부채") or metrics.get("부채")
        equity = metrics.get("총자본") or metrics.get("자본")
        
        if not all([assets, liabilities, equity]):
            return ValidationResult(
                passed=True,
                check_name="재무상태표 균형",
                message="검증에 필요한 데이터 없음 (자산/부채/자본)",
                requires_review=False
            )
        
        expected = liabilities + equity
        tolerance = assets * 0.01  # 1% tolerance
        passed = abs(assets - expected) <= tolerance
        
        return ValidationResult(
            passed=passed,
            check_name="재무상태표 균형 (자산 = 부채 + 자본)",
            expected=expected,
            actual=assets,
            message=f"자산({assets:,.0f}) {'=' if passed else '≠'} 부채({liabilities:,.0f}) + 자본({equity:,.0f})",
            requires_review=not passed
        )
    
    def _check_gross_profit(self, metrics: Dict[str, float]) -> ValidationResult:
        """Check: Revenue - COGS = Gross Profit"""
        revenue = metrics.get("매출액")
        cogs = metrics.get("매출원가")
        gross_profit = metrics.get("매출총이익")
        
        if not all([revenue, cogs, gross_profit]):
            return ValidationResult(
                passed=True,
                check_name="매출총이익 계산",
                message="검증에 필요한 데이터 없음",
                requires_review=False
            )
        
        expected = revenue - cogs
        tolerance = revenue * 0.01
        passed = abs(gross_profit - expected) <= tolerance
        
        return ValidationResult(
            passed=passed,
            check_name="매출총이익 (매출액 - 매출원가)",
            expected=expected,
            actual=gross_profit,
            message=f"매출총이익({gross_profit:,.0f}) {'=' if passed else '≠'} 매출({revenue:,.0f}) - 원가({cogs:,.0f})",
            requires_review=not passed
        )
    
    def _check_operating_profit(self, metrics: Dict[str, float]) -> ValidationResult:
        """Check: Gross Profit - SG&A = Operating Profit"""
        gross_profit = metrics.get("매출총이익")
        sga = metrics.get("판매비와관리비") or metrics.get("판관비")
        operating_profit = metrics.get("영업이익")
        
        if not all([gross_profit, sga, operating_profit]):
            return ValidationResult(
                passed=True,
                check_name="영업이익 계산",
                message="검증에 필요한 데이터 없음",
                requires_review=False
            )
        
        expected = gross_profit - sga
        tolerance = gross_profit * 0.01
        passed = abs(operating_profit - expected) <= tolerance
        
        return ValidationResult(
            passed=passed,
            check_name="영업이익 (매출총이익 - 판관비)",
            expected=expected,
            actual=operating_profit,
            message=f"영업이익({operating_profit:,.0f}) {'=' if passed else '≠'} 매출총이익({gross_profit:,.0f}) - 판관비({sga:,.0f})",
            requires_review=not passed
        )


class PIIMasker:
    """
    Masks Personally Identifiable Information for B2B compliance.
    """
    
    # Patterns for PII detection
    PATTERNS = {
        'phone': r'\b(0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4})\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'rrn': r'\b\d{6}[-\s]?\d{7}\b',  # 주민등록번호
        'account': r'\b\d{3}[-\s]?\d{2,6}[-\s]?\d{2,6}[-\s]?\d{0,4}\b',  # 계좌번호
        'card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # 카드번호
        'address': r'(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)[시도]?\s+\S+[시군구]\s+\S+[읍면동로길]',
    }
    
    MASK_REPLACEMENTS = {
        'phone': '[전화번호]',
        'email': '[이메일]',
        'rrn': '[주민등록번호]',
        'account': '[계좌번호]',
        'card': '[카드번호]',
        'address': '[주소]',
    }
    
    def mask(self, text: str) -> str:
        """Mask all PII in text."""
        masked = text
        for pii_type, pattern in self.PATTERNS.items():
            replacement = self.MASK_REPLACEMENTS.get(pii_type, '[개인정보]')
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
        return masked
    
    def mask_dict(self, data: Dict) -> Dict:
        """Recursively mask PII in dictionary."""
        if isinstance(data, dict):
            return {k: self.mask_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.mask_dict(item) for item in data]
        elif isinstance(data, str):
            return self.mask(data)
        return data


class XBRLExporter:
    """
    AI Training Data Exporter with dual output.
    Integrates XBRLReasoner for advanced reasoning Q&A.
    """
    
    def __init__(self):
        self.validator = FinancialValidator()
        self.pii_masker = PIIMasker()
        self._reasoner = None  # Lazy load to avoid circular imports
    
    @property
    def reasoner(self):
        if self._reasoner is None:
            from .xbrl_reasoner import XBRLReasoner
            self._reasoner = XBRLReasoner()
        return self._reasoner
    
    def to_jsonl(self, data: Dict[str, Any], include_reasoning: bool = True) -> str:
        """
        Generate JSONL with reasoning Q&A pairs for AI training.
        
        🔴 Critical Fixes:
        - 단순 조회형 질문 완전 제거 ("X는 얼마인가?" 등)
        - 분석형 질문만 생성 (비율, 성장률 등)
        - CoT 응답 포맷 강제 (공식 → 대입 → 결과 → 해석)
        """
        lines = []
        
        # Mask PII
        masked_data = self.pii_masker.mask_dict(data)
        
        # Validate data
        validations = self.validator.validate_all(masked_data)
        all_passed = all(v.passed for v in validations)
        
        # 🔴 FIX: 단순 조회형 Q&A 생성 완전 제거
        # 기본 fact Q&A는 AI 학습에 도움이 되지 않으므로 제거
        # for fact in masked_data.get("facts", []):
        #     qa = self._generate_fact_qa(fact)  # 제거됨
        
        # 수식 기반 Q&A만 생성 (Calculation Linkbase)
        formulas = masked_data.get("formulas", [])
        for formula_data in formulas:
            formula_qas = self._generate_formula_qas(formula_data)
            for qa in formula_qas:
                # 수식 설명 Q&A는 유지 (학습 가치 있음)
                qa["validation_status"] = "passed" if all_passed else "review_required"
                lines.append(json.dumps(qa, ensure_ascii=False))
        
        # 🔴 FIX: 추론형 Q&A만 생성 (비율 분석, 성장률 등)
        if include_reasoning:
            reasoning_qas = self._generate_reasoning_qas(masked_data)
            for qa in reasoning_qas:
                # CoT 형식 응답 강제
                if "calculations" in qa:
                    qa["response"] = self._format_cot_response(qa)
                qa["validation_status"] = "passed" if all_passed else "review_required"
                qa["type"] = "reasoning"
                lines.append(json.dumps(qa, ensure_ascii=False))
        
        # 고급 추론 Q&A (XBRLReasoner)
        if include_reasoning and masked_data.get("facts"):
            try:
                self.reasoner.load_data(masked_data)
                advanced_qas = self.reasoner.generate_reasoning_qa()
                
                # 🔴 FIX: XBRLReasoner 질문 필터링 적용
                from .xbrl_reasoner import XBRLReasoner
                advanced_qas = XBRLReasoner.filter_qa_pairs(advanced_qas)
                
                for qa in advanced_qas:
                    lines.append(json.dumps(qa, ensure_ascii=False))
            except Exception as e:
                pass  # 오류 시 조용히 진행
        
        # 데이터 없으면 경고 로그만
        if not lines:
            lines.append(json.dumps({
                "instruction": "재무 분석 데이터 상태",
                "response": "수치 데이터가 충분하지 않아 분석형 Q&A를 생성할 수 없습니다.",
                "type": "diagnostic"
            }, ensure_ascii=False))
        
        # 검증 결과 추가 (분석 Q&A로 포장)
        if validations:
            validation_qa = {
                "instruction": "이 재무데이터의 무결성을 검증하고 결과를 분석하십시오.",
                "response": self._format_validation_response_cot(validations),
                "type": "verification",
                "validation_status": "passed" if all_passed else "review_required"
            }
            lines.append(json.dumps(validation_qa, ensure_ascii=False))
        
        return '\n'.join(lines)
    
    def _format_cot_response(self, qa: Dict) -> str:
        """CoT 형식 응답 포맷팅"""
        calcs = qa.get("calculations", {})
        formula = calcs.get("formula", "")
        values = calcs.get("values", [])
        result = calcs.get("result", 0)
        
        response = f"""## 계산 분석

### 1️⃣ 계산 공식
{formula}

### 2️⃣ 수치 대입
입력값: {', '.join(f'{v:,.0f}' for v in values if isinstance(v, (int, float)))}

### 3️⃣ 계산 결과
**{result:.2f}%**

### 4️⃣ 회계적 해석
{qa.get('response', '')}
"""
        return response
    
    def _format_validation_response_cot(self, validations: List['ValidationResult']) -> str:
        """검증 결과 CoT 형식 응답"""
        lines = ["## 재무데이터 무결성 검증", ""]
        lines.append("### 검증 항목별 분석")
        lines.append("")
        
        for i, v in enumerate(validations, 1):
            status = "✅ 통과" if v.passed else "❌ 검토 필요"
            lines.append(f"**{i}. {v.check_name}**: {status}")
            if v.message:
                lines.append(f"   - 상세: {v.message}")
            lines.append("")
        
        all_passed = all(v.passed for v in validations)
        lines.append("### 종합 판정")
        lines.append("✅ **재무데이터 무결성 확인됨**" if all_passed else "⚠️ **일부 항목 검토 필요**")
        
        return '\n'.join(lines)
    
    def _generate_formula_qas(self, formula_data: Dict) -> List[Dict]:
        """Generate Q&A pairs from calculation formulas."""
        qas = []
        
        parent = formula_data.get("parent", "")
        label = formula_data.get("label", parent)
        formula = formula_data.get("formula", "")
        components = formula_data.get("components", [])
        
        if not formula:
            return qas
        
        # Q1: What are the sub-items?
        child_labels = [c[0].split('_')[-1] for c, w in components] if components else []
        qas.append({
            "instruction": f"{label}의 하위 항목은 무엇인가?",
            "response": f"{label}의 하위 항목: {', '.join(child_labels) if child_labels else '정보 없음'}",
            "formula": formula,
            "type": "hierarchy",
        })
        
        # Q2: Which items should be subtracted?
        subtract_items = [c[0].split('_')[-1] for c, w in components if w < 0]
        if subtract_items:
            qas.append({
                "instruction": f"{label}을(를) 계산할 때 빼야 하는 항목이 있는가?",
                "response": f"예, {', '.join(subtract_items)}을(를) 차감해야 합니다.",
                "formula": formula,
                "type": "calculation",
            })
        else:
            qas.append({
                "instruction": f"{label}을(를) 계산할 때 빼야 하는 항목이 있는가?",
                "response": "아니요, 모든 하위 항목을 더합니다.",
                "formula": formula,
                "type": "calculation",
            })
        
        # Q3: Formula explanation
        qas.append({
            "instruction": f"{label}의 계산 공식을 설명해줘.",
            "response": f"계산 공식: {formula}",
            "type": "formula",
        })
        
        return qas
    
    def _generate_fact_qa(self, fact: Dict) -> Optional[Dict]:
        """Generate Q&A for a single fact."""
        label = fact.get("label", "")
        value = fact.get("value", "")
        period = fact.get("period", "")
        hierarchy = fact.get("hierarchy", "")
        
        if not label or not value:
            return None
        
        # Build context from raw data
        context = f"<{fact.get('concept', 'unknown')}>{value}</{fact.get('concept', 'unknown')}>"
        
        return {
            "instruction": f"{period}년 {label}은(는) 얼마인가?",
            "response": f"{period}년 {label}은(는) {value}{fact.get('unit', '원')}입니다.",
            "context": context,
            "hierarchy": hierarchy,
            "type": "factual"
        }
    
    def _generate_reasoning_qas(self, data: Dict[str, Any]) -> List[Dict]:
        """Generate advanced reasoning Q&A pairs."""
        qas = []
        
        # Extract metrics for calculations
        metrics = {}
        for fact in data.get("facts", []):
            label = fact.get("label", "")
            value = fact.get("value", "")
            period = fact.get("period", "")
            try:
                clean = float(re.sub(r'[^\d.-]', '', str(value).replace(',', '')))
                metrics[f"{label}_{period}"] = clean
                metrics[label] = clean  # Also store without period for latest
            except (ValueError, TypeError):
                continue
        
        # 1. Debt Ratio (부채비율)
        if "총부채" in metrics and "총자본" in metrics:
            debt = metrics["총부채"]
            equity = metrics["총자본"]
            ratio = (debt / equity) * 100 if equity else 0
            
            qas.append({
                "instruction": "부채비율을 계산하고 재무 건전성을 평가해줘.",
                "response": f"부채비율은 {ratio:.1f}%입니다. {'100% 미만으로 재무구조가 안정적입니다.' if ratio < 100 else '100% 이상으로 재무 레버리지가 높은 편입니다.'}",
                "calculations": {
                    "formula": "Total Liabilities / Total Equity * 100",
                    "values": [debt, equity],
                    "result": ratio
                },
                "type": "reasoning"
            })
        
        # 2. Gross Profit Margin (매출총이익률)
        if "매출액" in metrics and "매출총이익" in metrics:
            revenue = metrics["매출액"]
            gross = metrics["매출총이익"]
            margin = (gross / revenue) * 100 if revenue else 0
            
            qas.append({
                "instruction": "매출총이익률은 얼마인가?",
                "response": f"매출총이익률은 {margin:.1f}%입니다.",
                "calculations": {
                    "formula": "Gross Profit / Revenue * 100",
                    "values": [gross, revenue],
                    "result": margin
                },
                "type": "reasoning"
            })
        
        # 3. Operating Profit Margin (영업이익률)
        if "매출액" in metrics and "영업이익" in metrics:
            revenue = metrics["매출액"]
            operating = metrics["영업이익"]
            margin = (operating / revenue) * 100 if revenue else 0
            
            qas.append({
                "instruction": "영업이익률을 분석해줘.",
                "response": f"영업이익률은 {margin:.1f}%입니다. {'10% 이상으로 수익성이 양호합니다.' if margin >= 10 else '10% 미만으로 수익성 개선이 필요합니다.'}",
                "calculations": {
                    "formula": "Operating Profit / Revenue * 100",
                    "values": [operating, revenue],
                    "result": margin
                },
                "type": "reasoning"
            })
        
        # 4. ROE (자기자본이익률)
        if "당기순이익" in metrics and "총자본" in metrics:
            net_income = metrics["당기순이익"]
            equity = metrics["총자본"]
            roe = (net_income / equity) * 100 if equity else 0
            
            qas.append({
                "instruction": "자기자본이익률(ROE)을 계산해줘.",
                "response": f"ROE는 {roe:.1f}%입니다. {'15% 이상으로 자본 효율성이 우수합니다.' if roe >= 15 else '자본 대비 수익 창출 능력을 개선할 필요가 있습니다.'}",
                "calculations": {
                    "formula": "Net Income / Total Equity * 100",
                    "values": [net_income, equity],
                    "result": roe
                },
                "type": "reasoning"
            })
        
        # 5. Current Ratio (유동비율)
        if "유동자산" in metrics and "유동부채" in metrics:
            current_assets = metrics["유동자산"]
            current_liabilities = metrics["유동부채"]
            ratio = (current_assets / current_liabilities) * 100 if current_liabilities else 0
            
            qas.append({
                "instruction": "유동비율을 계산하고 단기 유동성을 평가해줘.",
                "response": f"유동비율은 {ratio:.1f}%입니다. {'200% 이상으로 단기 지급능력이 매우 우수합니다.' if ratio >= 200 else '100% 이상이나 유동성 관리에 주의가 필요합니다.' if ratio >= 100 else '100% 미만으로 단기 유동성 리스크가 있습니다.'}",
                "calculations": {
                    "formula": "Current Assets / Current Liabilities * 100",
                    "values": [current_assets, current_liabilities],
                    "result": ratio
                },
                "type": "reasoning"
            })
        
        return qas
    
    def to_financial_statement_markdown(self, data: Dict[str, Any], company_name: str = "") -> str:
        """
        Generate proper financial statement format markdown.
        
        Creates actual Balance Sheet / Income Statement format with:
        - Clear Asset / Liability / Equity sections
        - Amount-based sorting (largest first)
        - Human-readable labels (not technical XBRL tags)
        """
        lines = []
        
        # Mask PII
        masked_data = self.pii_masker.mask_dict(data)
        
        # Determine company name and fiscal year
        if not company_name:
            company_name = masked_data.get("title", "").split(":")[-1].strip() or "기업"
        
        periods = set()
        for fact in masked_data.get("facts", []):
            if fact.get("period"):
                periods.add(fact.get("period"))
        fiscal_year = max(periods) if periods else datetime.now().strftime("%Y")
        
        lines.append(f"# {company_name} 재무제표")
        lines.append(f"**회계연도**: {fiscal_year}")
        lines.append(f"**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Group facts by hierarchy
        balance_sheet_facts = []
        income_facts = []
        cash_flow_facts = []
        other_facts = []
        
        for fact in masked_data.get("facts", []):
            hierarchy = fact.get("hierarchy", "")
            label = fact.get("label", "")
            value = fact.get("value", "")
            
            # Parse numeric value for sorting
            try:
                numeric = float(re.sub(r'[^\d.-]', '', str(value).replace(',', '')))
            except (ValueError, TypeError):
                numeric = 0
            
            fact_with_numeric = {**fact, "_numeric": numeric}
            
            if "재무상태표" in hierarchy or any(k in label for k in ['자산', '부채', '자본']):
                balance_sheet_facts.append(fact_with_numeric)
            elif "손익" in hierarchy or any(k in label for k in ['매출', '이익', '비용']):
                income_facts.append(fact_with_numeric)
            elif "현금" in hierarchy:
                cash_flow_facts.append(fact_with_numeric)
            else:
                other_facts.append(fact_with_numeric)
        
        # Balance Sheet
        if balance_sheet_facts:
            lines.extend(self._format_balance_sheet_section(balance_sheet_facts))
        
        # Income Statement
        if income_facts:
            lines.extend(self._format_income_statement_section(income_facts))
        
        # Cash Flow
        if cash_flow_facts:
            lines.extend(self._format_cash_flow_section(cash_flow_facts))
        
        # Handle empty data case
        if not balance_sheet_facts and not income_facts and not cash_flow_facts:
            lines.append("## ⚠️ 수치 데이터 없음")
            lines.append("")
            lines.append("파싱된 재무 수치 데이터가 없습니다.")
            parse_log = masked_data.get("parse_log", [])
            if parse_log:
                lines.append("")
                lines.append("### 파싱 로그")
                for log in parse_log[-5:]:
                    lines.append(f"- {log}")
        
        return '\n'.join(lines)
    
    def _format_balance_sheet_section(self, facts: List[Dict]) -> List[str]:
        """Format balance sheet section with proper grouping."""
        lines = [
            "## 재무상태표 (Statement of Financial Position)",
            "",
            "| 계정과목 | 금액 |",
            "|:---------|-----:|",
        ]
        
        # Group by type
        assets = [f for f in facts if '자산' in f.get("label", "")]
        liabilities = [f for f in facts if '부채' in f.get("label", "")]
        equity = [f for f in facts if '자본' in f.get("label", "")]
        
        # Sort each group by amount (descending)
        assets.sort(key=lambda x: abs(x.get("_numeric", 0)), reverse=True)
        liabilities.sort(key=lambda x: abs(x.get("_numeric", 0)), reverse=True)
        equity.sort(key=lambda x: abs(x.get("_numeric", 0)), reverse=True)
        
        # Assets section
        if assets:
            lines.append("| **[자산]** | |")
            for f in assets:
                lines.append(f"| {f.get('label', '')} | {f.get('value', '')} |")
        
        # Liabilities section
        if liabilities:
            lines.append("| **[부채]** | |")
            for f in liabilities:
                lines.append(f"| {f.get('label', '')} | {f.get('value', '')} |")
        
        # Equity section
        if equity:
            lines.append("| **[자본]** | |")
            for f in equity:
                lines.append(f"| {f.get('label', '')} | {f.get('value', '')} |")
        
        lines.append("")
        return lines
    
    def _format_income_statement_section(self, facts: List[Dict]) -> List[str]:
        """Format income statement section."""
        lines = [
            "## 포괄손익계산서 (Statement of Comprehensive Income)",
            "",
            "| 계정과목 | 금액 |",
            "|:---------|-----:|",
        ]
        
        # Standard order for income statement items
        order = ['매출액', '매출원가', '매출총이익', '판매비와관리비', 
                 '영업이익', '금융수익', '금융비용', '법인세비용차감전순이익',
                 '법인세비용', '당기순이익']
        
        fact_dict = {f.get("label", ""): f for f in facts}
        added = set()
        
        # Add in standard order first
        for label in order:
            if label in fact_dict:
                f = fact_dict[label]
                lines.append(f"| {label} | {f.get('value', '')} |")
                added.add(label)
        
        # Add remaining items sorted by amount
        remaining = [f for f in facts if f.get("label") not in added]
        remaining.sort(key=lambda x: abs(x.get("_numeric", 0)), reverse=True)
        for f in remaining:
            lines.append(f"| {f.get('label', '')} | {f.get('value', '')} |")
        
        lines.append("")
        return lines
    
    def _format_cash_flow_section(self, facts: List[Dict]) -> List[str]:
        """Format cash flow statement section."""
        lines = [
            "## 현금흐름표 (Statement of Cash Flows)",
            "",
            "| 구분 | 금액 |",
            "|:-----|-----:|",
        ]
        
        facts.sort(key=lambda x: abs(x.get("_numeric", 0)), reverse=True)
        for f in facts:
            lines.append(f"| {f.get('label', '')} | {f.get('value', '')} |")
        
        lines.append("")
        return lines
    
    def _format_validation_response(self, validations: List[ValidationResult]) -> str:
        """Format validation results as response text."""
        lines = ["재무데이터 무결성 검증 결과:"]
        
        for v in validations:
            status = "✅ 통과" if v.passed else "❌ 검토 필요"
            lines.append(f"- {v.check_name}: {status}")
            if v.message:
                lines.append(f"  {v.message}")
        
        return '\n'.join(lines)
    
    def to_markdown(self, data: Dict[str, Any]) -> str:
        """
        Generate Markdown with hierarchical table structure.
        Optimized for RAG systems.
        """
        lines = []
        
        # Mask PII
        masked_data = self.pii_masker.mask_dict(data)
        
        # Title
        title = masked_data.get("title", "XBRL 재무데이터")
        lines.append(f"# {title}")
        lines.append("")
        
        # Summary
        summary = masked_data.get("summary", "")
        if summary:
            lines.append(f"> {summary}")
            lines.append("")
        
        # Key Metrics
        key_metrics = masked_data.get("key_metrics", {})
        if key_metrics:
            lines.append("## 핵심 지표")
            lines.append("")
            lines.append("| 항목 | 금액 |")
            lines.append("|------|------|")
            for key, value in key_metrics.items():
                lines.append(f"| {key} | {value} |")
            lines.append("")
        
        # Tables by hierarchy
        tables = masked_data.get("tables", [])
        for table in tables:
            name = table.get("name", "데이터")
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            
            lines.append(f"## {name}")
            lines.append("")
            
            if headers:
                lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                lines.append("|" + "|".join(["------"] * len(headers)) + "|")
            
            for row in rows:
                lines.append("| " + " | ".join(str(cell) if cell else "" for cell in row) + " |")
            
            lines.append("")
        
        # Validation status
        validations = self.validator.validate_all(masked_data)
        lines.append("## 데이터 검증")
        lines.append("")
        for v in validations:
            status = "✅" if v.passed else "⚠️"
            lines.append(f"- {status} {v.check_name}: {v.message}")
        
        # Metadata
        metadata = masked_data.get("metadata", {})
        if metadata:
            lines.append("")
            lines.append("---")
            lines.append(f"*파일 타입: {metadata.get('file_type', 'xbrl')} | "
                        f"항목 수: {metadata.get('fact_count', 0)} | "
                        f"처리: {metadata.get('processed_by', 'unknown')}*")
        
        return '\n'.join(lines)


# Singleton instance
xbrl_exporter = XBRLExporter()
