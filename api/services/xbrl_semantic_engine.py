"""
FinDistill XBRL Semantic Engine

범용 XBRL 재무 지능 엔진 - AI 학습용 고차원 지식 생성

핵심 기능:
1. 시맨틱 결합 파싱 (Joint Parsing): _lab.xml 우선 파싱 → 라벨 매핑
2. 수치 스케일 표준화: decimals 속성에 따른 정확한 단위 환산
3. 컨텍스트 필터링: 연결재무제표 우선 타겟팅
4. 추론형 Q&A 생성: CoT 포맷의 고품질 학습 데이터
5. 구조화된 재무제표 마크다운 생성

Author: FinDistill AI Engine
Version: 1.0.0
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class SemanticFact:
    """시맨틱 라벨이 적용된 재무 팩트"""
    concept: str               # 원본 기술적 태그 (예: us-gaap:Assets)
    label: str                 # 인간 친화적 라벨 (예: 자산)
    value: Decimal             # 표준화된 수치 값
    raw_value: str             # 원본 값 (스케일 적용 전)
    unit: str                  # 화폐 단위
    period: str                # 기간 (YYYY 또는 YYYY-MM-DD)
    context_ref: str           # 컨텍스트 참조 ID
    decimals: Optional[int]    # 소수점 자릿수 / 스케일
    hierarchy: str             # 재무제표 계층 (예: 재무상태표 > 자산)
    is_consolidated: bool      # 연결재무제표 여부
    segment: Optional[str]     # 세그먼트 정보 (있는 경우)
    

@dataclass
class ParsedContext:
    """파싱된 XBRL 컨텍스트"""
    id: str
    entity: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    instant: Optional[str] = None
    is_consolidated: bool = True  # 기본값: 연결
    segment_members: List[str] = field(default_factory=list)


@dataclass
class XBRLIntelligenceResult:
    """XBRL 지능 엔진 출력 결과"""
    success: bool
    company_name: str
    fiscal_year: str
    facts: List[SemanticFact]
    reasoning_qa: List[Dict[str, str]]
    financial_report_md: str
    jsonl_data: List[str]
    key_metrics: Dict[str, Any]
    parse_summary: str
    errors: List[str]


# ============================================================
# SCALE PROCESSOR (v3 - Self-Healing)
# ============================================================

class ScaleProcessor:
    """
    수치 스케일 처리기 (v11.0) - Expert Financial Analysis Engine
    
    🔴 지능형 수치 보정 (Self-Healing):
    1. 원본 값이 이미 큰 절대값(≥10^6)이고 decimals가 음수면 곱셈 중단
    2. 최종값이 10^15 초과 시 자동 역산(Reverse Scaling)
    3. 모든 수치를 Billion($10^9) 단위로 표준화 (STRICT)
    
    🆕 v11.0 Features:
    - Strict Billion ($B$) Unit Only Policy
    - Variable Precision (3 decimals standard, 6 for small values)
    - Arithmetic Cross-Check Verification
    - Time-Series Average Calculation
    
    입력: 다양한 형식의 XBRL 수치
    출력: 합리적 범위(~$1T)의 표준화된 수치
    """
    
    # 표준화 목표 단위
    STANDARD_UNIT_BILLION = Decimal('1e9')   # $1B = 10^9
    STANDARD_UNIT_MILLION = Decimal('1e6')   # $1M = 10^6
    
    # v11.0: Precision Constants
    SMALL_VALUE_THRESHOLD = Decimal('1e6')   # $0.001B = $1M
    PRECISION_STANDARD = 3                    # Standard: 3 decimals
    PRECISION_EXTENDED = 6                    # Extended: 6 decimals for small values
    PRECISION_INSIGNIFICANT = Decimal('1e3') # Values below $1K are insignificant
    
    # 합리적 재무 수치 범위
    MAX_REASONABLE_VALUE = Decimal('1e13')   # 10조 (Apple 총자산 ~$400B의 10배)
    MIN_REASONABLE_VALUE = Decimal('1')
    
    # 이중 곱셈 방지를 위한 원본값 임계치
    RAW_VALUE_LARGE_THRESHOLD = Decimal('1e6')  # 원본이 100만 이상이면 이미 실제값
    
    # 잘못된 값 패턴 (URL, 날짜 등)
    INVALID_VALUE_PATTERNS = [
        r'^https?://',
        r'\.org/',
        r'\.xsd#',
        r'^\d{4}-\d{2}-\d{2}$',
        r'^\d{8}$',
        r'^\d{8}\.\d$',
        r'Member$',
        r'Axis$',
    ]
    
    @classmethod
    def is_valid_numeric_value(cls, raw_value: str) -> bool:
        """유효한 재무 수치 여부 확인"""
        if not raw_value:
            return False
        
        for pattern in cls.INVALID_VALUE_PATTERNS:
            if re.search(pattern, raw_value, re.IGNORECASE):
                return False
        
        clean = raw_value.replace(',', '').replace(' ', '').strip()
        clean_for_check = clean.lstrip('-').replace('.', '', 1)
        
        if not clean_for_check:
            return False
        
        return clean_for_check.isdigit()
    
    @classmethod
    def standardize_value(
        cls,
        raw_value: str, 
        decimals: Optional[str], 
        unit_ref: str = "",
        apply_unit_scale: bool = True
    ) -> Tuple[Decimal, str, bool]:
        """
        Self-Healing 수치 표준화
        
        Returns:
            (표준화된 값, 처리 설명, 유효성 여부)
        
        핵심 로직:
        1. 원본값이 이미 크면(≥10^6) 스케일링 건너뛰기
        2. 스케일링 후 범위 초과 시 역산(Reverse Scaling)
        3. 표준 단위(Billion/Million)으로 정규화
        """
        if not cls.is_valid_numeric_value(raw_value):
            return Decimal('0'), f"Invalid: {raw_value}", False
        
        clean_value = raw_value.replace(',', '').replace(' ', '').strip()
        
        try:
            original_value = Decimal(clean_value)
        except InvalidOperation:
            return Decimal('0'), f"Parse error: {raw_value}", False
        
        value = original_value
        description = "원본"
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: 지능형 스케일링 판단 (Self-Healing Logic)
        # ═══════════════════════════════════════════════════════════
        abs_original = abs(original_value)
        
        # 원본값이 이미 크면 (≥10^6) 스케일 적용하지 않음
        # (Workiva 등 일부 플랫폼은 이미 절대값으로 기록)
        skip_scaling = abs_original >= cls.RAW_VALUE_LARGE_THRESHOLD
        
        if skip_scaling and decimals:
            try:
                dec_int = int(decimals)
                if dec_int < 0:
                    # 원본이 크고 decimals도 음수면 이미 실제값 → 스케일링 건너뛰기
                    logger.info(f"Self-Healing: Raw value {abs_original} already large, skipping decimals={decimals} scaling")
                    description = f"Self-Heal: 원본 유지 (decimals={decimals} 무시)"
            except ValueError:
                pass
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: 조건부 스케일링 (원본이 작을 때만)
        # ═══════════════════════════════════════════════════════════
        if not skip_scaling and decimals:
            try:
                dec_int = int(decimals)
                if dec_int < 0:
                    multiplier = Decimal(10) ** abs(dec_int)
                    value = original_value * multiplier
                    
                    scale_map = {
                        -3: "천 단위 (×1,000)",
                        -6: "백만 단위 (×1,000,000)",
                        -9: "십억 단위 (×1,000,000,000)",
                    }
                    description = scale_map.get(dec_int, f"×10^{abs(dec_int)}")
            except ValueError:
                pass
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Self-Healing 역산 (Range Overflow 자동 보정)
        # ═══════════════════════════════════════════════════════════
        abs_value = abs(value)
        
        if abs_value > cls.MAX_REASONABLE_VALUE:
            # 값이 비현실적으로 크면 자동 역산
            reverse_factors = [
                (Decimal('1e12'), "역산 ÷10^12 (조→십억)"),
                (Decimal('1e9'), "역산 ÷10^9 (십억→백만)"),
                (Decimal('1e6'), "역산 ÷10^6 (백만→원)"),
            ]
            
            for factor, desc in reverse_factors:
                corrected = value / factor
                if abs(corrected) <= cls.MAX_REASONABLE_VALUE and abs(corrected) >= cls.MIN_REASONABLE_VALUE:
                    logger.warning(f"Self-Healing Reverse Scale: {value} → {corrected} ({desc})")
                    value = corrected
                    description = f"Self-Heal: {desc}"
                    break
            else:
                # 여전히 범위 초과면 원본값 사용
                logger.error(f"Self-Healing failed, using original: {original_value}")
                value = original_value
                description = "Self-Heal 실패 → 원본 사용"
        
        return value, description, True
    
    @staticmethod
    def format_currency(value: Decimal, currency: str = "USD") -> str:
        """
        v11.0: Strict Billion Unit Formatting with Variable Precision
        
        Policy: ALL values output in Billion ($B$) only
        - Values >= $0.001B: 3 decimal places (standard)
        - Values < $0.001B: 6 decimal places (extended precision)
        - Values < $0.000001B: marked as "< $0.001B (insignificant)"
        
        This eliminates M/K/T unit mixing that causes AI hallucinations.
        """
        try:
            abs_val = abs(value)
            sign = "-" if value < 0 else ""
            
            # Convert to Billion (10^9)
            billion_val = float(abs_val / Decimal('1e9'))
            
            # Variable precision based on magnitude
            if abs_val < ScaleProcessor.PRECISION_INSIGNIFICANT:
                # Very small values (< $1K)
                return f"{sign}< $0.001B (insignificant)"
            elif abs_val < ScaleProcessor.SMALL_VALUE_THRESHOLD:
                # Small values (< $1M): Extended precision (6 decimals)
                if currency == "USD":
                    return f"{sign}${billion_val:.6f}B"
                else:
                    return f"{sign}{billion_val:.6f}B {currency}"
            else:
                # Standard values (>= $1M): Standard precision (3 decimals)
                if currency == "USD":
                    return f"{sign}${billion_val:.3f}B"
                else:
                    return f"{sign}{billion_val:.3f}B {currency}"
        except:
            return str(value)
    
    @classmethod
    def format_currency_strict_billion(cls, value: Decimal, currency: str = "USD") -> str:
        """Alias for format_currency - v11.0 Strict Billion Policy"""
        return cls.format_currency(value, currency)
    
    @classmethod
    def normalize_to_billion(cls, value: Decimal, unit: str = "B") -> str:
        """
        v11.0: Strict Billion Normalization (No exceptions)
        
        All values output in Billion with variable precision:
        - Standard: 3 decimals for values >= $1M
        - Extended: 6 decimals for values < $1M
        """
        try:
            abs_val = abs(value)
            sign = "-" if value < 0 else ""
            billion_val = float(value / Decimal('1e9'))
            
            if abs_val < cls.PRECISION_INSIGNIFICANT:
                return f"{sign}< 0.001{unit}"
            elif abs_val < cls.SMALL_VALUE_THRESHOLD:
                return f"{sign}{billion_val:.6f}{unit}"
            else:
                return f"{sign}{billion_val:.3f}{unit}"
        except:
            return str(value)
    
    @classmethod
    def verify_calculation(
        cls,
        formula_name: str,
        numerator: Decimal,
        denominator: Decimal,
        reported_result: float,
        tolerance: float = 0.01
    ) -> Tuple[bool, str]:
        """
        v11.0: Arithmetic Cross-Check Verification
        
        Verifies that LLM-generated calculations match actual computation.
        This prevents arithmetic hallucinations in output.
        
        Args:
            formula_name: Name of the formula being verified
            numerator: Numerator value
            denominator: Denominator value
            reported_result: The result reported in the output
            tolerance: Acceptable difference (default 1%)
        
        Returns:
            (is_valid, verification_message)
        """
        if denominator == 0:
            return False, f"⚠️ {formula_name}: Division by zero"
        
        actual_result = float(numerator / denominator)
        difference = abs(actual_result - reported_result)
        relative_diff = difference / abs(actual_result) if actual_result != 0 else difference
        
        if relative_diff <= tolerance:
            return True, f"✅ Arithmetic Verified: {formula_name} = {actual_result:.4f}"
        else:
            return False, f"❌ Arithmetic Mismatch: {formula_name} expected {actual_result:.4f}, got {reported_result:.4f} (diff: {relative_diff*100:.2f}%)"
    
    @classmethod
    def calculate_average_balance(
        cls,
        current_value: Decimal,
        prior_value: Optional[Decimal],
        metric_name: str = "Balance"
    ) -> Tuple[Decimal, str]:
        """
        v11.0: Time-Series Average Calculation for Turnover Ratios
        
        Formula: Average = (Beginning Balance + Ending Balance) / 2
        
        This is the accounting-standard method for calculating turnover ratios.
        Using ending balance only is technically incorrect.
        
        Args:
            current_value: Ending balance (current period)
            prior_value: Beginning balance (prior period ending)
            metric_name: Name for description
        
        Returns:
            (average_value, calculation_description)
        """
        if prior_value is not None and prior_value > 0:
            average = (prior_value + current_value) / 2
            description = (
                f"Average {metric_name} = (Beginning {cls.format_currency(prior_value)} + "
                f"Ending {cls.format_currency(current_value)}) / 2 = {cls.format_currency(average)}"
            )
            return average, description
        else:
            # Fallback: Use ending balance only with warning
            description = (
                f"Ending {metric_name} = {cls.format_currency(current_value)} "
                f"(⚠️ Prior period data unavailable - using ending balance as fallback)"
            )
            return current_value, description
    
    @staticmethod
    def fix_label_typos(label: str) -> str:
        """
        Fix Label Typos & Translate to English (v10.0 Global Standard)
        
        1. Translation: Korean -> US-GAAP English
        2. Deduplication: English suffix cleanup (e.g., "Profitfit" -> "Profit")
        """
        if not label:
            return ""
        
        fixed = label.strip()
        
        # 1. Translation Map (Korean to English)
        translation_map = {
            # Comprehensive Income
            '매출액': 'Revenues', '매출': 'Revenues', '수익': 'Revenues',
            '매출원가': 'Cost of Goods Sold',
            '매출총이익': 'Gross Profit',
            '판매비와관리비': 'SG&A Expenses', '판관비': 'SG&A Expenses',
            '연구개발비': 'R&D Expenses',
            '영업이익': 'Operating Income',
            '당기순이익': 'Net Income',
            '법인세비용': 'Income Tax Expense',
            '금융수익': 'Financial Income', '금융비용': 'Financial Costs',
            
            # Financial Position
            '자산총계': 'Total Assets', '자산': 'Total Assets',
            '유동자산': 'Current Assets',
            '현금및현금성자산': 'Cash and Cash Equivalents',
            '매출채권': 'Accounts Receivable',
            '재고자산': 'Inventory',
            '비유동자산': 'Non-current Assets',
            '유형자산': 'Property, Plant and Equipment',
            
            '부채총계': 'Total Liabilities', '부채': 'Total Liabilities',
            '유동부채': 'Current Liabilities',
            '비유동부채': 'Non-current Liabilities',
            
            '자본총계': 'Total Equity', '자본': 'Total Equity',
            '이익잉여금': 'Retained Earnings',
            '자본금': 'Common Stock',
        }
        
        # Apply Translation (Exact Match First)
        if fixed in translation_map:
            return translation_map[fixed]
        
        # Partial Match / Cleanup (for English labels or unmapped Korean)
        # 2. English Suffix Deduplication (e.g., "Profitfit" -> "Profit")
        # Matches repeating 3+ char sequences at the end
        match = re.search(r'([a-zA-Z]{3,})\1$', fixed, re.IGNORECASE)
        if match:
            fixed = fixed[:-len(match.group(1))]
            
        return fixed
    
    @classmethod
    def validate_financial_equation(
        cls,
        assets: Optional[Decimal],
        liabilities: Optional[Decimal],
        equity: Optional[Decimal]
    ) -> Tuple[bool, str]:
        """
        재무등식 검증: Assets = Liabilities + Equity
        
        Returns:
            (검증 통과 여부, 검증 메시지)
        """
        if not assets or not liabilities or not equity:
            return True, "데이터 부족으로 검증 생략"
        
        expected = liabilities + equity
        difference = abs(assets - expected)
        tolerance = abs(assets) * Decimal('0.01')  # 1% 허용 오차

        if difference <= tolerance:
            return True, f"✅ 재무등식 검증 통과: Assets({cls.format_currency(assets)}) ≈ L+E({cls.format_currency(expected)})"
        else:
            return False, f"⚠️ 재무등식 불일치: Assets({cls.format_currency(assets)}) ≠ L+E({cls.format_currency(expected)}), 차이: {cls.format_currency(difference)}"

# ============================================================
# CONTEXT FILTER
# ============================================================

class ContextFilter:
    """
    컨텍스트 필터링기
    
    연결재무제표(Consolidated) vs 별도재무제표 구분:
    - 연결 컨텍스트 우선 타겟팅
    - 세그먼트 멤버 분석
    """
    
    # 연결재무제표 식별 패턴
    CONSOLIDATED_PATTERNS = [
        r'consolidated',
        r'연결',
        r'consol',
    ]
    
    # 별도재무제표 식별 패턴
    SEPARATE_PATTERNS = [
        r'nonconsolidated',
        r'separate',
        r'별도',
        r'individual',
        r'parent\s*only',
    ]
    
    # 제외할 세그먼트 패턴 (특정 세그먼트는 전체 재무가 아님)
    SEGMENT_EXCLUDE_PATTERNS = [
        r'segment',
        r'geographic',
        r'product.*line',
        r'operating.*segment',
    ]
    
    @classmethod
    def classify_context(cls, context: ParsedContext) -> Tuple[bool, str]:
        """
        컨텍스트 분류
        
        Returns:
            (is_consolidated, classification_reason)
        """
        context_text = ' '.join([
            context.id or '',
            context.entity or '',
            ' '.join(context.segment_members)
        ]).lower()
        
        # 1. 별도재무제표 명시 체크
        for pattern in cls.SEPARATE_PATTERNS:
            if re.search(pattern, context_text, re.IGNORECASE):
                return False, f"별도재무제표 패턴 감지: {pattern}"
        
        # 2. 세그먼트 제외 체크
        for pattern in cls.SEGMENT_EXCLUDE_PATTERNS:
            if re.search(pattern, context_text, re.IGNORECASE):
                return False, f"세그먼트 데이터: {pattern}"
        
        # 3. 연결재무제표 명시 체크
        for pattern in cls.CONSOLIDATED_PATTERNS:
            if re.search(pattern, context_text, re.IGNORECASE):
                return True, f"연결재무제표 패턴 감지: {pattern}"
        
        # 4. 기본값: 세그먼트 멤버가 없으면 연결로 추정
        if not context.segment_members:
            return True, "세그먼트 없음 - 연결 추정"
        
        return True, "기본값 - 연결 추정"
    
    @classmethod
    def filter_consolidated_priority(
        cls, 
        facts: List[SemanticFact],
        include_separate: bool = False
    ) -> List[SemanticFact]:
        """
        연결재무제표 데이터 우선 필터링
        
        Args:
            facts: 전체 팩트 리스트
            include_separate: 별도재무제표도 포함할지 여부
        
        Returns:
            필터링된 팩트 리스트 (연결 우선)
        """
        if include_separate:
            # 연결 먼저, 별도 나중 정렬
            return sorted(facts, key=lambda f: (not f.is_consolidated, f.concept))
        
        # 연결재무제표만 반환
        consolidated = [f for f in facts if f.is_consolidated]
        
        if not consolidated:
            logger.warning("연결재무제표 데이터 없음 - 전체 데이터 반환")
            return facts
        
        return consolidated


# ============================================================
# CORE FINANCIAL CONCEPTS
# ============================================================

class CoreFinancialConcepts:
    """핵심 재무 개념 정의"""
    
    # 재무상태표 핵심 항목
    BALANCE_SHEET = {
        # 자산
        "Assets": "자산총계",
        "CurrentAssets": "유동자산",
        "NoncurrentAssets": "비유동자산",
        "CashAndCashEquivalents": "현금및현금성자산",
        "Inventories": "재고자산",
        "TradeReceivables": "매출채권",
        "PropertyPlantAndEquipment": "유형자산",
        "IntangibleAssets": "무형자산",
        
        # 부채
        "Liabilities": "부채총계",
        "CurrentLiabilities": "유동부채",
        "NoncurrentLiabilities": "비유동부채",
        "TradePayables": "매입채무",
        "ShortTermBorrowings": "단기차입금",
        "LongTermDebt": "장기부채",
        
        # 자본
        "Equity": "자본총계",
        "IssuedCapital": "자본금",
        "RetainedEarnings": "이익잉여금",
        "SharePremium": "주식발행초과금",
    }
    
    # 손익계산서 핵심 항목
    INCOME_STATEMENT = {
        "Revenue": "매출액",
        "CostOfSales": "매출원가",
        "GrossProfit": "매출총이익",
        "SellingGeneralAndAdministrativeExpense": "판매비와관리비",
        "OperatingProfit": "영업이익",
        "FinanceIncome": "금융수익",
        "FinanceCosts": "금융비용",
        "ProfitBeforeTax": "법인세비용차감전순이익",
        "IncomeTaxExpense": "법인세비용",
        "ProfitLoss": "당기순이익",
        "NetIncome": "당기순이익",
    }
    
    # 현금흐름표 핵심 항목
    CASH_FLOW = {
        "CashFlowsFromOperatingActivities": "영업활동현금흐름",
        "CashFlowsFromInvestingActivities": "투자활동현금흐름",
        "CashFlowsFromFinancingActivities": "재무활동현금흐름",
    }
    
    # 통합 매핑
    ALL_CONCEPTS = {**BALANCE_SHEET, **INCOME_STATEMENT, **CASH_FLOW}
    
    # US-GAAP 확장 매핑 (복잡한 태그명을 영문 표준 라벨로)
    US_GAAP_LABELS = {
        "EquitySecuritiesFvNiCurrentAndNoncurrent": "Equity Securities (Fair Value)",
        "AvailableForSaleSecuritiesDebtSecurities": "Available-for-Sale Debt Securities",
        "MarketableSecuritiesCurrent": "Marketable Securities (Current)",
        "MarketableSecuritiesNoncurrent": "Marketable Securities (Non-current)",
        "AccountsReceivableNetCurrent": "Accounts Receivable, Net",
        "InventoryNet": "Inventory, Net",
        "PrepaidExpenseAndOtherAssetsCurrent": "Prepaid Expenses and Other Current Assets",
        "PropertyPlantAndEquipmentNet": "Property, Plant and Equipment, Net",
        "GoodwillAndIntangibleAssetsNet": "Goodwill and Intangible Assets",
        "OtherAssetsNoncurrent": "Other Non-current Assets",
        "AccountsPayableCurrent": "Accounts Payable",
        "AccruedLiabilitiesCurrent": "Accrued Liabilities",
        "DeferredRevenueCurrent": "Deferred Revenue (Current)",
        "CommercialPaper": "Commercial Paper",
        "LongTermDebtCurrent": "Long-term Debt (Current Portion)",
        "LongTermDebtNoncurrent": "Long-term Debt",
        "OtherLiabilitiesNoncurrent": "Other Non-current Liabilities",
        "CommonStocksIncludingAdditionalPaidInCapital": "Common Stock and Additional Paid-in Capital",
        "RetainedEarningsAccumulatedDeficit": "Retained Earnings (Accumulated Deficit)",
        "AccumulatedOtherComprehensiveIncomeLossNetOfTax": "Accumulated Other Comprehensive Income (Loss)",
        "StockholdersEquity": "Stockholders' Equity",
        "LiabilitiesAndStockholdersEquity": "Total Liabilities and Stockholders' Equity",
        "AssetsCurrent": "Current Assets",
        "AssetsNoncurrent": "Non-current Assets",
        "LiabilitiesCurrent": "Current Liabilities",
        "LiabilitiesNoncurrent": "Non-current Liabilities",
        "RevenueFromContractWithCustomerExcludingAssessedTax": "Net Sales",
        "CostOfGoodsAndServicesSold": "Cost of Sales",
        "ResearchAndDevelopmentExpense": "Research and Development",
        "SellingGeneralAndAdministrativeExpense": "Selling, General and Administrative",
        "OperatingIncomeLoss": "Operating Income",
        "NonoperatingIncomeExpense": "Other Income (Expense), Net",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": "Income Before Taxes",
        "IncomeTaxExpenseBenefit": "Income Tax Expense",
        "NetIncomeLoss": "Net Income",
        "EarningsPerShareBasic": "Earnings Per Share (Basic)",
        "EarningsPerShareDiluted": "Earnings Per Share (Diluted)",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "Cash and Cash Equivalents",
    }
    
    # 네임스페이스별 프리픽스
    NAMESPACE_PREFIXES = ['ifrs-full', 'us-gaap', 'dart', 'jppfs', 'edinet']
    
    @classmethod
    def get_label(cls, concept: str) -> str:
        """
        개념에서 인간 친화적 라벨 추출
        
        Enhanced: CamelCase 분리 및 US-GAAP 확장 매핑
        """
        # 네임스페이스 제거
        clean = concept
        for prefix in cls.NAMESPACE_PREFIXES:
            clean = clean.replace(f"{prefix}_", "").replace(f"{prefix}:", "")
        
        # _나 : 뒤의 이름만 추출
        if '_' in clean:
            clean = clean.split('_')[-1]
        if ':' in clean:
            clean = clean.split(':')[-1]
        
        # 1. US-GAAP 확장 매핑 확인
        if clean in cls.US_GAAP_LABELS:
            return cls.US_GAAP_LABELS[clean]
        
        # 2. 핵심 매핑 확인
        if clean in cls.ALL_CONCEPTS:
            return cls.ALL_CONCEPTS[clean]
        
        # 3. 폴백: CamelCase를 공백으로 분리
        # EquitySecuritiesFvNi -> Equity Securities Fv Ni
        readable = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean)
        readable = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', readable)
        
        return readable
    
    @classmethod
    def is_core_financial(cls, concept: str) -> bool:
        """핵심 재무 개념 여부 확인"""
        clean = concept
        for prefix in cls.NAMESPACE_PREFIXES:
            clean = clean.replace(f"{prefix}_", "").replace(f"{prefix}:", "")
        
        if '_' in clean:
            clean = clean.split('_')[-1]
        if ':' in clean:
            clean = clean.split(':')[-1]
        
        return clean in cls.ALL_CONCEPTS
    
    @classmethod
    def get_hierarchy(cls, concept: str) -> str:
        """재무제표 계층 반환"""
        clean = cls.get_label(concept)
        
        if clean in cls.BALANCE_SHEET.values():
            if '자산' in clean:
                return "재무상태표 > 자산"
            elif '부채' in clean:
                return "재무상태표 > 부채"
            elif '자본' in clean:
                return "재무상태표 > 자본"
            return "재무상태표"
        
        if clean in cls.INCOME_STATEMENT.values():
            return "포괄손익계산서"
        
        if clean in cls.CASH_FLOW.values():
            return "현금흐름표"
        
        return "기타"


# ============================================================
# INDUSTRY INSIGHT ENGINE (v11.0)
# ============================================================

class IndustryInsightEngine:
    """
    v11.0: Industry-Specific Professional Insight Generator
    
    Provides sector-appropriate analysis based on SIC codes or company identification.
    Different industries prioritize different metrics.
    
    SIC Code Mapping:
    - 3570-3579, 7370-7379: Computer/Technology (Tech)
    - 5200-5999: Retail Trade
    - 6000-6799: Finance, Insurance, Real Estate
    """
    
    INDUSTRY_TEMPLATES = {
        'tech': {
            'focus_metrics': ['rnd_intensity', 'gross_margin', 'revenue_growth'],
            'inventory_turnover': {
                'high': "For technology companies, high inventory turnover ({value:.1f}x) indicates efficient supply chain management and low obsolescence risk - critical for rapidly evolving product cycles. This is particularly important for semiconductor companies like NVIDIA where product lifecycles are short.",
                'low': "⚠️ Low inventory turnover ({value:.1f}x) in the tech sector raises concerns about product obsolescence and potential inventory write-downs. Technology products depreciate quickly due to rapid innovation cycles.",
            },
            'rnd_intensity': {
                'high': "✅ R&D intensity of {value:.1f}% demonstrates strong commitment to innovation, typical of industry leaders that maintain competitive moats through continuous technological advancement. For semiconductor companies, sustained R&D investment is essential for next-generation product development.",
                'low': "R&D intensity of {value:.1f}% is below tech sector average (10-15%). May indicate mature product portfolio, cost optimization phase, or potential competitive vulnerability.",
            },
            'operating_margin': {
                'high': "✅ Outstanding operating margin of {value:.1f}% reflects strong pricing power and scalable business model characteristic of technology leaders with differentiated products.",
                'low': "Operating margin of {value:.1f}% is below tech sector peers. Consider competitive pressure, product mix, or investment phase impacts.",
            },
            'asset_turnover': {
                'high': "Asset turnover of {value:.2f}x indicates efficient capital deployment in a capital-intensive semiconductor industry.",
                'low': "Asset turnover of {value:.2f}x reflects significant capital investment typical of fab or R&D intensive operations.",
            }
        },
        'retail': {
            'focus_metrics': ['inventory_turnover', 'operating_margin', 'same_store_sales'],
            'inventory_turnover': {
                'high': "✅ Excellent inventory turnover ({value:.1f}x) for retail - indicates strong consumer demand, efficient merchandising, and minimal markdowns. This is a key performance indicator for retail profitability.",
                'low': "⚠️ Low inventory turnover ({value:.1f}x) suggests potential overbuying, weak demand, or upcoming clearance needs. This may pressure gross margins through markdowns.",
            },
            'operating_margin': {
                'high': "Operating margin of {value:.1f}% is strong for retail sector where margins are typically thin.",
                'low': "Operating margin of {value:.1f}% is typical of retail's competitive, low-margin environment.",
            },
            'rnd_intensity': {
                'high': "R&D spending of {value:.1f}% is unusual for traditional retail; may indicate e-commerce or technology platform investment.",
                'low': "R&D intensity of {value:.1f}% is expected for traditional retail operations.",
            }
        },
        'financial': {
            'focus_metrics': ['roe', 'capital_adequacy', 'net_interest_margin'],
            'debt_ratio': {
                'high': "For financial institutions, leverage of {value:.1f}% is expected. Focus remains on capital adequacy ratios, regulatory compliance, and risk-weighted asset management.",
                'low': "Conservative leverage ({value:.1f}%) provides buffer against market volatility but may limit return on equity potential.",
            },
            'operating_margin': {
                'high': "Operating margin of {value:.1f}% indicates efficient operations and strong fee income or net interest margin.",
                'low': "Operating margin of {value:.1f}% may reflect elevated credit costs or competitive interest rate environment.",
            }
        },
        'default': {
            'inventory_turnover': {
                'high': "Inventory turnover of {value:.1f}x indicates efficient inventory management and strong sales velocity.",
                'low': "Inventory turnover of {value:.1f}x warrants investigation into demand patterns and inventory optimization opportunities.",
            },
            'rnd_intensity': {
                'high': "R&D intensity of {value:.1f}% indicates significant investment in innovation.",
                'low': "R&D intensity of {value:.1f}% is typical for industries with lower technology dependence.",
            },
            'operating_margin': {
                'high': "Operating margin of {value:.1f}% indicates strong profitability.",
                'low': "Operating margin of {value:.1f}% may warrant cost structure analysis.",
            },
            'debt_ratio': {
                'high': "Debt ratio of {value:.1f}% indicates higher financial leverage.",
                'low': "Debt ratio of {value:.1f}% indicates conservative capital structure.",
            },
            'asset_turnover': {
                'high': "Asset turnover of {value:.2f}x indicates efficient asset utilization.",
                'low': "Asset turnover of {value:.2f}x suggests asset-intensive operations.",
            },
            'dso': {
                'high': "DSO of {value:.0f} days indicates slower collection cycles that may impact working capital.",
                'low': "DSO of {value:.0f} days reflects efficient accounts receivable management.",
            },
            'current_ratio': {
                'high': "Current ratio of {value:.2f}x indicates strong short-term liquidity position.",
                'low': "Current ratio of {value:.2f}x may warrant attention to short-term liquidity management.",
            }
        }
    }
    
    # Metric thresholds for high/low classification
    THRESHOLDS = {
        'inventory_turnover': 6.0,
        'rnd_intensity': 10.0,
        'debt_ratio': 100.0,
        'operating_margin': 10.0,
        'asset_turnover': 1.0,
        'dso': 45.0,
        'current_ratio': 1.5,
    }
    
    @classmethod
    def classify_industry(cls, entity_name: str, sic_code: Optional[str] = None) -> str:
        """
        Classify company industry based on SIC code or entity name heuristics
        
        Returns: 'tech', 'retail', 'financial', or 'default'
        """
        if sic_code:
            try:
                sic_int = int(sic_code)
                if 3570 <= sic_int <= 3579 or 7370 <= sic_int <= 7379:
                    return 'tech'
                elif 5200 <= sic_int <= 5999:
                    return 'retail'
                elif 6000 <= sic_int <= 6799:
                    return 'financial'
            except ValueError:
                pass
        
        # Fallback: Name-based heuristics
        entity_lower = entity_name.lower()
        tech_keywords = ['nvidia', 'intel', 'amd', 'microsoft', 'apple', 'google', 
                        'meta', 'semiconductor', 'software', 'amazon', 'tesla']
        retail_keywords = ['walmart', 'target', 'costco', 'retail', 'store', 'mart']
        financial_keywords = ['bank', 'capital', 'financial', 'insurance', 'investment']
        
        if any(kw in entity_lower for kw in tech_keywords):
            return 'tech'
        if any(kw in entity_lower for kw in retail_keywords):
            return 'retail'
        if any(kw in entity_lower for kw in financial_keywords):
            return 'financial'
        
        return 'default'
    
    @classmethod
    def get_insight(cls, industry: str, metric: str, value: float) -> str:
        """
        Get industry-appropriate insight for a metric
        
        Args:
            industry: Industry classification ('tech', 'retail', 'financial', 'default')
            metric: Metric name (e.g., 'inventory_turnover', 'rnd_intensity')
            value: The calculated metric value
        
        Returns:
            Formatted insight string
        """
        templates = cls.INDUSTRY_TEMPLATES.get(industry, cls.INDUSTRY_TEMPLATES['default'])
        metric_templates = templates.get(metric, cls.INDUSTRY_TEMPLATES['default'].get(metric, {}))
        
        if not metric_templates:
            return f"{metric}: {value:.2f}"
        
        # Determine high/low based on metric thresholds
        threshold = cls.THRESHOLDS.get(metric, 5.0)
        
        # Special handling for DSO (lower is better)
        if metric == 'dso':
            level = 'low' if value <= threshold else 'high'
        else:
            level = 'high' if value >= threshold else 'low'
        
        template = metric_templates.get(level, f"{metric}: {value:.2f}")
        return template.format(value=value)


# ============================================================
# EXPERT COT GENERATOR (v11.0)
# ============================================================

class ExpertCoTGenerator:
    """
    v11.0: Expert Chain-of-Thought Generator - CFA Level III Standard
    
    Framework: 4-Step Analysis Chain
    1. [Definition]: Accounting definition + investor significance
    2. [Synthesis]: Cross-table data extraction and linking
    3. [Symbolic Reasoning]: LaTeX formula with step-by-step calculation
    4. [Professional Insight]: Industry-specific analyst interpretation
    """
    
    METRIC_DEFINITIONS = {
        'inventory_turnover': (
            "Inventory Turnover measures how many times a company's inventory is sold and "
            "replaced over a period. For investors, this ratio reveals operational efficiency "
            "and working capital management effectiveness. High turnover indicates strong "
            "demand and efficient inventory management; low turnover may signal obsolescence risk."
        ),
        'dso': (
            "Days Sales Outstanding (DSO) represents the average number of days required to "
            "collect payment after a sale. It directly impacts cash flow and working capital "
            "requirements. Lower DSO indicates efficient collection; higher DSO may signal "
            "credit quality issues or lax collection policies."
        ),
        'asset_turnover': (
            "Asset Turnover measures revenue generated per dollar of assets. This efficiency "
            "ratio helps investors assess how effectively management deploys capital. Higher "
            "ratios indicate efficient asset utilization; lower ratios may be acceptable in "
            "capital-intensive industries."
        ),
        'rnd_intensity': (
            "R&D Intensity represents the percentage of revenue reinvested in research and "
            "development. For technology companies, this metric signals commitment to "
            "innovation and future competitive positioning. Investors evaluate this against "
            "industry norms and the company's growth strategy."
        ),
        'operating_margin': (
            "Operating Margin measures operating profit as a percentage of revenue, indicating "
            "core business profitability before interest and taxes. It reflects pricing power, "
            "cost efficiency, and scalability of the business model."
        ),
        'current_ratio': (
            "Current Ratio assesses short-term liquidity by comparing current assets to "
            "current liabilities. A ratio above 1.0 indicates ability to meet short-term "
            "obligations; ratios below 1.0 suggest potential liquidity stress."
        ),
        'debt_ratio': (
            "Debt-to-Equity Ratio measures financial leverage by comparing total liabilities "
            "to shareholders' equity. It indicates the extent of debt financing and associated "
            "financial risk. Optimal levels vary by industry and interest rate environment."
        ),
        'roe': (
            "Return on Equity (ROE) measures profitability relative to shareholders' investment. "
            "It indicates management's effectiveness in generating returns from equity capital. "
            "DuPont analysis can decompose ROE into margin, turnover, and leverage components."
        ),
    }
    
    @classmethod
    def generate(
        cls,
        metric_name: str,
        formula_latex: str,
        data_sources: List[Tuple[str, str, Decimal]],  # [(statement, label, value), ...]
        calculation_steps: List[str],
        result: float,
        industry: str,
        company_name: str = "",
        verification_result: Optional[Tuple[bool, str]] = None
    ) -> str:
        """
        Generate complete 4-step CoT analysis
        
        Args:
            metric_name: Name of the metric (e.g., 'inventory_turnover')
            formula_latex: LaTeX formula string
            data_sources: List of (statement, label, value) tuples
            calculation_steps: List of calculation step strings
            result: Final calculated result
            industry: Industry classification
            company_name: Company name for context
            verification_result: Optional (is_valid, message) from arithmetic check
        
        Returns:
            Formatted 4-step CoT response
        """
        # Get definition
        definition = cls.METRIC_DEFINITIONS.get(
            metric_name, 
            f"{metric_name.replace('_', ' ').title()} analysis"
        )
        
        # Build synthesis section
        synthesis_lines = []
        for stmt, label, val in data_sources:
            synthesis_lines.append(f"- {stmt}: {label} = {ScaleProcessor.format_currency(val)}")
        synthesis = "\n".join(synthesis_lines)
        
        # Build symbolic reasoning
        symbolic = f"$${formula_latex}$$\n\n" + "\n".join(calculation_steps)
        
        # Get industry insight
        insight = IndustryInsightEngine.get_insight(industry, metric_name, result)
        
        # Build verification section if provided
        verification_section = ""
        if verification_result:
            is_valid, verify_msg = verification_result
            verification_section = f"\n\n[Verification]\n{verify_msg}"
        
        response = f"""[Definition]
{definition}

