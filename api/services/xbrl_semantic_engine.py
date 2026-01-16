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
    수치 스케일 처리기 (v3) - Self-Healing Scale Logic
    
    🔴 지능형 수치 보정 (Self-Healing):
    1. 원본 값이 이미 큰 절대값(≥10^6)이고 decimals가 음수면 곱셈 중단
    2. 최종값이 10^15 초과 시 자동 역산(Reverse Scaling)
    3. 모든 수치를 Billion($10^9) 또는 Million($10^6) 단위로 표준화
    
    입력: 다양한 형식의 XBRL 수치
    출력: 합리적 범위(~$1T)의 표준화된 수치
    """
    
    # 표준화 목표 단위
    STANDARD_UNIT_BILLION = Decimal('1e9')   # $1B = 10^9
    STANDARD_UNIT_MILLION = Decimal('1e6')   # $1M = 10^6
    
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
        """통화 포맷팅 (간소화된 단위 표시)"""
        try:
            abs_val = abs(value)
            sign = "-" if value < 0 else ""
            
            if abs_val >= Decimal('1e12'):
                formatted = f"{float(abs_val / Decimal('1e12')):.2f}T"
            elif abs_val >= Decimal('1e9'):
                formatted = f"{float(abs_val / Decimal('1e9')):.2f}B"
            elif abs_val >= Decimal('1e6'):
                formatted = f"{float(abs_val / Decimal('1e6')):.2f}M"
            elif abs_val >= Decimal('1e3'):
                formatted = f"{float(abs_val / Decimal('1e3')):.2f}K"
            else:
                formatted = f"{int(abs_val):,}"
            
            if currency == "KRW":
                return f"{sign}₩{formatted}"
            elif currency == "USD":
                return f"{sign}${formatted}"
            else:
                return f"{sign}{formatted} {currency}"
        except:
            return str(value)
    
    @classmethod
    def normalize_to_billion(cls, value: Decimal, unit: str = "B") -> str:
        """
        수치를 Billion 단위로 정규화 (테이블 행 출력용)
        
        예: 111601000000 → "111.60B"
        
        공식: Value_std = Value_raw / 10^9 (Billion)
        """
        try:
            abs_val = abs(value)
            sign = "-" if value < 0 else ""
            
            if abs_val >= Decimal('1e12'):
                # Trillion → 표시
                normalized = float(value / Decimal('1e12'))
                return f"{sign}{normalized:.2f}T"
            elif abs_val >= Decimal('1e9'):
                # Billion 정규화
                normalized = float(value / Decimal('1e9'))
                return f"{sign}{normalized:.2f}{unit}"
            elif abs_val >= Decimal('1e6'):
                # Million
                normalized = float(value / Decimal('1e6'))
                return f"{sign}{normalized:.2f}M"
            else:
                return f"{int(value):,}"
        except:
            return str(value)
    
    @staticmethod
    def fix_label_typos(label: str) -> str:
        """
        레이블 오타 수정
        
        - 중복 문자 제거: "매출총이익익익" → "매출총이익"
        - 연속 중복 패턴 정리
        """
        if not label:
            return label
        
        # 1. 끝의 중복 문자 제거 (예: 이익익익 → 이익)
        # 한글 중복 패턴
        fixed = re.sub(r'(.{1,3})\1+$', r'\1', label)
        
        # 2. 연속 동일 단어 제거
        fixed = re.sub(r'\b(\w+)\s+\1\b', r'\1', fixed)
        
        # 3. 특수 케이스 수정
        typo_fixes = {
            '매출총이익익': '매출총이익',
            '영업이익익': '영업이익',
            '당기순이익익': '당기순이익',
            '자산총계계': '자산총계',
            '부채총계계': '부채총계',
        }
        
        for typo, correct in typo_fixes.items():
            if typo in fixed:
                fixed = fixed.replace(typo, correct)
        
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
    
    def __init__(self, company_name: str = "", fiscal_year: str = ""):
        self.company_name = company_name
        self.fiscal_year = fiscal_year
        self.label_mapping: Dict[str, str] = {}  # concept → human label
        self.contexts: Dict[str, ParsedContext] = {}
        self.facts: List[SemanticFact] = []
        self.errors: List[str] = []
        self.parse_log: List[str] = []
        
        # 프로세서 초기화
        self.scale_processor = ScaleProcessor()
        self.context_filter = ContextFilter()
        
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
        
        return qa_pairs
    
    def _build_flexible_fact_dict(self, facts: List[SemanticFact]) -> Dict:
        """유연한 라벨/개념 매칭을 위한 복합 딕셔너리 구축"""
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
        }
        
        for fact in facts:
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
    
    def _generate_debt_ratio_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """부채비율 Q&A 생성"""
        liabilities = facts.get('부채총계') or facts.get('Liabilities')
        equity = facts.get('자본총계') or facts.get('Equity')
        
        if not liabilities or not equity or float(equity.value) == 0:
            return None
        
        ratio = float(liabilities.value) / float(equity.value) * 100
        
        return {
            "question": f"{self.company_name}의 {self.fiscal_year}년 부채비율(Debt Ratio)을 계산하고 재무 건전성을 평가하십시오.",
            "response": f"""## 부채비율 분석

