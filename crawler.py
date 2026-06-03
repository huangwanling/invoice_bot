import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import re

# 初始化 Firebase (確保 firebase_key.json 在同目錄)
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def crawl_and_save():
    print("正在爬取財政部最新號碼...")
    url = 'https://invoice.etax.nat.gov.tw/'
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 抓出頁面所有 8 位數號碼
    all_numbers = re.findall(r'\d{8}', soup.get_text())
    
    if len(all_numbers) >= 5:
        # 強制寫入 latest_invoice，確保對獎程式永遠讀到最新資料
        data = {
            'special_prize': all_numbers[0],
            'grand_prize': all_numbers[1],
            'first_prizes': all_numbers[2:5],
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('invoice_numbers').document("latest_invoice").set(data)
        print(f"✅ 更新成功！資料已存入 latest_invoice。")
    else:
        print("❌ 爬取失敗，未抓到足夠號碼。")

if __name__ == '__main__':
    crawl_and_save()