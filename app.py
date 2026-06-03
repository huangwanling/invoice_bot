from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import re
from datetime import datetime

app = Flask(__name__)

# Firebase 初始化
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    cred = credentials.Certificate(json.loads(firebase_config)) if firebase_config else credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- 既有且完善的對獎邏輯 ---
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
        
        # --- 新功能 1: 查看最新開獎號碼 (左邊按鈕) ---
        if action == 'get_latest_invoice':
            doc = db.collection('invoice_numbers').document('latest').get()
            if not doc.exists: return jsonify({"fulfillmentText": "暫無開獎資料。"})
            data = doc.to_dict()
            msg = (f"【{data.get('period', '最新期別')}】\n"
                   f"特別獎: {data.get('special_prize')}\n"
                   f"特獎: {data.get('grand_prize')}\n"
                   f"頭獎: {', '.join(data.get('first_prizes', []))}\n\n"
                   "【中獎規則】\n特別/特獎: 8碼全對(1000萬/200萬)\n"
                   "頭獎: 8碼全對(20萬)\n二獎: 末7碼(4萬)\n三獎: 末6碼(1萬)\n"
                   "四獎: 末5碼(4千)\n五獎: 末4碼(1千)\n六獎: 末3碼(200元)")
            return jsonify({"fulfillmentText": msg})

        # --- 新功能 2: 查看當月對獎紀錄 (右邊按鈕) ---
        elif action == 'get_history':
            current_month = datetime.now().strftime("%Y-%m")
            history_ref = db.collection('user_history').order_by('timestamp', direction='DESCENDING')
            docs = history_ref.stream()
            
            msg = f"【{datetime.now().strftime('%m')}月份對獎紀錄】\n"
            found = False
            for d in docs:
                item = d.to_dict()
                ts = item.get('timestamp')
                # 判斷是否為當月
                if ts and ts.strftime("%Y-%m") == current_month:
                    msg += f"號碼: {item['number']} | {item['result']}\n"
                    found = True
            
            return jsonify({"fulfillmentText": msg if found else "本月尚無對獎紀錄。"})

        # --- 既有對獎功能 ---
        else:
            params = req.get('queryResult', {}).get('parameters', {})
            user_num = params.get('number')
            if not user_num:
                query_text = req.get('queryResult', {}).get('queryText', '')
                digits = re.findall(r'\d+', str(query_text))
                user_num = digits[-1] if digits else None
            
            if not user_num: return jsonify({"fulfillmentText": "請輸入發票號碼。"})
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
        return jsonify({"fulfillmentText": f"發生錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run(port=5000)