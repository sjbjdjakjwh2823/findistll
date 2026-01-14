"""
FinDistill MCP Server - Google Gemini Version

Model Context Protocol (MCP) 서버를 제공하여 외부 AI 에이전트(Cursor, Claude 등)가
문서 데이터 추출 기능을 호출할 수 있도록 합니다. Google Gemini AI를 사용합니다.

사용 예시:
    # MCP 서버 실행
    python -m core.mcp_server
    
    # 또는 직접 실행
    python core/mcp_server.py
"""

import os
import sys
import json
import tempfile
import base64
from pathlib import Path
from typing import Optional, Any
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .env 파일 로드
load_dotenv(project_root / ".env")

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from core.parser import VisionParser, ExtractionResult
from core.validator import FinancialValidator
from utils.pdf_processor import PDFProcessor
from utils.logging_config import setup_logging, audit_logger

# 로거 설정
logger = setup_logging("mcp_server")

# MCP 서버 초기화
server = Server(
    name=os.getenv("MCP_SERVER_NAME", "findistill"),
    version=os.getenv("MCP_SERVER_VERSION", "1.0.0")
)


def get_gemini_api_key() -> str:
    """Gemini API 키 가져오기"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your-gemini-api-key-here":
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 유효한 API 키를 설정해주세요. "
            "https://aistudio.google.com/app/apikey 에서 무료로 발급 가능합니다."
        )
    return api_key


@server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 MCP 도구 목록 반환"""
    return [
        Tool(
            name="extract_financial_table",
            description="""PDF 파일에서 금융 표 데이터를 추출합니다.
            
이 도구는 다음 기능을 제공합니다:
- PDF에서 금융 표(재무제표, 대차대조표, 손익계산서 등) 추출
- 숫자 데이터 자동 정제 (콤마 제거, float 변환)
- 회계 수식 검증 (자산=부채+자본, 매출-원가=이익)
- 검증 실패 시 자가 교정 (최대 2회 재시도)
- 수동 검토 필요 여부 플래그 제공

사용 예시:
- "이 PDF에서 재무제표 뽑아줘"
- "대차대조표 데이터 추출해줘"
- "손익계산서 숫자 검증해줘"
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_base64": {
                        "type": "string",
                        "description": "Base64로 인코딩된 PDF 파일 데이터"
                    },
                    "pdf_path": {
                        "type": "string",
                        "description": "PDF 파일 경로 (로컬 파일인 경우)"
                    },
                    "page_number": {
                        "type": "integer",
                        "description": "추출할 페이지 번호 (0부터 시작, 기본값: 0)",
                        "default": 0
                    },
                    "currency": {
                        "type": "string",
                        "description": "통화 단위 (기본값: KRW)",
                        "default": "KRW"
                    },
                    "unit": {
                        "type": "integer",
                        "description": "금액 단위 (예: 1, 1000, 1000000, 기본값: 1)",
                        "default": 1
                    },
                    "auto_correct": {
                        "type": "boolean",
                        "description": "자가 교정 활성화 (기본값: true)",
                        "default": True
                    },
                    "max_correction_attempts": {
                        "type": "integer",
                        "description": "최대 자가 교정 시도 횟수 (기본값: 2)",
                        "default": 2
                    },
                    "tolerance": {
                        "type": "number",
                        "description": "검증 허용 오차 (기본값: 0.01)",
                        "default": 0.01
                    }
                },
                "oneOf": [
                    {"required": ["pdf_base64"]},
                    {"required": ["pdf_path"]}
                ]
            }
        ),
        Tool(
            name="validate_financial_table",
            description="""금융 표 데이터의 회계 수식을 검증합니다.

지원하는 검증 규칙:
- 대차대조표: 자산 = 부채 + 자본
- 손익계산서: 매출 - 원가 = 이익

검증 결과로 각 행의 오류 정보와 상세 리포트를 제공합니다.
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "표 제목"
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "테이블 헤더 목록"
                    },
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {}
                        },
                        "description": "테이블 행 데이터"
                    },
                    "currency": {
                        "type": "string",
                        "description": "통화 단위",
                        "default": "KRW"
                    },
                    "unit": {
                        "type": "integer",
                        "description": "금액 단위",
                        "default": 1
                    },
                    "tolerance": {
                        "type": "number",
                        "description": "검증 허용 오차 (기본값: 0.01)",
                        "default": 0.01
                    }
                },
                "required": ["title", "headers", "rows"]
            }
        ),
        Tool(
            name="get_pdf_info",
            description="PDF 파일의 기본 정보(페이지 수 등)를 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pdf_base64": {
                        "type": "string",
                        "description": "Base64로 인코딩된 PDF 파일 데이터"
                    },
                    "pdf_path": {
                        "type": "string",
                        "description": "PDF 파일 경로"
                    }
                },
                "oneOf": [
                    {"required": ["pdf_base64"]},
                    {"required": ["pdf_path"]}
                ]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """MCP 도구 호출 처리"""
    logger.info(f"🔧 MCP Tool 호출: {name}")
    
    try:
        if name == "extract_financial_table":
            result = await _extract_financial_table(arguments)
        elif name == "validate_financial_table":
            result = await _validate_financial_table(arguments)
        elif name == "get_pdf_info":
            result = await _get_pdf_info(arguments)
        else:
            result = {"error": f"알 수 없는 도구: {name}"}
        
        # 감사 로그 기록
        audit_logger.log_mcp_request(
            tool_name=name,
            arguments=arguments,
            success="error" not in result,
            error_message=result.get("error")
        )
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, ensure_ascii=False)
        )]
        
    except Exception as e:
        logger.error(f"❌ MCP Tool 오류: {name} - {str(e)}")
        
        # 감사 로그 기록
        audit_logger.log_mcp_request(
            tool_name=name,
            arguments=arguments,
            success=False,
            error_message=str(e)
        )
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "tool": name
            }, indent=2, ensure_ascii=False)
        )]