### 계산 공식
$$\\text{{부채비율}} = \\frac{{\\text{{부채총계}}}}{{\\text{{자본총계}}}} \\times 100$$

### 수치 대입
$$\\text{{부채비율}} = \\frac{{{self.scale_processor.format_currency(liabilities.value)}}}{{{self.scale_processor.format_currency(equity.value)}}} \\times 100$$

### 계산 결과
**부채비율 = {ratio:.2f}%**

### 회계적 해석
{'⚠️ **주의**: 부채비율이 200%를 초과하여 재무 레버리지가 높은 상태입니다. 이자 부담과 채무 상환 능력을 면밀히 검토해야 합니다.' if ratio > 200 else '✅ 부채비율이 적정 수준(200% 이하)으로, 재무구조가 안정적입니다.' if ratio <= 200 else '부채비율이 100% 미만으로 자기자본이 부채보다 많아 재무 안정성이 높습니다.'}
""",
            "context": f"부채: {liabilities.value}, 자본: {equity.value}",
            "type": "ratio_analysis"
        }
    
    def _generate_current_ratio_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """유동비율 Q&A 생성"""
        current_assets = facts.get('유동자산') or facts.get('CurrentAssets')
        current_liabilities = facts.get('유동부채') or facts.get('CurrentLiabilities')
        
        if not current_assets or not current_liabilities or float(current_liabilities.value) == 0:
            return None
        
        ratio = float(current_assets.value) / float(current_liabilities.value) * 100
        
        return {
            "question": f"{self.company_name}의 단기 채무 상환 능력을 유동비율로 평가하십시오.",
            "response": f"""## 유동비율 분석

### 계산 공식
$$\\text{{유동비율}} = \\frac{{\\text{{유동자산}}}}{{\\text{{유동부채}}}} \\times 100$$

### 수치 대입
$$\\text{{유동비율}} = \\frac{{{self.scale_processor.format_currency(current_assets.value)}}}{{{self.scale_processor.format_currency(current_liabilities.value)}}} \\times 100$$

### 계산 결과
**유동비율 = {ratio:.2f}%**

### 회계적 해석
{'✅ 유동비율이 200% 이상으로 단기 채무 상환 능력이 우수합니다.' if ratio >= 200 else '⚠️ 유동비율이 100% 미만으로 단기 유동성 위험이 있습니다. 현금흐름 관리가 필요합니다.' if ratio < 100 else '유동비율이 100%~200% 사이로 적정 수준입니다.'}
""",
            "context": f"유동자산: {current_assets.value}, 유동부채: {current_liabilities.value}",
            "type": "ratio_analysis"
        }
    
    def _generate_gross_margin_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """매출총이익률 Q&A 생성"""
        revenue = facts.get('매출액') or facts.get('Revenue')
        gross_profit = facts.get('매출총이익') or facts.get('GrossProfit')
        
        if not revenue or not gross_profit or float(revenue.value) == 0:
            return None
        
        margin = float(gross_profit.value) / float(revenue.value) * 100
        
        return {
            "question": f"{self.company_name}의 매출총이익률을 분석하고 원가 관리 효율성을 평가하십시오.",
            "response": f"""## 매출총이익률 분석

### 계산 공식
$$\\text{{매출총이익률}} = \\frac{{\\text{{매출총이익}}}}{{\\text{{매출액}}}} \\times 100$$

### 수치 대입
$$\\text{{매출총이익률}} = \\frac{{{self.scale_processor.format_currency(gross_profit.value)}}}{{{self.scale_processor.format_currency(revenue.value)}}} \\times 100$$

### 계산 결과
**매출총이익률 = {margin:.2f}%**

