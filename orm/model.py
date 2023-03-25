from sqlalchemy import Column, Integer, String, ForeignKey, create_engine, Index
from sqlalchemy.orm import relationship
from sqlalchemy.orm import validates
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# 榜單
class AdmissionList(Base):
    __tablename__ = 'AdmissionList'
    __table_args__ = (
        Index("idx_admission_list_id", "Id", unique=True),
        Index('idx_admission_list_year_method_school', 'Year', 'Method', 'SchoolDepartmentID'),
    )

    # 榜單ID
    id = Column('Id', Integer, primary_key=True, comment="榜單ID", autoincrement=True)
    
    # 學年度 (民國年) 
    year = Column('Year', Integer, comment="學年度 (民國年)", nullable=False)
    # 錄取方式
    method_id = Column('Method', Integer, ForeignKey('AdmissionType.Id'), comment="錄取方式的類型", nullable=False)
    # 校系ID
    school_department_id = Column('SchoolDepartmentID', Integer, ForeignKey('SchoolDepartment.Id'), nullable=False)
    
    # 平均錄取分數
    average_score = Column('AverageScore', String(20), comment="平均錄取分數", nullable=True)
    # 加權值
    weight = Column('Weight', String(20), comment="加權值", nullable=True)
    # 同分參酌
    same_grade_order = Column('SameGradeOrder', String(20), comment="同分參酌", nullable=True)
    # 一般生錄取分數
    general_grade = Column('GeneralGrade', String(20), comment="一般生錄取分數", nullable=True)
    # 原住民錄取分數
    native_grade = Column('NativeGrade', String(20), comment="原住民錄取分數", nullable=True)
    # 退伍軍人錄取分數
    veteran_grade = Column('VeteranGrade', String(20), comment="退伍軍人錄取分數", nullable=True)
    # 僑生錄取分數
    oversea_grade = Column('OverseaGrade', String(20), comment="僑生錄取分數", nullable=True)
    
    # 大學/科大個人申請(學測專用)
    university_apply = Column('UniversityApply', String(20), comment="大學/科大個人申請 (學測專用)", nullable=True)
    # 群組代碼 (統測專用)
    group_code = Column('GroupCode', String(20), comment="群組代碼 (統測專用)", nullable=True)
    
    # 一個榜單有很多人，一個人只會出現在一個榜單上 : 榜單->人 = 1->N
    admission_persons = relationship('AdmissionPerson', back_populates="admission_lists")
    # 一個榜單只會有一個錄取方式，一個錄取方式有很多榜單 : 錄取方式->榜單 = 1->N
    admission_type = relationship('AdmissionType', back_populates="admission_lists")
    # 一個榜單只會有一間校系，一間校系有很多榜單 : 校系->榜單 = 1->N
    school_department = relationship('SchoolDepartment', back_populates="admission_lists")
    
# 上榜單的人
class AdmissionPerson(Base):
    __tablename__ = 'AdmissionPerson'
    __table_args__ = (
        Index("idx_admission_person_id", "Id", unique=True),
        Index('idx_admission_person_listId_ticket', 'AdmissionListId', 'AdmissionTicket'),
    )
    
    # ID
    id = Column('Id', Integer, primary_key=True, comment="ID", autoincrement=True)
    # 榜單ID
    admission_list_id = Column('AdmissionListId', Integer, ForeignKey('AdmissionList.Id'), comment="榜單ID", nullable=False)
    # 准考證號碼
    admission_ticket = Column('AdmissionTicket', String(20), comment="准考證號碼", nullable=False)
    # 姓名
    name = Column('Name', String(20), comment="姓名", nullable=True)
    # 考區
    exam_area = Column('ExamArea', String(20), comment="考區", nullable=True)
    # 二階甄試狀態
    second_stage_status = Column('SecondStageStatus', String(20), comment="二階甄試狀態", nullable=True)
    # 錄取狀態
    admission_status = Column('AdmissionStatus', String(20), comment="錄取狀態", nullable=True)
    
    # 一個人有很多榜單，一個榜單只會有一個人 : 榜單->人 = 1->N
    admission_lists = relationship('AdmissionList', back_populates="admission_persons")
    
    @validates('admission_list_id', 'admission_ticket')
    def validate(self, key, value):
        if not value:
            raise ValueError(f'{key} value is empty')
        return value
    
    
# 錄取方式的類型 (分科/指考, 繁星, 學測, 統測甄選: 統測分發)
class AdmissionType(Base):
    __tablename__ = 'AdmissionType'
    __table_args__ = (
        Index("idx_admission_type_id", "Id", unique=True),
    )
    
    id = Column('Id', Integer, primary_key=True, comment="錄取方式的類型ID", autoincrement=True)
    name = Column('Name', String(20), comment="錄取方式的類型名稱", nullable=False)
    
    # 一個錄取方式有很多榜單，一個榜單只會有一個錄取方式 : 錄取方式->榜單 = 1->N
    admission_lists = relationship('AdmissionList', back_populates="admission_type")
    

# 學校系所
class SchoolDepartment(Base):
    __tablename__ = 'SchoolDepartment'
    __table_args__ = (
        Index("idx_school_department_id", "Id", unique=True),
        Index("idx_school_department_code", "SchoolCode", "DepartmentCode"),
    )
    
    id = Column('Id', Integer, primary_key=True, comment="校系ID", autoincrement=True)
    school_code = Column('SchoolCode', String(10), comment="學校代碼", nullable=False)
    depart_code = Column('DepartmentCode', String(10), comment="校系代碼", nullable=False)
    school_name = Column('SchoolName', String(50), comment="學校名稱", nullable=False)
    depart_name = Column('DepartmentName', String(50), comment="系所名稱", nullable=False)
    
    # 一個校系有很多榜單，一個榜單只會有一個校系 : 校系->榜單 = 1->N
    admission_lists = relationship('AdmissionList', back_populates="school_department")
    
    
if __name__ == '__main__':
    engine = create_engine('sqlite:///test.db', echo=True)
    Base.metadata.create_all(engine)