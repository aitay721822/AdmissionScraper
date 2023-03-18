import os
import sys
import logging
import argparse
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pydantic import ValidationError

from orm import Base
from conf import AppConfig
from scrapers.scraper import Scraper

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config_file', type=str, default='config.yaml', help='config file path')

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
        
    
    config = init_config(config_path)
    return config, init_logger(config), init_db(config)
    
def main(config_path):
    cfg, logger, db = init(config_path)
    logger.info('initialized configuration, start to scraping data!')
    crawler = Scraper(cfg, db)
    crawler.run()
    
if __name__ == '__main__':
    arg = parser.parse_args()
    main(arg.config_file)