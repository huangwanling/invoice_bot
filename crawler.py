import requests
import urllib3
import re
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def crawl_invoice():
    print("正在鎖定目標區域爬取...")
    url = 'https://invoice.etax.nat.gov.tw/index.html'
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        all_text = soup.get_text()
        numbers = re.findall(r'\d{8}', all_text)
        
        if len(numbers) < 5:
            print(f"❌ 數字太少，網頁可能沒載入完全: {numbers}")
            return

        target_numbers = numbers[-5:] 
        
        # 這裡的欄位名稱必須與 app.py 一致
        data = {
            'special_prize': target_numbers[0],
            'grand_prize': target_numbers[1],
            'first_prizes': target_numbers[2:] # 修正為 first_prizes
        }
        
        db.collection('invoice_numbers').document('latest').set(data)
        print("✅ 爬取成功並同步至 Firebase！")
        
    except Exception as e:
        print(f"❌ 爬蟲失敗: {e}")

if __name__ == '__main__':
    crawl_invoice()