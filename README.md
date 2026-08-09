# FFXIV Item Data

Final Fantasy XIV 道具資料整合庫，彙整多語言道具編號、名稱與描述，並提供壓縮後的 JSON 檔案，方便外部專案透過 CDN 直接存取與使用。

## 專案簡介

本專案從以下四個社群維護的 FFXIV 客戶端解析專案中，提取道具相關檔案，進行整合、過濾與格式轉換後，產出統一的多語言道具資料，並壓縮成 `.gz` 格式，以利外部系統快速調用。

### 資料來源

| 語言 | 來源專案 |
|------|----------|
| 英文 / 日文 / 法文 / 德文 | [xivapi/ffxiv-datamining](https://github.com/xivapi/ffxiv-datamining) |
| 繁體中文 | [thewakingsands/ffxiv-datamining-tc](https://github.com/thewakingsands/ffxiv-datamining-tc) |
| 簡體中文 | [thewakingsands/ffxiv-datamining-cn](https://github.com/thewakingsands/ffxiv-datamining-cn) |
| 韓文 | [Ra-Workspace/ffxiv-datamining-ko](https://github.com/Ra-Workspace/ffxiv-datamining-ko) |

## 資料存取與 API

本專案透過 jsDelivr CDN 與 Data API 提供穩定且帶有版本控管的存取管道：

### 1. 查詢最新版本號 API
在下載數據包前，建議先查詢版本 API 取得最新 Tag（例如 `2026.08.08-0328`），以便進行本地快取比對：

```
https://data.jsdelivr.com/v1/packages/gh/kuronekowen/ffxiv-item-data
```

### 2. 下載資料檔案 (.gz)

特定版本（推薦，利於 CDN 快取）：
```
https://cdn.jsdelivr.net/gh/kuronekowen/ffxiv-item-data@{version}/data/ffxiv_items_all_languages.json.gz
```

最新版本（直接拉取）：
```
https://cdn.jsdelivr.net/gh/kuronekowen/ffxiv-item-data@latest/data/ffxiv_items_all_languages.json.gz
```

解壓縮後即可得到完整的 JSON 陣列

## 資料格式範例

每筆道具資料包含道具 ID、圖示編號，以及各語言的名稱與描述：

```json
{
  "ID": 2,
  "Icon": 1,
  "Tc": "火之碎晶",
  "Cn": "火之碎晶",
  "Ja": "ファイアシャード",
  "En": "Fire Shard",
  "Fr": "Éclat de feu",
  "De": "Feuerscherbe",
  "Ko": "불 샤드",
  "Tc_Description": "火媒介的小結晶。",
  "Cn_Description": "火媒介的小结晶。",
  "Ja_Description": "炎の媒質の小結晶",
  "En_Description": "A tiny crystalline manifestation of aetheric fire energy.",
  "Fr_Description": "Un éclat provenant d'un cristal de feu.",
  "De_Description": "Eine kleine kristalline Verfestigung ätherischer Feuerenergie.",
  "Ko_Description": "불의 성질을 전달하는 작은 결정체."
}
```

### 欄位說明

| 欄位 | 說明 |
|------|------|
| `ID` | 道具唯一編號 |
| `Icon` | 圖示編號 |
| `Tc` / `Cn` / `Ja` / `En` / `Fr` / `De` / `Ko` | 各語言道具名稱 |
| `*_Description` | 各語言道具描述 |

語言對應：
- `Tc`：繁體中文
- `Cn`：簡體中文
- `Ja`：日文
- `En`：英文
- `Fr`：法文
- `De`：德文
- `Ko`：韓文

## 使用方式與快取最佳實踐
由於完整資料庫壓縮檔較大（約 5MB+），建議前端專案配合 IndexedDB 或 LocalStorage 實現快取比對機制，避免重複下載。

### JavaScript 範例 (結合版本檢查與 IndexedDB 快取)

``` JavaScript
const REPO = 'kuronekowen/ffxiv-item-data';

async function getFFXIVData() {
  // 1. 查詢 jsDelivr API 取得最新 Release Tag (僅約幾百 Bytes)
  const apiRes = await fetch(`[https://data.jsdelivr.com/v1/packages/gh/$](https://data.jsdelivr.com/v1/packages/gh/$){REPO}`);
  const apiData = await apiRes.json();
  const latestVersion = apiData.versions[0].version; // 例如 "2026.08.08-0328"

  // 2. 檢查本地快取的版本標籤
  const localVersion = localStorage.getItem('ffxiv_data_version');
  
  // (假設 getLocalDB() 為讀取本地 IndexedDB 的自訂函式)
  const cachedData = await getLocalDB(); 

  // 3. 版本吻合則直接使用快取
  if (cachedData && localVersion === latestVersion) {
    console.log(`[FFXIV Data] 使用本地快取版本: ${latestVersion}`);
    return cachedData;
  }

  // 4. 版本不符，載入指定 Tag 的最新數據包
  console.log(`[FFXIV Data] 下載新版本: ${latestVersion}`);
  const gzUrl = `[https://cdn.jsdelivr.net/gh/$](https://cdn.jsdelivr.net/gh/$){REPO}@${latestVersion}/data/ffxiv_items_all_languages.json.gz`;
  const response = await fetch(gzUrl);
  
  // Gzip 解壓縮
  const ds = new DecompressionStream('gzip');
  const decompressed = response.body.pipeThrough(ds);
  const items = await new Response(decompressed).json();

  // 5. 寫入本地快取
  await setLocalDB(items);
  localStorage.setItem('ffxiv_data_version', latestVersion);

  return items;
}
```

### 本地使用

1. 下載 `ffxiv_items_all_languages.json.gz`
2. 解壓縮後即可得到 `ffxiv_items_all_languages.json`
3. 依需求載入使用

## 授權與聲明

- 本專案僅進行資料彙整與格式轉換，原始資料版權歸屬於各自來源專案與 Square Enix。
- 資料僅供學習與研究用途，請勿用於商業用途或違反 Final Fantasy XIV 服務條款的行為。
- 本專案不保證資料的即時性與完整性，實際遊戲內容以官方為準。

## 相關連結

- [xivapi/ffxiv-datamining](https://github.com/xivapi/ffxiv-datamining)
- [thewakingsands/ffxiv-datamining-tc](https://github.com/thewakingsands/ffxiv-datamining-tc)
- [thewakingsands/ffxiv-datamining-cn](https://github.com/thewakingsands/ffxiv-datamining-cn)
- [Ra-Workspace/ffxiv-datamining-ko](https://github.com/Ra-Workspace/ffxiv-datamining-ko)