[Synthesis]
{synthesis}

[Symbolic Reasoning]
{symbolic}

[Professional Insight]
{insight}{verification_section}
"""
        return response


# ============================================================
# OUTPUT VALIDATOR (v11.0)
# ============================================================

class OutputValidator:
    """
    v11.0: Comprehensive Output Validation Suite
    
    Checks:
    1. Unit consistency (all values in $B)
    2. Precision compliance (3 or 6 decimals)
    3. No Korean text in output
    4. Arithmetic verification pass
    """
    
    @classmethod
    def validate_jsonl_output(cls, jsonl_lines: List[str]) -> Tuple[bool, Dict[str, Any]]:
        """
        Run all validation checks on output
        
        Returns:
            (all_passed, detailed_results)
        """
        results = {
            'unit_check': {'passed': True, 'errors': []},
            'precision_check': {'passed': True, 'errors': []},
            'language_check': {'passed': True, 'errors': []},
            'total_lines': len(jsonl_lines),
        }
        
        for i, line in enumerate(jsonl_lines):
            # 1. Unit check - no Million, Trillion, Thousand suffix
            if re.search(r'\$[\d.]+[MKT][^a-zA-Z]', line):
                results['unit_check']['passed'] = False
                results['unit_check']['errors'].append(f"Line {i+1}: Non-billion unit detected")
            
            # 2. Precision check - must have 3 or 6 decimals for B values
            matches = re.findall(r'\$(\d+\.\d+)B', line)
            for match in matches:
                decimals = len(match.split('.')[1])
                if decimals not in [3, 6]:
                    results['precision_check']['passed'] = False
                    results['precision_check']['errors'].append(
                        f"Line {i+1}: Invalid precision {decimals} decimals"
                    )
            
            # 3. Korean text check
            if re.search(r'[\u3131-\u318E\uAC00-\uD7A3]', line):
                results['language_check']['passed'] = False
                results['language_check']['errors'].append(f"Line {i+1}: Korean text detected")
        
        all_passed = all(r['passed'] for k, r in results.items() if isinstance(r, dict) and 'passed' in r)
        return all_passed, results


# ============================================================
# XBRL SEMANTIC ENGINE
# ============================================================

class XBRLSemanticEngine:
    """
    XBRL 시맨틱 결합 엔진
    
    범용 금융 AI 학습 데이터 생성을 위한 통합 파이프라인:
    
    워크플로우:
    1. _lab.xml 우선 파싱 → 라벨 매핑 구축
    2. _htm.xml 파싱 → 기술적 태그를 라벨로 치환
    3. 수치 스케일 표준화 (decimals 처리)
    4. 컨텍스트 필터링 (연결재무 우선)
    5. 추론형 Q&A 생성 → CoT 포맷
    6. 구조화된 마크다운 리포트 생성
    """
    
    def __init__(self, company_name: str = "", fiscal_year: str = "", sic_code: Optional[str] = None):
        self.company_name = company_name
        self.fiscal_year = fiscal_year
        self.sic_code = sic_code  # v11.0: Industry classification
        self.label_mapping: Dict[str, str] = {}  # concept → human label
        self.contexts: Dict[str, ParsedContext] = {}
        self.facts: List[SemanticFact] = []
        self.errors: List[str] = []
        self.parse_log: List[str] = []
        
        # 프로세서 초기화
        self.scale_processor = ScaleProcessor()
        self.context_filter = ContextFilter()
    
    @property
    def industry_code(self) -> str:
        """v11.0: Get industry classification for sector-specific insights"""
        return IndustryInsightEngine.classify_industry(self.company_name, self.sic_code)
        
    def process_joint(
        self, 
        label_content: Optional[bytes] = None,
        instance_content: Optional[bytes] = None
    ) -> XBRLIntelligenceResult:
        """
        시맨틱 결합 파싱 수행
        
        Args:
            label_content: _lab.xml 내용 (선택적, 없으면 기본 라벨 사용)
            instance_content: _htm.xml 또는 XBRL 인스턴스 내용
        
        Returns:
            XBRLIntelligenceResult: 완전한 AI 학습 데이터
        """
        self.parse_log.append(f"Starting joint parsing at {datetime.now().isoformat()}")
        
        try:
            # 1. Label Linkbase 파싱 (있으면)
            if label_content:
                self._build_label_mapping(label_content)
                self.parse_log.append(f"Built label mapping with {len(self.label_mapping)} entries")
            
            # 2. Instance Document 파싱
            if instance_content:
                self._parse_instance(instance_content)
                self.parse_log.append(f"Parsed {len(self.facts)} facts from instance")
            
            # 3. 핵심 재무 데이터 필터링
            core_facts = self._filter_core_financials()
            self.parse_log.append(f"Filtered to {len(core_facts)} core financial facts")
            
            # 4. 수치 데이터 검증
            if not core_facts:
                return self._build_empty_result("수치 데이터가 추출되지 않았습니다.")
            
            # 5. 추론형 Q&A 생성
            reasoning_qa = self._generate_reasoning_qa(core_facts)
            self.parse_log.append(f"Generated {len(reasoning_qa)} reasoning Q&A pairs")
            
            # 6. 마크다운 리포트 생성
            markdown_report = self._generate_financial_report(core_facts)
            
            # 7. JSONL 생성
            jsonl_data = self._generate_jsonl(core_facts, reasoning_qa)
            
            # 8. 주요 지표 추출
            key_metrics = self._extract_key_metrics(core_facts)
            
            return XBRLIntelligenceResult(
                success=True,
                company_name=self.company_name,
                fiscal_year=self.fiscal_year,
                facts=core_facts,
                reasoning_qa=reasoning_qa,
                financial_report_md=markdown_report,
                jsonl_data=jsonl_data,
                key_metrics=key_metrics,
                parse_summary="; ".join(self.parse_log[-5:]),
                errors=self.errors
            )
            
        except Exception as e:
            logger.error(f"Joint parsing failed: {e}")
            self.errors.append(str(e))
            return self._build_empty_result(f"파싱 실패: {e}")
    
    def _build_label_mapping(self, label_content: bytes) -> None:
        """_lab.xml에서 라벨 매핑 구축"""
        try:
            from .label_linkbase_parser import LabelLinkbaseParser
            
            parser = LabelLinkbaseParser()
            result = parser.parse(label_content)
            
            if result.get('success') and 'mappings' in result:
                for mapping in result['mappings']:
                    concept = mapping.get('concept', '')
                    label = mapping.get('preferred_label', '')
                    if concept and label:
                        self.label_mapping[concept] = label
            
            # 기본 라벨도 추가
            self.label_mapping.update(CoreFinancialConcepts.ALL_CONCEPTS)
            
        except ImportError:
            logger.warning("LabelLinkbaseParser not available, using default labels")
            self.label_mapping = CoreFinancialConcepts.ALL_CONCEPTS.copy()
        except Exception as e:
            logger.error(f"Label mapping build failed: {e}")
            self.label_mapping = CoreFinancialConcepts.ALL_CONCEPTS.copy()
    
    def _parse_instance(self, content: bytes) -> None:
        """XBRL 인스턴스 문서 파싱"""
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(content)
            
            # 컨텍스트 파싱
            self._parse_contexts(root)
            
            # 팩트 파싱
            self._parse_facts(root)
            
        except ET.ParseError as e:
            self.errors.append(f"XML Parse Error: {e}")
    
    def _parse_contexts(self, root) -> None:
        """컨텍스트 요소 파싱"""
        import xml.etree.ElementTree as ET
        
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            if tag == 'context':
                context_id = elem.get('id', '')
                if not context_id:
                    continue
                
                ctx = ParsedContext(id=context_id)
                
                for child in elem.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    
                    if child_tag == 'identifier' and child.text:
                        ctx.entity = child.text
                    elif child_tag == 'startDate' and child.text:
                        ctx.start_date = child.text
                    elif child_tag == 'endDate' and child.text:
                        ctx.end_date = child.text
                    elif child_tag == 'instant' and child.text:
                        ctx.instant = child.text
                    elif child_tag == 'explicitMember' and child.text:
                        ctx.segment_members.append(child.text)
                
                # 연결/별도 분류
                ctx.is_consolidated, _ = self.context_filter.classify_context(ctx)
                
                self.contexts[context_id] = ctx
    
    def _parse_facts(self, root) -> None:
        """
        팩트 요소 파싱 및 시맨틱 라벨 적용
        
        🔴 Fixed: 
        - ScaleProcessor.is_valid_numeric_value() 사용
        - 3-tuple 반환값 처리 (value, desc, is_valid)
        - URL/날짜 값 자동 필터링
        """
        import xml.etree.ElementTree as ET
        
        for elem in root.iter():
            # 값이 있는 요소만
            if not elem.text or not elem.text.strip():
                continue
            
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            
            # 메타데이터 태그 제외
            if tag in ('context', 'unit', 'schemaRef', 'linkbaseRef', 'identifier',
                       'startDate', 'endDate', 'instant', 'measure', 'explicitMember',
                       'segment', 'entity', 'period'):
                continue
            
            context_ref = elem.get('contextRef', '')
            unit_ref = elem.get('unitRef', '')
            decimals = elem.get('decimals')
            
            raw_value = elem.text.strip()
            
            # 🔴 FIX: ScaleProcessor의 유효성 검사 사용
            if not ScaleProcessor.is_valid_numeric_value(raw_value):
                continue
            
            # 네임스페이스에서 전체 개념 이름 구축
            namespace = elem.tag.split('}')[0].replace('{', '') if '}' in elem.tag else ''
            concept = self._build_concept_name(tag, namespace)
            
            # 시맨틱 라벨 적용 (기술 태그 → 인간 친화적 라벨)
            # 🔴 FIX: 오타 수정 적용 (이익익 → 이익)
            raw_label = self._apply_semantic_label(concept)
            label = ScaleProcessor.fix_label_typos(raw_label)
            
            # 🔴 FIX: 스케일 처리 - 새 API 사용 (3-tuple)
            standardized_value, scale_desc, is_valid = ScaleProcessor.standardize_value(
                raw_value, decimals, unit_ref
            )
            
            # 유효하지 않은 값 스킵
            if not is_valid:
                self.parse_log.append(f"Skipped invalid value: {raw_value} for {concept}")
                continue
            
            # 컨텍스트 정보
            ctx = self.contexts.get(context_ref, ParsedContext(id=context_ref))
            
            # 기간 추출
            period = ""
            if ctx.instant:
                period = ctx.instant[:4]
            elif ctx.end_date:
                period = ctx.end_date[:4]
            
            # 회사명 추출 시도
            if not self.company_name and ctx.entity:
                self.company_name = ctx.entity
            
            # 회계연도 추출
            if not self.fiscal_year and period:
                self.fiscal_year = period
            
            fact = SemanticFact(
                concept=concept,
                label=label,
                value=standardized_value,
                raw_value=raw_value,
                unit=unit_ref,
                period=period,
                context_ref=context_ref,
                decimals=int(decimals) if decimals and decimals.lstrip('-').isdigit() else None,
                hierarchy=CoreFinancialConcepts.get_hierarchy(concept),
                is_consolidated=ctx.is_consolidated,
                segment=ctx.segment_members[0] if ctx.segment_members else None
            )
            
            self.facts.append(fact)
    
    def _build_concept_name(self, tag: str, namespace: str) -> str:
        """네임스페이스와 태그로 전체 개념 이름 구축"""
        if 'ifrs' in namespace.lower():
            return f"ifrs-full_{tag}"
        elif 'gaap' in namespace.lower():
            return f"us-gaap_{tag}"
        elif 'dart' in namespace.lower():
            return f"dart_{tag}"
        return tag
    
    def _apply_semantic_label(self, concept: str) -> str:
        """기술적 태그에 인간 친화적 라벨 적용"""
        # 1. 명시적 매핑 확인
        if concept in self.label_mapping:
            return self.label_mapping[concept]
        
        # 2. 부분 매칭 시도
        for key, label in self.label_mapping.items():
            if concept.endswith(key) or key.endswith(concept.split('_')[-1]):
                return label
        
        # 3. CoreFinancialConcepts 폴백
        return CoreFinancialConcepts.get_label(concept)
    
    def _is_numeric(self, value: str) -> bool:
        """수치 여부 확인"""
        clean = value.replace(',', '').replace(' ', '').replace('-', '').replace('.', '')
        return clean.isdigit()
    
    def _filter_core_financials(self) -> List[SemanticFact]:
        """
        핵심 재무 데이터 필터링
        
        1. 연결재무제표 우선
        2. 핵심 계정 과목 우선
        3. 수치 데이터만
        """
        # 연결재무제표 우선 필터링
        filtered = self.context_filter.filter_consolidated_priority(self.facts)
        
        # 핵심 재무 개념 필터링  
        core = []
        other = []
        
        for fact in filtered:
            if CoreFinancialConcepts.is_core_financial(fact.concept):
                core.append(fact)
            elif fact.value != 0:  # 0이 아닌 값만
                other.append(fact)
        
        # 핵심 우선, 기타 후순위
        result = core + other
        
        # 금액 크기 순 정렬
        result.sort(key=lambda f: abs(float(f.value)), reverse=True)
        
        return result
    
    def _generate_reasoning_qa(self, facts: List[SemanticFact]) -> List[Dict[str, str]]:
        """
        추론형 Q&A 생성 (CoT 포맷) - v2 확장판
        
        🔴 FIX: 최소 50개 이상 Q&A 생성
        - 비율 분석 (Ratio Analysis)
        - 구성비 분석 (Composition %)  
        - 상위 항목 분석 (Top-N Analysis)
        - YoY 성장률 (Time Series)
        """
        qa_pairs = []
        
        # 1. 유연한 라벨 매칭으로 fact_dict 구축
        fact_dict = self._build_flexible_fact_dict(facts)
        
        # 2. 핵심 비율 분석 Q&A (5-10개)
        qa_pairs.extend(self._generate_ratio_analysis_qa(fact_dict, facts))
        
        # 3. 자산 구성비 분석 Q&A (개별 항목별, 20개+)
        qa_pairs.extend(self._generate_composition_qa(fact_dict, facts))
        
        # 4. 상위 20개 항목 분석 Q&A (20개)
        qa_pairs.extend(self._generate_top_items_qa(facts[:20]))
        
        # 5. 재무 건전성 종합 평가 Q&A
        qa = self._generate_financial_health_qa(fact_dict, facts)
        if qa:
            qa_pairs.append(qa)
            
        # 6. 활동성 분석 Q&A (v6.0)
        qa_pairs.extend(self._generate_activity_analysis_qa(fact_dict, facts))
        
        # 7. 효율성 분석 Q&A (v6.0)
        qa_pairs.extend(self._generate_efficiency_qa(fact_dict, facts))
        
        # 8. 추세 분석 Q&A (v6.0 - YoY)
        qa_pairs.extend(self._generate_trend_analysis_qa(facts))
        
        return qa_pairs
    
    def _build_flexible_fact_dict(self, facts: List[SemanticFact], target_period: str = None) -> Dict:
        """
        유연한 라벨/개념 매칭을 위한 복합 딕셔너리 구축
        
        Args:
            facts: 팩트 리스트
            target_period: 특정 기간(예: "2024") 데이터만 필터링 (None이면 모두)
        """
        fact_dict = {}
        
        # 핵심 항목 별칭 정의 (다양한 태그명 매핑)
        ALIASES = {
            'total_assets': ['Assets', 'TotalAssets', 'AssetsTotal', '자산총계', 'assets'],
            'total_liabilities': ['Liabilities', 'TotalLiabilities', 'LiabilitiesTotal', '부채총계', 'liabilities'],
            'total_equity': ['Equity', 'StockholdersEquity', 'TotalEquity', '자본총계', 'equity', 'ShareholdersEquity'],
            'current_assets': ['CurrentAssets', 'AssetsCurrent', '유동자산', 'currentassets'],
            'current_liabilities': ['CurrentLiabilities', 'LiabilitiesCurrent', '유동부채', 'currentliabilities'],
            'noncurrent_assets': ['NoncurrentAssets', 'AssetsNoncurrent', '비유동자산'],
            'revenue': ['Revenue', 'Revenues', 'NetSales', 'Sales', '매출액', 'TotalRevenue', 'RevenueFromContractWithCustomerExcludingAssessedTax'],
            'net_income': ['NetIncome', 'ProfitLoss', 'NetIncomeLoss', '당기순이익', 'NetEarnings'],
            'gross_profit': ['GrossProfit', '매출총이익', 'GrossMargin'],
            'operating_income': ['OperatingIncome', 'OperatingProfit', '영업이익', 'IncomeFromOperations'],
            'cash': ['Cash', 'CashAndCashEquivalents', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents', '현금및현금성자산'],
            'inventory': ['Inventory', 'Inventories', 'InventoryNet', '재고자산'],
            'receivables': ['AccountsReceivable', 'TradeReceivables', 'AccountsReceivableNetCurrent', '매출채권'],
            'cogs': ['CostOfGoodsAndServicesSold', 'CostOfRevenue', 'CostOfSales', '매출원가'],
            'rnd_expenses': ['ResearchAndDevelopmentExpense', 'ResearchAndDevelopment', 'ResearchAndDevelopmentExpenseExcludingAmortization', 'RndExpenese', '경상연구개발비'],
            'sga_expenses': ['SellingGeneralAndAdministrativeExpense', 'SellingGeneralAndAdministrative', 'SGA', '판관비', '판매비와관리비'],
        }
        
        for fact in facts:
            # 기간 필터링
            if target_period and fact.period != target_period:
                continue

            # 원본 라벨/개념으로 저장
            key = f"{fact.label}_{fact.period}"
            fact_dict[key] = fact
            fact_dict[fact.label] = fact
            fact_dict[fact.concept] = fact
            
            # 개념명의 마지막 부분으로도 저장 (us-gaap:Assets -> Assets)
            short_concept = fact.concept.split('_')[-1].split(':')[-1]
            fact_dict[short_concept] = fact
            fact_dict[short_concept.lower()] = fact
            
            # 별칭 매핑 체크
            for alias_key, patterns in ALIASES.items():
                for pattern in patterns:
                    if pattern.lower() in short_concept.lower() or pattern.lower() == short_concept.lower():
                        if alias_key not in fact_dict:  # 첫 매칭만
                            fact_dict[alias_key] = fact
                        break
        
        return fact_dict
    
    def _generate_ratio_analysis_qa(self, fact_dict: Dict, facts: List[SemanticFact]) -> List[Dict]:
        """비율 분석 Q&A 생성 (여러 종류)"""
        qa_list = []
        
        # 1. 부채비율 (Debt Ratio)
        liabilities = fact_dict.get('total_liabilities')
        equity = fact_dict.get('total_equity')
        
        if liabilities and equity and float(equity.value) != 0:
            ratio = float(liabilities.value) / float(equity.value) * 100
            qa_list.append({
                "question": f"Calculate the Debt-to-Equity Ratio for {self.company_name or 'this company'} in {self.fiscal_year}.",
                "response": f"""## Debt-to-Equity Ratio Analysis

