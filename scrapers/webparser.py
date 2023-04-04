from typing import Any, Dict, List
from bs4 import BeautifulSoup
from scrapers.ocr import *
from scrapers.model import *
from scrapers.utils import *
from scrapers.meta import Singleton
# from model import *
# from ocr import *
# from utils import *
# from meta import Singleton


class Parser():
    """
    Parser is an abstract class that defines the interface for all parsers.
    All parsers must implement the parse method.
    
    Functions:
        - parse: parse the html content and return model
    """
    def parse(self, html_content: str):
        raise NotImplementedError

class AvailableYearsParser(Parser):
    """
    從首頁 `https://www.com.tw/` 解析出可用的學年度
    """
    def __init__(self):
        self.admission_method = {
            '分科測驗': 'exam',
            '大學繁星': 'star',
            '學測查榜': 'cross',
            '統測甄選': 'vtech',
            '統測分發': 'techreg',
        }
        
    def parse(self, html_content: str) -> List[AvailableYearsModel]:
        available_years = []
        resp = BeautifulSoup(html_content, 'lxml')
        for nav_element in resp.select('ul.navigation > li'):
            nav_text = clean_string(nav_element.select_one('a').text)
            
            if nav_text in self.admission_method:
                available = []
                # 取得第一個 li 元素
                nav_element = nav_element.find_next('li')
                # 如果有下一個 li 元素，就繼續迴圈
                while nav_element:
                    # 取得 學年度的 HTML 元素以及文字
                    year_text = clean_string(nav_element.select_one('a').text)
                    # 取前三位數字，例如 109 學年度取 109
                    available.append(year_text[:3])
                    nav_element = nav_element.find_next_sibling('li')
                
                available_years.append(AvailableYearsModel(
                    method=self.admission_method[nav_text],
                    method_name=nav_text,
                    available_years=available
                ))
        return available_years

class UniversityListParser(Parser):
    """
    從大學列表頁面(類似於`https://www.com.tw/exam/university_list111.html`)解析出大學列表
    """
    def parse(self, html_content: str) -> List[SchoolModel]:
        schools = []
        resp = BeautifulSoup(html_content, 'lxml')
        table = resp.find('table', id='table1')
        row = table.find_next('tr')
        while row:
            item_elemets = row.find_all('td')
            if len(item_elemets) % 2 == 0:
                for i in range(0, len(item_elemets), 2):
                    # 放榜狀態元素
                    release_element = item_elemets[i].find_all('div')
                    # 放榜狀態 (release 跟 part 不會同時出現)
                    full_release, part_release = clean_string(release_element[0].text), clean_string(release_element[1].text)
                    release_status = full_release if full_release else part_release
                    # 放榜日期
                    release_date = ''
                    if len(release_element) >= 3 and release_element[2].get('id') == 'releasedate':
                        release_date = clean_string(release_element[2].text)
                    # 學校資訊元素
                    school_element = item_elemets[i+1]
                    school_href = school_element.find_next('a').get('href')
                    school_code, school_name = split_school_id_name(school_element.text)
                    schools.append(SchoolModel(
                        release_status,
                        release_date,
                        school_code,
                        school_name,
                        school_href
                    ))
            row = row.find_next_sibling('tr')
            
        return schools

class ExamDepartmentListParser(Parser):
    def parse(self, html_content: str) -> List[ExamDepartmentModel]:
        departments = []
        resp = BeautifulSoup(html_content, 'lxml')
        table = resp.find('table', id='table1')
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('div', id='university_dep_row_height')
            if item_elements and len(item_elements) == 5:
                department_id = clean_string(item_elements[0].text).strip('()')
                department_name = clean_string(item_elements[1].text)
                admission_href = clean_string(item_elements[2].select_one('a').get('href'))
                admission_score = clean_string(item_elements[3].text.strip())
                admission_weights = clean_string(item_elements[4].select_one('img').get('title'))
                departments.append(ExamDepartmentModel(
                    department_id=department_id,
                    department_name=department_name,
                    admission_href=admission_href,
                    admission_score=admission_score,
                    admission_weights=admission_weights
                ))
            row = row.find_next_sibling('tr')
        return departments

