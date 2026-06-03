import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import re

# 初始化 Firebase (請確保 firebase_key.json 在同目錄)
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def crawl_latest_invoice():
    print("正在自動爬取財政部最新一期號碼...")
    url = 'https://invoice.etax.nat.gov.tw/'
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res.encoding = 'utf-8'
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 抓取網頁上所有的 8 位數號碼
    all_text = soup.get_text()
    all_numbers = re.findall(r'\d{8}', all_text)
    
    if len(all_numbers) >= 3:
        data_to_save = {
            'special_prize': all_numbers[0],   # 特別獎
            'grand_prize': all_numbers[1],     # 特獎
            'first_prizes': all_numbers[2:5],  # 頭獎(通常有三組)
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        db.collection('invoice_numbers').document("latest_invoice").set(data_to_save)
        print(f"✅ 爬取成功，最新號碼已存入 Firebase: {data_to_save}")
    else:
        print("❌ 抓取號碼失敗，請檢查網頁結構。")

if __name__ == '__main__':
    crawl_latest_invoice()