### Formula
$$\\text{{Debt Ratio}} = \\frac{{\\text{{Total Liabilities}}}}{{\\text{{Total Equity}}}} \\times 100$$

### Calculation
- Total Liabilities: {ScaleProcessor.format_currency(liabilities.value)}
- Total Equity: {ScaleProcessor.format_currency(equity.value)}

$$\\text{{Debt Ratio}} = \\frac{{{float(liabilities.value):,.0f}}}{{{float(equity.value):,.0f}}} \\times 100 = {ratio:.2f}\\%$$

### Result: **{ratio:.2f}%**

### Interpretation
{'⚠️ High leverage (>200%). Interest burden and debt repayment capacity require attention.' if ratio > 200 else '✅ Healthy leverage ratio. Financial structure is stable.' if ratio <= 100 else 'Moderate leverage. Within acceptable range but monitor closely.'}
""",
                "type": "ratio_analysis"
            })
        
        # 2. 부채-자산 비율 (Debt-to-Assets)
        assets = fact_dict.get('total_assets')
        if liabilities and assets and float(assets.value) != 0:
            ratio = float(liabilities.value) / float(assets.value) * 100
            qa_list.append({
                "question": f"What percentage of {self.company_name or 'the company'}'s total assets are financed by debt?",
                "response": f"""## Debt-to-Assets Ratio

