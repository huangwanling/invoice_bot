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
        
        # 1. 抓取所有數字區塊 (div 或 span)
        # 觀察到財政部網站的中獎號碼通常放在 <span class="etw-tbiggest"> 或者是表格內
        # 我們直接尋找所有含有號碼的 table 或 div 區塊
        all_text = soup.get_text()
        
        # 2. 用正則表達式撈出所有 8 位數
        numbers = re.findall(r'\d{8}', all_text)
        
        # 3. 過濾：財政部網頁最上方通常會出現 3 位數的期別，我們要過濾掉它
        # 我們只要 8 位數，且不要期別 (如 115, 03 等)
        # 這裡我們取抓到的最後 8 個數字 (通常是最新的中獎號碼)
        # 特別獎(1), 特獎(1), 頭獎(3) = 至少 5 個
        if len(numbers) < 5:
            print(f"❌ 數字太少，網頁可能沒載入完全: {numbers}")
            return

        # 根據經驗，最新的號碼往往在列表的後段
        # 假設最新的一期包含 5 組以上 8 位數
        target_numbers = numbers[-5:] 
        
        data = {
            'special_prize': target_numbers[0],
            'grand_prize': target_numbers[1],
            'first_prize': target_numbers[2:]
        }
        
        db.collection('invoice_numbers').document('latest').set(data)
        print("✅ 爬取成功！")
        print(f"特別獎: {data['special_prize']}")
        print(f"特獎: {data['grand_prize']}")
        print(f"頭獎: {data['first_prize']}")
        
    except Exception as e:
        print(f"❌ 爬蟲失敗: {e}")

if __name__ == '__main__':
    crawl_invoice()
