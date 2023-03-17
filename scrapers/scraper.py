import logging
from scrapers.model import AvailableYearsModel
from scrapers.webparser import AvailableYearsParser 
from scrapers.crawlers import *
from conf import AppConfig
from typing import Dict, List
from sqlalchemy.engine import Engine
from scrapers.client import Client

class Scraper:
    
    base_url = 'https://www.com.tw/'
    
    def __init__(self, config: AppConfig, db: Engine):
        self.logger = logging.getLogger('scraper')
        
        self.config = config
        self.db = db
        self.client = Client.get_instance(config.flaresolverr)
        self.crawlers: Dict[str, Crawler] = {
            'exam': ExamCrawler(config, db),
            'star': StarCrawler(config, db),
            'cross': CrossCrawler(config, db),
            'vtech': VtechCrawler(config, db),
            'techreg': TechregCrawler(config, db),
        }

    def fetch_available_years(self) -> List[AvailableYearsModel]:
        resp = self.client.get(self.base_url)
        self.logger.info('開始解析學年度資料')
        parser = AvailableYearsParser()
        parsed = parser.parse(resp)
        
        return parsed

    def run(self):
        # 爬取學年度資料 (e.g. 111、110、109, ...)
        self.logger.info("開始爬取學年度資料")
        available_years = self.fetch_available_years()
        if not available_years:
            return
        self.logger.info(f"學年度資料爬取完成，資料: {available_years}")
        
        # 爬取各個入學管道的資料
        for current in available_years:
            for year in current.available_years:
                self.logger.info(f'開始爬取 {year} 學年度 {current.method} 入學管道的資料')
                try:
                    crawler = self.crawlers.get(current.method)
                    crawler.crawl(year)
                except KeyError as e:
                    self.logger.error(f'找不到 {current.method} 入學管道的爬蟲')
                