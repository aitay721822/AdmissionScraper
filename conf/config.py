import yaml
from pathlib import Path
from pydantic import BaseModel, validator


class DBConfig(BaseModel):
    # 資料庫類型，為下列值之一: mysql, sqlite, postgresql, mssql
    type: str = 'sqlite'
    # 資料庫連線使用者
    user: str = 'root'
    # 資料庫連線密碼
    password: str = ''
    # 資料庫連線主機
    host: str = 'localhost'
    # 資料庫連線名稱
    name: str = 'scraper'
    # 資料庫連線埠號
    port: int = 3306
    # 資料庫連線編碼
    charset: str = 'utf8mb4'
    # 資料庫連線檔案路徑(僅適用於sqlite)
    db_file: str = 'db.sqlite3'
    
    @validator('type')
    def check_type(cls, v):
        if v not in ['mysql', 'sqlite', 'postgresql', 'mssql']:
            raise ValueError('type must be one of: mysql, sqlite, postgresql, mssql')
        return v

class FlareSolverrConfig(BaseModel):
    # flaresolverr 服務網址
    flaresolverr_url: str = 'http://localhost:8191/v1'
    # 最大延遲秒數
    max_timeout = 60
    # retry 次數
    retry: int = 5
    # retry 延遲時間(秒)
    delay: int = 5
    
class LogConfig(BaseModel):
    # 日誌等級
    level: str = 'INFO'
    # 日誌檔案路徑
    file: str = 'scraper.log'
    # 日誌格式
    format: str = '%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(filename)s:%(lineno)d'
    
class OcrConfig(BaseModel):
    # ocr path
    pytesseract_path: str = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    # ocr cache path
    cache_path: str = 'ocr_cache.json'

class AppConfig(BaseModel):
    flaresolverr: FlareSolverrConfig = FlareSolverrConfig()
    database: DBConfig = DBConfig()
    logger: LogConfig = LogConfig()
    ocr: OcrConfig = OcrConfig()
    
    @staticmethod
    def save(cfg, path: str = 'config.yaml'):
        save_path = Path(path)
        if save_path.exists() and save_path.is_file():
            save_path.unlink()
                
        with open(save_path, mode='w', encoding='utf-8') as f:
            yaml.dump(cfg.dict(), f, sort_keys=False)
    
    @staticmethod
    def load(path: str = 'config.yaml'):
        load_path = Path(path)
        if load_path.exists() and load_path.is_file():
            with open(load_path, mode='r', encoding='utf-8') as f:
                return AppConfig(**yaml.load(f, Loader=yaml.FullLoader))
        else:
            cfg = AppConfig()
            AppConfig.save(cfg, path)
            return cfg
        
    @staticmethod
    def default():
        return AppConfig()

if __name__ == '__main__':
    cfg = AppConfig()
    AppConfig.save(cfg)
    print(AppConfig.load())