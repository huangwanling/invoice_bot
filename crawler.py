import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import re

# 初始化 Firebase
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
    
    # 財政部網頁最新期別資料通常在 class="etw-tbiggest" 的表格裡
    # 我們直接抓取網頁上所有的 8 位數號碼
    all_text = soup.get_text()
    # 抓出所有 8 位數
    all_numbers = re.findall(r'\d{8}', all_text)
    
    # 假設前 3 個號碼分別為 特別獎, 特獎, 頭獎 (這是財政部官網的慣用結構)
    if len(all_numbers) >= 3:
        data_to_save = {
            'special_prize': all_numbers[0],
            'grand_prize': all_numbers[1],
            'first_prizes': all_numbers[2:], # 頭獎可能有多組
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        db.collection('invoice_numbers').document("latest_invoice").set(data_to_save)
        print(f"✅ 自動爬蟲完成！最新號碼已存入資料庫: {data_to_save}")
    else:
        print("❌ 未抓到足夠號碼，請檢查網頁結構是否變動。")

if __name__ == '__main__':
    crawl_latest_invoice()