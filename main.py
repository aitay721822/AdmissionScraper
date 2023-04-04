import os
import pytesseract
import logging
import argparse
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pydantic import ValidationError

from orm import Base
from conf import AppConfig
from scrapers import Scraper
from scrapers.ocr import OCR

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config_file', type=str, default='config.yaml', help='config file path')
parser.add_argument('-m', '--method', type=str, default=None, help='scrape method')
parser.add_argument('-y', '--year', type=str, default=None, help='scrape year')
parser.add_argument('-v', '--version', action='version', version='Admission Scrapers 1.0.0')

def init(config_path: str):
    def init_config(config_path: str) -> AppConfig:
        try:
            return AppConfig.load(config_path)
        except ValidationError as e:
            print('Config validation error: ', e)
            os.exit(1)
    
    def init_logger(config: AppConfig):
        # 設定 format, level, file
        logging.basicConfig(
            level=config.logger.level,
            format=config.logger.format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(config.logger.file, encoding='utf-8'),
            ]
        )
        
        return logging.getLogger('main')
            
    def init_db(config: AppConfig):
        def build_connection_string() -> str:
            db_type = config.database.type
            if db_type == 'sqlite':
                return 'sqlite:///' + config.database.db_file
            elif db_type == 'mssql':
                db_type += '+pyodbc'
            return URL.create(
                db_type,
                username=config.database.user,
                password=config.database.password,
                host=config.database.host,
                database=config.database.name,
                port=config.database.port,
                query={'charset': config.database.charset}
            )
        # create engine
        engine = create_engine(build_connection_string(), echo=False)
        # migrate database schema
        Base.metadata.create_all(engine)
        return engine
    
    def init_ocr_engine(config: AppConfig):
        # 初始化 OCR 引擎 (使用 Tesseract)
        pytesseract.pytesseract.tesseract_cmd = config.ocr.pytesseract_path
        # OCR Cache 路徑
        OCR().load_cache(config.ocr.cache_path)
        
    config = init_config(config_path)
    init_ocr_engine(config)
    return config, init_logger(config), init_db(config)

def app_exit(config: AppConfig):
    # 保存 OCR Cache 
    OCR().save_cache(config.ocr.cache_path)
    
def main(config_path, scrape_method, scrape_year):
    cfg, logger, db = init(config_path)
    logger.info('initialized configuration, start to scraping data!')
    crawler = Scraper(cfg, db)
    crawler.run(scrape_method, scrape_year)
    app_exit(cfg)
    
if __name__ == '__main__':
    arg = parser.parse_args()
    main(arg.config_file, arg.method, arg.year)