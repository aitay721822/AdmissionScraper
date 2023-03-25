# AdmissionScraper

此程式功能為爬取 `www.com.tw` 各種入學管道的榜單資料。

## 專案結構

```c
admission_scraper/      // 專案根目錄
├─ conf/                // 設定檔模組
│  ├─ __init__.py       // conf package 
│  ├─ config.py         // 設定檔類別，包含載入、儲存、預設值功能
├─ orm/                 // SQL Model 模組
│  ├─ __init__.py       // orm package
│  ├─ model.py          // SQL Schema 定義
├─ scrapers/            // 爬蟲模組
│  ├─ __init__.py       // scrapers package
│  ├─ client.py         // 請求客戶端
│  ├─ crawlers.py       // 設計爬取邏輯
│  ├─ model.py          // 結構化爬取下來的資料
│  ├─ ocr.py            // OCR 模組
│  ├─ scraper.py        // 爬蟲主程式
│  ├─ utils.py          // 輔助字串清理的工具類
│  ├─ webparser.py      // 解析邏輯
├─ .gitignore           // .gitignore
├─ main.py              // 專案進入點
├─ README.md            // 說明文件
├─ requirements.txt     // 所需套件
```

## 如何繞過 cloudflare ? (2023/03/25)

借助 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) 工具實現繞過 cloudflare 之功能，並將繞過後的 cookie、useragent保存起來，以便於下一次請求。

## 如何使用

1. 首先，你需要安裝 [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)，使用 docker 安裝或是下載 [docker-compose.yml](https://github.com/FlareSolverr/FlareSolverr/blob/master/docker-compose.yml):

    ```bash
    docker run -d \
    --name=flaresolverr \
    -p 8191:8191 \
    -e LOG_LEVEL=info \
    --restart unless-stopped \
    ghcr.io/flaresolverr/flaresolverr:latest
    ```

2. 安裝 [tesseract ocr](https://tesseract-ocr.github.io/)

3. 安裝本專案的依賴項

    ```bash
    pip install -r requirements.txt
    ```

4. 使用 Python 執行 `main.py`

    ```bash
    python main.py
    ```

## 預設設定檔 (`config.yaml`)

- flaresolverr
  - `flaresolverr_url`: `flaresolverr` 服務網址
  - `retry`: 請求重試次數 [client.py]
  - `delay`: 當請求失敗時，需要 delay 多少秒(seconds)
  - `max_timeout`: 最大請求時間
- database
  - `type`: 可以是 `mysql`、`sqlite`、`postgresql`、`mssql` 其中之一，預設是 `sqlite`
  - `user`: 資料庫使用者名稱
  - `password`: 資料庫密碼
  - `host`: 資料庫主機位址
  - `port`: 資料庫主機埠號
  - `charset`: 資料庫字元集
  - `db_file`: 資料庫檔案位置 (僅 sqlite 適用)
- logger
  - `level`: logger log level
  - `file`: logger file location
  - `format`: logger format
- ocr
  - `pytesseract_path`: pytesseract.exe 位置

```yaml
flaresolverr:
  flaresolverr_url: http://localhost:8191/v1
  retry: 5
  delay: 5
  max_timeout: 60
database:
  type: sqlite
  user: root
  password: ''
  host: localhost
  name: scraper
  port: 3306
  charset: utf8mb4
  db_file: db.sqlite3
logger:
  level: INFO
  file: scraper.log
  format: '%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(filename)s:%(lineno)d'
ocr:
  pytesseract_path: C:\Program Files\Tesseract-OCR\tesseract.exe
```

## SQL Schema 說明

- `AdmissionList`: 榜單 Table
  - `Id` (Integer): 榜單ID
  - `Year` (Integer): 榜單年度
  - `Method` (Integer): 錄取方式 (外鍵)
  - `SchoolDepartmentID` (Integer): 校系 ID (外鍵)
  - `AverageScore` (String): 平均錄取分數
  - `Weight` (String): 加權值
  - `SameGradeOrder` (String): 同分斟酌
  - `GeneralGrade` (String): 普通生錄取分數
  - `NativeGrade` (String): 原住民錄取分數
  - `VeteranGrade` (String): 退伍軍人錄取分數
  - `OverseaGrade` (String): 僑生錄取分數
  - `UniversityApply` (String): 大學/科大個人申請(學測專用)
  - `GroupCode` (String): 群組代碼 (統測專用)
- `AdmissionPerson`: 上榜人 Table
  - `Id` (Integer): 上榜人ID
  - `AdmissionListId` (Integer): 榜單ID
  - `AdmissionTicket` (String): 准考證號碼
  - `Name` (String): 上榜人姓名
  - `ExamArea` (String): 考區
  - `SecondStageStatus` (String): 二階甄試狀態
  - `AdmissionStatus` (String): 上榜狀態
- `AdmissionType`: 錄取管道 Table
  - `Id` (Integer): 錄取管道 ID
  - `Name` (String): 錄取管道名稱
- `SchoolDepartment`: 校系 Table
  - `Id` (Integer): 校系 ID
  - `SchoolCode` (String): 學校代碼
  - `DepartmentCode` (String): 校系代碼
  - `SchoolName` (String): 學校名稱
  - `DepartmentName` (String): 系所名稱

## 如何修改程式，以對應將來頁面改動?

Q: 當頁面改動，使解析器不再工作時:

A: 修改 `scrapers/webparser.py` 中各解析器之程式碼，其中各解析器類別名稱前綴有各入學管道的代號: `exam` 代表分科/指考、`star` 代表繁星入學、`cross` 代表學測查榜、`vtech` 代表統測甄試、`techreg` 代表統測分發。

Q: 如果 cloudflare 繞過失敗怎麼辦:

A: 修改 `scrapers/client.py` 的邏輯。

Q: 如果某個入學管道爬取邏輯變動，怎麼辦?

A: 修改 `scrapers/crawlers.py` 的 `crawl` function
