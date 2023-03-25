

import logging
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from typing import List
from orm.model import *
from scrapers.webparser import *
from conf import AppConfig
from scrapers.client import Client

class Crawler:
    """
    Crawler is an abstract class that defines the interface for all crawlers.
    All parsers must implement the parse method.
    
    Functions:
        - crawl: process crawling logic, and save the crawled data to the database
        - init_parsers: initialize parsers to the crawler
        - get_parser: get a parser by name
    """
    def __init__(self, config: AppConfig, db: Engine) -> None:
        self.logger = logging.getLogger('crawler')
        
        self.db = db
        self.client = Client.get_instance(config.flaresolverr)
        self.parsers = {} 
        self.init_parsers()
    
    def init_parsers(self) -> None:
        self.parsers = {}
    
    def get_parser(self, name: str, parser_type):
        if name not in self.parsers:
            raise KeyError(f'Parser {name} not found')
        
        parser = self.parsers.get(name)
        if not isinstance(parser, parser_type):
            raise ValueError(f'Parser {name} is not a {parser_type.__name__}')
        return parser

    def crawl(self, year: str):
        raise NotImplementedError
    
class ExamCrawler(Crawler):
    
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)
        
        self.university_list_url = 'https://www.com.tw/exam/university_list{year}.html'
        self.department_list_url = 'https://www.com.tw/exam/university_{school_id}_{year}.html'
        self.admission_url = 'https://www.com.tw/exam/check_{school_department_id}_NO_0_{year}_0_3.html'
    
    def init_parsers(self) -> None:
        self.parsers.update({
            'university': UniversityListParser(),
            'department': ExamDepartmentListParser(),
            'admission': ExamAdmissionListParser(),
        })
    
    def crawl(self, year: str):
        # 爬取學校列表
        self.logger.info('[Exam] 開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'[Exam] 爬取學校列表成功, 共計 {len(university_result)} 所學校')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'[Exam] 開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', ExamDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'[Exam] 爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Exam] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', ExamAdmissionListParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('[Exam] 爬取科系列表失敗')
        else:
            self.logger.info('[Exam] 爬取學校列表失敗')
    
    def save(self, year: str, university: SchoolModel, department: ExamDepartmentModel, admissions: ExamAdmissionDetailModel):
        with Session(self.db) as session:
            # Step1. 找到入學管道的 id
            method = session.query(AdmissionType).filter(AdmissionType.name == '分科測驗').first()
            if not method:
                # 如果沒有分科測驗的入學管道, 則新增一個
                session.add(AdmissionType(name='分科測驗'))
                session.commit()
                method = session.query(AdmissionType).filter(AdmissionType.name == '分科測驗').first()
            # Step2. 找到學校的 id
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                            SchoolDepartment.depart_code == department.department_id).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                                SchoolDepartment.depart_code == department.department_id).first()
            # Step 3. 存入榜單資訊
            admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                 AdmissionList.method_id == method.id,
                                                                 AdmissionList.school_department_id == school.id).first()
            if not admission_info:
                session.add(AdmissionList(
                    year=year,
                    method_id=method.id,
                    school_department_id=school.id,
                    average_score=department.admission_score,
                    weight=department.admission_weights,
                    same_grade_order=admissions.order,
                    general_grade=admissions.general_grade,
                    native_grade=admissions.native_grade,
                    veteran_grade=admissions.veteran_grade,
                    oversea_grade=admissions.oversea_grade,
                ))
                session.commit()
                admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                     AdmissionList.method_id == method.id,
                                                                     AdmissionList.school_department_id == school.id).first()
            else:
                session.query(AdmissionList).filter(AdmissionList.id == admission_info.id).update({
                    AdmissionList.year: year,
                    AdmissionList.method_id: method.id,
                    AdmissionList.school_department_id: school.id,
                    AdmissionList.average_score: department.admission_score,
                    AdmissionList.weight: department.admission_weights,
                    AdmissionList.same_grade_order: admissions.order,
                    AdmissionList.general_grade: admissions.general_grade,
                    AdmissionList.native_grade: admissions.native_grade,
                    AdmissionList.veteran_grade: admissions.veteran_grade,
                    AdmissionList.oversea_grade: admissions.oversea_grade,
                })
                session.commit()
                
            # Step 4. 存入上榜資訊
            for admission in admissions.admission_list:
                person = session.query(AdmissionPerson).filter(AdmissionPerson.admission_list_id == admission_info.id,
                                                               AdmissionPerson.admission_ticket == admission.ticket).first()
                if not person:
                    try:
                        session.add(AdmissionPerson(
                            admission_list_id=admission_info.id,
                            admission_ticket=admission.ticket,
                            exam_area=admission.exam_area,
                            admission_status='已錄取',
                        ))
                    except ValueError as e:
                        self.logger.warning('[Exam] 存入錄取資訊失敗, 原因: {}, 可能是欄位錯誤'.format(e))
                else:
                    session.query(AdmissionPerson).filter(AdmissionPerson.id == person.id).update({
                        AdmissionPerson.admission_list_id: admission_info.id,
                        AdmissionPerson.admission_ticket: admission.ticket,
                        AdmissionPerson.exam_area: admission.exam_area,
                        AdmissionPerson.admission_status: '已錄取',
                    })
            session.commit()

