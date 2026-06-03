from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import re

app = Flask(__name__)

# 初始化 Firebase
if not firebase_admin._apps:
    # 優先從環境變數讀取 Firebase 金鑰 (適用於 Vercel)
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        # 本地開發用
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_prize_info(user_num, data):
    special = data.get('special_prize')
    grand = data.get('grand_prize')
    first_list = data.get('first_prizes', [])
    
    # 1. 檢查特別獎與特獎 (需 8 碼全對)
    if user_num == special: return "特別獎 (1,000萬元)"
    if user_num == grand: return "特獎 (200萬元)"
    
    # 2. 檢查頭獎及對應的二至六獎
    for f in first_list:
        if user_num == f: return "頭獎 (20萬元)"
        if len(user_num) >= 7 and user_num[-7:] == f[-7:]: return "二獎 (4萬元)"
        if len(user_num) >= 6 and user_num[-6:] == f[-6:]: return "三獎 (1萬元)"
        if len(user_num) >= 5 and user_num[-5:] == f[-5:]: return "四獎 (4,000元)"
        if len(user_num) >= 4 and user_num[-4:] == f[-4:]: return "五獎 (1,000元)"
        if len(user_num) >= 3 and user_num[-3:] == f[-3:]: return "六獎 (200元)"
            
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        params = req.get('queryResult', {}).get('parameters', {})
        
        # 抓取數字參數
        user_num = params.get('number')
        if not user_num:
            query_text = req.get('queryResult', {}).get('queryText', '')
            digits = re.findall(r'\d+', str(query_text))
            user_num = digits[-1] if digits else None
        
        if not user_num:
            return jsonify({"fulfillmentText": "請輸入發票號碼數字。"})

        user_num = str(int(float(user_num)))
        
        # 讀取 Firebase
        doc = db.collection('invoice_numbers').document('latest').get()
        if not doc.exists:
            return jsonify({"fulfillmentText": "目前查無開獎資料，請稍後。"})
        
        data = doc.to_dict()
        result = get_prize_info(user_num, data)
        
        if result:
            reply = f"🎉 恭喜！號碼 【{user_num}】 對中 【{result}】！"
        else:
            reply = f"❌ 號碼 【{user_num}】 未中獎，再接再厲！"
            
        return jsonify({"fulfillmentText": reply})

    except Exception as e:
        return jsonify({"fulfillmentText": f"發生錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run()