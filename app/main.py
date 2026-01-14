from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import traceback
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from core.parser import VisionParser, ExtractionResult
from core.validator import FinancialValidator
from utils.pdf_processor import PDFProcessor
from models.schemas import ExtractedData, DocumentType


# FastAPI 앱 초기화
app = FastAPI(
    title="FinDistill API",
    description="범용 문서 데이터 추출 엔진 - PDF에서 데이터를 추출하고 검증합니다. Google Gemini AI 사용.",
    version="2.0.0"
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """루트 엔드포인트 - API 정보 반환"""
    return {
        "name": "FinDistill API",
        "version": "2.0.0",
        "description": "범용 문서 데이터 추출 엔진 (Google Gemini AI)",
        "endpoints": {
            "/extract": "PDF에서 데이터 추출 및 검증",
            "/extract-with-correction": "PDF에서 데이터 추출 + 자가 교정",
            "/health": "헬스 체크"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}


@app.post("/extract")
async def extract_financial_data(
    file: UploadFile = File(..., description="PDF 파일"),
    page_number: Optional[int] = Form(0, description="추출할 페이지 번호 (0부터 시작)"),
    currency: Optional[str] = Form("KRW", description="통화 단위"),
    unit: Optional[int] = Form(1, description="금액 단위"),
    validate: Optional[bool] = Form(True, description="회계 검증 수행 여부"),
    tolerance: Optional[float] = Form(0.01, description="검증 허용 오차"),
    auto_correct: Optional[bool] = Form(False, description="자가 교정 활성화 (검증 실패 시 자동 재시도)"),
    max_correction_attempts: Optional[int] = Form(2, description="최대 자가 교정 시도 횟수")
):
    """
    PDF 파일에서 금융 표 데이터를 추출하고 검증
    
    Args:
        file: 업로드된 PDF 파일
        page_number: 추출할 페이지 번호 (기본값: 0)
        currency: 통화 단위 (기본값: KRW)
        unit: 금액 단위 (기본값: 1)
        validate: 회계 검증 수행 여부 (기본값: True)
        tolerance: 검증 허용 오차 (기본값: 0.01)
        auto_correct: 자가 교정 활성화 (기본값: False)
        max_correction_attempts: 최대 자가 교정 시도 횟수 (기본값: 2)
        
    Returns:
        JSON 응답:
        - success: 성공 여부
        - data: 추출된 FinancialTable 데이터
        - validation: 검증 결과 (validate=True인 경우)
        - self_correction: 자가 교정 정보 (auto_correct=True인 경우)
        - manual_review_required: 수동 검토 필요 여부
        - message: 메시지
    """
    temp_pdf_path = None
    temp_image_path = None
    
    try:
        # 1. 파일 형식 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="PDF 파일만 업로드 가능합니다."
            )
        
        # 2. 임시 디렉토리에 PDF 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf_path = temp_pdf.name
            shutil.copyfileobj(file.file, temp_pdf)
        
        # 3. PDF를 이미지로 변환
        try:
            pdf_processor = PDFProcessor(dpi=300)
            
            # 페이지 수 확인
            page_count = pdf_processor.get_pdf_page_count(temp_pdf_path)
            
            if page_number < 0 or page_number >= page_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"페이지 번호가 범위를 벗어났습니다. 유효 범위: 0-{page_count - 1}"
                )
            
            # 특정 페이지를 이미지로 변환
            temp_image_path = pdf_processor.pdf_page_to_image(
                temp_pdf_path, 
                page_num=page_number
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"PDF를 이미지로 변환하는 중 오류 발생: {str(e)}"
            )
        
        # 4. OpenAI API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
            )
        
        # 5. 자가 교정 모드 또는 일반 모드 처리
        if auto_correct and validate:
            # 자가 교정 모드: 추출 + 검증 + 자동 교정
            return await _process_with_correction(
                temp_image_path=temp_image_path,
                api_key=api_key,
                currency=currency,
                unit=unit,
                tolerance=tolerance,
                max_correction_attempts=max_correction_attempts,
                page_number=page_number,
                page_count=page_count,
                filename=file.filename
            )
        else:
            # 일반 모드: 추출 + 선택적 검증
            return await _process_without_correction(
                temp_image_path=temp_image_path,
                api_key=api_key,
                currency=currency,
                unit=unit,
                validate=validate,
                tolerance=tolerance,
                page_number=page_number,
                page_count=page_count,
                filename=file.filename
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Unexpected error: {error_trace}")
        
        raise HTTPException(
            status_code=500,
            detail=f"서버 내부 오류: {str(e)}"
        )
    
    finally:
        # 임시 파일 정리
        try:
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            
            if temp_image_path and os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
        except Exception as e:
            print(f"임시 파일 삭제 중 오류: {str(e)}")


@app.post("/extract-with-correction")
async def extract_with_correction(
    file: UploadFile = File(..., description="PDF 파일"),
    page_number: Optional[int] = Form(0, description="추출할 페이지 번호 (0부터 시작)"),
    currency: Optional[str] = Form("KRW", description="통화 단위"),
    unit: Optional[int] = Form(1, description="금액 단위"),
    tolerance: Optional[float] = Form(0.01, description="검증 허용 오차"),
    max_correction_attempts: Optional[int] = Form(2, description="최대 자가 교정 시도 횟수")
):
    """
    PDF 파일에서 금융 표 데이터를 추출하고, 자가 교정을 포함한 검증 수행
    
    이 엔드포인트는 자가 교정이 기본적으로 활성화되어 있습니다.
    검증 오류 발생 시 최대 max_correction_attempts 횟수만큼 자동으로 재추출을 시도합니다.
    최종적으로도 오류가 남아있으면 manual_review_required 플래그가 True로 설정됩니다.
    
    Args:
        file: 업로드된 PDF 파일
        page_number: 추출할 페이지 번호 (기본값: 0)
        currency: 통화 단위 (기본값: KRW)
        unit: 금액 단위 (기본값: 1)
        tolerance: 검증 허용 오차 (기본값: 0.01)
        max_correction_attempts: 최대 자가 교정 시도 횟수 (기본값: 2)
        
    Returns:
        JSON 응답:
        - success: 성공 여부
        - data: 추출된 FinancialTable 데이터
        - is_valid: 검증 통과 여부
        - manual_review_required: 수동 검토 필요 여부
        - correction_attempts: 실제 교정 시도 횟수
        - correction_history: 교정 이력
        - validation_errors: 남아있는 검증 오류 (있는 경우)
        - message: 메시지
    """
    temp_pdf_path = None
    temp_image_path = None
    
    try:
        # 1. 파일 형식 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="PDF 파일만 업로드 가능합니다."
            )
        
        # 2. 임시 디렉토리에 PDF 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            temp_pdf_path = temp_pdf.name
            shutil.copyfileobj(file.file, temp_pdf)
        
        # 3. PDF를 이미지로 변환
        try:
            pdf_processor = PDFProcessor(dpi=300)
            page_count = pdf_processor.get_pdf_page_count(temp_pdf_path)
            
            if page_number < 0 or page_number >= page_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"페이지 번호가 범위를 벗어났습니다. 유효 범위: 0-{page_count - 1}"
                )
            
            temp_image_path = pdf_processor.pdf_page_to_image(
                temp_pdf_path, 
                page_num=page_number
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"PDF를 이미지로 변환하는 중 오류 발생: {str(e)}"
            )
        
        # 4. OpenAI API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
            )
        
        # 5. 자가 교정 모드로 처리
        return await _process_with_correction(
            temp_image_path=temp_image_path,
            api_key=api_key,
            currency=currency,
            unit=unit,
            tolerance=tolerance,
            max_correction_attempts=max_correction_attempts,
            page_number=page_number,
            page_count=page_count,
            filename=file.filename
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Unexpected error: {error_trace}")
        
        raise HTTPException(
            status_code=500,
            detail=f"서버 내부 오류: {str(e)}"
        )
    
    finally:
        try:
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            
            if temp_image_path and os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
        except Exception as e:
            print(f"임시 파일 삭제 중 오류: {str(e)}")


async def _process_with_correction(
    temp_image_path: str,
    api_key: str,
    currency: str,
    unit: int,
    tolerance: float,
    max_correction_attempts: int,
    page_number: int,
    page_count: int,
    filename: str
) -> JSONResponse:
    """자가 교정 모드로 데이터 추출 및 검증"""
    try:
        parser = VisionParser(api_key=api_key, max_correction_attempts=max_correction_attempts)
        validator = FinancialValidator(tolerance=tolerance)
        
        # 자가 교정을 포함한 추출 수행
        extraction_result = parser.extract_and_validate_with_correction(
            image_path=temp_image_path,
            validator=validator,
            currency=currency,
            unit=unit
        )
        
        # 응답 생성
        response_data = {
            "success": True,
            "message": _get_result_message(extraction_result),
            "data": {
                "title": extraction_result.table.title,
                "headers": extraction_result.table.headers,
                "rows": extraction_result.table.rows,
                "currency": extraction_result.table.currency,
                "unit": extraction_result.table.unit
            },
            "metadata": {
                "page_number": page_number,
                "total_pages": page_count,
                "filename": filename
            },
            "is_valid": extraction_result.is_valid,
            "manual_review_required": extraction_result.manual_review_required,
            "self_correction": {
                "correction_attempts": extraction_result.correction_attempts,
                "correction_history": extraction_result.correction_history
            }
        }
        
        # 검증 오류가 있는 경우 추가
        if extraction_result.validation_errors:
            response_data["validation_errors"] = extraction_result.validation_errors
        
        return JSONResponse(content=response_data)
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"데이터 파싱 실패: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터 추출 중 오류 발생: {str(e)}")