class ExamAdmissionListParser(Parser):
    def parse(self, html_content: str) -> ExamAdmissionDetailModel:
        def parse_info(table_element):
            result = {}
            info_row = table_element.find_next('tr')
            i = 0
            while info_row:
                if i == 1:
                    # 加權值
                    weights_element = info_row.find_all('td')
                    result['weights'] = clean_string(weights_element[-1].text)
                elif i == 2:
                    # 一般生
                    general_element = info_row.find_all('td')
                    # 把成績跟同分參酌順序取出來
                    grade_order = clean_string(general_element[-1].text)
                    grade_order = clean_split(grade_order, ' ', 1)
                    result['general_grade'] = grade_order[0]
                    result['order'] = grade_order[-1]
                elif i == 3:
                    # 原住民
                    native_element = info_row.find_all('td')
                    result['native_grade'] = clean_string(native_element[-1].text)
                elif i == 4:
                    # 退伍軍人
                    verteran_element = info_row.find_all('td')
                    result['veteran_grade'] = clean_string(verteran_element[-1].text)
                elif i == 5:
                    # 僑生
                    oversea_grade = info_row.find_all('td')
                    result['oversea_grade'] = clean_string(oversea_grade[-1].text)
                info_row = info_row.find_next_sibling('tr')
                i += 1
            return result

        resp = BeautifulSoup(html_content, 'lxml')
        main_content = resp.find('div', id='mainContent')
        # 先取得加權值以及平均分數
        info_table = main_content.find_next('table')
        info = parse_info(info_table)
        # 取得榜單項目
        admissions = [] 
        table = info_table.find_next_sibling('table')
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('td', recursive=False)
            if item_elements and len(item_elements) == 5:
                ticket_examarea = clean_split(item_elements[2].text, ' ', -1)
                school, depart = split_school_department(item_elements[4].text)
                admissions.append(ExamAdmissionModel(
                    ticket=ticket_examarea[0],
                    exam_area=ticket_examarea[-1],
                    school_name=school,
                    school_depart=depart,
                ))
            row = row.find_next_sibling('tr')
        return ExamAdmissionDetailModel(
            weights=info['weights'],
            order=info['order'],
            general_grade=info['general_grade'],
            native_grade=info['native_grade'],
            veteran_grade=info['veteran_grade'],
            oversea_grade=info['oversea_grade'],
            admission_list=admissions
        )

class StarDepartmentListParser(Parser):
    def parse(self, html_content: str) -> List[StarDepartmentModel]:
        departments = []
        resp = BeautifulSoup(html_content, 'lxml')
        table = resp.find('table', id='table1')
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('div', id='university_dep_row_height')
            if item_elements and len(item_elements) == 5:
                department_id = clean_string(item_elements[0].text).strip("()")
                department_name = clean_string(item_elements[1].text)
                admission_href = clean_string(item_elements[2].select_one('a').get('href'))
                departments.append(StarDepartmentModel(
                    department_id=department_id,
                    department_name=department_name,
                    admission_href=admission_href,
                ))
            row = row.find_next_sibling('tr')
        return departments

class StarAdmissionListParser(Parser):
    def parse(self, html_content: str) -> List[StarAdmissionModel]:
        resp = BeautifulSoup(html_content, 'lxml')
        main_content = resp.find('div', id='mainContent')
        # 取得榜單項目
        admissions = [] 
        table = main_content.find_next('table')
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('td', recursive=False)
            if item_elements and len(item_elements) == 5:
                ticket_examarea = clean_split(item_elements[2].text, ' ', -1)
                school, depart = split_school_department(item_elements[4].text)
                admissions.append(StarAdmissionModel(
                    ticket=ticket_examarea[0],
                    exam_area=ticket_examarea[-1],
                    school_name=school,
                    school_depart=depart,
                ))
            row = row.find_next_sibling('tr')
        return admissions