async def _extract_financial_table(arguments: dict) -> dict:
    """금융 표 데이터 추출"""
    temp_pdf_path = None
    temp_image_path = None
    
    try:
        # API 키 확인
        api_key = get_gemini_api_key()
        
        # PDF 파일 처리
        if "pdf_base64" in arguments:
            # Base64 데이터에서 PDF 생성
            pdf_data = base64.b64decode(arguments["pdf_base64"])
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
                f.write(pdf_data)
                temp_pdf_path = f.name
        elif "pdf_path" in arguments:
            temp_pdf_path = arguments["pdf_path"]
            if not os.path.exists(temp_pdf_path):
                return {"error": f"PDF 파일을 찾을 수 없습니다: {temp_pdf_path}"}
        else:
            return {"error": "pdf_base64 또는 pdf_path가 필요합니다."}
        
        # 파라미터 추출
        page_number = arguments.get("page_number", 0)
        currency = arguments.get("currency", "KRW")
        unit = arguments.get("unit", 1)
        auto_correct = arguments.get("auto_correct", True)
        max_correction_attempts = arguments.get("max_correction_attempts", 2)
        tolerance = arguments.get("tolerance", 0.01)
        
        # PDF를 이미지로 변환
        pdf_processor = PDFProcessor(dpi=300)
        page_count = pdf_processor.get_pdf_page_count(temp_pdf_path)
        
        if page_number < 0 or page_number >= page_count:
            return {
                "error": f"페이지 번호가 범위를 벗어났습니다. 유효 범위: 0-{page_count - 1}"
            }
        
        temp_image_path = pdf_processor.pdf_page_to_image(temp_pdf_path, page_num=page_number)
        
        # VisionParser 초기화
        parser = VisionParser(api_key=api_key, max_correction_attempts=max_correction_attempts)
        validator = FinancialValidator(tolerance=tolerance)
        
        if auto_correct:
            # 자가 교정 모드
            extraction_result = parser.extract_and_validate_with_correction(
                image_path=temp_image_path,
                validator=validator,
                currency=currency,
                unit=unit
            )
            
            result = {
                "success": True,
                "data": {
                    "title": extraction_result.table.title,
                    "headers": extraction_result.table.headers,
                    "rows": extraction_result.table.rows,
                    "currency": extraction_result.table.currency,
                    "unit": extraction_result.table.unit
                },
                "metadata": {
                    "page_number": page_number,
                    "total_pages": page_count
                },
                "is_valid": extraction_result.is_valid,
                "manual_review_required": extraction_result.manual_review_required,
                "self_correction": {
                    "correction_attempts": extraction_result.correction_attempts,
                    "correction_history": extraction_result.correction_history
                }
            }
            
            if extraction_result.validation_errors:
                result["validation_errors"] = extraction_result.validation_errors
            
            # 감사 로그
            audit_logger.log_extraction(
                filename=arguments.get("pdf_path", "uploaded.pdf"),
                page_number=page_number,
                success=True,
                rows_extracted=len(extraction_result.table.rows),
                validation_passed=extraction_result.is_valid,
                correction_attempts=extraction_result.correction_attempts,
                manual_review_required=extraction_result.manual_review_required
            )
            
        else:
            # 일반 모드
            financial_table = parser.extract_table_from_image(
                image_path=temp_image_path,
                currency=currency,
                unit=unit
            )
            
            validation_result = validator.validate(financial_table)
            
            result = {
                "success": True,
                "data": {
                    "title": financial_table.title,
                    "headers": financial_table.headers,
                    "rows": financial_table.rows,
                    "currency": financial_table.currency,
                    "unit": financial_table.unit
                },
                "metadata": {
                    "page_number": page_number,
                    "total_pages": page_count
                },
                "validation": {
                    "is_valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "report": validation_result.get_report()
                }
            }
            
            # 감사 로그
            audit_logger.log_extraction(
                filename=arguments.get("pdf_path", "uploaded.pdf"),
                page_number=page_number,
                success=True,
                rows_extracted=len(financial_table.rows),
                validation_passed=validation_result.is_valid
            )
        
        logger.info(f"✅ 금융 표 추출 완료: {len(result['data']['rows'])}개 행")
        return result
        
    except Exception as e:
        logger.error(f"❌ 추출 오류: {str(e)}")
        return {"error": str(e)}
    
    finally:
        # 임시 파일 정리
        if temp_pdf_path and "pdf_base64" in arguments and os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)
        if temp_image_path and os.path.exists(temp_image_path):
            os.unlink(temp_image_path)


