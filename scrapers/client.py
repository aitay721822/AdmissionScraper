import time
import logging
import requests
import cloudscraper
from scrapers.meta import Singleton


class Client(metaclass=Singleton):
    
    def __init__(self, 
                 config, 
                 logger: logging.Logger = logging.getLogger('client')):
        self.config = config            
        self.logger = logger
        self.cookies = None
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
        self.requests = cloudscraper.create_scraper()
        
    def _get(self, url):
        # 思路簡單，就是先請求一次，如果 Cloudflare 驗證失敗，就用 FlareSolverr 來解決驗證問題(更新 cookies)
        try:
            resp = self.requests.get(url, cookies=self.cookies, timeout=self.config.max_timeout, headers={
                'User-Agent': self.user_agent
            })
            # 檢查請求是否成功
            if resp and resp.status_code == 200:
                return resp.text
            else:
                raise Exception(f'請求失敗，狀態碼: {resp.status_code}')
        except cloudscraper.exceptions.CloudflareChallengeError as e:
            resp = requests.post(self.config.flaresolverr_url, headers={'Content-Type': 'application/json'}, json={
                "cmd": "request.get",
                "url": url,
                "maxTimeout": self.config.max_timeout * 1000,
            }, timeout=self.config.max_timeout)
            if resp and resp.status_code == 200:
                j = resp.json()
                if j and j.get('status') == 'ok':
                    self.logger.info(f'FlareSolverr 請求成功，正在更新 cookies')
                    self.cookies = {i['name']:i['value'] for i in j['solution']['cookies']}
                    self.user_agent = j['solution']['userAgent']
                    return j['solution']['response']
                else:
                    self.logger.error(f'FlareSolverr 請求失敗，可能是 Cloudflare 驗證失敗')
            else:
                self.logger.error(f'FlareSolverr 請求失敗，可能是 FlareSolverr Server 未啟動')
                raise Exception(f'請求失敗，狀態碼: {resp.status_code}')
        
    def get(self, url):
        retry = 0
        self.logger.debug(f'開始請求，請求次數: {retry}')
        while retry < self.config.retry:
            try:
                return self._get(url)
            except Exception as e:
                self.logger.error(f'請求失敗，正在重試: {e}')
                time.sleep(self.config.delay)
            retry += 1
        self.logger.error(f'請求失敗，已超過最大重試次數: {self.config.retry}')
        return None
    
if __name__ == '__main__':
    
    class FlareSolverrConfig:
        flaresolverr_url: str = 'http://localhost:8191/v1'
        max_timeout = 60
        retry: int = 5
        delay: int = 5
        
    config = FlareSolverrConfig()
    client = Client(config)
    for i in range(2):
        print(client.get('https://www.google.com/'))