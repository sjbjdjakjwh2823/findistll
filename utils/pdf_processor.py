import fitz  # PyMuPDF
from PIL import Image
from typing import List, Optional
import io
import os
from pathlib import Path


class PDFProcessor:
    """
    PDF 파일을 이미지로 변환하는 유틸리티 클래스
    """
    
    def __init__(self, dpi: int = 300):
        """
        PDFProcessor 초기화
        
        Args:
            dpi: 이미지 해상도 (기본값: 300)
        """
        self.dpi = dpi
        self.zoom = dpi / 72  # PDF 기본 해상도는 72 DPI
    
    def pdf_to_images(
        self, 
        pdf_path: str, 
        output_dir: Optional[str] = None,
        image_format: str = "png"
    ) -> List[str]:
        """
        PDF 파일의 모든 페이지를 이미지로 변환
        
        Args:
            pdf_path: PDF 파일 경로
            output_dir: 출력 디렉토리 (None인 경우 PDF와 같은 디렉토리)
            image_format: 이미지 포맷 (png, jpg 등)
            
        Returns:
            List[str]: 생성된 이미지 파일 경로 리스트
            
        Raises:
            FileNotFoundError: PDF 파일이 존재하지 않는 경우
            Exception: PDF 변환 실패 시
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        # 출력 디렉토리 설정
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path)
        
        os.makedirs(output_dir, exist_ok=True)
        
        image_paths = []
        
        try:
            # PDF 문서 열기
            pdf_document = fitz.open(pdf_path)
            
            # 각 페이지를 이미지로 변환
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # 페이지를 이미지로 렌더링
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # 이미지 저장
                base_name = Path(pdf_path).stem
                image_path = os.path.join(
                    output_dir, 
                    f"{base_name}_page_{page_num + 1}.{image_format}"
                )
                
                pix.save(image_path)
                image_paths.append(image_path)
            
            pdf_document.close()
            
            return image_paths
        
        except Exception as e:
            raise Exception(f"PDF를 이미지로 변환하는 중 오류 발생: {str(e)}")
    
    def pdf_page_to_image(
        self, 
        pdf_path: str, 
        page_num: int = 0,
        output_path: Optional[str] = None
    ) -> str:
        """
        PDF의 특정 페이지를 이미지로 변환
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (0부터 시작)
            output_path: 출력 파일 경로 (None인 경우 자동 생성)
            
        Returns:
            str: 생성된 이미지 파일 경로
            
        Raises:
            FileNotFoundError: PDF 파일이 존재하지 않는 경우
            IndexError: 페이지 번호가 범위를 벗어난 경우
            Exception: PDF 변환 실패 시
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        try:
            # PDF 문서 열기
            pdf_document = fitz.open(pdf_path)
            
            # 페이지 번호 유효성 검사
            if page_num < 0 or page_num >= len(pdf_document):
                raise IndexError(
                    f"페이지 번호가 범위를 벗어났습니다. "
                    f"유효 범위: 0-{len(pdf_document) - 1}, 입력값: {page_num}"
                )
            
            # 페이지를 이미지로 렌더링
            page = pdf_document[page_num]
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 출력 경로 설정
            if output_path is None:
                base_name = Path(pdf_path).stem
                output_dir = os.path.dirname(pdf_path)
                output_path = os.path.join(
                    output_dir, 
                    f"{base_name}_page_{page_num + 1}.png"
                )
            
            # 이미지 저장
            pix.save(output_path)
            pdf_document.close()
            
            return output_path
        
        except Exception as e:
            raise Exception(f"PDF 페이지를 이미지로 변환하는 중 오류 발생: {str(e)}")
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        """
        PDF의 총 페이지 수 반환
        
        Args:
            pdf_path: PDF 파일 경로
            
        Returns:
            int: 페이지 수
            
        Raises:
            FileNotFoundError: PDF 파일이 존재하지 않는 경우
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        try:
            pdf_document = fitz.open(pdf_path)
            page_count = len(pdf_document)
            pdf_document.close()
            return page_count
        except Exception as e:
            raise Exception(f"PDF 페이지 수를 가져오는 중 오류 발생: {str(e)}")