### 회계적 해석
매출총이익률 {margin:.2f}%는 매출액 100원당 {margin:.0f}원의 총이익을 창출함을 의미합니다. 
{'높은 매출총이익률은 원가 관리가 효율적이거나 제품의 부가가치가 높음을 나타냅니다.' if margin > 30 else '매출총이익률 개선을 위해 원가 절감 또는 가격 정책 재검토가 필요할 수 있습니다.'}
""",
            "context": f"매출액: {revenue.value}, 매출총이익: {gross_profit.value}",
            "type": "ratio_analysis"
        }
    
    def _generate_roe_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """ROE Q&A 생성"""
        net_income = facts.get('당기순이익') or facts.get('ProfitLoss') or facts.get('NetIncome')
        equity = facts.get('자본총계') or facts.get('Equity')
        
        if not net_income or not equity or float(equity.value) == 0:
            return None
        
        roe = float(net_income.value) / float(equity.value) * 100
        
        return {
            "question": f"{self.company_name}의 자기자본이익률(ROE)을 계산하고 주주 가치 창출 능력을 평가하십시오.",
            "response": f"""## ROE (자기자본이익률) 분석

### 계산 공식
$$\\text{{ROE}} = \\frac{{\\text{{당기순이익}}}}{{\\text{{자기자본}}}} \\times 100$$

### 수치 대입
$$\\text{{ROE}} = \\frac{{{self.scale_processor.format_currency(net_income.value)}}}{{{self.scale_processor.format_currency(equity.value)}}} \\times 100$$

### 계산 결과
**ROE = {roe:.2f}%**