class StarCrawler(Crawler):
    
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)
        
        self.university_list_url = 'https://www.com.tw/star/university_list{year}.html'
        self.department_list_url = 'https://www.com.tw/star/university_{school_id}_{year}.html'
        self.admission_url = 'https://www.com.tw/star/check_{school_department_id}_NO_0_{year}_0_3.html'
    
    def init_parsers(self) -> None:
        self.parsers.update({
            'university': UniversityListParser(),
            'department': StarDepartmentListParser(),
            'admission': StarAdmissionListParser(),
        })
    
    def crawl(self, year: str):
        # 爬取學校列表
        self.logger.info('[Star] 開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'[Star] 爬取學校列表成功, 共計 {len(university_result)} 所學校')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'[Star] 開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', StarDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'[Star] 爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Star] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', StarAdmissionListParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('[Star] 爬取科系列表失敗')
        else:
            self.logger.info('[Star] 爬取學校列表失敗')
    
    def save(self, year: str, university: SchoolModel, department: StarDepartmentModel, admissions: List[StarAdmissionModel]):
        with Session(self.db) as session:
            # Step1. 找到入學管道的 id
            method = session.query(AdmissionType).filter(AdmissionType.name == '大學繁星').first()
            if not method:
                # 如果沒有大學繁星的入學管道, 則新增一個
                session.add(AdmissionType(name='大學繁星'))
                session.commit()
                method = session.query(AdmissionType).filter(AdmissionType.name == '大學繁星').first()
            # Step2. 找到學校的 id
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                            SchoolDepartment.depart_code == department.department_id).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                                SchoolDepartment.depart_code == department.department_id).first()
            # Step 3. 存入榜單資訊
            admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                 AdmissionList.method_id == method.id,
                                                                 AdmissionList.school_department_id == school.id).first()
            if not admission_info:
                session.add(AdmissionList(
                    year=year,
                    method_id=method.id,
                    school_department_id=school.id,
                ))
                session.commit()
                admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                     AdmissionList.method_id == method.id,
                                                                     AdmissionList.school_department_id == school.id).first()
            else:
                session.query(AdmissionList).filter(AdmissionList.id == admission_info.id).update({
                    AdmissionList.year: year,
                    AdmissionList.method_id: method.id,
                    AdmissionList.school_department_id: school.id,
                })
                session.commit()
            # Step 4. 存入上榜資訊
            for admission in admissions:
                person = session.query(AdmissionPerson).filter(AdmissionPerson.admission_list_id == admission_info.id,
                                                               AdmissionPerson.admission_ticket == admission.ticket).first()
                if not person:
                    try:
                        session.add(AdmissionPerson(
                            admission_list_id=admission_info.id,
                            admission_ticket=admission.ticket,
                            exam_area=admission.exam_area,
                            admission_status='已錄取',
                        ))
                    except ValueError as e:
                        self.logger.warning('[Star] 存入錄取資訊失敗, 原因: {}, 可能是欄位錯誤'.format(e))
                else:
                    session.query(AdmissionPerson).filter(AdmissionPerson.id == person.id).update({
                        AdmissionPerson.admission_list_id: admission_info.id,
                        AdmissionPerson.admission_ticket: admission.ticket,
                        AdmissionPerson.exam_area: admission.exam_area,
                        AdmissionPerson.admission_status: '已錄取',
                    })
            session.commit()
            
