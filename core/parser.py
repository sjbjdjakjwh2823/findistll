"""
FinDistill Multimodal Parser - Google Gemini Version

Google Gemini API를 사용하여 이미지나 PDF에서 문서 데이터를 추출하는 클래스입니다.
gemini-1.5-flash 모델을 기본으로 사용합니다.
"""

from typing import Dict, List, Any, Optional, Union
import json
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

# .env 파일 로드
load_dotenv()

# 스키마 import
from models.schemas import ExtractedData, ExtractedMetadata, DocumentType


# 시스템 프롬프트: 문서 레이아웃 분석 및 데이터 추출 지침
SYSTEM_PROMPT = """당신은 문서 분석 전문가입니다. 다음 지침에 따라 문서를 분석해주세요:

## 핵심 임무
문서의 레이아웃을 분석하여 가장 중요한 Key-Value 쌍과 표 데이터를 추출하세요.

## 분석 지침
1. **문서 유형 판별**: 문서가 어떤 종류인지 파악하세요 (invoice, contract, manual, medical_report, financial_statement, balance_sheet, income_statement, receipt, form, report, table, other)
2. **핵심 정보 추출**: 문서에서 가장 중요한 Key-Value 쌍을 찾아 data 필드에 담으세요
3. **표 데이터 추출**: 표가 있다면 headers와 rows 필드에 정확히 추출하세요
4. **요약 생성**: 문서 내용을 한 줄로 요약하세요
5. **확신도 평가**: 추출 정확도에 대한 확신도(0.0~1.0)를 제공하세요

## 숫자 처리 규칙
- 숫자는 콤마를 포함한 원본 형식 그대로 유지하세요 (예: "1,234,567")
- 빈 셀은 빈 문자열("") 또는 null로 표시하세요
- 통화 기호는 유지하세요 (예: "$1,000", "₩10,000")

## 표 처리 규칙
- 병합된 셀이 있는 경우, 모든 행에 해당 값을 채워서 플래트닝하세요
- 헤더와 데이터 행을 명확히 구분하세요
- 행의 순서를 유지하세요

## 출력 형식
반드시 다음 JSON 형식으로만 응답하세요. 다른 설명이나 마크다운은 절대 포함하지 마세요:
{
    "document_type": "문서 종류",
    "summary": "문서 내용 한 줄 요약",
    "data": {
        "key1": "value1",
        "key2": "value2"
    },
    "confidence_score": 0.95,
    "title": "문서/표 제목",
    "headers": ["헤더1", "헤더2"],
    "rows": [
        ["데이터1-1", "데이터1-2"],
        ["데이터2-1", "데이터2-2"]
    ]
}
"""


class ExtractionResult:
    """
    추출 결과를 담는 클래스
    """
    
    def __init__(
        self,
        data: ExtractedData,
        is_valid: bool = True,
        manual_review_required: bool = False,
        correction_attempts: int = 0,
        validation_errors: List[Union[Dict[str, Any], ValidationError]] = None,
        correction_history: List[Dict[str, Any]] = None
    ):
        self.data = data
        self.table = data  # 하위 호환성
        self.is_valid = is_valid
        self.manual_review_required = manual_review_required
        self.correction_attempts = correction_attempts
        self.validation_errors = validation_errors or []
        self.correction_history = correction_history or []
    
    def to_dict(self) -> Dict[str, Any]:
        """결과를 딕셔너리로 변환"""
        # ValidationError 객체 직렬화 처리
        serialized_errors = []
        for error in self.validation_errors:
            if hasattr(error, 'model_dump'):
                serialized_errors.append(error.model_dump())
            elif hasattr(error, 'to_dict'):
                serialized_errors.append(error.to_dict())
            else:
                serialized_errors.append(error)
                
        return {
            "data": self.data.model_dump(),
            "is_valid": self.is_valid,
            "manual_review_required": self.manual_review_required,
            "correction_attempts": self.correction_attempts,
            "validation_errors": serialized_errors,
            "correction_history": self.correction_history
        }