### 회계적 해석
ROE {roe:.2f}%는 주주가 투자한 자본 100원당 {roe:.0f}원의 순이익을 창출했음을 의미합니다.
{'✅ ROE가 15% 이상으로 우수한 수익성을 보여주고 있습니다.' if roe >= 15 else '⚠️ ROE가 10% 미만으로 자본 효율성 개선이 필요합니다.' if roe < 10 else 'ROE가 10%~15% 사이로 양호한 수준입니다.'}
""",
            "context": f"당기순이익: {net_income.value}, 자본: {equity.value}",
            "type": "ratio_analysis"
        }
    
    def _generate_asset_composition_qa(self, facts: Dict) -> Optional[Dict[str, str]]:
        """자산 구성 분석 Q&A"""
        total_assets = facts.get('자산총계') or facts.get('Assets')
        current_assets = facts.get('유동자산') or facts.get('CurrentAssets')
        noncurrent_assets = facts.get('비유동자산') or facts.get('NoncurrentAssets')
        
        if not total_assets:
            return None
        
        response_parts = [f"## 자산 구성 분석\n\n### 총자산\n**{self.scale_processor.format_currency(total_assets.value)}**\n"]
        
        if current_assets:
            current_ratio = float(current_assets.value) / float(total_assets.value) * 100
            response_parts.append(f"\n### 유동자산\n- 금액: {self.scale_processor.format_currency(current_assets.value)}\n- 비중: {current_ratio:.1f}%")
        
        if noncurrent_assets:
            noncurrent_ratio = float(noncurrent_assets.value) / float(total_assets.value) * 100
            response_parts.append(f"\n### 비유동자산\n- 금액: {self.scale_processor.format_currency(noncurrent_assets.value)}\n- 비중: {noncurrent_ratio:.1f}%")
        
        return {
            "question": f"{self.company_name}의 자산 구성을 분석하십시오.",
            "response": "".join(response_parts),
            "context": f"총자산: {total_assets.value}",
            "type": "composition_analysis"
        }
    
    def _generate_financial_report(self, facts: List[SemanticFact]) -> str:
        """구조화된 재무제표 마크다운 생성"""
        lines = [
            f"# {self.company_name} 재무제표",
            f"**회계연도**: {self.fiscal_year}",
            f"**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            ""
        ]
        
        # 재무상태표
        balance_sheet_facts = [f for f in facts if '재무상태표' in f.hierarchy]
        if balance_sheet_facts:
            lines.extend(self._generate_balance_sheet_section(balance_sheet_facts))
        
        # 손익계산서
        income_facts = [f for f in facts if '손익계산서' in f.hierarchy or '포괄' in f.hierarchy]
        if income_facts:
            lines.extend(self._generate_income_statement_section(income_facts))
        
        # 현금흐름표
        cash_flow_facts = [f for f in facts if '현금흐름' in f.hierarchy]
        if cash_flow_facts:
            lines.extend(self._generate_cash_flow_section(cash_flow_facts))
        
        return "\n".join(lines)
    
    def _generate_balance_sheet_section(self, facts: List[SemanticFact]) -> List[str]:
        """재무상태표 섹션 생성"""
        lines = [
            "## 재무상태표 (Statement of Financial Position)",
            "",
            "| 계정과목 | 금액 |",
            "|:---------|-----:|",
        ]
        
        # 자산 섹션
        asset_facts = [f for f in facts if '자산' in f.hierarchy]
        if asset_facts:
            lines.append("| **[자산]** | |")
            for fact in sorted(asset_facts, key=lambda x: float(x.value), reverse=True):
                lines.append(f"| {fact.label} | {self.scale_processor.format_currency(fact.value)} |")
        
        # 부채 섹션
        liability_facts = [f for f in facts if '부채' in f.hierarchy]
        if liability_facts:
            lines.append("| **[부채]** | |")
            for fact in sorted(liability_facts, key=lambda x: float(x.value), reverse=True):
                lines.append(f"| {fact.label} | {self.scale_processor.format_currency(fact.value)} |")
        
        # 자본 섹션
        equity_facts = [f for f in facts if '자본' in f.hierarchy]
        if equity_facts:
            lines.append("| **[자본]** | |")
            for fact in sorted(equity_facts, key=lambda x: float(x.value), reverse=True):
                lines.append(f"| {fact.label} | {self.scale_processor.format_currency(fact.value)} |")
        
        lines.append("")
        return lines
    
    def _generate_income_statement_section(self, facts: List[SemanticFact]) -> List[str]:
        """손익계산서 섹션 생성"""
        lines = [
            "## 포괄손익계산서 (Statement of Comprehensive Income)",
            "",
            "| 계정과목 | 금액 |",
            "|:---------|-----:|",
        ]
        
        # 손익 항목 순서 정의
        income_order = ['매출액', '매출원가', '매출총이익', '판매비와관리비', 
                        '영업이익', '금융수익', '금융비용', '법인세비용차감전순이익',
                        '법인세비용', '당기순이익']
        
        fact_dict = {f.label: f for f in facts}
        
        for label in income_order:
            if label in fact_dict:
                fact = fact_dict[label]
                lines.append(f"| {label} | {self.scale_processor.format_currency(fact.value)} |")
        
        # 순서에 없는 항목 추가
        for fact in facts:
            if fact.label not in income_order:
                lines.append(f"| {fact.label} | {self.scale_processor.format_currency(fact.value)} |")
        
        lines.append("")
        return lines
    
    def _generate_cash_flow_section(self, facts: List[SemanticFact]) -> List[str]:
        """현금흐름표 섹션 생성"""
        lines = [
            "## 현금흐름표 (Statement of Cash Flows)",
            "",
            "| 구분 | 금액 |",
            "|:-----|-----:|",
        ]
        
        for fact in facts:
            lines.append(f"| {fact.label} | {self.scale_processor.format_currency(fact.value)} |")
        
        lines.append("")
        return lines
    
    def _generate_jsonl(
        self, 
        facts: List[SemanticFact], 
        reasoning_qa: List[Dict[str, str]]
    ) -> List[str]:
        """JSONL 형식 데이터 생성"""
        jsonl_lines = []
        
        # 추론형 Q&A를 JSONL로 변환
        for qa in reasoning_qa:
            entry = {
                "instruction": qa["question"],
                "input": qa.get("context", ""),
                "output": qa["response"],
                "metadata": {
                    "company": self.company_name,
                    "fiscal_year": self.fiscal_year,
                    "type": qa.get("type", "analysis"),
                    "source": "xbrl_semantic_engine"
                }
            }
            jsonl_lines.append(json.dumps(entry, ensure_ascii=False))
        
        # 핵심 팩트 Q&A 추가
        for fact in facts[:20]:  # 상위 20개만
            entry = {
                "instruction": f"{self.company_name}의 {self.fiscal_year}년 {fact.label}은 얼마인가?",
                "input": "",
                "output": f"{self.company_name}의 {self.fiscal_year}년 {fact.label}은 {self.scale_processor.format_currency(fact.value)}입니다.",
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
        """주요 지표 추출"""
        metrics = {}
        
        key_labels = ['자산총계', '부채총계', '자본총계', '매출액', '영업이익', '당기순이익']
        
        for fact in facts:
            if fact.label in key_labels:
                metrics[fact.label] = {
                    "value": float(fact.value),
                    "formatted": self.scale_processor.format_currency(fact.value),
                    "period": fact.period
                }
        
        return metrics
    
    def _build_empty_result(self, error_message: str) -> XBRLIntelligenceResult:
        """빈 결과 생성 (실패 시)"""
        self.errors.append(error_message)
        logger.error(f"Empty result: {error_message}")
        
        return XBRLIntelligenceResult(
            success=False,
            company_name=self.company_name,
            fiscal_year=self.fiscal_year,
            facts=[],
            reasoning_qa=[],
            financial_report_md=f"# 파싱 실패\n\n{error_message}",
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
