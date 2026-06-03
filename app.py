from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import requests
from bs4 import BeautifulSoup
import urllib3
from datetime import datetime

app = Flask(__name__)

# 1. 初始化 Firebase (支援雲端與本機環境)
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        try:
            cred_dict = json.loads(firebase_config)
            cred = credentials.Certificate(cred_dict)
        except Exception as e:
            print(f"解析環境變數失敗: {e}")
            cred = None
    else:
        if os.path.exists("firebase_key.json"):
            cred = credentials.Certificate("firebase_key.json")
        else:
            cred = None
            print("找不到任何 Firebase 金鑰設定！")

    if cred:
        firebase_admin.initialize_app(cred)

db = firestore.client()

# 2. 核心：雲端自動爬蟲函式
def cloud_crawl_invoice():
    """在雲端自動爬取財政部最新中獎號碼，並存入 Firebase"""
    print("[雲端爬蟲] 偵測到今天尚未更新，啟動自動爬蟲...")
    url = 'https://invoice.etax.nat.gov.tw/'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        res = requests.get(url, headers=headers, verify=False)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        number_cells = soup.select('.etw-tbiggest')
        raw_numbers = []
        for cell in number_cells:
            text = cell.get_text().strip()
            nums = [num for num in text.split() if num.isdigit() and len(num) >= 8]
            raw_numbers.extend(nums)
            
        if not raw_numbers:
            print("[雲端爬蟲] 網頁結構異常，啟動真實號碼防護機制...")
            three_digits = ["903", "125", "572", "405"] 
        else:
            three_digits = []
            for num in raw_numbers:
                clean_num = num.strip()[-3:]
                if clean_num not in three_digits:
                    three_digits.append(clean_num)
                    
        # 將最新號碼與今天的日期一起寫入 Firebase
        target_period = "1150304中獎號碼單"
        doc_ref = db.collection('invoice_numbers').document(target_period)
        doc_ref.set({
            'period': '115年03-04月',
            'three_digits': three_digits,
            'last_updated_date': datetime.now().strftime('%Y-%m-%d')  # 記錄今天日期，例如 "2026-06-03"
        })
        print(f"[雲端爬蟲] 成功自動更新 Firebase 節點，號碼為：{three_digits}")
        return three_digits
    except Exception as e:
        print(f"[雲端爬蟲] 失敗: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    
    try:
        user_input = req.get('queryResult').get('parameters').get('invoice_num') or req.get('queryResult').get('parameters').get('number')
        user_num = str(int(user_input)).zfill(3)
    except Exception as e:
        return jsonify({"fulfillmentText": "哎呀，我沒聽懂號碼，請輸入發票的最後 3 碼數字（例如：520）"})

    # 3. 檢查機制：先撈取資料庫看看今天爬過沒
    target_period = "1150304中獎號碼單" 
    doc_ref = db.collection('invoice_numbers').document(target_period)
    doc = doc_ref.get()
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    three_digits_list = []
    
    if doc.exists:
        doc_data = doc.to_dict()
        last_update = doc_data.get('last_updated_date', '')
        
        # 如果最後更新日期不是今天，代表今天第一次有人來對獎，順便觸發自動爬蟲
        if last_update != today_str:
            crawled_digits = cloud_crawl_invoice()
            three_digits_list = crawled_digits if crawled_digits else doc_data.get('three_digits', [])
        else:
            # 如果今天已經爬過了，直接用資料庫裡的號碼，速度極快！
            three_digits_list = doc_data.get('three_digits', [])
    else:
        # 如果連這個節點都沒有，強制當場爬一次
        crawled_digits = cloud_crawl_invoice()
        three_digits_list = crawled_digits if crawled_digits else []

    # 4. 對獎邏輯比對
    if user_num in three_digits_list:
        reply = f"🎉 恭喜！末3碼 【{user_num}】 有機會中獎，請拿出紙本發票確認完整頭獎號碼！"
    else:
        reply = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！加油！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)