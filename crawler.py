import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

# 初始化 Firebase (請確保 firebase_key.json 在同一目錄)
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def crawl_invoice():
    print("正在爬取財政部最新中獎號碼...")
    url = 'https://invoice.etax.nat.gov.tw/index.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(url, headers=headers)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 抓取特別獎與特獎 (它們位於 .etw-tbiggest)
        etw_tbiggest = soup.select('.etw-tbiggest')
        special = etw_tbiggest[0].text.strip()
        grand = etw_tbiggest[1].text.strip()
        
        # 抓取頭獎 (頭獎區塊位於 .etw-tpi)
        first_raw = soup.select('.etw-tpi')[0].text.strip()
        # 將頭獎號碼每8碼切割成列表
        first_prizes = [first_raw[i:i+8] for i in range(0, len(first_raw), 8)]
        
        # 寫入 Firebase
        data = {
            'special_prize': special,
            'grand_prize': grand,
            'first_prizes': first_prizes
        }
        db.collection('invoice_numbers').document('latest').set(data)
        
        print(f"✅ 更新成功！")
        print(f"特別獎: {special} | 特獎: {grand} | 頭獎: {first_prizes}")
        
    except Exception as e:
        print(f"❌ 爬蟲失敗: {e}")

if __name__ == '__main__':
    crawl_invoice()