### Formula
$$\\text{{Debt-to-Assets}} = \\frac{{\\text{{Total Liabilities}}}}{{\\text{{Total Assets}}}} \\times 100$$

### Calculation
- Total Liabilities: {ScaleProcessor.format_currency(liabilities.value)}
- Total Assets: {ScaleProcessor.format_currency(assets.value)}

### Result: **{ratio:.2f}%**

### Interpretation
This means {ratio:.1f}% of the company's assets are financed through debt, while {100-ratio:.1f}% are financed through equity.
""",
                "type": "ratio_analysis"
            })
        
        # 3. 유동비율 (Current Ratio)
        current_assets = fact_dict.get('current_assets')
        current_liabilities = fact_dict.get('current_liabilities')
        
        if current_assets and current_liabilities and float(current_liabilities.value) != 0:
            ratio = float(current_assets.value) / float(current_liabilities.value)
            qa_list.append({
                "question": f"Evaluate the short-term liquidity position using the Current Ratio.",
                "response": f"""## Current Ratio Analysis

### Formula
$$\\text{{Current Ratio}} = \\frac{{\\text{{Current Assets}}}}{{\\text{{Current Liabilities}}}}$$

### Calculation
- Current Assets: {ScaleProcessor.format_currency(current_assets.value)}
- Current Liabilities: {ScaleProcessor.format_currency(current_liabilities.value)}

