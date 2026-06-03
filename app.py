from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import re

app = Flask(__name__)

# Firebase 初始化
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        cred = credentials.Certificate(json.loads(firebase_config))
        firebase_admin.initialize_app(cred)
    else:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    
    # 1. 直接抓取使用者在 LINE 打的原始整句話
    user_raw_text = req.get('queryResult', {}).get('queryText', '')
    digits = re.findall(r'\d+', str(user_raw_text))
    
    if not digits:
        return jsonify({"fulfillmentText": "請輸入發票最後 3 碼數字（例如：810）！"})
    
    user_num = digits[0][-3:].zfill(3)

    # 2. 讀取最新號碼
    doc_ref = db.collection('invoice_numbers').document("latest_invoice")
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統目前沒有開獎資料，請先執行爬蟲程式。"})
        
    data = doc.to_dict()
    special = str(data.get('special_prize', '')).strip()
    grand = str(data.get('grand_prize', '')).strip()
    first_list = [str(n).strip() for n in data.get('first_prizes', [])]

    # 3. 對獎邏輯 (3碼比對)
    msg = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！"
    
    # 比對六獎 (頭獎末3碼)
    for f in first_list:
        if user_num == f[-3:]:
            msg = f"🎉 恭喜！末3碼 【{user_num}】 對中 【六獎】，金額 200 元！"
            break
    
    # 若有中大獎末3碼提示
    if user_num == special[-3:]:
        msg = f"🚨 驚！末3碼 【{user_num}】 符合特別獎末3碼，請確認發票「完整8碼」是否為 {special}！"
    elif user_num == grand[-3:]:
        msg = f"🚨 驚！末3碼 【{user_num}】 符合特獎末3碼，請確認發票「完整8碼」是否為 {grand}！"

    return jsonify({"fulfillmentText": msg})

if __name__ == '__main__':
    app.run()