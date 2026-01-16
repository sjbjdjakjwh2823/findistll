"""
FinDistill XBRL Semantic Engine - Unit Tests

Tests for the Universal XBRL Financial Intelligence Engine:
- ScaleProcessor: decimals handling
- ContextFilter: consolidated vs separate classification  
- XBRLSemanticEngine: joint parsing workflow
- XBRLReasoner: question filtering
"""

import pytest
import json
from decimal import Decimal
from typing import Dict, Any

# Import modules under test
import sys
sys.path.insert(0, 'c:/Users/Administrator/Desktop/project_1')

from api.services.xbrl_semantic_engine import (
    ScaleProcessor,
    ContextFilter,
    CoreFinancialConcepts,
    XBRLSemanticEngine,
    ParsedContext,
    SemanticFact,
)
from api.services.xbrl_reasoner import XBRLReasoner


# ============================================================
# ScaleProcessor Tests
# ============================================================

class TestScaleProcessor:
    """Tests for numeric scale processing."""
    
    def test_decimals_negative_6_millions(self):
        """Test decimals=-6 converts to millions."""
        value, desc = ScaleProcessor.standardize_value("100", "-6", "")
        assert value == Decimal("100000000")
        assert "백만" in desc or "1,000,000" in desc
    
    def test_decimals_negative_3_thousands(self):
        """Test decimals=-3 converts to thousands."""
        value, desc = ScaleProcessor.standardize_value("500", "-3", "")
        assert value == Decimal("500000")
    
    def test_decimals_zero_no_change(self):
        """Test decimals=0 leaves value unchanged."""
        value, desc = ScaleProcessor.standardize_value("1234567", "0", "")
        assert value == Decimal("1234567")
    
    def test_unit_ref_thousands(self):
        """Test Korean thousand unit detection."""
        value, desc = ScaleProcessor.standardize_value("100", None, "천원")
        assert value == Decimal("100000")
    
    def test_unit_ref_millions(self):
        """Test Korean million unit detection."""
        value, desc = ScaleProcessor.standardize_value("50", None, "백만원")
        assert value == Decimal("50000000")
    
    def test_invalid_number(self):
        """Test invalid number handling."""
        value, desc = ScaleProcessor.standardize_value("N/A", None, "")
        assert value == Decimal("0")
        assert "Invalid" in desc
    
    def test_comma_removal(self):
        """Test comma removal from numbers."""
        value, desc = ScaleProcessor.standardize_value("1,234,567", None, "")
        assert value == Decimal("1234567")
    
    def test_currency_formatting_krw(self):
        """Test Korean Won formatting."""
        formatted = ScaleProcessor.format_currency(Decimal("1000000000"), "KRW")
        assert "₩" in formatted
        assert "1,000,000,000" in formatted
    
    def test_currency_formatting_usd(self):
        """Test USD formatting."""
        formatted = ScaleProcessor.format_currency(Decimal("1000000"), "USD")
        assert "$" in formatted


# ============================================================
# ContextFilter Tests
# ============================================================

class TestContextFilter:
    """Tests for consolidated vs separate context classification."""
    
    def test_consolidated_pattern_detection(self):
        """Test detection of consolidated context."""
        ctx = ParsedContext(
            id="c-1",
            entity="1234567890_consolidated"
        )
        is_consolidated, reason = ContextFilter.classify_context(ctx)
        assert is_consolidated is True
        assert "연결" in reason or "consol" in reason.lower()
    
    def test_separate_pattern_detection(self):
        """Test detection of separate (non-consolidated) context."""
        ctx = ParsedContext(
            id="c-10",
            entity="company",
            segment_members=["SeparateFinancialStatementsMember"]
        )
        is_consolidated, reason = ContextFilter.classify_context(ctx)
        assert is_consolidated is False
    
    def test_korean_separate_detection(self):
        """Test detection of Korean 별도 pattern."""
        ctx = ParsedContext(
            id="c-20",
            segment_members=["별도재무제표"]
        )
        is_consolidated, reason = ContextFilter.classify_context(ctx)
        assert is_consolidated is False
    
    def test_no_segment_defaults_consolidated(self):
        """Test that no segment defaults to consolidated."""
        ctx = ParsedContext(
            id="c-100",
            entity="company123"
        )
        is_consolidated, reason = ContextFilter.classify_context(ctx)
        assert is_consolidated is True
    
    def test_filter_consolidated_priority(self):
        """Test filtering keeps consolidated facts first."""
        facts = [
            SemanticFact(
                concept="Assets", label="자산", value=Decimal(1000),
                raw_value="1000", unit="KRW", period="2025",
                context_ref="c-1", decimals=None, hierarchy="",
                is_consolidated=False, segment=None
            ),
            SemanticFact(
                concept="Assets", label="자산", value=Decimal(2000),
                raw_value="2000", unit="KRW", period="2025",
                context_ref="c-2", decimals=None, hierarchy="",
                is_consolidated=True, segment=None
            ),
        ]
        
        filtered = ContextFilter.filter_consolidated_priority(facts)
        # Only consolidated should remain when include_separate=False (default)
        assert len(filtered) == 1
        assert filtered[0].is_consolidated is True


