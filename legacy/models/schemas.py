"""
FinDistill 범용 데이터 스키마

Pydantic v2를 사용하여 어떤 문서(invoice, contract, manual, medical_report 등)든
담을 수 있는 유연한 데이터 구조를 제공합니다.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import re


class DocumentType(str, Enum):
    """지원하는 문서 타입"""
    INVOICE = "invoice"                    # 청구서/인보이스
    CONTRACT = "contract"                  # 계약서
    MANUAL = "manual"                      # 매뉴얼/설명서
    MEDICAL_REPORT = "medical_report"      # 의료 보고서
    FINANCIAL_STATEMENT = "financial_statement"  # 재무제표
    BALANCE_SHEET = "balance_sheet"        # 대차대조표
    INCOME_STATEMENT = "income_statement"  # 손익계산서
    RECEIPT = "receipt"                    # 영수증
    FORM = "form"                          # 양식/서식
    REPORT = "report"                      # 일반 보고서
    TABLE = "table"                        # 표 데이터
    OTHER = "other"                        # 기타


class ExtractedMetadata(BaseModel):
    """추출 메타데이터"""
    filename: Optional[str] = Field(default=None, description="원본 파일명")
    extracted_at: datetime = Field(default_factory=datetime.now, description="추출 일시")
    page_number: Optional[int] = Field(default=None, description="페이지 번호")
    total_pages: Optional[int] = Field(default=None, description="전체 페이지 수")
    source_format: Optional[str] = Field(default=None, description="원본 파일 형식 (pdf, image 등)")
    language: Optional[str] = Field(default="ko", description="문서 언어")
    processing_time_ms: Optional[int] = Field(default=None, description="처리 시간 (밀리초)")
    model_used: Optional[str] = Field(default="gpt-4o", description="사용된 AI 모델")
    custom: Optional[Dict[str, Any]] = Field(default=None, description="추가 메타데이터")


class ExtractedData(BaseModel):
    """
    범용 추출 데이터 스키마
    
    어떤 종류의 문서든 담을 수 있는 유연한 구조입니다.
    """
    document_type: DocumentType = Field(
        default=DocumentType.OTHER,
        description="문서 종류 (invoice, contract, manual, medical_report 등)"
    )
    
    summary: str = Field(
        default="",
        description="문서 내용의 한 줄 요약"
    )
    
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="실제 추출된 핵심 정보를 담는 Dictionary (JSON)"
    )
    
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="추출 결과에 대한 AI의 확신도 (0~1)"
    )
    
    metadata: ExtractedMetadata = Field(
        default_factory=ExtractedMetadata,
        description="추출 날짜, 파일명 등 메타데이터"
    )
    
    # 하위 호환성을 위한 필드 (테이블 데이터)
    title: Optional[str] = Field(default=None, description="표/문서 제목")
    headers: Optional[List[str]] = Field(default=None, description="테이블 헤더")
    rows: Optional[List[List[Any]]] = Field(default=None, description="테이블 행 데이터")
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """확신도 값 검증 (0~1 범위)"""
        if v < 0:
            return 0.0
        if v > 1:
            return 1.0
        return round(v, 4)
    
    @field_validator('data')
    @classmethod
    def normalize_data_numbers(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """data 필드 내의 숫자 데이터를 정규화"""
        return cls._normalize_dict_numbers(v)
    
    @field_validator('rows')
    @classmethod
    def normalize_rows_numbers(cls, v: Optional[List[List[Any]]]) -> Optional[List[List[Any]]]:
        """rows 필드 내의 숫자 데이터를 정규화"""
        if v is None:
            return None
        return [[cls._normalize_value(cell) for cell in row] for row in v]
    
    @classmethod
    def _normalize_dict_numbers(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        """딕셔너리 내의 모든 숫자 데이터를 재귀적으로 정규화"""
        result = {}
        for key, value in d.items():
            result[key] = cls._normalize_value(value)
        return result
    
    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """개별 값을 정규화"""
        if value is None:
            return None
        
        # 딕셔너리인 경우 재귀 처리
        if isinstance(value, dict):
            return cls._normalize_dict_numbers(value)
        
        # 리스트인 경우 재귀 처리
        if isinstance(value, list):
            return [cls._normalize_value(item) for item in value]
        
        # 이미 숫자형인 경우 그대로 반환
        if isinstance(value, (int, float)):
            return float(value) if isinstance(value, float) else value
        
        # 문자열인 경우 숫자 변환 시도
        if isinstance(value, str):
            return cls._try_convert_to_number(value)
        
        return value
    
    @classmethod
    def _try_convert_to_number(cls, value: str) -> Union[float, int, str]:
        """
        문자열을 숫자로 변환 시도
        - 콤마 제거: "1,234,567" → 1234567
        - 백분율 처리: "50%" → 0.5
        - 통화 기호 제거: "$1,000" → 1000
        """
        if not value or not isinstance(value, str):
            return value
        
        original = value.strip()
        
        # 빈 문자열이나 대시는 None으로 처리하지 않고 그대로 반환
        if original == '' or original == '-' or original == 'N/A':
            return original
        
        # 통화 기호 제거
        cleaned = re.sub(r'^[$€£¥₩₹]', '', original)
        cleaned = re.sub(r'[$€£¥₩₹]$', '', cleaned)
        
        # 콤마 제거
        cleaned = cleaned.replace(',', '').strip()
        
        # 백분율 처리
        is_percentage = cleaned.endswith('%')
        if is_percentage:
            cleaned = cleaned[:-1].strip()
        
        # 괄호로 표시된 음수 처리: (1000) → -1000
        is_negative = cleaned.startswith('(') and cleaned.endswith(')')
        if is_negative:
            cleaned = cleaned[1:-1].strip()
        
        # 숫자 변환 시도
        try:
            if '.' in cleaned:
                num = float(cleaned)
            else:
                num = int(cleaned)
                num = float(num)  # 일관성을 위해 float로 변환
            
            # 음수 처리
            if is_negative:
                num = -num
            
            # 백분율 처리 (0~1 범위로 변환)
            if is_percentage:
                num = num / 100.0
            
            return num
            
        except ValueError:
            # 숫자로 변환 불가능한 경우 원본 반환
            return original
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "document_type": "invoice",
                    "summary": "2024년 1월 서비스 청구서 - 총 1,500,000원",
                    "data": {
                        "invoice_number": "INV-2024-001",
                        "issue_date": "2024-01-15",
                        "due_date": "2024-02-15",
                        "vendor": "ABC 주식회사",
                        "customer": "XYZ 기업",
                        "items": [
                            {"description": "컨설팅 서비스", "quantity": 10, "unit_price": 100000, "amount": 1000000},
                            {"description": "교육 서비스", "quantity": 5, "unit_price": 100000, "amount": 500000}
                        ],
                        "subtotal": 1500000,
                        "tax": 150000,
                        "total": 1650000
                    },
                    "confidence_score": 0.95,
                    "metadata": {
                        "filename": "invoice_2024_001.pdf",
                        "page_number": 0,
                        "total_pages": 1
                    }
                },
                {
                    "document_type": "financial_statement",
                    "summary": "2024년 1분기 재무제표",
                    "data": {
                        "period": "2024-Q1",
                        "assets": 10000000,
                        "liabilities": 4000000,
                        "equity": 6000000,
                        "revenue": 5000000,
                        "expenses": 3000000,
                        "net_income": 2000000
                    },
                    "confidence_score": 0.92,
                    "metadata": {
                        "filename": "financial_q1_2024.pdf"
                    },
                    "title": "2024년 1분기 재무제표",
                    "headers": ["항목", "금액"],
                    "rows": [
                        ["자산", 10000000],
                        ["부채", 4000000],
                        ["자본", 6000000]
                    ]
                }
            ]
        }
    }


# 하위 호환성을 위한 별칭
FinancialTable = ExtractedData


class ValidationSeverity(str, Enum):
    """검증 결과 심각도"""
    ERROR = "error"          # 필수 검증 실패 (is_valid = False)
    WARNING = "warning"      # 검토 필요 (manual_review_required = True)
    INFO = "info"            # 정보성 메시지


class ValidationError(BaseModel):
    """검증 오류/경고 정보"""
    severity: ValidationSeverity = Field(default=ValidationSeverity.ERROR, description="심각도")
    error_type: str = Field(description="오류 유형")
    message: str = Field(description="오류 메시지")
    field: Optional[str] = Field(default=None, description="관련 필드명")
    row_index: Optional[int] = Field(default=None, description="관련 행 번호 (테이블인 경우)")
    details: Optional[Dict[str, Any]] = Field(default=None, description="상세 정보")


class ValidationResult(BaseModel):
    """검증 결과"""
    is_valid: bool = Field(default=True, description="검증 통과 여부 (Error가 없으면 True)")
    needs_review: bool = Field(default=False, description="검토 필요 여부 (Warning이 있으면 True)")
    errors: List[ValidationError] = Field(default_factory=list, description="오류/경고 목록")
    
    def add_issue(self, error: ValidationError):
        """이슈 추가 및 상태 업데이트"""
        self.errors.append(error)
        if error.severity == ValidationSeverity.ERROR:
            self.is_valid = False
        elif error.severity == ValidationSeverity.WARNING:
            self.needs_review = True
            
    def get_report(self) -> str:
        """상세 리포트 생성"""
        if not self.errors:
            return "✅ 모든 검증을 통과했습니다."
        
        report = []
        
        # 에러 분리
        cnt_error = sum(1 for e in self.errors if e.severity == ValidationSeverity.ERROR)
        cnt_warn = sum(1 for e in self.errors if e.severity == ValidationSeverity.WARNING)
        cnt_info = sum(1 for e in self.errors if e.severity == ValidationSeverity.INFO)
        
        if cnt_error > 0:
            report.append(f"❌ 오류: {cnt_error}개")
        if cnt_warn > 0:
            report.append(f"⚠️ 경고: {cnt_warn}개")
        if cnt_info > 0:
            report.append(f"ℹ️ 정보: {cnt_info}개")
            
        report.append("")
        
        for idx, error in enumerate(self.errors, 1):
            icon = "❌" if error.severity == ValidationSeverity.ERROR else "⚠️" if error.severity == ValidationSeverity.WARNING else "ℹ️"
            report.append(f"[{idx}] {icon} [{error.error_type}] {error.message}")
            if error.field:
                report.append(f"    필드: {error.field}")
            if error.row_index is not None:
                report.append(f"    행: {error.row_index}")
            if error.details:
                report.append(f"    상세: {error.details}")
            report.append("")
            
        return "\n".join(report)


class ExtractionRequest(BaseModel):
    """추출 요청"""
    pdf_path: Optional[str] = Field(default=None, description="PDF 파일 경로")
    pdf_base64: Optional[str] = Field(default=None, description="Base64 인코딩된 PDF")
    page_number: int = Field(default=0, description="추출할 페이지 번호")
    document_type: Optional[DocumentType] = Field(default=None, description="예상 문서 타입")
    language: str = Field(default="ko", description="문서 언어")
    auto_correct: bool = Field(default=True, description="자가 교정 활성화")
    max_correction_attempts: int = Field(default=2, description="최대 교정 횟수")


class ExtractionResponse(BaseModel):
    """추출 응답"""
    success: bool = Field(description="성공 여부")
    message: str = Field(description="결과 메시지")
    data: Optional[ExtractedData] = Field(default=None, description="추출된 데이터")
    is_valid: Optional[bool] = Field(default=None, description="검증 통과 여부")
    manual_review_required: bool = Field(default=False, description="수동 검토 필요 여부")
    correction_attempts: int = Field(default=0, description="교정 시도 횟수")
    validation_errors: Optional[List[ValidationError]] = Field(default=None, description="검증 오류")
