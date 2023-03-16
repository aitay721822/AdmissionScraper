import re
from typing import List, Tuple


"""
清理字串，將 u\xa0 跟 \n 換成空白，並且去除頭尾的空白，為了方便後續的處理
"""
def clean_string(s: str) -> str:
    return s.replace(u'\xa0', ' ').replace('\n', ' ').strip()

"""
將字串切割後，再將每個元素清理，並且去除空白的元素
"""
def clean_split(s: str, sep: str, cut: int=-1) -> List[str]:
    s = clean_string(s)
    
    res = []
    for x in s.split(sep, cut):
        x = clean_string(x)
        if x: res.append(x)
    return res

"""
將含有大學字串、科系字串的字串切割成大學字串、科系字串
"""
regex_school_department_pattern = re.compile(r"(.+(大學|學院|學校))\s*(.*)")
def split_school_department(s: str) -> Tuple[str, str]:
    s = clean_string(s)
    # 先嘗試能不能用正規表達式切割
    m = regex_school_department_pattern.findall(s)
    if len(m) > 0 and len(m[0]) == 3:
        # 切割成功
        return m[0][0], m[0][2]
    else:
        # fallback 成一般的切割
        return clean_split(s, ' ', 1)

"""
將含有大學ID字串、大學名稱的字串切割成大學ID、大學名稱
"""
regex_school_id_name_pattern = re.compile(r"(\d+)\s*(.+大學|學院|學校)")
def split_school_id_name(s: str) -> Tuple[str, str]:
    s = clean_string(s)
    m = regex_school_id_name_pattern.findall(s)
    if len(m) > 0 and len(m[0]) == 2:
        return m[0][0], m[0][1]
    else:
        # fallback 成一般的切割
        return clean_split(s, ' ', 1)    
    
if __name__ == '__main__':
    print(split_school_department("國立臺灣大學  資訊工程學系"))