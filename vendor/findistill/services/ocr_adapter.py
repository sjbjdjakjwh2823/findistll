import logging
from typing import List

logger = logging.getLogger(__name__)


def extract_text_from_images(images: List["Image.Image"]) -> str:
    """Run OCR on a list of PIL Images using best available engine."""
    if not images:
        return ""

    # Prefer PaddleOCR if available
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang="en")
        texts = []
        for img in images:
            result = ocr.ocr(img, cls=True)
            for line in result or []:
                if not line:
                    continue
                for item in line:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        text = item[1][0]
                        if text:
                            texts.append(text)
        return "\n".join(texts)
    except ModuleNotFoundError:
        # Paddle wheels are often unavailable depending on platform/python version.
        logger.info("PaddleOCR not available; falling back to pytesseract")
    except Exception as e:
        logger.warning("PaddleOCR failed: %s", e)

    # Fallback to pytesseract
    try:
        import pytesseract
        from PIL import ImageEnhance, ImageOps
        texts = []
        for img in images:
            # Light preprocessing to help OCR without heavy dependencies.
            try:
                proc = ImageOps.grayscale(img)
                proc = ImageEnhance.Contrast(proc).enhance(1.6)
                proc = proc.point(lambda p: 255 if p > 180 else 0)
            except Exception:
                proc = img

            text = pytesseract.image_to_string(proc, config="--oem 1 --psm 6")
            if text:
                texts.append(text)
        return "\n".join(texts)
    except Exception as e:
        logger.warning(f"pytesseract unavailable or failed: {e}")
        return ""
