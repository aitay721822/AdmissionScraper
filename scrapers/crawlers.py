

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
        self.logger.info('開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'爬取學校列表成功, 共計 {len(university_result)} 所學校')
            self.logger.debug(f'[Exam] University Info: {university_result}')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', ExamDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Exam] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        self.logger.debug(f'[Exam] Department Info: {department}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', ExamAdmissionListParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('爬取科系列表失敗')
        else:
            self.logger.info('爬取學校列表失敗')
    
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
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_name == university.school_name, 
                                                            SchoolDepartment.depart_name == department.department_name).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_name == university.school_name,
                                                                SchoolDepartment.depart_name == department.department_name).first()
            # Step 3. 存入榜單資訊
            adimssionlist = AdmissionList(
                year=year,
                method_id=method.id,
                school_department_id=department.department_id,
                average_score=department.admission_score,
                weight=department.admission_weights,
                same_grade_order=admissions.order,
                general_grade=admissions.general_grade,
                native_grade=admissions.native_grade,
                veteran_grade=admissions.veteran_grade,
                oversea_grade=admissions.oversea_grade,
            )
            session.add(adimssionlist)
            session.commit()
            # Step 4. 存入上榜資訊
            for admission in admissions.admission_list:
                session.add(AdmissionPerson(
                    admission_list_id=adimssionlist.id,
                    admission_ticket=admission.ticket,
                    exam_area=admission.exam_area,
                    admission_status='已錄取',
                ))
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
        self.logger.info('開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'爬取學校列表成功, 共計 {len(university_result)} 所學校')
            self.logger.debug(f'[Star] University Info: {university_result}')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', StarDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Star] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        self.logger.debug(f'[Star] Department Info: {department}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', StarAdmissionListParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('爬取科系列表失敗')
        else:
            self.logger.info('爬取學校列表失敗')
    
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
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_name == university.school_name, 
                                                            SchoolDepartment.depart_name == department.department_name).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_name == university.school_name,
                                                                SchoolDepartment.depart_name == department.department_name).first()
            # Step 3. 存入榜單資訊
            adimssionlist = AdmissionList(
                year=year,
                method_id=method.id,
                school_department_id=department.department_id,
            )
            session.add(adimssionlist)
            session.commit()
            # Step 4. 存入上榜資訊
            for admission in admissions:
                session.add(AdmissionPerson(
                    admission_list_id=adimssionlist.id,
                    admission_ticket=admission.ticket,
                    exam_area=admission.exam_area,
                    admission_status='已錄取',
                ))
            session.commit()
            
class CrossCrawler(Crawler):
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)
        
        self.university_list_url = 'https://www.com.tw/cross/university_list{year}.html'
        self.department_list_url = 'https://www.com.tw/cross/university_{school_id}_{year}.html'
        
        self.admission_url = 'https://www.com.tw/cross/check_{school_department_id}_NO_0_{year}_0_3.html'
        self.admission_tech_url = 'https://www.com.tw/cross/check_{school_department_id}_NO_0_{year}_0_3.html'
    
    def init_parsers(self) -> None:
        self.parsers.update({
            'university': UniversityListParser(),
            'department': CrossDepartmentListParser(),
            'admission': CrossAdmissionListParser(),
        })
    
    def crawl(self, year: str):
        # 爬取學校列表
        self.logger.info('開始爬取學校列表')
        university_list_html = self.client.get(self.university_list_url.format(year=year))
        university_parser = self.get_parser('university', UniversityListParser)
        university_result = university_parser.parse(university_list_html)
        if university_result:
            self.logger.info(f'爬取學校列表成功, 共計 {len(university_result)} 所學校')
            self.logger.debug(f'[Cross] University Info: {university_result}')
            
            # 爬取各個學校的科系列表
            for university in university_result:
                self.logger.info(f'開始爬取 {university.school_name} 的科系列表')
                
                department_list_html = self.client.get(self.department_list_url.format(school_id=university.school_id, year=year))
                department_parser = self.get_parser('department', CrossDepartmentListParser)
                department_result = department_parser.parse(department_list_html)
                if department_result:
                    self.logger.info(f'爬取 {university.school_name} 的科系列表成功, 共計 {len(department_result)} 個科系')
                    
                    for department in department_result:
                        self.logger.info(f'[Cross] 現在爬取學校科系: {university.school_name} {department.department_name} 年度: {year}')
                        self.logger.debug(f'[Cross] Department Info: {department}')
                        
                        # 爬取各個科系的榜單
                        admission_html = self.client.get(self.admission_url.format(school_department_id=department.department_id, year=year))
                        admission_parser = self.get_parser('admission', CrossAdmissionListParser)
                        admission_result = admission_parser.parse(admission_html)
                        if admission_result:
                            # 存入資料庫
                            self.save(year, university, department, admission_result)
                else:
                    self.logger.info('爬取科系列表失敗')
        else:
            self.logger.info('爬取學校列表失敗')
    
    def save(self, year: str, university: SchoolModel, department: CrossDepartmentModel, admissions: List[CrossAdmissionModel]):
        with Session(self.db) as session:
            # Step1. 找到入學管道的 id
            method = session.query(AdmissionType).filter(AdmissionType.name == '大學繁星').first()
            if not method:
                # 如果沒有大學繁星的入學管道, 則新增一個
                session.add(AdmissionType(name='大學繁星'))
                session.commit()
                method = session.query(AdmissionType).filter(AdmissionType.name == '大學繁星').first()
            # Step2. 找到學校的 id
            school = session.query(SchoolDepartment).filter(SchoolDepartment.school_name == university.school_name, 
                                                            SchoolDepartment.depart_name == department.department_name).first()
            if not school:
                # 如果沒有該學校與校系, 則新增一個
                session.add(SchoolDepartment(school_name=university.school_name, 
                                             depart_name=department.department_name,
                                             school_code=university.school_id,
                                             depart_code=department.department_id))
                session.commit()
                school = session.query(SchoolDepartment).filter(SchoolDepartment.school_name == university.school_name,
                                                                SchoolDepartment.depart_name == department.department_name).first()
            # Step 3. 存入榜單資訊
            adimssionlist = AdmissionList(
                year=year,
                method_id=method.id,
                school_department_id=department.department_id,
                university_apply=
            )
            session.add(adimssionlist)
            session.commit()
            # Step 4. 存入上榜資訊
            for admission in admissions:
                session.add(AdmissionPerson(
                    admission_list_id=adimssionlist.id,
                    admission_ticket=admission.ticket,
                    exam_area=admission.exam_area,
                    admission_status='已錄取',
                ))
            session.commit()

        
class VtechCrawler(Crawler):
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)
        
class TechregCrawler(Crawler):
    def __init__(self, config: AppConfig, db: Engine) -> None:
        super().__init__(config, db)    
            
if __name__ == '__main__':
    crawler = ExamCrawler()
    crawler.crawl('111')