### Result: **{ratio:.2f}x**

### Interpretation
{'✅ Strong liquidity (>2.0x). Company can easily cover short-term obligations.' if ratio >= 2.0 else '⚠️ Weak liquidity (<1.0x). May face difficulty meeting short-term obligations.' if ratio < 1.0 else 'Adequate liquidity. Can meet short-term obligations.'}
""",
                "type": "ratio_analysis"
            })
        
        # 4. 자기자본비율 (Equity Ratio)
        if equity and assets and float(assets.value) != 0:
            ratio = float(equity.value) / float(assets.value) * 100
            qa_list.append({
                "question": f"What is the Equity Ratio and what does it indicate about financial stability?",
                "response": f"""## Equity Ratio Analysis

### Formula
$$\\text{{Equity Ratio}} = \\frac{{\\text{{Total Equity}}}}{{\\text{{Total Assets}}}} \\times 100$$

### Calculation
- Total Equity: {ScaleProcessor.format_currency(equity.value)}
- Total Assets: {ScaleProcessor.format_currency(assets.value)}

### Result: **{ratio:.2f}%**

### Interpretation
An equity ratio of {ratio:.1f}% means shareholders own {ratio:.1f}% of total assets outright, indicating {'strong' if ratio > 50 else 'moderate' if ratio > 30 else 'lower'} financial independence.
""",
                "type": "ratio_analysis"
            })
        
        # 5. 현금 비중
        cash = fact_dict.get('cash')
        if cash and assets and float(assets.value) != 0:
            ratio = float(cash.value) / float(assets.value) * 100
            qa_list.append({
                "question": f"What percentage of total assets is held as cash and cash equivalents?",
                "response": f"""## Cash Position Analysis

