#!/usr/bin/env python3
"""
FFXIV 物品數據整合工具 (帶 GitHub Commit Hash 自動更新檢查)
1. 每天檢查 4 個資料來源的最新 commit hash。
2. 若與本地紀錄不一致，才下載並合併 7 種語言的物品數據，輸出 CSV 和壓縮 JSON。
3. 更新完畢後寫入 commit_hashes.json，隔天直接比對即可。
"""

import os
import sys
import json
import gzip
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import requests

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 1. 定義語系代碼與對應的 URL 端點
URLS = {
    "de": "https://cdn.jsdelivr.net/gh/xivapi/ffxiv-datamining/csv/de/Item.csv",
    "en": "https://cdn.jsdelivr.net/gh/xivapi/ffxiv-datamining/csv/en/Item.csv",
    "fr": "https://cdn.jsdelivr.net/gh/xivapi/ffxiv-datamining/csv/fr/Item.csv",
    "ja": "https://cdn.jsdelivr.net/gh/xivapi/ffxiv-datamining/csv/ja/Item.csv",
    "tc": "https://cdn.jsdelivr.net/gh/thewakingsands/ffxiv-datamining-tc/Item.csv",
    "cn": "https://cdn.jsdelivr.net/gh/thewakingsands/ffxiv-datamining-cn/Item.csv",
    "ko": "https://cdn.jsdelivr.net/gh/Ra-Workspace/ffxiv-datamining-ko/csv/Item.csv",
}

# 語言順序
LANG_ORDER = ["Ja", "En", "Fr", "De", "Cn", "Tc", "Ko"]

# 輸出檔案名稱
OUTPUT_CSV = "ffxiv_items_all_languages.csv"
OUTPUT_JSON_GZ = "ffxiv_items_all_languages.json.gz"
VERSION_FILE = "version.txt"
COMMIT_HASHES_FILE = "commit_hashes.json"   # 儲存於 data/ 目錄

# GitHub API 端點（用來取得最新 commit SHA）
# 注意：ja 使用 path=csv/ja，其餘為 repo 根目錄
COMMIT_ENDPOINTS = {
    "ja": "https://api.github.com/repos/xivapi/ffxiv-datamining/commits?path=csv/ja&per_page=1",
    "tc": "https://api.github.com/repos/thewakingsands/ffxiv-datamining-tc/commits?per_page=1",
    "cn": "https://api.github.com/repos/thewakingsands/ffxiv-datamining-cn/commits?per_page=1",
    "ko": "https://api.github.com/repos/Ra-Workspace/ffxiv-datamining-ko/commits?per_page=1",
}


