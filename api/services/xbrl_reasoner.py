"""
FinDistill XBRL Reasoning Engine

Senior-level financial data scientist module for generating
high-quality reasoning Q&A pairs for LLM fine-tuning.

Features:
- Compound financial ratio calculations (ROE, ROA, Debt Ratio, etc.)
- Time-series analysis (YoY growth rates)
- Chain-of-Thought (CoT) response generation
- Context preservation with original XML tags
- Verification flags based on calculation validation
- US GAAP / IFRS terminology standardization
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================
# TERMINOLOGY STANDARDIZATION
# ============================================================

class AccountStandardizer:
    """
    Standardizes US GAAP and IFRS account names to canonical forms.
    Prevents AI confusion from synonymous terms.
    """
    
    # US GAAP → Standard mapping
    GAAP_SYNONYMS = {
        # Revenue variations
        "NetSales": "Revenue",
        "SalesRevenueNet": "Revenue",
        "Revenues": "Revenue",
        "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
        "SalesRevenueGoodsNet": "Revenue",
        
        # Cost variations
        "CostOfRevenue": "CostOfSales",
        "CostOfGoodsAndServicesSold": "CostOfSales",
        "CostOfGoodsSold": "CostOfSales",
        
        # Profit variations
        "OperatingIncomeLoss": "OperatingProfit",
        "NetIncomeLoss": "NetIncome",
        "ProfitLoss": "NetIncome",
        "NetIncomeLossAvailableToCommonStockholdersBasic": "NetIncome",
        
        # Asset variations
        "AssetsCurrent": "CurrentAssets",
        "AssetsNoncurrent": "NoncurrentAssets",
        
        # Liability variations
        "LiabilitiesCurrent": "CurrentLiabilities",
        "LiabilitiesNoncurrent": "NoncurrentLiabilities",
        
        # Equity variations
        "StockholdersEquity": "Equity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "TotalEquity",
    }
    
    # Korean labels for standardized terms
    KOREAN_LABELS = {
        "Revenue": "매출액",
        "CostOfSales": "매출원가",
        "GrossProfit": "매출총이익",
        "OperatingProfit": "영업이익",
        "NetIncome": "당기순이익",
        "Assets": "자산",
        "CurrentAssets": "유동자산",
        "NoncurrentAssets": "비유동자산",
        "Liabilities": "부채",
        "CurrentLiabilities": "유동부채",
        "NoncurrentLiabilities": "비유동부채",
        "Equity": "자본",
        "TotalEquity": "자본총계",
        "CashAndCashEquivalents": "현금및현금성자산",
    }
    
    @classmethod
    def standardize(cls, concept: str) -> str:
        """Standardize a concept name to canonical form."""
        # Extract local name from full concept
        local_name = concept.split(':')[-1].split('_')[-1]
        
        # Check for synonym
        return cls.GAAP_SYNONYMS.get(local_name, local_name)
    
    @classmethod
    def get_korean_label(cls, concept: str) -> str:
        """Get Korean label for a standardized concept."""
        std = cls.standardize(concept)
        return cls.KOREAN_LABELS.get(std, std)


# ============================================================
# FINANCIAL METRICS ENGINE
# ============================================================

@dataclass
class FinancialMetric:
    """Represents a calculated financial metric."""
    name: str
    value: float
    formula: str
    reasoning_steps: List[str]
    context_tags: List[str]
    verified: bool = True
    period: Optional[str] = None


class FinancialMetricsEngine:
    """
    Calculates compound financial ratios and metrics.
    Implements standard financial analysis formulas.
    """
    
    def __init__(self):
        self.extracted_values: Dict[str, Dict[str, float]] = {}  # {period: {metric: value}}
        self.raw_contexts: Dict[str, str] = {}  # {metric: raw_xml}
    
    def load_from_facts(self, facts: List[Dict]) -> None:
        """Load values from parsed XBRL facts."""
        for fact in facts:
            concept = fact.get("concept", "")
            label = fact.get("label", "")
            value_str = fact.get("value", "")
            period = fact.get("period", "current")
            
            # Parse numeric value
            try:
                clean = re.sub(r'[^\d.-]', '', str(value_str).replace(',', ''))
                if clean:
                    value = float(clean)
                    
                    # Store by standardized name
                    std_name = AccountStandardizer.standardize(concept)
                    
                    if period not in self.extracted_values:
                        self.extracted_values[period] = {}
                    
                    self.extracted_values[period][std_name] = value
                    self.extracted_values[period][label] = value  # Also store by label
                    
                    # Store context
                    self.raw_contexts[std_name] = f"<{concept}>{value_str}</{concept}>"
                    
            except (ValueError, TypeError):
                continue
    
    def get_value(self, name: str, period: str = "current") -> Optional[float]:
        """Get a value by name and period."""
        if period in self.extracted_values:
            # Try standardized name first
            std_name = AccountStandardizer.standardize(name)
            if std_name in self.extracted_values[period]:
                return self.extracted_values[period][std_name]
            # Try original name
            if name in self.extracted_values[period]:
                return self.extracted_values[period][name]
            # Try Korean label
            kr_label = AccountStandardizer.get_korean_label(name)
            if kr_label in self.extracted_values[period]:
                return self.extracted_values[period][kr_label]
        return None
    
    def get_context(self, name: str) -> str:
        """Get raw XML context for a concept."""
        std_name = AccountStandardizer.standardize(name)
        return self.raw_contexts.get(std_name, f"<{name}>N/A</{name}>")
    
    # ============ RATIO CALCULATIONS ============
    
    def calc_debt_ratio(self, period: str = "current") -> Optional[FinancialMetric]:
        """Calculate Debt Ratio = Total Liabilities / Total Equity × 100"""
        liabilities = self.get_value("Liabilities", period) or self.get_value("부채", period)
        equity = self.get_value("Equity", period) or self.get_value("자본", period)
        
        if not liabilities or not equity or equity == 0:
            return None
        
        ratio = (liabilities / equity) * 100
        
        return FinancialMetric(
            name="부채비율",
            value=ratio,
            formula="$$\\text{Debt Ratio} = \\frac{\\text{Total Liabilities}}{\\text{Total Equity}} \\times 100$$",
            reasoning_steps=[
                f"1. 총부채 확인: {liabilities:,.0f}",
                f"2. 총자본 확인: {equity:,.0f}",
                f"3. 비율 계산: {liabilities:,.0f} ÷ {equity:,.0f} × 100 = {ratio:.1f}%"
            ],
            context_tags=[
                self.get_context("Liabilities"),
                self.get_context("Equity")
            ],
            period=period
        )
    
    def calc_current_ratio(self, period: str = "current") -> Optional[FinancialMetric]:
        """Calculate Current Ratio = Current Assets / Current Liabilities × 100"""
        current_assets = self.get_value("CurrentAssets", period) or self.get_value("유동자산", period)
        current_liabilities = self.get_value("CurrentLiabilities", period) or self.get_value("유동부채", period)
        
        if not current_assets or not current_liabilities or current_liabilities == 0:
            return None
        
        ratio = (current_assets / current_liabilities) * 100
        
        return FinancialMetric(
            name="유동비율",
            value=ratio,
            formula="$$\\text{Current Ratio} = \\frac{\\text{Current Assets}}{\\text{Current Liabilities}} \\times 100$$",
            reasoning_steps=[
                f"1. 유동자산 확인: {current_assets:,.0f}",
                f"2. 유동부채 확인: {current_liabilities:,.0f}",
                f"3. 비율 계산: {current_assets:,.0f} ÷ {current_liabilities:,.0f} × 100 = {ratio:.1f}%"
            ],
            context_tags=[
                self.get_context("CurrentAssets"),
                self.get_context("CurrentLiabilities")
            ],
            period=period
        )
    
    def calc_gross_profit_margin(self, period: str = "current") -> Optional[FinancialMetric]:
        """Calculate Gross Profit Margin = Gross Profit / Revenue × 100"""
        revenue = self.get_value("Revenue", period) or self.get_value("매출액", period)
        gross_profit = self.get_value("GrossProfit", period) or self.get_value("매출총이익", period)
        
        if not revenue or not gross_profit or revenue == 0:
            return None
        
        margin = (gross_profit / revenue) * 100
        
        return FinancialMetric(
            name="매출총이익률",
            value=margin,
            formula="$$\\text{Gross Profit Margin} = \\frac{\\text{Gross Profit}}{\\text{Revenue}} \\times 100$$",
            reasoning_steps=[
                f"1. 매출액 확인: {revenue:,.0f}",
                f"2. 매출총이익 확인: {gross_profit:,.0f}",
                f"3. 비율 계산: {gross_profit:,.0f} ÷ {revenue:,.0f} × 100 = {margin:.1f}%"
            ],
            context_tags=[
                self.get_context("Revenue"),
                self.get_context("GrossProfit")
            ],
            period=period
        )
    
    def calc_net_profit_margin(self, period: str = "current") -> Optional[FinancialMetric]:
        """Calculate Net Profit Margin = Net Income / Revenue × 100"""
        revenue = self.get_value("Revenue", period) or self.get_value("매출액", period)
        net_income = self.get_value("NetIncome", period) or self.get_value("당기순이익", period)
        
        if not revenue or not net_income or revenue == 0:
            return None
        
        margin = (net_income / revenue) * 100
        
        return FinancialMetric(
            name="순이익률",
            value=margin,
            formula="$$\\text{Net Profit Margin} = \\frac{\\text{Net Income}}{\\text{Revenue}} \\times 100$$",
            reasoning_steps=[
                f"1. 매출액 확인: {revenue:,.0f}",
                f"2. 당기순이익 확인: {net_income:,.0f}",
                f"3. 비율 계산: {net_income:,.0f} ÷ {revenue:,.0f} × 100 = {margin:.1f}%"
            ],
            context_tags=[
                self.get_context("Revenue"),
                self.get_context("NetIncome")
            ],
            period=period
        )
    
    def calc_roe(self, period: str = "current") -> Optional[FinancialMetric]:
        """Calculate ROE = Net Income / Shareholders' Equity × 100"""
        net_income = self.get_value("NetIncome", period) or self.get_value("당기순이익", period)
        equity = self.get_value("Equity", period) or self.get_value("자본", period)
        
        if not net_income or not equity or equity == 0:
            return None
        
        roe = (net_income / equity) * 100
        
        return FinancialMetric(
            name="자기자본이익률(ROE)",
            value=roe,
            formula="$$ROE = \\frac{\\text{Net Income}}{\\text{Shareholder's Equity}} \\times 100$$",
            reasoning_steps=[
                f"1. 당기순이익 확인: {net_income:,.0f}",
                f"2. 자기자본 확인: {equity:,.0f}",
                f"3. ROE 계산: {net_income:,.0f} ÷ {equity:,.0f} × 100 = {roe:.1f}%"
            ],
            context_tags=[
                self.get_context("NetIncome"),
                self.get_context("Equity")
            ],
            period=period
        )
    
    def calc_roa(self, period: str = "current") -> Optional[FinancialMetric]:
        """Calculate ROA = Net Income / Total Assets × 100"""
        net_income = self.get_value("NetIncome", period) or self.get_value("당기순이익", period)
        assets = self.get_value("Assets", period) or self.get_value("자산", period)
        
        if not net_income or not assets or assets == 0:
            return None
        
        roa = (net_income / assets) * 100
        
        return FinancialMetric(
            name="총자산이익률(ROA)",
            value=roa,
            formula="$$ROA = \\frac{\\text{Net Income}}{\\text{Total Assets}} \\times 100$$",
            reasoning_steps=[
                f"1. 당기순이익 확인: {net_income:,.0f}",
                f"2. 총자산 확인: {assets:,.0f}",
                f"3. ROA 계산: {net_income:,.0f} ÷ {assets:,.0f} × 100 = {roa:.1f}%"
            ],
            context_tags=[
                self.get_context("NetIncome"),
                self.get_context("Assets")
            ],
            period=period
        )
    
    def calc_yoy_growth(self, metric_name: str, current_period: str, prior_period: str) -> Optional[FinancialMetric]:
        """Calculate Year-over-Year growth rate."""
        current = self.get_value(metric_name, current_period)
        prior = self.get_value(metric_name, prior_period)
        
        if not current or not prior or prior == 0:
            return None
        
        growth = ((current - prior) / abs(prior)) * 100
        
        kr_label = AccountStandardizer.get_korean_label(metric_name)
        
        return FinancialMetric(
            name=f"{kr_label} 성장률",
            value=growth,
            formula="$$\\text{Growth Rate} = \\frac{\\text{Current} - \\text{Prior}}{|\\text{Prior}|} \\times 100$$",
            reasoning_steps=[
                f"1. {current_period}년 {kr_label}: {current:,.0f}",
                f"2. {prior_period}년 {kr_label}: {prior:,.0f}",
                f"3. 증감: {current - prior:,.0f} ({'+' if growth >= 0 else ''}{growth:.1f}%)"
            ],
            context_tags=[
                self.get_context(metric_name)
            ],
            period=current_period
        )
    
    def validate_balance_sheet(self, period: str = "current") -> bool:
        """Validate: Assets = Liabilities + Equity"""
        assets = self.get_value("Assets", period) or self.get_value("자산", period)
        liabilities = self.get_value("Liabilities", period) or self.get_value("부채", period)
        equity = self.get_value("Equity", period) or self.get_value("자본", period)
        
        if not all([assets, liabilities, equity]):
            return True  # Can't verify if data missing
        
        expected = liabilities + equity
        tolerance = assets * 0.01  # 1% tolerance
        
        return abs(assets - expected) <= tolerance