### Calculation
- Cash & Equivalents: {ScaleProcessor.format_currency(cash.value)}
- Total Assets: {ScaleProcessor.format_currency(assets.value)}

### Cash Ratio: **{ratio:.2f}%**

### Interpretation
The company maintains {ratio:.1f}% of assets in liquid form. {'High cash position provides flexibility for investments or acquisitions.' if ratio > 20 else 'Moderate cash position.' if ratio > 10 else 'Lower cash reserves; company may be investing aggressively or returning cash to shareholders.'}
""",
                "type": "ratio_analysis"
            })
        
        return qa_list
    
    def _generate_composition_qa(self, fact_dict: Dict, facts: List[SemanticFact]) -> List[Dict]:
        """개별 항목의 총자산 대비 구성비 Q&A 생성"""
        qa_list = []
        
        total_assets = fact_dict.get('total_assets')
        if not total_assets or float(total_assets.value) == 0:
            return qa_list
        
        total_val = float(total_assets.value)
        
        # 자산 관련 항목들의 구성비 분석
        asset_facts = [f for f in facts if 'asset' in f.label.lower() or 'asset' in f.concept.lower() 
                       or '자산' in f.label]
        
        for fact in asset_facts[:15]:  # 상위 15개
            if float(fact.value) > 0 and fact.label != '자산총계' and 'total' not in fact.label.lower():
                ratio = float(fact.value) / total_val * 100
                if ratio > 0.1:  # 0.1% 이상만
                    qa_list.append({
                        "question": f"What is the proportion of {fact.label} to total assets?",
                        "response": f"""## Asset Composition: {fact.label}

### Values
- {fact.label}: {ScaleProcessor.format_currency(fact.value)}
- Total Assets: {ScaleProcessor.format_currency(total_assets.value)}

### Composition Ratio: **{ratio:.2f}%**

This item represents {ratio:.2f}% of total assets ({self.fiscal_year}).
""",
                        "type": "composition_analysis"
                    })
        
        return qa_list
    
    def _generate_top_items_qa(self, top_facts: List[SemanticFact]) -> List[Dict]:
        """상위 N개 항목에 대한 개별 Q&A 생성"""
        qa_list = []
        
        for i, fact in enumerate(top_facts, 1):
            qa_list.append({
                "question": f"What is the value of {fact.label} in the {self.fiscal_year} financial statements?",
                "response": f"""## {fact.label}

### Value: **{ScaleProcessor.format_currency(fact.value)}**

### Details
- Period: {fact.period}
- Category: {fact.hierarchy}
- Consolidated: {'Yes' if fact.is_consolidated else 'No'}

This is ranked #{i} by absolute value among all reported items.
""",
                "type": "item_lookup"
            })
        
        return qa_list
    
    def _generate_financial_health_qa(self, fact_dict: Dict, facts: List[SemanticFact]) -> Optional[Dict]:
        """종합 재무 건전성 평가 Q&A"""
        assets = fact_dict.get('total_assets')
        liabilities = fact_dict.get('total_liabilities')
        equity = fact_dict.get('total_equity')
        
        if not assets or not liabilities:
            return None
        
        # 🔴 FIX: 재무 등식(Sanity Check) 검증
        is_valid_eq, eq_msg = ScaleProcessor.validate_financial_equation(
            assets.value, liabilities.value, equity.value if equity else None
        )
        
        debt_ratio = float(liabilities.value) / float(assets.value) * 100 if assets else 0
        equity_ratio = float(equity.value) / float(assets.value) * 100 if equity and assets else 0
        
        return {
            "question": f"Provide a comprehensive financial health assessment for {self.company_name or 'this company'}.",
            "response": f"""## Comprehensive Financial Health Assessment

### 📊 Data Integrity Check (Sanity Check)
{eq_msg}

### Key Metrics Summary
| Metric | Value |
|--------|-------|
| Total Assets | {ScaleProcessor.format_currency(assets.value)} |
| Total Liabilities | {ScaleProcessor.format_currency(liabilities.value)} |
| Total Equity | {ScaleProcessor.format_currency(equity.value) if equity else 'N/A'} |
| Debt-to-Assets | {debt_ratio:.1f}% |
| Equity Ratio | {equity_ratio:.1f}% |

### Overall Assessment
{'✅ **Strong Financial Position**: Low leverage with substantial equity buffer.' if debt_ratio < 50 else '⚠️ **Moderate Risk**: Higher leverage requires monitoring.' if debt_ratio < 70 else '❌ **High Risk**: Significant debt burden may impact financial flexibility.'}

### Number of Items Analyzed: {len(facts)}
""",
            "type": "comprehensive_analysis"
        }
    
    def _generate_activity_analysis_qa(self, fact_dict: Dict, facts: List[SemanticFact]) -> List[Dict]:
        """
        v11.0: Activity Analysis Q&A with Expert CoT Framework
        
        Features:
        - 4-Step Analysis Chain (Definition, Synthesis, Symbolic Reasoning, Professional Insight)
        - Time-Series Average Calculation: (Beginning + Ending) / 2
        - Arithmetic Cross-Check Verification
        - Industry-Specific Insights
        """
        qa_list = []
        
        # Load Prior Year Data for averaging
        try:
            current_year = int(self.fiscal_year)
            prior_year = str(current_year - 1)
            py_fact_dict = self._build_flexible_fact_dict(facts, target_period=prior_year)
        except:
            py_fact_dict = {}
        
        # Get industry classification
        industry = self.industry_code
        
        # 1. Inventory Turnover - Expert CoT
        cogs = fact_dict.get('cogs')
        inventory = fact_dict.get('inventory')
        
        if cogs and inventory:
            py_inventory = py_fact_dict.get('inventory')
            
            # v11.0: Use proper averaging logic
            avg_inv, avg_desc = ScaleProcessor.calculate_average_balance(
                inventory.value,
                py_inventory.value if py_inventory else None,
                "Inventory"
            )
            
            if float(avg_inv) > 0:
                turnover = float(cogs.value) / float(avg_inv)
                
                # Arithmetic verification
                verify_result = ScaleProcessor.verify_calculation(
                    "Inventory Turnover", cogs.value, avg_inv, turnover
                )
                
                # Generate expert CoT response
                cogs_b = float(cogs.value) / 1e9
                avg_inv_b = float(avg_inv) / 1e9
                
                response = ExpertCoTGenerator.generate(
                    metric_name='inventory_turnover',
                    formula_latex=r"Inventory\ Turnover = \frac{Cost\ of\ Goods\ Sold}{\frac{Beginning\ Inv + Ending\ Inv}{2}}",
                    data_sources=[
                        ("Income Statement", "Cost of Goods Sold", cogs.value),
                        ("Balance Sheet (Current)", "Ending Inventory", inventory.value),
                        ("Balance Sheet (Prior)", "Beginning Inventory", py_inventory.value if py_inventory else Decimal(0)),
                    ],
                    calculation_steps=[
                        avg_desc,
                        f"$= \\frac{{{cogs_b:.3f}B}}{{{avg_inv_b:.3f}B}} = {turnover:.2f}$ times"
                    ],
                    result=turnover,
                    industry=industry,
                    company_name=self.company_name,
                    verification_result=verify_result
                )
                
                qa_list.append({
                    "question": f"How does the Inventory Turnover ratio reflect {self.company_name}'s supply chain and inventory management efficiency, and what are the risk implications?",
                    "response": response,
                    "type": "activity_analysis",
                    "context": f"Cost of Goods Sold: {ScaleProcessor.format_currency(cogs.value)}, Average Inventory: {ScaleProcessor.format_currency(avg_inv)}"
                })

        # 2. Days Sales Outstanding (DSO) - Expert CoT
        revenue = fact_dict.get('revenue')
        receivables = fact_dict.get('receivables')
        
        if revenue and receivables:
            py_recv = py_fact_dict.get('receivables')
            
            # v11.0: Use proper averaging logic
            avg_recv, recv_avg_desc = ScaleProcessor.calculate_average_balance(
                receivables.value,
                py_recv.value if py_recv else None,
                "Receivables"
            )
                
            if float(avg_recv) > 0:
                recv_turnover = float(revenue.value) / float(avg_recv)
                dso = 365 / recv_turnover
                
                # Arithmetic verification
                verify_result = ScaleProcessor.verify_calculation(
                    "DSO", Decimal(365), Decimal(recv_turnover), dso
                )
                
                rev_b = float(revenue.value) / 1e9
                avg_recv_b = float(avg_recv) / 1e9
                
                response = ExpertCoTGenerator.generate(
                    metric_name='dso',
                    formula_latex=r"DSO = \frac{365}{\frac{Revenues}{Average\ Receivables}}",
                    data_sources=[
                        ("Income Statement", "Revenues", revenue.value),
                        ("Balance Sheet (Current)", "Accounts Receivable", receivables.value),
                        ("Balance Sheet (Prior)", "Beginning Receivables", py_recv.value if py_recv else Decimal(0)),
                    ],
                    calculation_steps=[
                        recv_avg_desc,
                        f"Receivables Turnover $= \\frac{{{rev_b:.3f}B}}{{{avg_recv_b:.3f}B}} = {recv_turnover:.2f}$ times",
                        f"$DSO = \\frac{{365}}{{{recv_turnover:.2f}}} = {dso:.1f}$ days"
                    ],
                    result=dso,
                    industry=industry,
                    company_name=self.company_name,
                    verification_result=verify_result
                )
                
                qa_list.append({
                    "question": f"Why does the Days Sales Outstanding matter for {self.company_name}'s cash conversion cycle, and how does it compare to industry benchmarks?",
                    "response": response,
                    "type": "activity_analysis",
                    "context": f"Revenues: {ScaleProcessor.format_currency(revenue.value)}, Average Receivables: {ScaleProcessor.format_currency(avg_recv)}"
                })

        # 3. Asset Turnover - Expert CoT
        assets = fact_dict.get('total_assets')
        if revenue and assets:
            py_assets = py_fact_dict.get('total_assets')
            
            # v11.0: Use proper averaging logic
            avg_assets, assets_avg_desc = ScaleProcessor.calculate_average_balance(
                assets.value,
                py_assets.value if py_assets else None,
                "Total Assets"
            )
            
            if float(avg_assets) > 0:
                turnover = float(revenue.value) / float(avg_assets)
                
                # Arithmetic verification
                verify_result = ScaleProcessor.verify_calculation(
                    "Asset Turnover", revenue.value, avg_assets, turnover
                )
                
                rev_b = float(revenue.value) / 1e9
                avg_assets_b = float(avg_assets) / 1e9
                
                response = ExpertCoTGenerator.generate(
                    metric_name='asset_turnover',
                    formula_latex=r"Asset\ Turnover = \frac{Revenues}{\frac{Beginning\ Assets + Ending\ Assets}{2}}",
                    data_sources=[
                        ("Income Statement", "Revenues", revenue.value),
                        ("Balance Sheet (Current)", "Total Assets", assets.value),
                        ("Balance Sheet (Prior)", "Beginning Assets", py_assets.value if py_assets else Decimal(0)),
                    ],
                    calculation_steps=[
                        assets_avg_desc,
                        f"$= \\frac{{{rev_b:.3f}B}}{{{avg_assets_b:.3f}B}} = {turnover:.2f}$"
                    ],
                    result=turnover,
                    industry=industry,
                    company_name=self.company_name,
                    verification_result=verify_result
                )
                
                qa_list.append({
                    "question": f"How effectively does {self.company_name} utilize its assets to generate revenue, and what does the Asset Turnover indicate about capital efficiency?",
                    "response": response,
                    "type": "activity_analysis",
                    "context": f"Revenues: {ScaleProcessor.format_currency(revenue.value)}, Average Total Assets: {ScaleProcessor.format_currency(avg_assets)}"
                })
        
        return qa_list

    def _generate_efficiency_qa(self, fact_dict: Dict, facts: List[SemanticFact]) -> List[Dict]:
        """
        v11.0: Efficiency Analysis Q&A with Expert CoT Framework
        
        Features:
        - 4-Step Analysis Chain (Definition, Synthesis, Symbolic Reasoning, Professional Insight)
        - Arithmetic Cross-Check Verification
        - Industry-Specific Insights (Tech: R&D focus, Retail: margin focus)
        """
        qa_list = []
        industry = self.industry_code
        
        revenue = fact_dict.get('revenue')
        rnd = fact_dict.get('rnd_expenses')
        sga = fact_dict.get('sga_expenses')
        op_income = fact_dict.get('operating_income')
        
        # 1. R&D Intensity - Expert CoT
        if revenue and rnd and float(revenue.value) > 0:
            intensity = float(rnd.value) / float(revenue.value) * 100
            
            # Arithmetic verification
            verify_result = ScaleProcessor.verify_calculation(
                "R&D Intensity", rnd.value, revenue.value, intensity / 100
            )
            
            rev_b = float(revenue.value) / 1e9
            rnd_b = float(rnd.value) / 1e9
            
            response = ExpertCoTGenerator.generate(
                metric_name='rnd_intensity',
                formula_latex=r"R\&D\ Intensity = \frac{R\&D\ Expenses}{Revenues} \times 100\%",
                data_sources=[
                    ("Income Statement", "Revenues", revenue.value),
                    ("Income Statement", "R&D Expenses", rnd.value),
                ],
                calculation_steps=[
                    f"$= \\frac{{{rnd_b:.3f}B}}{{{rev_b:.3f}B}} \\times 100\\% = {intensity:.2f}\\%$"
                ],
                result=intensity,
                industry=industry,
                company_name=self.company_name,
                verification_result=verify_result
            )
            
            qa_list.append({
                "question": f"Why is R&D investment critical for {self.company_name}'s competitive positioning, and how does its R&D Intensity compare to sector benchmarks?",
                "response": response,
                "type": "efficiency_analysis",
                "context": f"R&D Expenses: {ScaleProcessor.format_currency(rnd.value)}, Revenues: {ScaleProcessor.format_currency(revenue.value)}"
            })
            
        # 2. Operating Margin - Expert CoT
        if revenue and op_income and float(revenue.value) > 0:
            margin = float(op_income.value) / float(revenue.value) * 100
            
            # Arithmetic verification
            verify_result = ScaleProcessor.verify_calculation(
                "Operating Margin", op_income.value, revenue.value, margin / 100
            )
            
            rev_b = float(revenue.value) / 1e9
            op_b = float(op_income.value) / 1e9
            
            response = ExpertCoTGenerator.generate(
                metric_name='operating_margin',
                formula_latex=r"Operating\ Margin = \frac{Operating\ Income}{Revenues} \times 100\%",
                data_sources=[
                    ("Income Statement", "Revenues", revenue.value),
                    ("Income Statement", "Operating Income", op_income.value),
                ],
                calculation_steps=[
                    f"$= \\frac{{{op_b:.3f}B}}{{{rev_b:.3f}B}} \\times 100\\% = {margin:.2f}\\%$"
                ],
                result=margin,
                industry=industry,
                company_name=self.company_name,
                verification_result=verify_result
            )
            
            qa_list.append({
                "question": f"How does {self.company_name}'s Operating Margin reflect its pricing power and cost efficiency, and what does it indicate about scalability?",
                "response": response,
                "type": "efficiency_analysis",
                "context": f"Operating Income: {ScaleProcessor.format_currency(op_income.value)}, Revenues: {ScaleProcessor.format_currency(revenue.value)}"
            })

        # 3. SG&A Efficiency - Simple format (less critical metric)
        if revenue and sga and float(revenue.value) > 0:
            ratio = float(sga.value) / float(revenue.value) * 100
            
            sga_b = float(sga.value) / 1e9
            rev_b = float(revenue.value) / 1e9
            
            qa_list.append({
                "question": f"What does the SG&A Efficiency Ratio reveal about {self.company_name}'s operational cost structure?",
                "response": f"""[Definition]