async def _validate_financial_table(arguments: dict) -> dict:
    """금융 표 데이터 검증"""
    try:
        from models.schemas import FinancialTable
        
        # FinancialTable 생성
        table = FinancialTable(
            title=arguments.get("title", ""),
            headers=arguments["headers"],
            rows=arguments["rows"],
            currency=arguments.get("currency", "KRW"),
            unit=arguments.get("unit", 1)
        )
        
        # 검증 수행
        tolerance = arguments.get("tolerance", 0.01)
        validator = FinancialValidator(tolerance=tolerance)
        validation_result = validator.validate(table)
        
        # 감사 로그
        audit_logger.log_validation(
            table_title=table.title,
            is_valid=validation_result.is_valid,
            error_count=len(validation_result.errors),
            errors=validation_result.errors
        )
        
        logger.info(f"✅ 검증 완료: {'통과' if validation_result.is_valid else '실패'}")
        
        return {
            "success": True,
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "report": validation_result.get_report()
        }
        
    except Exception as e:
        logger.error(f"❌ 검증 오류: {str(e)}")
        return {"error": str(e)}


async def _get_pdf_info(arguments: dict) -> dict:
    """PDF 파일 정보 조회"""
    temp_pdf_path = None
    
    try:
        # PDF 파일 처리
        if "pdf_base64" in arguments:
            pdf_data = base64.b64decode(arguments["pdf_base64"])
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as f:
                f.write(pdf_data)
                temp_pdf_path = f.name
        elif "pdf_path" in arguments:
            temp_pdf_path = arguments["pdf_path"]
            if not os.path.exists(temp_pdf_path):
                return {"error": f"PDF 파일을 찾을 수 없습니다: {temp_pdf_path}"}
        else:
            return {"error": "pdf_base64 또는 pdf_path가 필요합니다."}
        
        # PDF 정보 추출
        pdf_processor = PDFProcessor()
        page_count = pdf_processor.get_pdf_page_count(temp_pdf_path)
        
        logger.info(f"✅ PDF 정보 조회: {page_count}페이지")
        
        return {
            "success": True,
            "page_count": page_count
        }
        
    except Exception as e:
        logger.error(f"❌ PDF 정보 조회 오류: {str(e)}")
        return {"error": str(e)}
    
    finally:
        if temp_pdf_path and "pdf_base64" in arguments and os.path.exists(temp_pdf_path):
            os.unlink(temp_pdf_path)


async def run_server():
    """MCP 서버 실행"""
    logger.info("🚀 FinDistill MCP Server 시작")
    logger.info(f"   서버 이름: {os.getenv('MCP_SERVER_NAME', 'findistill')}")
    logger.info(f"   버전: {os.getenv('MCP_SERVER_VERSION', '1.0.0')}")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_server())
