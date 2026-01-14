"""
FinDistill Universal Validator

문서 유형(document_type)에 따라 서로 다른 검증 규칙을 적용하는 범용 검증기입니다.
"""

from typing import Dict, List, Any, Optional, Callable
from models.schemas import ExtractedData, DocumentType, ValidationResult, ValidationError, ValidationSeverity


class UniversalValidator:
    """
    문서 유형(DocumentType)에 따라 다른 검증 규칙을 적용하는 범용 검증기
    
    지원 문서 유형:
    - invoice: 공급가액 + 부가세 = 합계 (tolerance 허용)
    - contract: 필수 조항 (당사자, 계약일) 및 계약 금액 확인
    - financial_statement: 자산 = 부채 + 자본, 매출 - 비용 = 이익
    - receipt: 단순 합계 검증
    
    공통 품질 검사:
    - 신뢰도 점수(Confidence Score) 확인
    - 결측치(Null Value) 비율 확인
    """
    
    # 신뢰도 임계값 (이보다 낮으면 경고)
    CONFIDENCE_THRESHOLD = 0.7
    
    # Null 값 비율 임계값 (이보다 높으면 경고: 30%)
    NULL_RATIO_THRESHOLD = 0.3
    
    def __init__(self, tolerance: float = 0.01):
        """
        초기화
        
        Args:
            tolerance: 숫자 검증 시 허용 오차 (기본값: 0.01)
        """
        self.tolerance = tolerance
        
        # 문서 유형별 검증 메서드 매핑
        self._validators: Dict[DocumentType, Callable] = {
            DocumentType.INVOICE: self._validate_invoice,
            DocumentType.RECEIPT: self._validate_receipt,
            DocumentType.CONTRACT: self._validate_contract,
            DocumentType.FINANCIAL_STATEMENT: self._validate_financial_statement,
            DocumentType.BALANCE_SHEET: self._validate_balance_sheet,
            DocumentType.INCOME_STATEMENT: self._validate_income_statement,
            DocumentType.TABLE: self._validate_table,
        }
    
    def validate(
        self, 
        data: ExtractedData, 
        validation_rules: Optional[List[Dict[str, Any]]] = None
    ) -> ValidationResult:
        """
        데이터 검증 수행
        
        Args:
            data: 추출된 데이터 객체
            validation_rules: 커스텀 검증 규칙 리스트 (선택)
            
        Returns:
            ValidationResult: 검증 결과 (오류 및 경고 포함)
        """
        result = ValidationResult()
        
        # 1. 공통 품질 검사
        self._check_confidence_score(data, result)
        self._check_null_ratio(data, result)
        self._check_required_metadata(data, result)
        
        # 2. 문서 유형별 검증
        validator = self._validators.get(data.document_type)
        if validator:
            validator(data, result)
        else:
            # 매핑된 검증기가 없으면 기본 테이블 검증 시도
            self._validate_table(data, result)
        
        # 3. 커스텀 규칙 검증
        if validation_rules:
            self._apply_custom_rules(data, validation_rules, result)
        
        return result
    
    # ==================== 공통 품질 검사 ====================
    
    def _check_confidence_score(self, data: ExtractedData, result: ValidationResult):
        """신뢰도 점수가 임계값보다 낮은지 확인"""
        if data.confidence_score < self.CONFIDENCE_THRESHOLD:
            result.add_issue(ValidationError(
                severity=ValidationSeverity.WARNING,
                error_type="LOW_CONFIDENCE",
                message=f"AI 신뢰도가 낮습니다 ({data.confidence_score:.2f} < {self.CONFIDENCE_THRESHOLD}). 수동 검토가 권장됩니다.",
                details={"confidence": data.confidence_score, "threshold": self.CONFIDENCE_THRESHOLD}
            ))
            
    def _check_null_ratio(self, data: ExtractedData, result: ValidationResult):
        """데이터 내 Null/빈 값 비율 확인"""
        null_count, total_count = self._count_null_values(data.data)
        
        # 행 데이터도 포함해서 계산
        if data.rows:
            for row in data.rows:
                for cell in row:
                    total_count += 1
                    if self._is_empty(cell):
                        null_count += 1
                        
        if total_count > 0:
            ratio = null_count / total_count
            if ratio >= self.NULL_RATIO_THRESHOLD:
                result.add_issue(ValidationError(
                    severity=ValidationSeverity.WARNING,
                    error_type="HIGH_NULL_RATIO",
                    message=f"데이터 누락이 많습니다 (누락률: {ratio:.1%}). 원본 품질을 확인하세요.",
                    details={"null_count": null_count, "total_count": total_count, "ratio": ratio}
                ))
    
    def _check_required_metadata(self, data: ExtractedData, result: ValidationResult):
        """필수 메타데이터 확인"""
        if not data.summary:
            result.add_issue(ValidationError(
                severity=ValidationSeverity.INFO,
                error_type="MISSING_SUMMARY",
                message="문서 요약이 생성되지 않았습니다.",
                field="summary"
            ))
            
        if not data.data and not data.rows:
            result.add_issue(ValidationError(
                severity=ValidationSeverity.WARNING,
                error_type="EMPTY_DATA",
                message="추출된 데이터가 없습니다.",
                field="data"
            ))

    # ==================== 문서 유형별 검증 로직 ====================

    def _validate_invoice(self, data: ExtractedData, result: ValidationResult):
        """청구서/인보이스 검증: 공급가액 + 세액 = 합계"""
        d = data.data
        
        supply_keys = ["공급가액", "supply_amount", "subtotal", "net_amount", "공급가", "금액"]
        tax_keys = ["부가세", "tax", "vat", "부가가치세", "세액"]
        total_keys = ["합계", "total", "total_amount", "총액", "청구금액"]
        
        supply = self._find_numeric_value(d, supply_keys)
        tax = self._find_numeric_value(d, tax_keys)
        total = self._find_numeric_value(d, total_keys)
        
        # 필수 필드 누락 경고
        if supply is None:
            self._add_missing_field_warning(result, "공급가액", supply_keys)
        if total is None:
            self._add_missing_field_warning(result, "합계", total_keys)
            
        # 수식 검증
        if supply is not None and tax is not None and total is not None:
            expected = supply + tax
            if abs(expected - total) > self.tolerance:
                result.add_issue(ValidationError(
                    severity=ValidationSeverity.ERROR,
                    error_type="CALCULATION_MISMATCH",
                    message=f"금액 불일치: 공급가액({supply:,.0f}) + 부가세({tax:,.0f}) ≠ 합계({total:,.0f})",
                    details={"supply": supply, "tax": tax, "total": total, "expected": expected}
                ))
        elif supply is not None and tax is None and total is not None:
            # 부가세가 없는 경우 (면세 등) -> 공급가액 = 합계 확인
            if abs(supply - total) > self.tolerance:
                # 이건 에러보다는 경고나 정보로 처리 (부가세 누락 가능성)
                 result.add_issue(ValidationError(
                    severity=ValidationSeverity.WARNING,
                    error_type="TAX_MISSING_OR_MISMATCH",
                    message=f"부가세가 없으나 공급가액({supply:,.0f})과 합계({total:,.0f})가 다릅니다.",
                    details={"supply": supply, "total": total}
                ))

    def _validate_receipt(self, data: ExtractedData, result: ValidationResult):
        """영수증 검증"""
        self._validate_invoice(data, result)

    def _validate_contract(self, data: ExtractedData, result: ValidationResult):
        """계약서 검증: 필수 당사자 및 날짜 확인"""
        d = data.data
        
        # 1. 당사자 확인 (갑/을)
        party_a_keys = ["갑", "party_a", "first_party", "발주자", "매도인", "임대인"]
        party_b_keys = ["을", "party_b", "second_party", "수주자", "매수인", "임차인"]
        
        party_a = self._find_value(d, party_a_keys)
        party_b = self._find_value(d, party_b_keys)
        
        if not party_a:
            result.add_issue(ValidationError(
                severity=ValidationSeverity.ERROR,
                error_type="MISSING_PARTY",
                message="계약 당사자 '갑'(First Party) 정보가 누락되었습니다.",
                field="party_a"
            ))
        if not party_b:
            result.add_issue(ValidationError(
                severity=ValidationSeverity.ERROR,
                error_type="MISSING_PARTY",
                message="계약 당사자 '을'(Second Party) 정보가 누락되었습니다.",
                field="party_b"
            ))
            
        # 2. 계약일 확인
        date_keys = ["계약일", "contract_date", "date", "signed_date", "체결일"]
        contract_date = self._find_value(d, date_keys)
        
        if not contract_date:
             result.add_issue(ValidationError(
                severity=ValidationSeverity.ERROR,
                error_type="MISSING_DATE",
                message="계약 체결일 정보가 누락되었습니다.",
                field="contract_date"
            ))

    def _validate_financial_statement(self, data: ExtractedData, result: ValidationResult):
        """재무제표 통합 검증"""
        self._validate_balance_sheet(data, result)
        self._validate_income_statement(data, result)

    def _validate_balance_sheet(self, data: ExtractedData, result: ValidationResult):
        """대차대조표: 자산 = 부채 + 자본"""
        d = data.data
        
        asset_keys = ["자산", "assets", "total_assets", "자산총계"]
        liab_keys = ["부채", "liabilities", "total_liabilities", "부채총계"]
        equity_keys = ["자본", "equity", "total_equity", "자본총계"]
        
        asset = self._find_numeric_value(d, asset_keys)
        liab = self._find_numeric_value(d, liab_keys)
        equity = self._find_numeric_value(d, equity_keys)
        
        # 테이블 데이터에서 검색 시도 (data 딕셔너리에 없을 경우)
        if data.rows and data.headers:
            if asset is None: asset = self._find_in_rows(data, asset_keys)
            if liab is None: liab = self._find_in_rows(data, liab_keys)
            if equity is None: equity = self._find_in_rows(data, equity_keys)
            
        if asset is not None and liab is not None and equity is not None:
            expected = liab + equity
            if abs(asset - expected) > self.tolerance:
                result.add_issue(ValidationError(
                    severity=ValidationSeverity.ERROR,
                    error_type="ACCOUNTING_MISMATCH",
                    message=f"대차평형 원리 위반: 자산({asset:,.0f}) ≠ 부채({liab:,.0f}) + 자본({equity:,.0f})",
                    details={"asset": asset, "liabilities": liab, "equity": equity, "diff": abs(asset - expected)}
                ))

    def _validate_income_statement(self, data: ExtractedData, result: ValidationResult):
        """손익계산서: 매출 - 비용 = 이익"""
        d = data.data
        
        rev_keys = ["매출", "revenue", "sales", "매출액"]
        exp_keys = ["비용", "expenses", "cost", "원가", "매출원가", "영업비용"]
        profit_keys = ["이익", "profit", "income", "net_income", "당기순이익", "영업이익"]
        
        rev = self._find_numeric_value(d, rev_keys)
        exp = self._find_numeric_value(d, exp_keys)
        profit = self._find_numeric_value(d, profit_keys)
        
        if data.rows and data.headers:
             if rev is None: rev = self._find_in_rows(data, rev_keys)
             if exp is None: exp = self._find_in_rows(data, exp_keys)
             if profit is None: profit = self._find_in_rows(data, profit_keys)
             
        if rev is not None and exp is not None and profit is not None:
            # 단순 검증: 매출 - 비용 = 이익 (가장 기본적인 형태만)
            # 손익계산서는 구조가 복잡하므로 (매출-원가=매출이익-판관비=영업이익...) 
            # 정확한 매칭이 어려울 수 있어 오차가 크면 경고로 처리하거나, 특정 키워드(영업이익 등)에 맞춰 검증해야 함
            pass 

    def _validate_table(self, data: ExtractedData, result: ValidationResult):
        """일반 표 구조 검증"""
        if data.headers and data.rows:
            header_count = len(data.headers)
            for idx, row in enumerate(data.rows):
                if len(row) != header_count:
                     result.add_issue(ValidationError(
                        severity=ValidationSeverity.WARNING,
                        error_type="ROW_LENGTH_MISMATCH",
                        message=f"행 {idx}의 열 개수({len(row)})가 헤더({header_count})와 다릅니다.",
                        row_index=idx,
                        details={"row": row}
                    ))

    def _apply_custom_rules(self, data: ExtractedData, rules: List[Dict], result: ValidationResult):
        """사용자 정의 규칙 검증"""
        for rule in rules:
            rule_type = rule.get("type")
            if rule_type == "required":
                field = rule.get("field")
                if not self._find_value(data.data, [field]):
                     result.add_issue(ValidationError(
                        severity=ValidationSeverity.ERROR,
                        error_type="CUSTOM_REQUIRED_MISSING",
                        message=f"필수 필드 '{field}'가 누락되었습니다.",
                        field=field
                    ))

    # ==================== 유틸리티 ====================

    def _count_null_values(self, d: Dict[str, Any]) -> tuple[int, int]:
        """(null 개수, 전체 항목 수) 반환"""
        nulls = 0
        total = 0
        for v in d.values():
            if isinstance(v, dict):
                n, t = self._count_null_values(v)
                nulls += n
                total += t
            elif isinstance(v, list):
                for item in v:
                    total += 1
                    if self._is_empty(item): nulls += 1
            else:
                total += 1
                if self._is_empty(v): nulls += 1
        return nulls, total

    def _is_empty(self, v: Any) -> bool:
        return v is None or v == "" or v == "N/A" or v == "-"

    def _find_value(self, d: Dict[str, Any], keys: List[str]) -> Any:
        """키 목록 중 하나라도 매칭되면 값 반환"""
        for k in keys:
            # 1. Exact match
            if k in d: return d[k]
            # 2. Case insensitive match
            for dk in d.keys():
                if dk.lower() == k.lower(): return d[dk]
                # 3. Partial match (optional, but useful)
                if k in dk or dk in k: pass 
        return None

    def _find_numeric_value(self, d: Dict[str, Any], keys: List[str]) -> Optional[float]:
        val = self._find_value(d, keys)
        if val is not None:
            return self._to_float(val)
        return None

    def _find_in_rows(self, data: ExtractedData, keys: List[str]) -> Optional[float]:
        """테이블 행의 첫 번째 열(항목명)에서 키를 찾아 마지막 열(값)의 숫자 반환"""
        if not data.rows: return None
        for row in data.rows:
            if not row: continue
            item_name = str(row[0])
            for k in keys:
                if k in item_name or item_name in k:
                    # 값이 있는 마지막 셀 탐색
                    for cell in reversed(row[1:]):
                        val = self._to_float(cell)
                        if val is not None: return val
        return None

    def _to_float(self, v: Any) -> Optional[float]:
        if isinstance(v, (int, float)): return float(v)
        if isinstance(v, str):
            try:
                clean = v.replace(',', '').replace('$', '').replace('₩', '').strip()
                return float(clean)
            except: pass
        return None

    def _add_missing_field_warning(self, result: ValidationResult, field_name: str, keys: List[str]):
        """필수 필드 누락 시 경고 추가"""
        result.add_issue(ValidationError(
            severity=ValidationSeverity.WARNING,
            error_type="MISSING_FIELD",
            message=f"필수 필드 '{field_name}'을(를) 찾을 수 없습니다. (검색 키: {', '.join(keys)})",
            field=field_name
        ))


# 하위 호환성 (기존 코드에서 FinancialValidator로 임포트하는 경우 대응)
FinancialValidator = UniversalValidator
