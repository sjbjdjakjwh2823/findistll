"""
FinDistill 로깅 설정 모듈

금융 데이터 보호를 위한 보안 로깅 기능을 제공합니다.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import json
import re

# .env 파일 로드
load_dotenv()


class SensitiveDataFilter(logging.Filter):
    """
    민감한 데이터를 마스킹하는 로그 필터
    """
    
    # 마스킹할 패턴들
    PATTERNS = [
        (r'api[_-]?key["\s:=]+["\']?([a-zA-Z0-9-_]+)["\']?', 'api_key="***MASKED***"'),
        (r'sk-[a-zA-Z0-9-_]+', '***API_KEY_MASKED***'),
        (r'\b\d{13,16}\b', '***CARD_NUMBER***'),  # 카드 번호
        (r'\b\d{3}-\d{2}-\d{4}\b', '***SSN***'),  # 주민번호 패턴
    ]
    
    def __init__(self, mask_enabled: bool = True):
        super().__init__()
        self.mask_enabled = mask_enabled
    
    def filter(self, record: logging.LogRecord) -> bool:
        if self.mask_enabled and hasattr(record, 'msg'):
            record.msg = self._mask_sensitive_data(str(record.msg))
        return True
    
    def _mask_sensitive_data(self, message: str) -> str:
        """민감한 데이터를 마스킹"""
        for pattern, replacement in self.PATTERNS:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        return message


class AuditLogger:
    """
    금융 데이터 감사 로그를 기록하는 클래스
    """
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or os.getenv("LOG_FILE", "logs/audit.log")
        self.enabled = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"
        
        if self.enabled:
            # 로그 디렉토리 생성
            log_dir = Path(self.log_file).parent
            log_dir.mkdir(parents=True, exist_ok=True)
    
    def log_extraction(
        self,
        filename: str,
        page_number: int,
        success: bool,
        rows_extracted: int = 0,
        validation_passed: bool = False,
        correction_attempts: int = 0,
        manual_review_required: bool = False,
        user_id: Optional[str] = None
    ):
        """데이터 추출 이벤트 로깅"""
        if not self.enabled:
            return
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "DATA_EXTRACTION",
            "filename": filename,
            "page_number": page_number,
            "success": success,
            "rows_extracted": rows_extracted,
            "validation_passed": validation_passed,
            "correction_attempts": correction_attempts,
            "manual_review_required": manual_review_required,
            "user_id": user_id or "anonymous"
        }
        
        self._write_log(event)
    
    def log_validation(
        self,
        table_title: str,
        is_valid: bool,
        error_count: int = 0,
        errors: list = None
    ):
        """검증 이벤트 로깅"""
        if not self.enabled:
            return
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "VALIDATION",
            "table_title": table_title,
            "is_valid": is_valid,
            "error_count": error_count,
            "errors": errors or []
        }
        
        self._write_log(event)
    
    def log_mcp_request(
        self,
        tool_name: str,
        arguments: dict,
        success: bool,
        error_message: Optional[str] = None
    ):
        """MCP 요청 로깅"""
        if not self.enabled:
            return
        
        # 민감한 정보 제거
        safe_args = {k: v for k, v in arguments.items() if k not in ['api_key', 'password']}
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "MCP_REQUEST",
            "tool_name": tool_name,
            "arguments": safe_args,
            "success": success,
            "error_message": error_message
        }
        
        self._write_log(event)
    
    def _write_log(self, event: dict):
        """로그 파일에 이벤트 기록"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"감사 로그 기록 실패: {e}")


def setup_logging(
    name: str = "findistill",
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    로깅 설정
    
    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로
        
    Returns:
        logging.Logger: 설정된 로거
    """
    # 환경변수에서 설정 로드
    level = level or os.getenv("LOG_LEVEL", "INFO")
    log_file = log_file or os.getenv("LOG_FILE", "logs/findistill.log")
    mask_enabled = os.getenv("MASK_SENSITIVE_DATA", "true").lower() == "true"
    
    # 로그 디렉토리 생성
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 기존 핸들러 제거
    logger.handlers = []
    
    # 포맷터 설정
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter(mask_enabled))
    logger.addHandler(console_handler)
    
    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SensitiveDataFilter(mask_enabled))
    logger.addHandler(file_handler)
    
    return logger


# 기본 로거 인스턴스
logger = setup_logging()
audit_logger = AuditLogger()
