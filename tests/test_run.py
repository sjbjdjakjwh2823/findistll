"""
FinDistill API 통합 테스트 스크립트

이 스크립트는 FastAPI 서버에 PDF 파일을 업로드하고
금융 데이터 추출 및 검증 결과를 확인합니다.
"""

import requests
import json
import os
import sys
from pathlib import Path
import time


# API 설정
API_BASE_URL = "http://localhost:8000"
EXTRACT_ENDPOINT = f"{API_BASE_URL}/extract"


def check_server_health():
    """서버 헬스 체크"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 서버가 정상적으로 실행 중입니다.")
            return True
        else:
            print(f"❌ 서버 응답 오류: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다.")
        print("   서버를 먼저 실행해주세요: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ 헬스 체크 실패: {str(e)}")
        return False


def test_extract_api(
    pdf_path: str,
    page_number: int = 0,
    currency: str = "KRW",
    unit: int = 1,
    validate: bool = True,
    tolerance: float = 0.01
):
    """
    /extract API 테스트
    
    Args:
        pdf_path: PDF 파일 경로
        page_number: 추출할 페이지 번호
        currency: 통화 단위
        unit: 금액 단위
        validate: 검증 수행 여부
        tolerance: 검증 허용 오차
    """
    print("\n" + "="*60)
    print("📄 PDF 파일 업로드 및 데이터 추출 테스트")
    print("="*60)
    
    # 파일 존재 확인
    if not os.path.exists(pdf_path):
        print(f"❌ PDF 파일을 찾을 수 없습니다: {pdf_path}")
        print("\n💡 샘플 PDF 파일을 준비해주세요.")
        return None
    
    print(f"\n📁 파일: {pdf_path}")
    print(f"📄 페이지: {page_number}")
    print(f"💱 통화: {currency}")
    print(f"📊 단위: {unit}")
    print(f"✓ 검증: {validate}")
    
    try:
        # PDF 파일 열기
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {
                'page_number': page_number,
                'currency': currency,
                'unit': unit,
                'validate': validate,
                'tolerance': tolerance
            }
            
            print("\n⏳ API 요청 중...")
            start_time = time.time()
            
            # API 호출
            response = requests.post(EXTRACT_ENDPOINT, files=files, data=data)
            
            elapsed_time = time.time() - start_time
            print(f"⏱️  소요 시간: {elapsed_time:.2f}초")
        
        # 응답 확인
        print(f"\n📡 응답 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ 데이터 추출 성공!")
            print_result(result)
            return result
        else:
            print(f"\n❌ API 오류 발생")
            print(f"상태 코드: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"오류 내용: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
            except:
                print(f"오류 내용: {response.text}")
            return None
    
    except requests.exceptions.ConnectionError:
        print("\n❌ 서버에 연결할 수 없습니다.")
        print("   서버가 실행 중인지 확인해주세요.")
        return None
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def print_result(result: dict):
    """결과를 보기 좋게 출력"""
    print("\n" + "-"*60)
    print("📊 추출된 데이터")
    print("-"*60)
    
    if result.get('success'):
        data = result.get('data', {})
        
        print(f"\n제목: {data.get('title', 'N/A')}")
        print(f"통화: {data.get('currency', 'N/A')}")
        print(f"단위: {data.get('unit', 'N/A')}")
        
        # 헤더 출력
        headers = data.get('headers', [])
        print(f"\n헤더 ({len(headers)}개):")
        print(f"  {headers}")
        
        # 행 데이터 출력
        rows = data.get('rows', [])
        print(f"\n데이터 ({len(rows)}행):")
        for idx, row in enumerate(rows):
            print(f"  행 {idx}: {row}")
        
        # 메타데이터 출력
        metadata = result.get('metadata', {})
        if metadata:
            print(f"\n메타데이터:")
            print(f"  파일명: {metadata.get('filename', 'N/A')}")
            print(f"  페이지: {metadata.get('page_number', 'N/A')} / {metadata.get('total_pages', 'N/A')}")
        
        # 검증 결과 출력
        validation = result.get('validation')
        if validation:
            print("\n" + "-"*60)
            print("🔍 검증 결과")
            print("-"*60)
            
            is_valid = validation.get('is_valid', False)
            if is_valid:
                print("\n✅ 모든 검증을 통과했습니다!")
            else:
                print("\n❌ 검증 실패")
                errors = validation.get('errors', [])
                print(f"\n오류 개수: {len(errors)}개")
                
                for idx, error in enumerate(errors, 1):
                    print(f"\n[오류 {idx}]")
                    print(f"  행 번호: {error.get('row_index', 'N/A')}")
                    print(f"  오류 유형: {error.get('error_type', 'N/A')}")
                    print(f"  메시지: {error.get('message', 'N/A')}")
                    
                    details = error.get('details', {})
                    if details:
                        print(f"  상세 정보:")
                        for key, value in details.items():
                            print(f"    - {key}: {value}")
            
            # 전체 리포트 출력
            report = validation.get('report', '')
            if report:
                print("\n" + "-"*60)
                print("📋 상세 리포트")
                print("-"*60)
                print(report)


def save_result_to_file(result: dict, output_path: str = "test_result.json"):
    """결과를 JSON 파일로 저장"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 결과가 저장되었습니다: {output_path}")
    except Exception as e:
        print(f"\n❌ 결과 저장 실패: {str(e)}")


def main():
    """메인 테스트 함수"""
    print("="*60)
    print("🚀 FinDistill API 통합 테스트")
    print("="*60)
    
    # 1. 서버 헬스 체크
    print("\n[1/3] 서버 헬스 체크")
    if not check_server_health():
        print("\n⚠️  서버를 먼저 실행해주세요:")
        print("   cd c:\\Users\\Administrator\\Desktop\\project_1")
        print("   uvicorn app.main:app --reload")
        sys.exit(1)
    
    # 2. OpenAI API 키 확인
    print("\n[2/3] 환경 변수 확인")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("\n설정 방법 (PowerShell):")
        print('   $env:OPENAI_API_KEY="your-api-key-here"')
        sys.exit(1)
    else:
        print(f"✅ OPENAI_API_KEY 설정됨 (길이: {len(api_key)})")
    
    # 3. PDF 파일 경로 설정
    print("\n[3/3] PDF 파일 테스트")
    
    # 현재 디렉토리에서 PDF 파일 찾기
    current_dir = Path.cwd()
    pdf_files = list(current_dir.glob("*.pdf"))
    
    if pdf_files:
        # 첫 번째 PDF 파일 사용
        pdf_path = str(pdf_files[0])
        print(f"✅ PDF 파일 발견: {pdf_path}")
    else:
        # 샘플 PDF 경로 (사용자가 직접 지정)
        print("\n⚠️  현재 디렉토리에 PDF 파일이 없습니다.")
        print("\nPDF 파일 경로를 입력하세요 (Enter를 누르면 종료):")
        pdf_path = input("> ").strip()
        
        if not pdf_path:
            print("\n💡 테스트를 위해 PDF 파일을 준비해주세요.")
            print("   예: financial_report.pdf")
            sys.exit(0)
    
    # API 테스트 실행
    result = test_extract_api(
        pdf_path=pdf_path,
        page_number=0,
        currency="KRW",
        unit=1,
        validate=True,
        tolerance=0.01
    )
    
    # 결과 저장
    if result:
        save_result_to_file(result, "test_result.json")
        print("\n" + "="*60)
        print("✅ 테스트 완료!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ 테스트 실패")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main()