# ============================================================
# REASONING Q&A GENERATOR
# ============================================================

class XBRLReasoner:
    """
    Generates high-quality reasoning Q&A pairs for LLM fine-tuning.
    
    Features:
    - Excludes simple lookup questions (dates, identifiers)
    - Generates analysis-focused Q&A (ratios, trends)
    - Chain-of-Thought (CoT) format: Formula → Substitution → Result → Interpretation
    """
    
    # 제외할 질문 패턴 (단순 조회형 질문)
    EXCLUDED_QUESTION_PATTERNS = [
        r"날짜.*언제",
        r"시작일.*무엇",
        r"종료일.*무엇",
        r"식별자.*무엇",
        r"what.*date",
        r"when.*start",
        r"when.*end",
        r"identifier",
        r"context.*id",
        r"unit.*is",
    ]
    
    QUESTION_TEMPLATES = {
        "debt_ratio": [
            "{company}의 {period}년 재무 건전성을 부채비율 근거로 평가하십시오.",
            "{company}의 부채비율을 계산하고 재무 안정성을 분석해주세요.",
            "{period}년 기준 {company}의 레버리지 수준은 어떠한가?",
        ],
        "current_ratio": [
            "{company}의 {period}년 유동성 위험을 평가하십시오.",
            "{company}의 단기 채무 이행 능력을 유동비율로 분석해주세요.",
            "{period}년 {company}의 운전자본 상태는 양호한가?",
        ],
        "profitability": [
            "{company}의 {period}년 수익성을 분석하십시오.",
            "{company}의 매출총이익률과 순이익률을 비교 분석해주세요.",
            "{period}년 {company}의 영업 효율성은 어떠한가?",
        ],
        "roe": [
            "{company}의 자기자본이익률(ROE)을 계산하고 주주 관점에서 평가하십시오.",
            "{period}년 {company}의 자본 효율성은 어떠한가?",
        ],
        "growth": [
            "전년 대비 {company}의 매출 성장세가 둔화되었는가?",
            "{company}의 {prior_period}년 대비 {period}년 실적 변화를 분석하십시오.",
        ],
    }
    
    def __init__(self, company_name: str = ""):
        self.company_name = company_name
        self.metrics_engine = FinancialMetricsEngine()
    
    @classmethod
    def is_excluded_question(cls, question: str) -> bool:
        """Check if question matches excluded patterns (simple lookup)."""
        question_lower = question.lower()
        for pattern in cls.EXCLUDED_QUESTION_PATTERNS:
            if re.search(pattern, question_lower, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def filter_qa_pairs(cls, qa_pairs: List[Dict]) -> List[Dict]:
        """Filter out simple lookup Q&A pairs, keep only analysis-type."""
        return [
            qa for qa in qa_pairs
            if not cls.is_excluded_question(qa.get("instruction", ""))
        ]
    
    def load_data(self, parsed_data: Dict[str, Any]) -> None:
        """Load parsed XBRL data."""
        facts = parsed_data.get("facts", [])
        self.metrics_engine.load_from_facts(facts)
        
        # Try to extract company name from data
        if not self.company_name:
            title = parsed_data.get("title", "")
            if ":" in title:
                self.company_name = title.split(":")[1].strip()
            else:
                self.company_name = "해당 기업"
    
    def generate_reasoning_qa(self, period: str = "current") -> List[Dict]:
        """Generate all reasoning Q&A pairs."""
        qas = []
        
        # Validate data first
        is_verified = self.metrics_engine.validate_balance_sheet(period)
        
        # 1. Debt Ratio Analysis
        debt_metric = self.metrics_engine.calc_debt_ratio(period)
        if debt_metric:
            qas.append(self._build_qa(
                template_key="debt_ratio",
                metric=debt_metric,
                period=period,
                verified=is_verified,
                analysis=self._analyze_debt_ratio(debt_metric.value)
            ))
        
        # 2. Current Ratio Analysis
        current_metric = self.metrics_engine.calc_current_ratio(period)
        if current_metric:
            qas.append(self._build_qa(
                template_key="current_ratio",
                metric=current_metric,
                period=period,
                verified=is_verified,
                analysis=self._analyze_current_ratio(current_metric.value)
            ))
        
        # 3. Profitability Analysis
        gpm = self.metrics_engine.calc_gross_profit_margin(period)
        npm = self.metrics_engine.calc_net_profit_margin(period)
        if gpm or npm:
            qas.append(self._build_profitability_qa(gpm, npm, period, is_verified))
        
        # 4. ROE Analysis
        roe_metric = self.metrics_engine.calc_roe(period)
        if roe_metric:
            qas.append(self._build_qa(
                template_key="roe",
                metric=roe_metric,
                period=period,
                verified=is_verified,
                analysis=self._analyze_roe(roe_metric.value)
            ))
        
        # 5. ROA Analysis
        roa_metric = self.metrics_engine.calc_roa(period)
        if roa_metric:
            qas.append({
                "instruction": f"{self.company_name}의 총자산이익률(ROA)을 분석하십시오.",
                "response": (
                    f"{period}년 기준 ROA는 {roa_metric.value:.1f}%로 산출됩니다. "
                    f"{'자산 활용 효율이 우수합니다.' if roa_metric.value >= 5 else '자산 대비 수익 창출 능력 개선이 필요합니다.'}"
                ),
                "reasoning_steps": " -> ".join(roa_metric.reasoning_steps),
                "calculations": {
                    "name": roa_metric.name,
                    "value": roa_metric.value,
                    "formula": roa_metric.formula
                },
                "context": roa_metric.context_tags,
                "verified": is_verified,
                "type": "reasoning"
            })
        
        return qas
    
    def _build_qa(self, template_key: str, metric: FinancialMetric, 
                  period: str, verified: bool, analysis: str) -> Dict:
        """Build a single Q&A pair."""
        templates = self.QUESTION_TEMPLATES.get(template_key, [])
        question = templates[0].format(
            company=self.company_name,
            period=period,
            prior_period=str(int(period) - 1) if period.isdigit() else "전기"
        ) if templates else f"{metric.name}을(를) 분석하십시오."
        
        return {
            "instruction": question,
            "response": (
                f"{period}년 기준 {metric.name}은(는) {metric.value:.1f}%로 산출됩니다. "
                f"{analysis}"
            ),
            "reasoning_steps": " -> ".join(metric.reasoning_steps),
            "calculations": {
                "name": metric.name,
                "value": metric.value,
                "formula": metric.formula
            },
            "context": metric.context_tags,
            "verified": verified,
            "type": "reasoning"
        }
    
    def _build_profitability_qa(self, gpm: Optional[FinancialMetric], 
                                 npm: Optional[FinancialMetric],
                                 period: str, verified: bool) -> Dict:
        """Build profitability analysis Q&A."""
        response_parts = []
        steps = []
        contexts = []
        
        if gpm:
            response_parts.append(f"매출총이익률 {gpm.value:.1f}%")
            steps.extend(gpm.reasoning_steps)
            contexts.extend(gpm.context_tags)
        
        if npm:
            response_parts.append(f"순이익률 {npm.value:.1f}%")
            steps.extend(npm.reasoning_steps)
            contexts.extend(npm.context_tags)
        
        analysis = "수익성이 양호합니다." if (npm and npm.value >= 10) else "수익성 개선이 필요합니다."
        
        return {
            "instruction": f"{self.company_name}의 {period}년 수익성을 분석하십시오.",
            "response": f"{period}년 기준 {', '.join(response_parts)}입니다. {analysis}",
            "reasoning_steps": " -> ".join(steps),
            "calculations": {
                "gross_profit_margin": gpm.value if gpm else None,
                "net_profit_margin": npm.value if npm else None
            },
            "context": contexts,
            "verified": verified,
            "type": "reasoning"
        }
    
    def _analyze_debt_ratio(self, ratio: float) -> str:
        """Provide analysis for debt ratio."""
        if ratio < 50:
            return "부채비율이 50% 미만으로 재무구조가 매우 안정적입니다."
        elif ratio < 100:
            return "부채비율이 100% 미만으로 재무 건전성이 양호합니다."
        elif ratio < 200:
            return "부채비율이 100~200% 수준으로 업종 평균 범위 내입니다."
        else:
            return "부채비율이 200%를 초과하여 재무 레버리지가 높은 편입니다."
    
    def _analyze_current_ratio(self, ratio: float) -> str:
        """Provide analysis for current ratio."""
        if ratio >= 200:
            return "유동비율 200% 이상으로 단기 지급능력이 매우 우수합니다."
        elif ratio >= 150:
            return "유동비율이 양호하여 단기 채무 이행에 문제가 없습니다."
        elif ratio >= 100:
            return "유동비율이 100% 이상이나 유동성 관리에 주의가 필요합니다."
        else:
            return "유동비율이 100% 미만으로 단기 유동성 리스크가 있습니다."
    
    def _analyze_roe(self, roe: float) -> str:
        """Provide analysis for ROE."""
        if roe >= 20:
            return "ROE 20% 이상으로 자본 효율성이 매우 우수합니다."
        elif roe >= 15:
            return "ROE가 양호한 수준으로 주주가치 창출에 긍정적입니다."
        elif roe >= 10:
            return "ROE가 보통 수준입니다."
        else:
            return "ROE가 낮아 자본 대비 수익 창출 능력 개선이 필요합니다."
    
    def generate_timeseries_qa(self, current_period: str = "2025", 
                                prior_period: str = "2024") -> List[Dict]:
        """Generate time-series comparison Q&A pairs."""
        qas = []
        
        # Key metrics to compare
        metrics_to_compare = [
            ("Revenue", "매출액", "성장"),
            ("NetIncome", "당기순이익", "증가"),
            ("Assets", "총자산", "확대"),
            ("Equity", "자본", "증가"),
            ("OperatingProfit", "영업이익", "성장"),
        ]
        
        for metric_name, kr_name, trend_word in metrics_to_compare:
            growth_metric = self.metrics_engine.calc_yoy_growth(
                metric_name, current_period, prior_period
            )
            
            if growth_metric:
                current_val = self.metrics_engine.get_value(metric_name, current_period)
                prior_val = self.metrics_engine.get_value(metric_name, prior_period)
                
                if current_val and prior_val:
                    trend = "증가" if growth_metric.value >= 0 else "감소"
                    trend_analysis = self._analyze_trend(kr_name, growth_metric.value)
                    
                    qas.append({
                        "instruction": f"전년 대비 {self.company_name}의 {kr_name} {trend_word}세가 어떻게 변화했는가?",
                        "response": (
                            f"{current_period}년 {kr_name}은 {current_val:,.0f}으로, "
                            f"{prior_period}년 {prior_val:,.0f} 대비 "
                            f"{abs(growth_metric.value):.1f}% {trend}했습니다. "
                            f"{trend_analysis}"
                        ),
                        "reasoning_steps": (
                            f"1단계: {prior_period}년 {kr_name} 확인 ({prior_val:,.0f}) -> "
                            f"2단계: {current_period}년 {kr_name} 확인 ({current_val:,.0f}) -> "
                            f"3단계: 증감률 계산 $$\\frac{{{current_val:,.0f} - {prior_val:,.0f}}}{{{prior_val:,.0f}}} \\times 100 = {growth_metric.value:.1f}\\%$$"
                        ),
                        "calculations": {
                            "metric": kr_name,
                            "current_value": current_val,
                            "prior_value": prior_val,
                            "change_amount": current_val - prior_val,
                            "change_percent": growth_metric.value,
                            "formula": growth_metric.formula
                        },
                        "context": [
                            f"<{metric_name} period='{prior_period}'>{prior_val}</{metric_name}>",
                            f"<{metric_name} period='{current_period}'>{current_val}</{metric_name}>"
                        ],
                        "verified": True,
                        "type": "timeseries"
                    })
        
        return qas
    
    def _analyze_trend(self, metric_name: str, growth_rate: float) -> str:
        """Provide strategic analysis for growth trends."""
        if metric_name in ["매출액", "영업이익"]:
            if growth_rate >= 20:
                return "고성장 국면으로 시장 점유율 확대 전략이 효과적입니다."
            elif growth_rate >= 10:
                return "안정적인 성장세를 유지하고 있습니다."
            elif growth_rate >= 0:
                return "성장 모멘텀이 다소 둔화되었으나 긍정적입니다."
            elif growth_rate >= -10:
                return "소폭 감소로 시장 환경 모니터링이 필요합니다."
            else:
                return "급격한 하락으로 전략적 대응이 시급합니다."
        elif metric_name in ["당기순이익"]:
            if growth_rate >= 0:
                return "수익성이 개선되어 재무 건전성에 긍정적입니다."
            else:
                return "수익성 하락에 대한 원인 분석이 필요합니다."
        else:
            return "전년 대비 변화 추이를 지속 모니터링해야 합니다."
    
    def generate_verification_qa(self, period: str = "current") -> List[Dict]:
        """Generate data integrity verification Q&A."""
        qas = []
        
        # Balance Sheet Verification
        assets = self.metrics_engine.get_value("Assets", period)
        liabilities = self.metrics_engine.get_value("Liabilities", period)
        equity = self.metrics_engine.get_value("Equity", period)
        
        if all([assets, liabilities, equity]):
            expected = liabilities + equity
            diff = abs(assets - expected)
            is_valid = diff <= (assets * 0.01)
            
            qas.append({
                "instruction": f"{self.company_name}의 재무상태표가 회계 등식(자산 = 부채 + 자본)을 충족하는지 검증하십시오.",
                "response": (
                    f"검증 결과: {'✅ 통과' if is_valid else '⚠️ 불일치'}\n\n"
                    f"$$\\text{{총자산}} = \\text{{총부채}} + \\text{{자본}}$$\n\n"
                    f"• 총자산: {assets:,.0f}\n"
                    f"• 총부채 + 자본: {liabilities:,.0f} + {equity:,.0f} = {expected:,.0f}\n"
                    f"• 차이: {diff:,.0f} ({'허용범위 1% 이내' if is_valid else '검토 필요'})"
                ),
                "reasoning_steps": (
                    f"1단계: 총자산 확인 ({assets:,.0f}) -> "
                    f"2단계: 총부채 확인 ({liabilities:,.0f}) -> "
                    f"3단계: 자본 확인 ({equity:,.0f}) -> "
                    f"4단계: 등식 검증 ({assets:,.0f} ≈ {expected:,.0f})"
                ),
                "calculations": {
                    "assets": assets,
                    "liabilities": liabilities,
                    "equity": equity,
                    "expected_sum": expected,
                    "difference": diff,
                    "tolerance_percent": 1.0,
                    "formula": "$$\\text{Assets} = \\text{Liabilities} + \\text{Equity}$$"
                },
                "context": [
                    self.metrics_engine.get_context("Assets"),
                    self.metrics_engine.get_context("Liabilities"),
                    self.metrics_engine.get_context("Equity")
                ],
                "verified": is_valid,
                "type": "verification"
            })
        
        # Gross Profit Verification
        revenue = self.metrics_engine.get_value("Revenue", period)
        cogs = self.metrics_engine.get_value("CostOfSales", period)
        gross_profit = self.metrics_engine.get_value("GrossProfit", period)
        
        if all([revenue, cogs, gross_profit]):
            expected_gp = revenue - cogs
            diff = abs(gross_profit - expected_gp)
            is_valid = diff <= (revenue * 0.01)
            
            qas.append({
                "instruction": f"매출총이익이 올바르게 계산되었는지 검증하십시오.",
                "response": (
                    f"검증 결과: {'✅ 통과' if is_valid else '⚠️ 불일치'}\n\n"
                    f"$$\\text{{매출총이익}} = \\text{{매출액}} - \\text{{매출원가}}$$\n\n"
                    f"• 매출액: {revenue:,.0f}\n"
                    f"• 매출원가: {cogs:,.0f}\n"
                    f"• 계산된 매출총이익: {expected_gp:,.0f}\n"
                    f"• 보고된 매출총이익: {gross_profit:,.0f}"
                ),
                "reasoning_steps": (
                    f"1단계: 매출액 확인 -> 2단계: 매출원가 확인 -> "
                    f"3단계: 차감 계산 -> 4단계: 보고값과 비교"
                ),
                "calculations": {
                    "revenue": revenue,
                    "cost_of_sales": cogs,
                    "calculated_gross_profit": expected_gp,
                    "reported_gross_profit": gross_profit,
                    "formula": "$$\\text{Gross Profit} = \\text{Revenue} - \\text{COGS}$$"
                },
                "context": [
                    self.metrics_engine.get_context("Revenue"),
                    self.metrics_engine.get_context("CostOfSales"),
                    self.metrics_engine.get_context("GrossProfit")
                ],
                "verified": is_valid,
                "type": "verification"
            })
        
        return qas
    
    def calc_operating_profit_margin(self, period: str = "current") -> Optional[Dict]:
        """Generate Operating Profit Margin Q&A."""
        revenue = self.metrics_engine.get_value("Revenue", period)
        operating = self.metrics_engine.get_value("OperatingProfit", period)
        
        if not revenue or not operating or revenue == 0:
            return None
        
        margin = (operating / revenue) * 100
        
        analysis = (
            "영업효율이 우수합니다." if margin >= 15 else
            "양호한 영업효율을 보이고 있습니다." if margin >= 10 else
            "영업효율 개선이 필요합니다."
        )
        
        return {
            "instruction": f"{self.company_name}의 영업이익률(Operating Profit Margin)을 분석하십시오.",
            "response": (
                f"{period}년 기준 영업이익률은 {margin:.1f}%로 산출됩니다. "
                f"$$\\text{{영업이익률}} = \\frac{{{operating:,.0f}}}{{{revenue:,.0f}}} \\times 100 = {margin:.1f}\\%$$ "
                f"{analysis}"
            ),
            "reasoning_steps": (
                f"1단계: 매출액(Net Sales) 확인 ({revenue:,.0f}) -> "
                f"2단계: 영업이익(Operating Income) 확인 ({operating:,.0f}) -> "
                f"3단계: 나눗셈 실행 ({operating:,.0f} ÷ {revenue:,.0f} × 100)"
            ),
            "calculations": {
                "name": "영업이익률",
                "revenue": revenue,
                "operating_profit": operating,
                "margin_percent": margin,
                "formula": "$$\\text{Operating Profit Margin} = \\frac{\\text{Operating Income}}{\\text{Net Sales}} \\times 100$$"
            },
            "context": [
                self.metrics_engine.get_context("Revenue"),
                self.metrics_engine.get_context("OperatingProfit")
            ],
            "verified": True,
            "type": "reasoning"
        }
    
    def generate_all_qa(self, current_period: str = "2025", 
                        prior_period: str = "2024") -> List[Dict]:
        """Generate all types of Q&A pairs: reasoning, timeseries, verification."""
        all_qas = []
        
        # 1. Basic reasoning Q&A (existing)
        all_qas.extend(self.generate_reasoning_qa(current_period))
        
        # 2. Operating Profit Margin
        opm_qa = self.calc_operating_profit_margin(current_period)
        if opm_qa:
            all_qas.append(opm_qa)
        
        # 3. Time-series comparison
        all_qas.extend(self.generate_timeseries_qa(current_period, prior_period))
        
        # 4. Data verification
        all_qas.extend(self.generate_verification_qa(current_period))
        
        return all_qas
    
    def to_jsonl(self, parsed_data: Dict[str, Any], period: str = "current") -> str:
        """Generate JSONL output with all Q&A pairs."""
        self.load_data(parsed_data)
        
        # Try to detect periods from data
        periods = set()
        for fact in parsed_data.get("facts", []):
            p = fact.get("period")
            if p and p.isdigit():
                periods.add(p)
        
        sorted_periods = sorted(periods, reverse=True)
        current = sorted_periods[0] if sorted_periods else "current"
        prior = sorted_periods[1] if len(sorted_periods) > 1 else str(int(current) - 1) if current.isdigit() else "prior"
        
        # Generate all Q&A types
        qas = self.generate_all_qa(current, prior)
        
        lines = []
        for qa in qas:
            lines.append(json.dumps(qa, ensure_ascii=False))
        
        return '\n'.join(lines)


# Singleton
xbrl_reasoner = XBRLReasoner()
