from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os, json, re
from datetime import datetime

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

# --- 既有的對獎規則邏輯 ---
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
        
        # 1. 查看最新開獎號碼 (優化版)
        if action == 'get_latest_invoice':
            doc = db.collection('invoice_numbers').document('latest').get()
            if not doc.exists: return jsonify({"fulfillmentText": "暫無開獎資料。"})
            data = doc.to_dict()
            msg = (f"【最新開獎號碼】\n開獎期別：115年 03-04月\n\n"
                   f"特別獎: {data['special_prize']}\n特獎: {data['grand_prize']}\n"
                   f"頭獎: {', '.join(data['first_prizes'])}\n\n"
                   f"【獎項說明】\n二獎：對中頭獎後7碼\n三獎：對中頭獎後6碼\n"
                   f"四獎：對中頭獎後5碼\n五獎：對中頭獎後4碼\n六獎：對中頭獎後3碼")
            return jsonify({"fulfillmentText": msg})

        # 2. 查看當月對獎記錄 (優化版：顯示所有紀錄、時間、金額)
        elif action == 'get_history':
            # 設定查詢本月範圍 (這裡以 2026 年 6 月為例)
            start_date = datetime(2026, 6, 1)
            history_ref = db.collection('user_history').where('timestamp', '>=', start_date).order_by('timestamp', direction='DESCENDING')
            docs = history_ref.stream()
            
            msg = f"【{start_date.strftime('%Y/%m')}月 對獎記錄】\n"
            records = []
            for d in docs:
                item = d.to_dict()
                ts = item['timestamp'].strftime('%m/%d %H:%M') if hasattr(item['timestamp'], 'strftime') else "無時間"
                records.append(f"[{ts}] 號碼:{item['number']} -> {item['result']}")
            
            msg += "\n".join(records) if records else "本月尚無對獎紀錄。"
            return jsonify({"fulfillmentText": msg})

        # 3. 既有的對獎功能
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
        return jsonify({"fulfillmentText": f"系統錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run(port=5000)