class CommitHashChecker:
    """透過 GitHub Commit Hash 判斷是否需要更新"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.hash_file = data_dir / COMMIT_HASHES_FILE
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "FFXIV-Item-Data-Updater"
        }

    def _fetch_latest_sha(self, url: str) -> Optional[str]:
        """從 GitHub API 取得最新 commit SHA"""
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("sha")
            logger.warning(f"⚠️ API 回傳格式異常: {url}")
            return None
        except Exception as e:
            logger.error(f"❌ 取得 commit SHA 失敗 ({url}): {e}")
            return None

    def get_current_hashes(self) -> Dict[str, str]:
        """取得目前 4 個來源的最新 commit hash"""
        current = {}
        for key, url in COMMIT_ENDPOINTS.items():
            sha = self._fetch_latest_sha(url)
            if sha:
                current[key] = sha
                logger.info(f"🔍 [{key.upper()}] 最新 commit: {sha[:12]}...")
            else:
                logger.warning(f"⚠️ 無法取得 [{key}] 的 commit hash")
        return current

    def load_recorded_hashes(self) -> Dict[str, str]:
        """讀取本地紀錄的 commit hash"""
        if not self.hash_file.exists():
            logger.info("📄 尚未有 commit_hashes.json，視為需要更新")
            return {}
        try:
            with open(self.hash_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ 讀取 commit_hashes.json 失敗: {e}，視為需要更新")
            return {}

    def save_hashes(self, hashes: Dict[str, str]) -> None:
        """更新完畢後寫入最新的 commit hash"""
        self.data_dir.mkdir(exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(),
            "hashes": hashes
        }
        with open(self.hash_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 已更新 commit hash 紀錄 → {self.hash_file}")

    def needs_update(self) -> tuple[bool, Dict[str, str]]:
        """
        比對目前 hash 與本地紀錄
        回傳 (是否需要更新, 目前最新的 hashes)
        """
        current = self.get_current_hashes()
        if not current:
            logger.warning("⚠️ 無法取得任何 commit hash，為防漏更新將強制執行")
            return True, current

        recorded = self.load_recorded_hashes()
        recorded_hashes = recorded.get("hashes", {}) if isinstance(recorded, dict) else {}

        changed = []
        for key, sha in current.items():
            old = recorded_hashes.get(key)
            if old != sha:
                changed.append(key)

        if changed:
            logger.info(f"✨ 偵測到資料來源有更新: {', '.join(changed).upper()}")
            # ja 變動時，en/fr/de 也會一起更新（因為共用客戶端）
            if "ja" in changed:
                logger.info("   └─ JA 有變動 → 國際服 (JA/EN/FR/DE) 將一併更新")
            return True, current
        else:
            logger.info("☕ 所有來源的 commit hash 皆與紀錄一致，跳過本次更新。")
            return False, current


class FFXIVItemDataProcessor:
    """FFXIV 物品數據處理器"""
    
    def __init__(self, data_dir: str = "data", output_dir: str = "dist"):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.all_dfs: Dict[str, pd.DataFrame] = {}
        self.run_timestamp = datetime.now()
        
    def setup_directories(self) -> None:
        """建立必要的目錄"""
        self.data_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f"📁 數據目錄: '{self.data_dir}/'")
        logger.info(f"📁 輸出目錄: '{self.output_dir}/'")
    
    def download_files(self) -> Dict[str, bool]:
        """下載所有語系的 CSV 檔案"""
        results = {}
        
        for lang, url in URLS.items():
            filename = f"Item_{lang}.csv"
            file_path = self.data_dir / filename
            
            logger.info(f"⬇️  正在下載 [{lang.upper()}] 語系: {url}")
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                with open(file_path, "wb") as f:
                    f.write(response.content)
                
                file_size_kb = len(response.content) / 1024
                logger.info(f"   └─ ✅ 成功儲存為 `{file_path}` ({file_size_kb:.1f} KB)")
                results[lang] = True
                
            except requests.exceptions.RequestException as e:
                logger.error(f"   └─ ❌ 下載失敗 [{lang}]: {e}")
                results[lang] = False
        
        return results
    
    def process_international_csv(self, lang: str) -> Optional[pd.DataFrame]:
        """處理國際服 CSV (Standard Header)"""
        file_path = self.data_dir / f"Item_{lang}.csv"
        
        if not file_path.exists():
            logger.warning(f"⚠️ 找不到檔案: {file_path}")
            return None
        
        try:
            df = pd.read_csv(file_path, skiprows=[1, 2], low_memory=False)
            
            # 處理 ID
            id_col = df.columns[0]
            df[id_col] = pd.to_numeric(df[id_col], errors="coerce")
            df = df.dropna(subset=[id_col])
            df[id_col] = df[id_col].astype(int)
            
            lang_code = lang.capitalize()
            
            # 建立欄位映射
            cols = {id_col: "ID"}
            if "Name" in df.columns:
                cols["Name"] = lang_code
            if "Description" in df.columns:
                cols["Description"] = f"{lang_code}_Description"
            if "Icon" in df.columns:
                cols["Icon"] = "Icon"
            
            sub_df = df[list(cols.keys())].rename(columns=cols)
            
            # 填充空值
            if f"{lang_code}_Description" in sub_df.columns:
                sub_df[f"{lang_code}_Description"] = sub_df[f"{lang_code}_Description"].fillna("")
            
            if "Icon" in sub_df.columns:
                sub_df["Icon"] = pd.to_numeric(sub_df["Icon"], errors="coerce").fillna(0).astype(int)
            
            logger.info(f"✅ [{lang_code}] 國際服資料處理完成 ({len(sub_df)} 筆)")
            return sub_df
            
        except Exception as e:
            logger.error(f"❌ 處理 [{lang}] 國際服資料時發生錯誤: {e}")
            return None
    
    def process_extended_csv(self, lang: str) -> Optional[pd.DataFrame]:
        """處理代理服/社群版 CSV (Custom Header)"""
        file_path = self.data_dir / f"Item_{lang}.csv"
        
        if not file_path.exists():
            logger.warning(f"⚠️ 找不到檔案: {file_path}")
            return None
        
        try:
            df = pd.read_csv(file_path, skiprows=[1, 2], header=None, low_memory=False)
            
            lang_code = lang.capitalize()
            
            # 處理 ID (index 0)
            df[0] = pd.to_numeric(df[0], errors="coerce")
            df = df.dropna(subset=[0])
            df[0] = df[0].astype(int)
            
            # 提取 Name (col 1) 與 Description (col 3/9)
            sub_df = pd.DataFrame()
            sub_df["ID"] = df[0]
            sub_df[lang_code] = df[1].fillna("").astype(str)
            
            if df.shape[1] > 9:
                sub_df[f"{lang_code}_Description"] = df[9].fillna("").astype(str)
            else:
                sub_df[f"{lang_code}_Description"] = ""
            
            logger.info(f"✅ [{lang_code}] 獨立/社群服資料處理完成 ({len(sub_df)} 筆)")
            return sub_df
            
        except Exception as e:
            logger.error(f"❌ 處理 [{lang}] 獨立/社群服資料時發生錯誤: {e}")
            return None
    
    def process_all_languages(self) -> None:
        """處理所有語言的數據"""
        int_langs = ["ja", "en", "fr", "de"]
        for lang in int_langs:
            df = self.process_international_csv(lang)
            if df is not None:
                self.all_dfs[lang.capitalize()] = df
        
        ext_langs = ["cn", "tc", "ko"]
        for lang in ext_langs:
            df = self.process_extended_csv(lang)
            if df is not None:
                self.all_dfs[lang.capitalize()] = df
    
    def merge_all_data(self) -> pd.DataFrame:
        """合併所有語言的數據"""
        merged_df = None
        
        for lang_code in LANG_ORDER:
            if lang_code in self.all_dfs:
                if merged_df is None:
                    merged_df = self.all_dfs[lang_code]
                else:
                    df_to_merge = self.all_dfs[lang_code]
                    if "Icon" in merged_df.columns and "Icon" in df_to_merge.columns:
                        df_to_merge = df_to_merge.drop(columns=["Icon"])
                    merged_df = pd.merge(merged_df, df_to_merge, on="ID", how="outer")
        
        if merged_df is None:
            raise ValueError("沒有數據可以合併")
        
        return merged_df
    
    def clean_and_finalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """清理和格式化最終數據"""
        final_columns = [
            "ID", "Ja", "En", "Fr", "De", "Cn", "Tc", "Ko",
            "Icon",
            "Ja_Description", "En_Description", "Fr_Description", "De_Description",
            "Cn_Description", "Tc_Description", "Ko_Description"
        ]
        
        for col in final_columns:
            if col not in df.columns:
                df[col] = ""
        
        final_df = df[final_columns].sort_values("ID").reset_index(drop=True)
        
        text_columns = [col for col in final_columns if col not in ["ID", "Icon"]]
        numeric_columns = ["Icon"] if "Icon" in final_columns else []
        
        for col in text_columns:
            if col in final_df.columns:
                final_df[col] = final_df[col].fillna("").astype(str)
        
        for col in numeric_columns:
            if col in final_df.columns:
                final_df[col] = pd.to_numeric(final_df[col], errors="coerce").fillna(0).astype(int)
        
        final_df["ID"] = pd.to_numeric(final_df["ID"], errors="coerce").fillna(0).astype(int)
        
        return final_df
    
    def save_csv(self, df: pd.DataFrame) -> Path:
        """儲存 CSV 檔案"""
        output_path = self.output_dir / OUTPUT_CSV
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"✅ CSV 已儲存至 `{output_path}` ({len(df)} 筆)")
        return output_path
    
    def save_json_gz(self, df: pd.DataFrame) -> Path:
        """儲存壓縮 JSON 檔案"""
        output_path = self.output_dir / OUTPUT_JSON_GZ
        
        records = df.to_dict(orient="records")
        
        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=None)
        
        file_size_kb = output_path.stat().st_size / 1024
        logger.info(f"✅ JSON 壓縮檔已儲存至 `{output_path}` ({file_size_kb:.1f} KB)")
        return output_path
    
    def save_version_file(self, metadata: Dict) -> Path:
        """儲存版本資訊檔案"""
        version_path = self.output_dir / VERSION_FILE
        
        version_content = f"""# FFXIV Item Data - Version Information