SG&A Ratio measures the percentage of revenue consumed by selling, general, and administrative expenses. It indicates operational efficiency and cost discipline.

[Synthesis]
- Income Statement: Revenues = {ScaleProcessor.format_currency(revenue.value)}
- Income Statement: SG&A Expenses = {ScaleProcessor.format_currency(sga.value)}

[Symbolic Reasoning]
$$SG\\&A\\ Ratio = \\frac{{SG\\&A\\ Expenses}}{{Revenues}} \\times 100\\%$$

$$= \\frac{{{sga_b:.3f}B}}{{{rev_b:.3f}B}} \\times 100\\% = {ratio:.2f}\\%$$

[Professional Insight]
SG&A expenses consume {ratio:.2f}% of revenue. {'✅ Highly efficient cost structure indicates strong operational leverage.' if ratio <= 15 else '⚠️ Higher SG&A may reflect investment in growth or distribution channels.' if ratio <= 25 else 'Elevated SG&A ratio warrants cost structure analysis.'}
""",
                "type": "efficiency_analysis",
                "context": f"SG&A Expenses: {ScaleProcessor.format_currency(sga.value)}, Revenues: {ScaleProcessor.format_currency(revenue.value)}"
            })
            
        return qa_list

    def _generate_trend_analysis_qa(self, facts: List[SemanticFact]) -> List[Dict]:
        """Trend Analysis Q&A (YoY Growth) - v10.0 English"""
        qa_list = []
        
        try:
            curr_year = str(self.fiscal_year)
            prev_year = str(int(self.fiscal_year) - 1)
        except:
            return []
            
        curr_dict = self._build_flexible_fact_dict(facts, target_period=curr_year)
        prev_dict = self._build_flexible_fact_dict(facts, target_period=prev_year)
        
        targets = [
            ('revenue', 'Revenues'),
            ('gross_profit', 'Gross Profit'),
            ('operating_income', 'Operating Income'),
            ('net_income', 'Net Income'),
            ('total_assets', 'Total Assets'),
            ('total_liabilities', 'Total Liabilities'),
            ('total_equity', 'Total Equity'),
            ('current_assets', 'Current Assets'),
            ('current_liabilities', 'Current Liabilities'),
            ('cash', 'Cash and Cash Equivalents'),
            ('inventory', 'Inventory'),
            ('receivables', 'Accounts Receivable')
        ]
        
        for key, label in targets:
            curr = curr_dict.get(key)
            prev = prev_dict.get(key)
            
            if curr and prev and float(prev.value) != 0:
                growth = (float(curr.value) - float(prev.value)) / abs(float(prev.value)) * 100
                
                is_outlier = abs(growth) > 50
                outlier_note = " ⚠️ Significant fluctuation detected." if is_outlier else ""
                
                qa_list.append({
                    "question": f"Analyze the Year-over-Year (YoY) growth of {label} for {self.company_name} in {curr_year}.",
                    "response": f"""[Definition]: YoY Growth calculated as (Current Year - Prior Year) / Prior Year * 100.
[Extraction]: Current Year ({curr_year}) {self.scale_processor.format_currency(curr.value)}, Prior Year ({prev_year}) {self.scale_processor.format_currency(prev.value)}
[Calculation]: ({float(curr.value):,.0f} - {float(prev.value):,.0f}) / {float(prev.value):,.0f} * 100 = {growth:+.2f}%
[Interpretation]: {label} {'increased' if growth > 0 else 'decreased'} by {abs(growth):.2f}%.{outlier_note} {'✅ High growth.' if growth >= 10 else 'Stable performance.'}""",
                    "type": "trend_analysis",
                    "context": f"Current {label}: {self.scale_processor.format_currency(curr.value)}, Prior {label}: {self.scale_processor.format_currency(prev.value)}"
                })
        
        return qa_list
    
    def _generate_debt_ratio_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """Debt Ratio Q&A - v10.0 English"""
        liabilities = facts.get('total_liabilities') or facts.get('부채총계') or facts.get('Liabilities')
        equity = facts.get('total_equity') or facts.get('자본총계') or facts.get('Equity')
        
        if not liabilities or not equity or float(equity.value) == 0:
            return None
        
        ratio = float(liabilities.value) / float(equity.value) * 100
        
        return {
            "question": f"Calculate the Debt-to-Equity Ratio for {self.company_name} in {self.fiscal_year} and assess financial leverage.",
            "response": f"""[Definition]: Debt-to-Equity Ratio measures the degree to which a company is financing its operations through debt versus wholly-owned funds. Formula: (Total Liabilities / Total Equity) * 100.
[Extraction]: Total Liabilities {self.scale_processor.format_currency(liabilities.value)}, Total Equity {self.scale_processor.format_currency(equity.value)}
[Calculation]: ({float(liabilities.value):,.0f} / {float(equity.value):,.0f}) * 100 = {ratio:.2f}%
[Interpretation]: The Debt-to-Equity Ratio is {ratio:.2f}%. {'⚠️ High leverage (over 200%), indicating higher financial risk.' if ratio > 200 else '✅ Stable leverage (under 200%).' if ratio <= 200 else 'Very low leverage.'}""",
            "context": f"Total Liabilities: {self.scale_processor.format_currency(liabilities.value)}, Total Equity: {self.scale_processor.format_currency(equity.value)}",
            "type": "ratio_analysis"
        }
    
    def _generate_current_ratio_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """Current Ratio Q&A - v10.0 English"""
        current_assets = facts.get('current_assets') or facts.get('유동자산') or facts.get('CurrentAssets')
        current_liabilities = facts.get('current_liabilities') or facts.get('유동부채') or facts.get('CurrentLiabilities')
        
        if not current_assets or not current_liabilities or float(current_liabilities.value) == 0:
            return None
        
        ratio = float(current_assets.value) / float(current_liabilities.value) * 100
        
        return {
            "question": f"Assess the short-term liquidity of {self.company_name} using the Current Ratio.",
            "response": f"""[Definition]: Current Ratio measures a company's ability to pay short-term obligations or those due within one year. Formula: (Current Assets / Current Liabilities) * 100.
[Extraction]: Current Assets {self.scale_processor.format_currency(current_assets.value)}, Current Liabilities {self.scale_processor.format_currency(current_liabilities.value)}
[Calculation]: ({float(current_assets.value):,.0f} / {float(current_liabilities.value):,.0f}) * 100 = {ratio:.2f}%
[Interpretation]: The Current Ratio is {ratio:.2f}%. {'✅ Strong liquidity (over 200%).' if ratio >= 200 else '⚠️ Potential liquidity risk (under 100%).' if ratio < 100 else 'Adequate liquidity (100-200%).'}""",
            "context": f"Current Assets: {self.scale_processor.format_currency(current_assets.value)}, Current Liabilities: {self.scale_processor.format_currency(current_liabilities.value)}",
            "type": "ratio_analysis"
        }
    
    def _generate_gross_margin_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """Gross Margin Q&A - v10.0 English"""
        revenue = facts.get('revenue') or facts.get('매출액') or facts.get('Revenue')
        gross_profit = facts.get('gross_profit') or facts.get('매출총이익') or facts.get('GrossProfit')
        
        if not revenue or not gross_profit or float(revenue.value) == 0:
            return None
        
        margin = float(gross_profit.value) / float(revenue.value) * 100
        
        return {
            "question": f"Calculate the Gross Profit Margin for {self.company_name} and evaluate cost efficiency.",
            "response": f"""[Definition]: Gross Profit Margin reveals the proportion of money left over from revenues after accounting for the cost of goods sold. Formula: (Gross Profit / Revenues) * 100.