class CrossCrawler(Crawler):
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)
        
        self.university_list_url = 'https://www.com.tw/cross/university_list{year}.html'
        self.university_tech_list_url = 'https://www.com.tw/cross/tech_university_list{year}.html'
        
        self.department_list_url = 'https://www.com.tw/cross/university_{school_id}_{year}.html'
        self.department_tech_list_url = 'https://www.com.tw/cross/university_1{school_id}_{year}.html'
        
        self.admission_url = 'https://www.com.tw/cross/check_{school_department_id}_NO_1_{year}_0_0.html'
        self.admission_tech_url = 'https://www.com.tw/cross/check_1{school_department_id}_NO_1_{year}_1_1.html'
    
    def init_parsers(self) -> None:
        self.parsers.update({
            'university': UniversityListParser(),
            'department': CrossDepartmentListParser(),
            'admission': CrossAdmissionListParser(),
        })
    
    def crawl(self, year: str):
        # 爬取普通大學的榜單
        self.logger.info('[Cross] 開始爬取普大個人申請學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'[Cross] 爬取普大學校列表成功, 共計 {len(university_result)} 所學校')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'[Cross] 開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', CrossDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'[Cross] 爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Cross] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', CrossAdmissionListParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result, False)
                else:
                    self.logger.info('[Cross] 爬取普大科系列表失敗')
        else:
            self.logger.info('[Cross] 爬取普大學校列表失敗')
            
        # 爬取科技大學的榜單
        self.logger.info('[Cross] 開始爬取科技大學個人申請學校列表')
        tech_list_html = self.client.get(self.university_tech_list_url.format(year=year))
        tech_result = university_parser.parse(tech_list_html)
        if tech_result:
            self.logger.info(f'[Cross] 爬取科技大學列表成功, 共計 {len(tech_result)} 所學校')
            
            for university in tech_result:
                self.logger.info(f'[Cross] 開始爬取 {university.school_name} 的科系列表')
                
                tech_department_list_html = self.client.get(self.department_tech_list_url.format(school_id=university.school_id, year=year))
                tech_department_result = department_parser.parse(tech_department_list_html)
                if tech_department_result:
                    self.logger.info(f'[Cross] 爬取 {university.school_name} 的科系列表成功, 共計 {len(tech_department_result)} 個科系')
                    
                    for department in tech_department_result:
                        self.logger.info(f'[Cross] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        
                        admission_html = self.client.get(self.admission_tech_url.format(school_department_id=department.department_id, year=year))
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            self.save(year, university, department, admission_result, True)
                else:
                    self.logger.info('[Cross] 爬取科技大學科系列表失敗')
        else:
            self.logger.info('[Cross] 爬取科技大學學校列表失敗')
        
    
    def save(self, year: str, university: SchoolModel, department: CrossDepartmentModel, admissions: List[CrossAdmissionModel], is_tech_university: bool = False):
        with Session(self.db) as session:
            # Step1. 找到入學管道的 id
            method = session.query(AdmissionType).filter(AdmissionType.name == '學測查榜').first()
            if not method:
                # 如果沒有學測查榜的入學管道, 則新增一個
                session.add(AdmissionType(name='學測查榜'))
                session.commit()
                method = session.query(AdmissionType).filter(AdmissionType.name == '學測查榜').first()
            # Step2. 找到學校的 id
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                            SchoolDepartment.depart_code == department.department_id).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                                SchoolDepartment.depart_code == department.department_id).first()
            # Step 3. 存入榜單資訊
            admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                 AdmissionList.method_id == method.id,
                                                                 AdmissionList.school_department_id == school.id).first()
            if not admission_info:
                session.add(AdmissionList(
                    year=year,
                    method_id=method.id,
                    school_department_id=school.id,
                    university_apply='大學個人申請' if not is_tech_university else '科大四技申請'
                ))
                session.commit()
                admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                     AdmissionList.method_id == method.id,
                                                                     AdmissionList.school_department_id == school.id).first()
            else:
                session.query(AdmissionList).filter(AdmissionList.id == admission_info.id).update({
                    AdmissionList.year: year,
                    AdmissionList.method_id: method.id,
                    AdmissionList.school_department_id: school.id,
                    AdmissionList.university_apply: '大學個人申請' if not is_tech_university else '科大四技申請',
                })
                session.commit()
                
            # Step 4. 存入上榜資訊
            for admission in admissions:
                for school in admission.schools:
                    if school.school_name == university.school_name and school.department_name == department.department_name:
                        person = session.query(AdmissionPerson).filter(AdmissionPerson.admission_list_id == admission_info.id,
                                                                        AdmissionPerson.admission_ticket == admission.ticket).first()
                        if not person:
                            try:
                                session.add(AdmissionPerson(
                                    admission_list_id=admission_info.id,
                                    admission_ticket=admission.ticket,
                                    exam_area=admission.exam_area,
                                    admission_status=school.status,
                                ))
                            except ValueError as e:
                                self.logger.warning('[Cross] 存入錄取資訊失敗, 原因: {}, 可能是欄位錯誤'.format(e))
                        else:
                            session.query(AdmissionPerson).filter(AdmissionPerson.id == person.id).update({
                                AdmissionPerson.admission_list_id: admission_info.id,
                                AdmissionPerson.admission_ticket: admission.ticket,
                                AdmissionPerson.exam_area: admission.exam_area,
                                AdmissionPerson.admission_status: school.status,
                            })
            session.commit()