# ============================================================
# CoreFinancialConcepts Tests  
# ============================================================

class TestCoreFinancialConcepts:
    """Tests for core financial concept mapping."""
    
    def test_get_label_ifrs(self):
        """Test IFRS concept label extraction."""
        label = CoreFinancialConcepts.get_label("ifrs-full_Assets")
        assert label == "자산총계"
    
    def test_get_label_us_gaap(self):
        """Test US GAAP concept label extraction."""
        label = CoreFinancialConcepts.get_label("us-gaap_Revenue")
        assert label == "매출액"
    
    def test_is_core_financial_true(self):
        """Test core financial concept detection."""
        assert CoreFinancialConcepts.is_core_financial("Revenue") is True
        assert CoreFinancialConcepts.is_core_financial("Assets") is True
    
    def test_is_core_financial_false(self):
        """Test non-core concept detection."""
        assert CoreFinancialConcepts.is_core_financial("RandomConcept") is False
    
    def test_get_hierarchy_balance_sheet(self):
        """Test hierarchy detection for balance sheet items."""
        hierarchy = CoreFinancialConcepts.get_hierarchy("자산총계")
        assert "재무상태표" in hierarchy
    
    def test_get_hierarchy_income_statement(self):
        """Test hierarchy detection for income statement items."""
        hierarchy = CoreFinancialConcepts.get_hierarchy("매출액")
        assert "손익계산서" in hierarchy


# ============================================================
# XBRLReasoner Question Filter Tests
# ============================================================

class TestXBRLReasonerQuestionFilter:
    """Tests for question filtering in XBRLReasoner."""
    
    def test_exclude_date_question_korean(self):
        """Test Korean date question exclusion."""
        assert XBRLReasoner.is_excluded_question("보고서 날짜가 언제인가요?") is True
    
    def test_exclude_identifier_question(self):
        """Test identifier question exclusion."""
        assert XBRLReasoner.is_excluded_question("What is the identifier?") is True
    
    def test_exclude_context_id_question(self):
        """Test context ID question exclusion."""
        assert XBRLReasoner.is_excluded_question("context id는 무엇인가?") is True
    
    def test_include_ratio_question(self):
        """Test that ratio questions are NOT excluded."""
        assert XBRLReasoner.is_excluded_question("부채비율을 계산해주세요") is False
    
    def test_include_analysis_question(self):
        """Test that analysis questions are NOT excluded."""
        assert XBRLReasoner.is_excluded_question("재무 건전성을 평가하십시오") is False
    
    def test_filter_qa_pairs(self):
        """Test batch filtering of Q&A pairs."""
        qa_pairs = [
            {"instruction": "날짜가 언제인가요?", "response": "2025-01-01"},
            {"instruction": "부채비율을 분석해주세요", "response": "부채비율은 50%입니다"},
            {"instruction": "What is the context id?", "response": "c-1"},
        ]
        
        filtered = XBRLReasoner.filter_qa_pairs(qa_pairs)
        assert len(filtered) == 1
        assert "부채비율" in filtered[0]["instruction"]


# ============================================================
# XBRLSemanticEngine Integration Tests
# ============================================================

class TestXBRLSemanticEngine:
    """Integration tests for the semantic engine."""
    
    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        engine = XBRLSemanticEngine(company_name="Test Corp", fiscal_year="2025")
        assert engine.company_name == "Test Corp"
        assert engine.fiscal_year == "2025"
    
    def test_empty_input_returns_error(self):
        """Test engine handles empty input gracefully."""
        engine = XBRLSemanticEngine()
        result = engine.process_joint(None, None)
        
        assert result.success is False
        assert "추출되지 않았습니다" in result.parse_summary or len(result.errors) > 0
    
    def test_label_mapping_fallback(self):
        """Test label mapping falls back to defaults."""
        engine = XBRLSemanticEngine()
        # Without loading any label content, should use defaults
        label = engine._apply_semantic_label("ifrs-full_Assets")
        # Should get some reasonable label
        assert label is not None
        assert len(label) > 0


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
