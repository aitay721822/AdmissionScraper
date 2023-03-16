from io import BytesIO
import re
from PIL import Image
import pytesseract
import base64

"""
Here is Mini Doc for pytesseract

Lang: 
    - eng (English)
    - chi_sim (Chinese Simplified)
    - chi_tra (Chinese Traditional)
    
Page Segmentation Mode (PSM):
  0    Orientation and script detection (OSD) only.
  1    Automatic page segmentation with OSD.
  2    Automatic page segmentation, but no OSD, or OCR. (not implemented)
  3    Fully automatic page segmentation, but no OSD. (Default)
  4    Assume a single column of text of variable sizes.
  5    Assume a single uniform block of vertically aligned text.
  6    Assume a single uniform block of text.
  7    Treat the image as a single text line.
  8    Treat the image as a single word.
  9    Treat the image as a single word in a circle.
 10    Treat the image as a single character.
 11    Sparse text. Find as much text as possible in no particular order.
 12    Sparse text with OSD.
 13    Raw line. Treat the image as a single text line,
       bypassing hacks that are Tesseract-specific.

OCR Engine Mode (OEM):
  0    Legacy engine only.
  1    Neural nets LSTM engine only.
  2    Legacy + LSTM engines.
  3    Default, based on what is available.
"""

pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
base64_regex_pattern = re.compile(r'^.+?(;base64),')

def base64_to_image(base64_string):
    base64_string = base64_regex_pattern.sub('', base64_string)
    img_data = base64.b64decode(base64_string)
    return Image.open(BytesIO(img_data))

def image_to_text(image, lang='eng', config='--psm 3 --oem 3'):
    return pytesseract.image_to_string(image, lang, config)

def base64_to_text(base64_string, lang='eng', config='--psm 3 --oem 3'):
    return pytesseract.image_to_string(base64_to_image(base64_string), lang, config)

def single_line_ocr(image, lang):
    if isinstance(image, str):
        image = base64_to_image(image)
    return pytesseract.image_to_string(image, lang, config='--psm 7 --oem 3')

def multi_line_ocr(image, lang):
    if isinstance(image, str):
        image = base64_to_image(image)
    return pytesseract.image_to_string(image, lang, config='--psm 6 --oem 3')