class VisionParser:
    """
    Google Gemini Multimodal API를 사용하여 이미지나 PDF에서 데이터를 추출하는 클래스
    
    기본 모델: gemini-1.5-flash
    """
    
    DEFAULT_MODEL = "gemini-1.5-flash"
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: Optional[str] = None,
        max_correction_attempts: int = 2
    ):
        """
        VisionParser 초기화
        
        Args:
            api_key: Gemini API 키 (None인 경우 환경변수에서 가져옴)
            model: 사용할 Gemini 모델 (기본값: gemini-1.5-flash)
            max_correction_attempts: 최대 자가 교정 시도 횟수 (기본값: 2)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key or self.api_key == "your-gemini-api-key-here":
            raise ValueError(
                "Gemini API 키가 설정되지 않았습니다. "
                "api_key 파라미터나 GEMINI_API_KEY 환경변수를 설정해주세요. "
                "https://aistudio.google.com/app/apikey 에서 무료로 발급 가능합니다."
            )
        
        # Gemini 설정
        genai.configure(api_key=self.api_key)
        self.model_name = model or self.DEFAULT_MODEL
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=SYSTEM_PROMPT
        )
        self.max_correction_attempts = max_correction_attempts
    
    def extract_data(
        self, 
        file_path: str,
        document_type: Optional[DocumentType] = None,
        language: str = "ko"
    ) -> ExtractedData:
        """
        이미지나 PDF에서 데이터를 추출하여 ExtractedData 객체로 반환
        
        Args:
            file_path: 이미지 또는 PDF 파일 경로
            document_type: 예상 문서 타입 (None인 경우 자동 감지)
            language: 문서 언어 (기본값: ko)
            
        Returns:
            ExtractedData: 추출된 데이터
            
        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            ValueError: API 응답 파싱 실패 시
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        file_ext = Path(file_path).suffix.lower()
        start_time = datetime.now()
        
        # 파일 타입에 따른 처리
        if file_ext == '.pdf':
            # PDF는 이미지로 변환 후 처리
            from utils.pdf_processor import PDFProcessor
            processor = PDFProcessor(dpi=300)
            temp_image_path = processor.pdf_page_to_image(file_path, page_num=0)
            try:
                image = Image.open(temp_image_path)
                response = self._call_gemini_api(image, document_type, language)
            finally:
                if os.path.exists(temp_image_path):
                    os.unlink(temp_image_path)
        else:
            # 이미지 파일 직접 처리
            image = Image.open(file_path)
            response = self._call_gemini_api(image, document_type, language)
        
        # 처리 시간 계산
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # 응답 파싱
        extracted_data = self._parse_json_response(response, file_path, processing_time)
        
        return extracted_data
    
    def extract_from_image(
        self, 
        image_path: str,
        document_type: Optional[DocumentType] = None,
        language: str = "ko"
    ) -> ExtractedData:
        """이미지에서 데이터 추출 (extract_data의 별칭)"""
        return self.extract_data(image_path, document_type, language)
    
    def extract_table_from_image(
        self, 
        image_path: str,
        currency: str = "KRW",
        unit: int = 1
    ) -> ExtractedData:
        """하위 호환성을 위한 메서드"""
        data = self.extract_data(image_path, DocumentType.TABLE)
        data.data["currency"] = currency
        data.data["unit"] = unit
        return data
    
    def extract_and_validate_with_correction(
        self,
        image_path: str,
        validator,
        document_type: Optional[DocumentType] = None,
        language: str = "ko",
        currency: str = "KRW",
        unit: int = 1,
        validation_rules: Optional[List[Dict[str, Any]]] = None
    ) -> ExtractionResult:
        """
        데이터 추출 후 검증, 오류 시 자가 교정 수행
        
        최대 max_correction_attempts 횟수만큼 자가 교정을 시도하며,
        최종 실패 시 manual_review_required 플래그를 True로 설정
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {image_path}")
        
        image = Image.open(image_path)
        correction_history = []
        current_data = None
        current_errors = []
        
        # 최초 추출
        print("📊 [1차 시도] 문서에서 데이터 추출 중...")
        response = self._call_gemini_api(image, document_type, language)
        current_data = self._parse_json_response(response, image_path)
        
        # 추가 필드 설정
        current_data.data["currency"] = currency
        current_data.data["unit"] = unit
        
        # 검증
        validation_result = validator.validate(current_data, validation_rules)
        
        # 검증 통과 (Warning만 있는 경우 포함)
        if validation_result.is_valid:
            status_msg = "✅ 검증 통과!"
            if validation_result.needs_review:
                status_msg += " (단, 검토 필요 경고 있음)"
            print(status_msg)
            
            return ExtractionResult(
                data=current_data,
                is_valid=True,
                manual_review_required=validation_result.needs_review,
                correction_attempts=0,
                validation_errors=[e.model_dump(mode='json') for e in validation_result.errors] # 경고 포함
            )
        
        current_errors = [e.model_dump(mode='json') for e in validation_result.errors]
        # 심각한 오류만 필터링해서 교정 요청할 수도 있지만, 일단 전체 전달
        correction_history.append({
            "attempt": 0,
            "type": "initial_extraction",
            "errors_count": len(current_errors)
        })
        
        print(f"⚠️ 검증 실패: {len(current_errors)}개의 이슈 발견. 자가 교정 시작...")
        
        # 자가 교정 루프
        for attempt in range(1, self.max_correction_attempts + 1):
            print(f"\n🔄 [자가 교정 {attempt}/{self.max_correction_attempts}]")
            
            correction_response = self._call_correction_api(
                image=image,
                previous_result=current_data.model_dump(),
                validation_errors=current_errors
            )
            
            try:
                current_data = self._parse_json_response(correction_response, image_path)
                current_data.data["currency"] = currency
                current_data.data["unit"] = unit
            except ValueError as e:
                print(f"   ❌ 교정 응답 파싱 실패: {e}")
                correction_history.append({
                    "attempt": attempt,
                    "type": "parse_failed"
                })
                continue
            
            validation_result = validator.validate(current_data, validation_rules)
            
            if validation_result.is_valid:
                print(f"   ✅ 자가 교정 성공! ({attempt}번째 시도)")
                correction_history.append({
                    "attempt": attempt,
                    "type": "success"
                })
                return ExtractionResult(
                    data=current_data,
                    is_valid=True,
                    manual_review_required=validation_result.needs_review,
                    correction_attempts=attempt,
                    validation_errors=[e.model_dump(mode='json') for e in validation_result.errors],
                    correction_history=correction_history
                )
            
            current_errors = [e.model_dump(mode='json') for e in validation_result.errors]
            print(f"   ⚠️ {len(current_errors)}개 이슈 남음")
            correction_history.append({
                "attempt": attempt,
                "type": "partial",
                "errors_count": len(current_errors)
            })
        
        print(f"\n❌ 자가 교정 {self.max_correction_attempts}회 후에도 오류 존재")
        print("   📋 수동 검토가 필요합니다.")
        
        return ExtractionResult(
            data=current_data,
            is_valid=False,
            manual_review_required=True,
            correction_attempts=self.max_correction_attempts,
            validation_errors=current_errors,
            correction_history=correction_history
        )
    
    def _call_gemini_api(
        self, 
        image: Image.Image,
        document_type: Optional[DocumentType] = None,
        language: str = "ko"
    ) -> str:
        """Gemini Vision API 호출"""
        
        # 문서 타입 힌트
        doc_type_hint = ""
        if document_type:
            doc_type_hint = f"이 문서는 '{document_type.value}' 타입으로 예상됩니다. "
        
        # 사용자 프롬프트
        user_prompt = f"""{doc_type_hint}이 문서를 분석하고 데이터를 추출해주세요.

