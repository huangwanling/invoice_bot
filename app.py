from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import re

app = Flask(__name__)

# 初始化 Firebase
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- 核心對獎邏輯 ---
def get_prize_info(user_num, data):
    special = data.get('special_prize')
    grand = data.get('grand_prize')
    first_list = data.get('first_prizes', [])
    
    if user_num == special: return "特別獎 (1,000萬元)"
    if user_num == grand: return "特獎 (200萬元)"
    
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
        action = req.get('queryResult', {}).get('action')
        
        # --- 新功能 1: 查看最新開獎號碼 ---
        if action == 'get_latest_invoice':
            doc = db.collection('invoice_numbers').document('latest').get()
            if not doc.exists: return jsonify({"fulfillmentText": "暫無開獎資料。"})
            data = doc.to_dict()
            msg = (f"【最新開獎號碼】\n特別獎: {data['special_prize']}\n特獎: {data['grand_prize']}\n"
                   f"頭獎: {', '.join(data['first_prizes'])}\n\n規則：頭獎後三碼以上即中獎。")
            return jsonify({"fulfillmentText": msg})

        # --- 新功能 2: 查看過往對獎記錄 ---
        elif action == 'get_history':
            history_ref = db.collection('user_history').order_by('timestamp', direction='DESCENDING').limit(10)
            docs = history_ref.stream()
            msg = "【您的近十筆對獎記錄】\n"
            records = [f"號碼: {d.to_dict()['number']} -> {d.to_dict()['result']}" for d in docs]
            msg += "\n".join(records) if records else "尚無對獎紀錄。"
            return jsonify({"fulfillmentText": msg})

        # --- 既有的對獎功能 (處理輸入的發票數字) ---
        else:
            params = req.get('queryResult', {}).get('parameters', {})
            user_num = params.get('number')
            
            if not user_num:
                query_text = req.get('queryResult', {}).get('queryText', '')
                digits = re.findall(r'\d+', str(query_text))
                user_num = digits[-1] if digits else None
            
            if not user_num: return jsonify({"fulfillmentText": "請輸入發票號碼數字。"})

            user_num = str(int(float(user_num)))
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            result = get_prize_info(user_num, data)
            
            reply = f"🎉 恭喜！號碼 【{user_num}】 對中 【{result}】！" if result else f"❌ 號碼 【{user_num}】 未中獎。"
            
            # 存入紀錄
            db.collection('user_history').add({
                'number': user_num,
                'result': result if result else "未中獎",
                'timestamp': firestore.SERVER_TIMESTAMP
            })
            return jsonify({"fulfillmentText": reply})

    except Exception as e:
        return jsonify({"fulfillmentText": f"系統發生錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run()