class VtechCrawler(Crawler):
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)
        
        self.university_list_url = 'https://www.com.tw/vtech/university_list{year}.html'
        self.department_list_url = 'https://www.com.tw/vtech/university_{school_id}_{year}.html'
        self.admission_url = 'https://www.com.tw/vtech/check_{school_department_id}_NO_1_{year}_1_3.html'
    
    def init_parsers(self) -> None:
        self.parsers.update({
            'university': UniversityListParser(),
            'department': VtechDepartmentListParser(),
            'admission': VtechAdmissionParser(),
        })
    
    def crawl(self, year: str):
        self.logger.info('[Vtech] 開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'[Vtech] 爬取學校列表成功, 共計 {len(university_result)} 所學校')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'[Vtech] 開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', VtechDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'[Vtech] 爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Vtech] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', VtechAdmissionParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('[Vtech] 爬取科系列表失敗')
        else:
            self.logger.info('[Vtech] 爬取學校列表失敗')
            
    def save(self, year: str, university: SchoolModel, department: VtechDepartmentModel, admissions: List[VtechAdmissionModel]):
        with Session(self.db) as session:
            # Step1. 找到入學管道的 id
            method = session.query(AdmissionType).filter(AdmissionType.name == '統測甄選').first()
            if not method:
                # 如果沒有統測甄選的入學管道, 則新增一個
                session.add(AdmissionType(name='統測甄選'))
                session.commit()
                method = session.query(AdmissionType).filter(AdmissionType.name == '統測甄選').first()
            # Step2. 找到學校的 id
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                            SchoolDepartment.depart_code == department.department_id).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                                SchoolDepartment.depart_code == department.department_id).first()
            # Step 3. 存入榜單資訊
            admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                 AdmissionList.method_id == method.id,
                                                                 AdmissionList.school_department_id == school.id).first()
            if not admission_info:
                session.add(AdmissionList(
                    year=year,
                    method_id=method.id,
                    school_department_id=school.id,
                    group_code=department.group,
                ))
                session.commit()
                admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                     AdmissionList.method_id == method.id,
                                                                     AdmissionList.school_department_id == school.id).first()
            else:
                session.query(AdmissionList).filter(AdmissionList.id == admission_info.id).update({
                    AdmissionList.year: year,
                    AdmissionList.method_id: method.id,
                    AdmissionList.school_department_id: school.id,
                    AdmissionList.group_code: department.group,
                })
                session.commit()
                
            # Step 4. 存入上榜資訊
            for admission in admissions:
                for school in admission.schools:
                    if school.school_name == university.school_name and school.department_name == department.department_name:
                        person = session.query(AdmissionPerson).filter(AdmissionPerson.admission_list_id == admission_info.id,
                                                                        AdmissionPerson.admission_ticket == admission.ticket).first()
                        if not person:
                            try:
                                session.add(AdmissionPerson(
                                    admission_list_id=admission_info.id,
                                    admission_ticket=admission.ticket,
                                    admission_status=school.status,
                                    second_stage_status=school.status,
                                ))
                            except ValueError as e:
                                self.logger.warning('[Vtech] 存入錄取資訊失敗, 原因: {}, 可能是欄位錯誤'.format(e))
                        else:
                            session.query(AdmissionPerson).filter(AdmissionPerson.id == person.id).update({
                                AdmissionPerson.admission_list_id: admission_info.id,
                                AdmissionPerson.admission_ticket: admission.ticket,
                                AdmissionPerson.admission_status: school.status,
                                AdmissionPerson.second_stage_status: school.status,
                            })
            session.commit()

        