문서 언어: {language}

중요: 응답은 반드시 순수 JSON 형식이어야 합니다. 마크다운 코드 블록(```json)을 사용하지 마세요.
"""
        
        # API 호출
        response = self.model.generate_content(
            [user_prompt, image],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # 일관된 결과를 위해 낮은 온도
                max_output_tokens=4096
            )
        )
        
        return response.text
    
    def _call_correction_api(
        self,
        image: Image.Image,
        previous_result: Dict[str, Any],
        validation_errors: List[Union[Dict[str, Any], ValidationError]]
    ) -> str:
        """자가 교정 API 호출"""
        
        # 오류 메시지 포맷팅
        error_messages = []
        for idx, error in enumerate(validation_errors, 1):
            if hasattr(error, 'message'):
                msg = error.message
            else:
                msg = error.get('message', 'Unknown error')
            error_messages.append(f"{idx}. {msg}")
        
        errors_text = "\n".join(error_messages)
        
        # 교정 프롬프트
        correction_prompt = f"""이전 추출 결과에서 다음 오류가 발견되었습니다:

**발견된 오류:**
{errors_text}

**이전 추출 결과:**
{json.dumps(previous_result, indent=2, ensure_ascii=False)}

**요청사항:**
1. 원본 문서 이미지를 다시 분석하세요
2. 위 오류를 수정하세요
3. 특히 숫자 값이 정확한지 확인하세요

중요: 응답은 반드시 순수 JSON 형식이어야 합니다. 마크다운 코드 블록(```json)을 사용하지 마세요.
"""
        
        response = self.model.generate_content(
            [correction_prompt, image],
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=4096
            )
        )
        
        return response.text
    
    def _parse_json_response(
        self, 
        response_text: str, 
        source_path: str,
        processing_time_ms: Optional[int] = None
    ) -> ExtractedData:
        """
        Gemini API 응답을 파싱하여 ExtractedData로 변환
        
        마크다운 코드 블록(```json)을 제거하고 순수 JSON을 파싱합니다.
        """
        try:
            # 마크다운 코드 블록 제거
            cleaned_text = self._clean_json_response(response_text)
            
            # JSON 파싱
            parsed = json.loads(cleaned_text)
            
            # document_type 변환
            doc_type_str = parsed.get("document_type", "other")
            try:
                doc_type = DocumentType(doc_type_str)
            except ValueError:
                doc_type = DocumentType.OTHER
            
            # ExtractedData 생성
            extracted_data = ExtractedData(
                document_type=doc_type,
                summary=parsed.get("summary", ""),
                data=parsed.get("data", {}),
                confidence_score=float(parsed.get("confidence_score", 0.0)),
                metadata=ExtractedMetadata(
                    filename=os.path.basename(source_path),
                    source_format=Path(source_path).suffix.lower().lstrip('.'),
                    model_used=self.model_name,
                    processing_time_ms=processing_time_ms
                ),
                title=parsed.get("title"),
                headers=parsed.get("headers"),
                rows=parsed.get("rows")
            )
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            raise ValueError(
                f"API 응답을 JSON으로 파싱할 수 없습니다: {e}\n"
                f"정제된 응답: {cleaned_text[:500]}..."
            )
        except Exception as e:
            raise ValueError(f"응답 파싱 중 오류 발생: {e}")
    
    def _clean_json_response(self, response_text: str) -> str:
        """
        응답에서 마크다운 코드 블록과 불필요한 문자를 제거
        
        처리하는 패턴:
        - ```json ... ```
        - ``` ... ```
        - 앞뒤 공백
        - BOM 문자
        """
        cleaned = response_text.strip()
        
        # BOM 문자 제거
        if cleaned.startswith('\ufeff'):
            cleaned = cleaned[1:]
        
        # ```json ... ``` 패턴 제거
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```JSON"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        # 앞뒤 공백 다시 제거
        cleaned = cleaned.strip()
        
        # JSON 객체 시작/끝 찾기 (혹시 앞뒤에 다른 텍스트가 있는 경우)
        json_start = cleaned.find('{')
        json_end = cleaned.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_end > json_start:
            cleaned = cleaned[json_start:json_end + 1]
        
        return cleaned
