from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import re
import os
import json

app = Flask(__name__)

# 初始化 Firebase (支援 Vercel 環境變數與本地 firebase_key.json)
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_prize_info(user_num, data):
    special = data.get('special_prize', '')
    grand = data.get('grand_prize', '')
    # 這裡對應您資料庫中的欄位名稱
    first_list = data.get('first_prize', [])
    
    # 8碼完整比對邏輯
    if len(user_num) == 8:
        if user_num == special: return "特別獎 (1,000萬元)"
        if user_num == grand: return "特獎 (200萬元)"
        for f in first_list:
            if user_num == f: return "頭獎 (20萬元)"
            if user_num[-7:] == f[-7:]: return "二獎 (4萬元)"
            if user_num[-6:] == f[-6:]: return "三獎 (1萬元)"
            if user_num[-5:] == f[-5:]: return "四獎 (4,000元)"
            if user_num[-4:] == f[-4:]: return "五獎 (1,000元)"
            if user_num[-3:] == f[-3:]: return "六獎 (200元)"
    
    # 3碼快速比對邏輯 (六獎)
    elif len(user_num) == 3:
        for f in first_list:
            if user_num == f[-3:]: return "六獎 (200元)"
        if user_num == special[-3:] or user_num == grand[-3:]:
            return "六獎 (200元)"
            
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    # 取得 Dialogflow 傳來的請求
    req = request.get_json(silent=True, force=True)
    params = req.get('queryResult', {}).get('parameters', {})
    
    # 從 Dialogflow 參數抓取數字，若無則從文字中解析
    user_num = params.get('number')
    if not user_num:
        query_text = req.get('queryResult', {}).get('queryText', '')
        digits = re.findall(r'\d+', str(query_text))
        user_num = digits[-1] if digits else None
    
    if user_num:
        user_num = str(int(float(user_num)))
    else:
        return jsonify({"fulfillmentText": "請輸入發票號碼數字，例如：123 或完整 8 碼"})

    # 從 Firebase 讀取資料
    doc = db.collection('invoice_numbers').document('latest').get()
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統暫無開獎資料，請稍後。"})
        
    data = doc.to_dict()
    result = get_prize_info(user_num, data)
    
    if result:
        reply = f"🎉 恭喜！號碼 【{user_num}】 對中 【{result}】！"
    else:
        reply = f"❌ 號碼 【{user_num}】 未中獎，再接再厲！"
        
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(port=5000)