class CrossDepartmentListParser(Parser):
    def parse(self, html_content: str) -> List[CrossDepartmentModel]:
        departments = []
        resp = BeautifulSoup(html_content, 'lxml')
        table = resp.find('table', id='table1')
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('td', id='university_dep_row_height')
            if item_elements and len(item_elements) == 5:
                department_id = clean_string(item_elements[0].text).strip("()")
                department_name = clean_string(item_elements[1].text)
                admission_href = clean_string(item_elements[2].select_one('a').get('href'))
                release_status = clean_string(item_elements[4].text)
                departments.append(CrossDepartmentModel(
                    department_id=department_id,
                    department_name=department_name,
                    admission_href=admission_href,
                    release_status=release_status,
                ))
            row = row.find_next_sibling('tr')
        return departments
    
class CrossAdmissionListParser(Parser):
    def parse(self, html_content: str) -> List[CrossAdmissionModel]:
        adminssion = []
        # ocr object
        ocr_obj = OCR()
        
        resp = BeautifulSoup(html_content, 'lxml')
        main_content = resp.find('div', id='mainContent')
        # 取得榜單項目
        table = main_content.find('table', recursive=False)
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('td', recursive=False)
            if item_elements and len(item_elements) == 5:
                
                # 准考證號碼、考區
                ticket_examarea_element = item_elements[2]
                ticket = clean_string(ocr_obj.single_line_number_ocr(ticket_examarea_element.select_one('img').get('src')))
                examarea = clean_split(ticket_examarea_element.select_one('a').text, ':')[-1]

                # 名稱 OCR (準確度不高)
                # name = ''
                name = ''
                name_element = item_elements[3]
                match_img_pattern = '<img.*?/>'
                match_star_pattern = '(?:>)([*])(?:<)'
                imgs = [m.end() for m in re.finditer(match_img_pattern, str(name_element))]
                star = [m.end() for m in re.finditer(match_star_pattern, str(name_element))]
                if imgs and star:
                    star_position = star[0]
                    image_element = name_element.find_next('img')
                    for img_position in imgs:
                        if img_position > star_position:
                            name += '*'
                        image = put_center(image_element.get('src'), (255,255,255), scale=2)
                        name += clean_string(ocr_obj.single_character_ocr(image, lang='chi_tra'))
                        image_element = image_element.find_next_sibling('img')
                    if star_position > imgs[-1]:
                        name += '*'
                else:
                    name = '*'

                # 學校錄取情況
                school_admission_status = []
                school_depart_element = item_elements[4].find_next('table')
                school_row = school_depart_element.find_next('tr')
                while school_row:
                    school_item_elements = school_row.find_all('td', recursive=False)
                    if school_item_elements and len(school_item_elements) == 3:
                        # 檢查是否分發錄取
                        is_admission = True if school_item_elements[0].find('img', {'title': '分發錄取'}) else False
                        # 學校、科系
                        school_depart_text = clean_string(school_item_elements[1].select_one('a').text)
                        if school_depart_text:
                            school, depart = split_school_department(school_depart_text)
                            # 二階甄試
                            release_status_element = school_item_elements[2].select_one('img')
                            release_date = clean_string(school_item_elements[2].select_one('div.retestdate').text)
                            if release_status_element:
                                if len(release_status_element.parent.get('class')) == 0:
                                    admit = False
                                    release_status = '未錄取'
                                else:
                                    prefix_string = clean_string(school_item_elements[2].text)
                                    admit = clean_string(release_status_element.parent.get('class')[0]) == 'leftred'
                                    release_img = release_status_element.get('src')
                                    release_img = crop_image_by_x_axis(release_img, start_x=45)
                                    release_img = replace_transparent_background(release_img)
                                    release_status = clean_string(ocr_obj.single_line_number_ocr(release_img))
                                    release_status = '正取' if admit else '備取' + release_status
                                    release_status = prefix_string + release_status
                            else:
                                release_status = '' if not release_date else release_date
                            school_admission_status.append(SchoolAdmissionStatusModel(
                                is_admission,
                                school,
                                depart,
                                release_status
                            ))
                    school_row = school_row.find_next_sibling('tr')
                adminssion.append(CrossAdmissionModel(
                    ticket,
                    examarea,
                    name,
                    school_admission_status
                ))
            row = row.find_next_sibling('tr')
        return adminssion
    
