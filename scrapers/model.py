from dataclasses import dataclass
from typing import List


@dataclass
class AvailableYearsModel:
    method: str
    method_name: str
    available_years: List[str]
    
@dataclass
class SchoolModel:
    release_status: str
    release_date: str
    school_id: str
    school_name: str
    school_href: str

@dataclass
class ExamDepartmentModel:
    department_id: str
    department_name: str
    admission_href: str
    admission_score: str
    admission_weights: str

@dataclass
class ExamAdmissionModel:
    ticket: str
    exam_area: str
    school_name: str
    school_depart: str

@dataclass
class ExamAdmissionDetailModel:
    weights: str
    order: str
    general_grade: str
    native_grade: str
    veteran_grade: str
    oversea_grade: str
    admission_list: List[ExamAdmissionModel]
    
@dataclass
class StarDepartmentModel:
    department_id: str
    department_name: str
    admission_href: str
    
@dataclass
class StarAdmissionModel:
    ticket: str
    exam_area: str
    school_name: str
    school_depart: str

@dataclass
class CrossDepartmentModel:
    department_id: str
    department_name: str
    admission_href: str
    release_status: str
    
@dataclass
class SchoolAdmissionStatusModel:
    admission: bool
    school_name: str
    department_name: str
    status: str

@dataclass
class CrossAdmissionModel:
    ticket: str
    exam_area: str
    name: str
    schools: List[SchoolAdmissionStatusModel]
    
@dataclass
class VtechDepartmentModel:
    department_id: str
    department_name: str
    admission_href: str
    group: str
    
@dataclass
class VtechAdmissionModel:
    ticket: str
    name: str
    schools: List[SchoolAdmissionStatusModel]
    
@dataclass
class TechregDepartmentModel:
    department_id: str
    department_name: str
    admission_href: str
    average_score: str
    group: str

@dataclass
class TechregAdmissionModel:
    ticket: str
    name: str
    
@dataclass
class TechregAdmissionDetailModel:
    general_grade: str
    native_grade: str
    veteran_grade: str
    oversea_grade: str
    admission_list: List[TechregAdmissionModel]
