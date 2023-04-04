import re
import os
import json
import base64
import pytesseract
from io import BytesIO
from PIL import Image
# from scrapers.utils import clean_string
# from scrapers.meta import Singleton
from utils import clean_string
from meta import Singleton


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

base64_regex_pattern = re.compile(r'^.+?(;base64),')
def base64_to_image(base64_string, mode='RGB'):
    base64_string = base64_regex_pattern.sub('', base64_string)
    img_data = base64.b64decode(base64_string)
    return Image.open(BytesIO(img_data)).convert(mode)

def image_to_base64(image: Image.Image):
    b64 = base64.b64encode(image.tobytes())
    return b64.decode('utf-8')

def crop_image_by_x_axis(image, start_x=-1, end_x=-1):
    if isinstance(image, str):
        image = base64_to_image(image)
    if start_x == -1:
        start_x = 0
    if end_x == -1:
        end_x = image.width
    return image.crop((start_x, 0, end_x, image.height))

def crop_image_by_y_axis(image, start_y=-1, end_y=-1):
    if isinstance(image, str):
        image = base64_to_image(image)
    if start_y == -1:
        start_y = 0
    if end_y == -1:
        end_y = image.height
    return image.crop((0, start_y, image.width, end_y))

def replace_transparent_background(image, color=(0, 0, 0)):
    if isinstance(image, str):
        image = base64_to_image(image, mode='RGBA')
        
    image = image.convert('RGBA')
    new_image = Image.new("RGBA", image.size, color)
    new_image.paste(image, (0, 0), image)
    return new_image

def put_center(image, color=(0,0,0), scale=1):
    if isinstance(image, str):
        image = base64_to_image(image, mode='RGBA')

    image = image.convert('RGBA')
    size = (image.width * scale, image.height * scale)
    background = Image.new('RGBA', size, color)
    background.paste(image, (int((size[0] - image.width) / 2), int((size[1] - image.height) / 2)), image)
    return background

class OCR(metaclass=Singleton):
    
    def __init__(self) -> None:
        self.engine = pytesseract.image_to_string
        self.cache = {}
    
    def ocr(self, image, lang, **kwargs) -> str:
        if isinstance(image, str):
            hash_key = image
            image = base64_to_image(image)
        else:
            hash_key = image_to_base64(image)
            
        if self.cache.get(hash_key) is not None:
            return self.cache[hash_key]
        res = clean_string(self.engine(image, lang=lang, **kwargs))
        self.cache[hash_key] = res
        return res

    def single_line_ocr(self, image, lang='eng', **kwargs) -> str:
        kwargs['config'] = '--psm 7 --oem 3'
        return self.ocr(image, lang, **kwargs)
    
    def multi_line_ocr(self, image, lang='eng', **kwargs) -> str:
        kwargs['config'] = '--psm 6 --oem 3'
        return self.ocr(image, lang, **kwargs)
    
    def single_character_ocr(self, image, lang='eng', **kwargs) -> str:
        kwargs['config'] = '--psm 10 --oem 3'
        return self.ocr(image, lang, **kwargs)

    def single_line_number_ocr(self, image, lang='eng', **kwargs) -> str:
        kwargs['config'] = '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789'
        return self.ocr(image, lang, **kwargs)
    
    def load_cache(self, path):
        if not os.path.exists(path):
            return 
        
        with open(path, 'r', encoding='utf8') as f:
            self.cache = json.load(f)

    def save_cache(self, path):
        with open(path, 'w', encoding='utf8') as f:
            self.cache = json.dump(self.cache, f)