class VtechDepartmentListParser(Parser):
    def parse(self, html_content: str) -> List[VtechDepartmentModel]:
        departments = []
        resp = BeautifulSoup(html_content, 'lxml')
        table = resp.find('table', id='table1')
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('td', id='university_dep_row_height')
            if item_elements and len(item_elements) == 5:
                department_id = clean_string(item_elements[0].text).strip("()")
                department_name = clean_string(item_elements[1].text)
                admission_href = clean_string(item_elements[2].select_one('a').get('href'))
                group = clean_string(item_elements[3].text)
                departments.append(VtechDepartmentModel(
                    department_id=department_id,
                    department_name=department_name,
                    admission_href=admission_href,
                    group=group,
                ))
            row = row.find_next_sibling('tr')
        return departments

class VtechAdmissionParser(Parser):
    def parse(self, html_content: str) -> List[VtechAdmissionModel]:
        adminssion = []
        
        # ocr object
        ocr_obj = OCR()
        
        resp = BeautifulSoup(html_content, 'lxml')
        main_content = resp.find('div', id='mainContent')
        # 取得榜單項目
        table = main_content.find('table', recursive=False)
        row = table.find_next('tr')
        while row:
            item_elements = row.find_all('td', recursive=False)
            if item_elements and len(item_elements) == 5:
                # 准考證號碼
                ticket_examarea_element = item_elements[2]
                ticket = clean_string(ocr_obj.single_line_number_ocr(ticket_examarea_element.select_one('img').get('src')))

                # 名稱 OCR (準確度不高)
                # name = ''
                name = ''
                name_element = item_elements[3]
                match_img_pattern = '<img.*?/>'
                match_star_pattern = '(?:>)([*])(?:<)'
                imgs = [m.end() for m in re.finditer(match_img_pattern, str(name_element))]
                star = [m.end() for m in re.finditer(match_star_pattern, str(name_element))]
                if imgs and star:
                    star_position = star[0]
                    image_element = name_element.find_next('img')
                    for img_position in imgs:
                        if img_position > star_position:
                            name += '*'
                        image = put_center(image_element.get('src'), (255,255,255), scale=2)
                        name += clean_string(ocr_obj.single_character_ocr(image, lang='chi_tra'))
                        image_element = image_element.find_next_sibling('img')
                    if star_position > imgs[-1]:
                        name += '*'
                else:
                    name = '*'
                
                # 學校錄取情況
                school_admission_status = []
                school_depart_element = item_elements[4].find_next('table')
                school_row = school_depart_element.find_next('tr')
                while school_row:
                    school_item_elements = school_row.find_all('td', recursive=False)
                    if school_item_elements and len(school_item_elements) == 3:
                        # 檢查是否分發錄取
                        is_admission = True if school_item_elements[0].find('img', {'title': '分發錄取'}) else False
                        # 學校、科系
                        school_depart_text = clean_string(school_item_elements[1].select_one('a').text)
                        if school_depart_text:
                            school, depart = split_school_department(school_depart_text)
                            # 二階甄試
                            release_status_element = school_item_elements[2].select_one('img')
                            release_date = clean_string(school_item_elements[2].select_one('div.retestdate').text)
                            if release_status_element:
                                if len(release_status_element.parent.get('class')) == 0:
                                    admit = False
                                    release_status = '未錄取'
                                else:
                                    prefix_string = clean_string(school_item_elements[2].text)
                                    admit = clean_string(release_status_element.parent.get('class')[0]) == 'leftred'
                                    release_img = release_status_element.get('src')
                                    release_img = crop_image_by_x_axis(release_img, start_x=45)
                                    release_img = replace_transparent_background(release_img)
                                    release_status = clean_string(ocr_obj.single_line_number_ocr(release_img))
                                    release_status = '正取' if admit else '備取' + release_status
                                    release_status = prefix_string + release_status
                            else:
                                release_status = '' if not release_date else release_date
                            school_admission_status.append(SchoolAdmissionStatusModel(
                                is_admission,
                                school,
                                depart,
                                release_status
                            ))
                    school_row = school_row.find_next_sibling('tr')
                adminssion.append(VtechAdmissionModel(
                    ticket,
                    name,
                    school_admission_status
                ))
            row = row.find_next_sibling('tr')
        return adminssion
    