Generated: {self.run_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}
Timestamp: {self.run_timestamp.isoformat()}
Records: {metadata.get('record_count', 0)}
Languages: {', '.join(LANG_ORDER)}
Sources:
  - International: EN, FR, DE, JA (xivapi/ffxiv-datamining)
  - Traditional Chinese: thewakingsands/ffxiv-datamining-tc
  - Simplified Chinese: thewakingsands/ffxiv-datamining-cn
  - Korean: Ra-Workspace/ffxiv-datamining-ko
Output Files:
  - CSV: {OUTPUT_CSV}
  - JSON GZ: {OUTPUT_JSON_GZ}
"""
        
        with open(version_path, "w", encoding="utf-8") as f:
            f.write(version_content)
        
        logger.info(f"✅ 版本資訊已儲存至 `{version_path}`")
        return version_path
    
    def run(self) -> Dict[str, Path]:
        """執行完整的處理流程"""
        self.setup_directories()
        
        download_results = self.download_files()
        success_count = sum(1 for v in download_results.values() if v)
        logger.info(f"📥 下載完成: {success_count}/{len(URLS)} 個檔案成功")
        
        if success_count == 0:
            raise RuntimeError("所有檔案下載失敗，無法繼續處理")
        
        self.process_all_languages()
        
        merged_df = self.merge_all_data()
        logger.info(f"📊 合併完成: {len(merged_df)} 筆數據")
        
        final_df = self.clean_and_finalize(merged_df)
        logger.info(f"✨ 清理完成: {len(final_df)} 筆數據")
        
        csv_path = self.save_csv(final_df)
        json_gz_path = self.save_json_gz(final_df)
        
        data_csv_path = self.data_dir / OUTPUT_CSV
        data_json_gz_path = self.data_dir / OUTPUT_JSON_GZ
        shutil.copy2(csv_path, data_csv_path)
        shutil.copy2(json_gz_path, data_json_gz_path)
        logger.info(f"✅ 已同步最新資料至 data/：")
        logger.info(f"   └─ {data_csv_path}")
        logger.info(f"   └─ {data_json_gz_path}")
        
        metadata = {
            'record_count': len(final_df),
            'timestamp': self.run_timestamp.isoformat()
        }
        version_path = self.save_version_file(metadata)
        
        return {
            "csv": csv_path,
            "json_gz": json_gz_path,
            "version": version_path,
            "data_csv": data_csv_path,
            "data_json_gz": data_json_gz_path,
        }


def main():
    """主程式入口"""
    try:
        data_dir = Path("data")
        checker = CommitHashChecker(data_dir)

        # 1. 檢查是否需要更新
        need_update, current_hashes = checker.needs_update()
        if not need_update:
            # 退出程序且不拋錯 (Exit Code 0)，GitHub Action 會正常完成，且無 Git 變更
            sys.exit(0)

        # 2. 確認有更新，執行 Pipeline
        processor = FFXIVItemDataProcessor()
        output_files = processor.run()

        # 3. 更新成功後寫入最新的 commit hash
        if current_hashes:
            checker.save_hashes(current_hashes)
        
        logger.info("🎉 所有處理程序完成！")
        logger.info(f"📄 CSV 檔案 (dist/): {output_files['csv']}")
        logger.info(f"📦 JSON 壓縮檔 (dist/): {output_files['json_gz']}")
        logger.info(f"📄 CSV 檔案 (data/): {output_files['data_csv']}")
        logger.info(f"📦 JSON 壓縮檔 (data/): {output_files['data_json_gz']}")
        logger.info(f"📋 版本檔案: {output_files['version']}")
        
    except Exception as e:
        logger.error(f"❌ 處理過程中發生錯誤: {e}")
        raise

if __name__ == "__main__":
    main()