[Extraction]: Revenues {self.scale_processor.format_currency(revenue.value)}, Gross Profit {self.scale_processor.format_currency(gross_profit.value)}
[Calculation]: ({float(gross_profit.value):,.0f} / {float(revenue.value):,.0f}) * 100 = {margin:.2f}%
[Interpretation]: Gross margin is {margin:.2f}%. {'High margin indicates efficient production or high value-add.' if margin > 30 else 'Lower margin suggests high cost of goods sold.'}""",
            "context": f"Revenues: {self.scale_processor.format_currency(revenue.value)}, Gross Profit: {self.scale_processor.format_currency(gross_profit.value)}",
            "type": "ratio_analysis"
        }
    
    def _generate_roe_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """ROE Q&A - v10.0 English"""
        net_income = facts.get('net_income') or facts.get('당기순이익') or facts.get('ProfitLoss') or facts.get('NetIncome')
        equity = facts.get('total_equity') or facts.get('자본총계') or facts.get('Equity')
        
        if not net_income or not equity or float(equity.value) == 0:
            return None
        
        roe = float(net_income.value) / float(equity.value) * 100
        
        return {
            "question": f"Calculate Return on Equity (ROE) for {self.company_name} and evaluate shareholder value creation.",
            "response": f"""[Definition]: ROE measures financial performance calculated by dividing net income by shareholders' equity. Formula: (Net Income / Total Equity) * 100.
[Extraction]: Net Income {self.scale_processor.format_currency(net_income.value)}, Total Equity {self.scale_processor.format_currency(equity.value)}
[Calculation]: ({float(net_income.value):,.0f} / {float(equity.value):,.0f}) * 100 = {roe:.2f}%
[Interpretation]: ROE is {roe:.2f}%. {'✅ Excellent return (over 15%).' if roe >= 15 else '⚠️ Low return (under 10%), implies inefficient capital usage.' if roe < 10 else 'Good return (10-15%).'}""",
            "context": f"Net Income: {self.scale_processor.format_currency(net_income.value)}, Total Equity: {self.scale_processor.format_currency(equity.value)}",
            "type": "ratio_analysis"
        }
    
    def _generate_asset_composition_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """Asset Composition Analysis - v10.0 English"""
        total_assets = facts.get('total_assets') or facts.get('자산총계') or facts.get('Assets')
        current_assets = facts.get('current_assets') or facts.get('유동자산') or facts.get('CurrentAssets')
        noncurrent_assets = facts.get('non_current_assets') or facts.get('비유동자산') or facts.get('NoncurrentAssets')
        
        if not total_assets:
            return None
        
        response_parts = [f"## Asset Composition Analysis\n\n### Total Assets\n**{self.scale_processor.format_currency(total_assets.value)}**\n"]
        
        if current_assets:
            current_ratio = float(current_assets.value) / float(total_assets.value) * 100
            response_parts.append(f"\n### Current Assets\n- Amount: {self.scale_processor.format_currency(current_assets.value)}\n- Weight: {current_ratio:.1f}%")
        
        if noncurrent_assets:
            noncurrent_ratio = float(noncurrent_assets.value) / float(total_assets.value) * 100
            response_parts.append(f"\n### Non-current Assets\n- Amount: {self.scale_processor.format_currency(noncurrent_assets.value)}\n- Weight: {noncurrent_ratio:.1f}%")
        
        return {
            "question": f"Analyze the asset composition of {self.company_name}.",
            "response": "".join(response_parts),
            "context": f"Total Assets: {total_assets.value}",
            "type": "composition_analysis"
        }
    
    def _generate_financial_report(self, facts: List[SemanticFact]) -> str:
        """Generate Financial Report Markdown - v10.0 English"""
        lines = [
            f"# {self.company_name} Financial Report",
            f"**Fiscal Year**: {self.fiscal_year}",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            ""
        ]
        
        # Balance Sheet
        balance_sheet_facts = [f for f in facts if '재무상태표' in f.hierarchy]
        if balance_sheet_facts:
            lines.extend(self._generate_balance_sheet_section(balance_sheet_facts))
        
        # Income Statement
        income_facts = [f for f in facts if '손익계산서' in f.hierarchy or '포괄' in f.hierarchy]
        if income_facts:
            lines.extend(self._generate_income_statement_section(income_facts))
        
        # Cash Flow
        cash_flow_facts = [f for f in facts if '현금흐름' in f.hierarchy]
        if cash_flow_facts:
            lines.extend(self._generate_cash_flow_section(cash_flow_facts))
        
        return "\n".join(lines)
    
    def _generate_balance_sheet_section(self, facts: List[SemanticFact]) -> List[str]:
        """Generate Balance Sheet Section - English"""
        lines = [
            "## Statement of Financial Position",
            "",
            "| Account | Amount |",
            "|:--------|-------:|",
        ]
        
        # Assets
        asset_facts = [f for f in facts if '자산' in f.hierarchy]
        if asset_facts:
            lines.append("| **[Assets]** | |")
            for fact in sorted(asset_facts, key=lambda x: float(x.value), reverse=True):
                english_label = self.scale_processor.fix_label_typos(fact.label)
                lines.append(f"| {english_label} | {self.scale_processor.format_currency(fact.value)} |")
        
        # Liabilities
        liability_facts = [f for f in facts if '부채' in f.hierarchy]
        if liability_facts:
            lines.append("| **[Liabilities]** | |")
            for fact in sorted(liability_facts, key=lambda x: float(x.value), reverse=True):
                english_label = self.scale_processor.fix_label_typos(fact.label)
                lines.append(f"| {english_label} | {self.scale_processor.format_currency(fact.value)} |")
        
        # Equity
        equity_facts = [f for f in facts if '자본' in f.hierarchy]
        if equity_facts:
            lines.append("| **[Equity]** | |")
            for fact in sorted(equity_facts, key=lambda x: float(x.value), reverse=True):
                english_label = self.scale_processor.fix_label_typos(fact.label)
                lines.append(f"| {english_label} | {self.scale_processor.format_currency(fact.value)} |")
        
        lines.append("")
        return lines
    
    def _generate_income_statement_section(self, facts: List[SemanticFact]) -> List[str]:
        """Generate Income Statement Section - English"""
        lines = [
            "## Statement of Comprehensive Income",
            "",
            "| Account | Amount |",
            "|:--------|-------:|",
        ]
        
        fact_dict = {f.label: f for f in facts}
        # Explicit order for readability, using standard English keys?
        # NO, 'income_order' used korean keys in original.
        # I will use sorted by value for now to avoid mapping complexity in table, 
        # relying on fix_label_typos to show English.
        
        lines.append("| **[Income Statement]** | |")
        for fact in sorted(facts, key=lambda x: float(x.value), reverse=True):
             english_label = self.scale_processor.fix_label_typos(fact.label)
             lines.append(f"| {english_label} | {self.scale_processor.format_currency(fact.value)} |")

        lines.append("")
        return lines
    
    def _generate_cash_flow_section(self, facts: List[SemanticFact]) -> List[str]:
        """Generate Cash Flow Section - English"""
        lines = [
            "## Statement of Cash Flows",
            "",
            "| Account | Amount |",
            "|:--------|-------:|",
        ]
        
        for fact in facts:
            english_label = self.scale_processor.fix_label_typos(fact.label)
            lines.append(f"| {english_label} | {self.scale_processor.format_currency(fact.value)} |")
        
        lines.append("")
        return lines
    
    def _generate_jsonl(
        self, 
        facts: List[SemanticFact], 
        reasoning_qa: List[Dict[str, str]]
    ) -> List[str]:
        """Generate JSONL Data - v10.0 English"""
        jsonl_lines = []
        
        # Post-Processing
        def clean_text(text: str) -> str:
            if not text: return ""
            return self.scale_processor.fix_label_typos(text) # Ensures English
        
        # Reasoning Q&A
        for qa in reasoning_qa:
            entry = {
                "instruction": clean_text(qa["question"]),
                "input": clean_text(qa.get("context", "")),
                "output": clean_text(qa["response"]),
                "metadata": {
                    "company": self.company_name,
                    "fiscal_year": self.fiscal_year,
                    "type": qa.get("type", "analysis"),
                    "source": "xbrl_semantic_engine"
                }
            }
            jsonl_lines.append(json.dumps(entry, ensure_ascii=False))
        
        # Simple Facts (Top 3)
        for fact in facts[:3]:
            label = self.scale_processor.fix_label_typos(fact.label) # Returns English
            val_norm = self.scale_processor.format_currency(fact.value)
            
            entry = {
                "instruction": f"What is the {label} for {self.company_name} in {self.fiscal_year}?",
                "input": f"{label}: {fact.value}",
                "output": f"The {label} for {self.company_name} in {self.fiscal_year} is {val_norm}.",
                "metadata": {
                    "company": self.company_name,
                    "fiscal_year": self.fiscal_year,
                    "concept": fact.concept,
                    "type": "fact_retrieval",
                    "source": "xbrl_semantic_engine"
                }
            }
            jsonl_lines.append(json.dumps(entry, ensure_ascii=False))
        
        return jsonl_lines
    
    def _extract_key_metrics(self, facts: List[SemanticFact]) -> Dict[str, Any]:
        """Extract Key Metrics - v10.0 English"""
        metrics = {}
        
        # Mapped to English
        target_map = {
            '자산총계': 'Total Assets', 'Assets': 'Total Assets', 'TotalAssets': 'Total Assets',
            '부채총계': 'Total Liabilities', 'Liabilities': 'Total Liabilities', 'TotalLiabilities': 'Total Liabilities',
            '자본총계': 'Total Equity', 'Equity': 'Total Equity', 'TotalEquity': 'Total Equity',
            '매출액': 'Revenues', 'Revenues': 'Revenues', 'Revenue': 'Revenues',
            '영업이익': 'Operating Income', 'OperatingIncome': 'Operating Income',
            '당기순이익': 'Net Income', 'NetIncome': 'Net Income'
        }
        
        for fact in facts:
            if fact.label in target_map:
                english_key = target_map[fact.label]
                metrics[english_key] = {
                    "value": float(fact.value),
                    "formatted": self.scale_processor.format_currency(fact.value),
                    "period": fact.period
                }
        
        return metrics
    
    def _build_empty_result(self, error_message: str) -> XBRLIntelligenceResult:
        """Build Empty Result (on Failure) - English"""
        self.errors.append(error_message)
        logger.error(f"Empty result: {error_message}")
        
        return XBRLIntelligenceResult(
            success=False,
            company_name=self.company_name,
            fiscal_year=self.fiscal_year,
            facts=[],
            reasoning_qa=[],
            financial_report_md=f"# Parsing Failed\n\n{error_message}",
            jsonl_data=[],
            key_metrics={},
            parse_summary=error_message,
            errors=self.errors
        )


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def process_xbrl_files(
    label_file_path: Optional[str] = None,
    instance_file_path: Optional[str] = None,
    company_name: str = "",
    output_dir: Optional[str] = None
) -> XBRLIntelligenceResult:
    """
    XBRL 파일 처리 편의 함수
    
    Args:
        label_file_path: _lab.xml 파일 경로
        instance_file_path: _htm.xml 또는 XBRL 인스턴스 파일 경로
        company_name: 회사명 (선택)
        output_dir: 출력 디렉토리 (선택, 지정 시 파일 저장)
    
    Returns:
        XBRLIntelligenceResult
    """
    label_content = None
    instance_content = None
    
    if label_file_path:
        with open(label_file_path, 'rb') as f:
            label_content = f.read()
    
    if instance_file_path:
        with open(instance_file_path, 'rb') as f:
            instance_content = f.read()
    
    engine = XBRLSemanticEngine(company_name=company_name)
    result = engine.process_joint(label_content, instance_content)
    
    # 파일 저장
    if output_dir and result.success:
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # 마크다운 저장
        md_path = os.path.join(output_dir, f"{company_name or 'report'}_financial.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(result.financial_report_md)
        
        # JSONL 저장
        jsonl_path = os.path.join(output_dir, f"{company_name or 'report'}_qa.jsonl")
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(result.jsonl_data))
        
        logger.info(f"Output saved to {output_dir}")
    
    return result


# Singleton instance
xbrl_semantic_engine = XBRLSemanticEngine()