class TechregCrawler(Crawler):
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)    
        
        self.university_list_url = 'https://www.com.tw/techreg/university_list{year}.html'
        self.department_list_url = 'https://www.com.tw/techreg/university_{school_id}_{year}.html'
        self.admission_url = 'https://www.com.tw/techreg/check_{school_department_id}_{year}.html'

    def init_parsers(self) -> None:
        self.parsers.update({
            'university': UniversityListParser(),
            'department': TechregDepartmentParser(),
            'admission': TechregAdmissionParser(),
        })
    
    def crawl(self, year: str):
        self.logger.info('[Techreg] 開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'[Techreg] 爬取學校列表成功, 共計 {len(university_result)} 所學校')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'[Techreg] 開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', TechregDepartmentParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'[Techreg] 爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Techreg] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', TechregAdmissionParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('[Techreg] 爬取科系列表失敗')
        else:
            self.logger.info('[Techreg] 爬取學校列表失敗')
            
    def save(self, year: str, university: SchoolModel, department: TechregDepartmentModel, admissions: TechregAdmissionDetailModel):
        with Session(self.db) as session:
            # Step1. 找到入學管道的 id
            method = session.query(AdmissionType).filter(AdmissionType.name == '統測分發').first()
            if not method:
                # 如果沒有統測分發的入學管道, 則新增一個
                session.add(AdmissionType(name='統測分發'))
                session.commit()
                method = session.query(AdmissionType).filter(AdmissionType.name == '統測分發').first()
            # Step2. 找到學校的 id
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                            SchoolDepartment.depart_code == department.department_id).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_code == university.school_id, 
                                                                SchoolDepartment.depart_code == department.department_id).first()
            # Step 3. 存入榜單資訊
            admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                 AdmissionList.method_id == method.id,
                                                                 AdmissionList.school_department_id == school.id).first()
            if not admission_info:
                session.add(AdmissionList(
                    year=year,
                    method_id=method.id,
                    school_department_id=school.id,
                    group_code=department.group,
                    average_score=department.average_score,
                    general_grade=admissions.general_grade,
                    native_grade=admissions.native_grade,
                    veteran_grade=admissions.veteran_grade,
                    oversea_grade=admissions.oversea_grade,
                ))
                session.commit()
                admission_info = session.query(AdmissionList).filter(AdmissionList.year == year,
                                                                     AdmissionList.method_id == method.id,
                                                                     AdmissionList.school_department_id == school.id).first()
            else:
                session.query(AdmissionList).filter(AdmissionList.id == admission_info.id).update({
                    AdmissionList.year: year,
                    AdmissionList.method_id: method.id,
                    AdmissionList.school_department_id: school.id,
                    AdmissionList.group_code: department.group,
                    AdmissionList.average_score: department.average_score,
                    AdmissionList.general_grade: admissions.general_grade,
                    AdmissionList.native_grade: admissions.native_grade,
                    AdmissionList.veteran_grade: admissions.veteran_grade,
                    AdmissionList.oversea_grade: admissions.oversea_grade,
                })
                session.commit()
                
            # Step 4. 存入上榜資訊
            for admission in admissions.admission_list:
                person = session.query(AdmissionPerson).filter(AdmissionPerson.admission_list_id == admission_info.id,
                                                               AdmissionPerson.admission_ticket == admission.ticket).first()
                if not person:
                    try:
                        session.add(AdmissionPerson(
                            admission_list_id=admission_info.id,
                            admission_ticket=admission.ticket,
                            admission_status='已錄取',
                        ))
                    except ValueError as e:
                        self.logger.warning('[Techreg] 存入錄取資訊失敗, 原因: {}, 可能是欄位錯誤'.format(e))
                else:
                    session.query(AdmissionPerson).filter(AdmissionPerson.id == person.id).update({
                        AdmissionPerson.admission_list_id: admission_info.id,
                        AdmissionPerson.admission_ticket: admission.ticket,
                        AdmissionPerson.admission_status: '已錄取',
                    })
            session.commit()