async def _process_without_correction(
    temp_image_path: str,
    api_key: str,
    currency: str,
    unit: int,
    validate: bool,
    tolerance: float,
    page_number: int,
    page_count: int,
    filename: str
) -> JSONResponse:
    """일반 모드로 데이터 추출 및 검증"""
    try:
        parser = VisionParser(api_key=api_key)
        financial_table = parser.extract_table_from_image(
            image_path=temp_image_path,
            currency=currency,
            unit=unit
        )
        
        response_data = {
            "success": True,
            "message": "데이터 추출 완료",
            "data": {
                "title": financial_table.title,
                "headers": financial_table.headers,
                "rows": financial_table.rows,
                "currency": financial_table.currency,
                "unit": financial_table.unit
            },
            "metadata": {
                "page_number": page_number,
                "total_pages": page_count,
                "filename": filename
            }
        }
        
        if validate:
            validator = FinancialValidator(tolerance=tolerance)
            validation_result = validator.validate(financial_table)
            
            response_data["validation"] = {
                "is_valid": validation_result.is_valid,
                "errors": validation_result.errors,
                "report": validation_result.get_report()
            }
        
        return JSONResponse(content=response_data)
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"데이터 파싱 실패: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"표 데이터 추출 중 오류 발생: {str(e)}")


def _get_result_message(result: ExtractionResult) -> str:
    """결과에 따른 메시지 생성"""
    if result.is_valid:
        if result.correction_attempts == 0:
            return "데이터 추출 및 검증 완료 (1차 시도 성공)"
        else:
            return f"데이터 추출 및 검증 완료 (자가 교정 {result.correction_attempts}회 후 성공)"
    else:
        if result.manual_review_required:
            return f"⚠️ 검증 실패: {result.correction_attempts}회 자가 교정 후에도 오류가 남아있습니다. 수동 검토가 필요합니다."
        else:
            return "데이터 추출 완료 (검증 실패)"


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