class TechregDepartmentParser(Parser):
    def parse(self, html_content: str) -> List[TechregDepartmentModel]:
        departments = []
        resp = BeautifulSoup(html_content, 'lxml')
        table = resp.find('table', id='table1')
        row = table.find_next('tr')
        while row:
            item_elemets = row.find_all('td', id='university_dep_row_height')
            if len(item_elemets) == 5:
                department_id = clean_string(item_elemets[0].text).strip("()")
                department_name = clean_string(item_elemets[1].text)
                admission_href = clean_string(item_elemets[2].select_one('a').get('href'))
                group = clean_string(item_elemets[3].text)
                average_score = clean_string(item_elemets[4].text)
                departments.append(TechregDepartmentModel(
                    department_id=department_id,
                    department_name=department_name,
                    admission_href=admission_href,
                    group=group,
                    average_score=average_score,
                ))
            row = row.find_next_sibling('tr')
        return departments

class TechregAdmissionParser(Parser):
    def parse(self, html_content: str) -> TechregAdmissionDetailModel:
        def parse_info(table_element):
            result = {}
            info_row = table_element.find_next('tr')
            i = 0
            while info_row:
                grade_element = info_row.find_all('td')
                if len(grade_element) == 4:
                    if i == 1:
                        # 一般生
                        result['general_grade'] = clean_string(grade_element[1].text)
                    elif i == 2:
                        # 原住民
                        result['native_grade'] = clean_string(grade_element[1].text)
                    elif i == 3:
                        # 退伍軍人
                        result['veteran_grade'] = clean_string(grade_element[1].text)
                    elif i == 4:
                        # 僑生
                        result['oversea_grade'] = clean_string(grade_element[1].text)
                info_row = info_row.find_next_sibling('tr')
                i += 1
            return result

        resp = BeautifulSoup(html_content, 'lxml')
        main_content = resp.find('div', id='mainContent')
        # 先取得平均分數
        info_table = main_content.find_next('table')
        info = parse_info(info_table)
        # 取得榜單項目
        admissions = [] 
        table = info_table.find_next_sibling('table')
        row = table.find_next('tr')
        while row:
            item_elemets = row.find_all('td', recursive=False)
            if len(item_elemets) == 3:
                ticket, name = clean_split(item_elemets[2].text, ' ', 1)
                admissions.append(TechregAdmissionModel(
                    ticket=ticket,
                    name=name,
                ))
            row = row.find_next_sibling('tr')
        return TechregAdmissionDetailModel(
            general_grade=info['general_grade'],
            native_grade=info['native_grade'],
            veteran_grade=info['veteran_grade'],
            oversea_grade=info['oversea_grade'],
            admission_list=admissions
        )

if __name__ == '__main__':
    import os
    print(os.getcwd())
    pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    with open(os.path.join(os.getcwd(), 'scrapers\\resources\\vtech_test.html'), 'r', encoding='utf-8') as f:
        html_content = f.read()
        result = VtechAdmissionParser().parse(html_content)
        try:
            print(*result, sep='\n')
        except:
            print(result)