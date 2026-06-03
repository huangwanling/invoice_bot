from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os, json, re
from datetime import datetime, timedelta

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

def get_prize_info(user_num, data):
    special, grand = data.get('special_prize'), data.get('grand_prize')
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
        # 取得 userId
        user_id = req.get('originalDetectIntentRequest', {}).get('payload', {}).get('data', {}).get('source', {}).get('userId')
        action = req.get('queryResult', {}).get('action')
        
        # --- 新功能 1: 最新開獎號碼 ---
        if action == 'get_latest_invoice':
            doc = db.collection('invoice_numbers').document('latest').get()
            data = doc.to_dict()
            msg = (f"【最新開獎號碼】\n特別獎: {data['special_prize']}\n特獎: {data['grand_prize']}\n"
                   f"頭獎: {', '.join(data['first_prizes'])}\n\n"
                   f"二獎：對中頭獎後7碼\n三獎：對中頭獎後6碼\n四獎：對中頭獎後5碼\n五獎：對中頭獎後4碼\n六獎：對中頭獎後3碼")
            return jsonify({"fulfillmentText": msg})

        # --- 新功能 2: 個人歷史紀錄 (僅限自己) ---
        elif action == 'get_history':
            if not user_id: return jsonify({"fulfillmentText": "無法識別用戶身份。"})
            start_date = datetime(2026, 6, 1) # 設定當月開始日期
            
            # 使用 userId 過濾與 timestamp 排序
            docs = db.collection('user_history').where('userId', '==', user_id)\
                .where('timestamp', '>=', start_date).order_by('timestamp', direction='DESCENDING').stream()
            
            msg = "【您的當月對獎紀錄】\n"
            records = []
            for d in docs:
                item = d.to_dict()
                # 轉為台灣時間 (+8小時)
                ts = (item['timestamp'].replace(tzinfo=None) + timedelta(hours=8)).strftime('%m/%d %H:%M')
                records.append(f"[{ts}] {item['number']} -> {item['result']}")
            
            return jsonify({"fulfillmentText": msg + "\n".join(records) if records else "尚無紀錄。"})

        # --- 既有對獎功能 ---
        else:
            params = req.get('queryResult', {}).get('parameters', {})
            user_num = params.get('number')
            if not user_num:
                digits = re.findall(r'\d+', str(req.get('queryResult', {}).get('queryText', '')))
                user_num = digits[-1] if digits else None
            
            if not user_num: return jsonify({"fulfillmentText": "請輸入發票號碼。"})
            user_num = str(int(float(user_num)))
            
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            result = get_prize_info(user_num, data)
            reply = f"🎉 恭喜！號碼 【{user_num}】 對中 【{result}】！" if result else f"❌ 號碼 【{user_num}】 未中獎。"
            
            # 存入時帶入 userId
            if user_id:
                db.collection('user_history').add({
                    'userId': user_id,
                    'number': user_num,
                    'result': result if result else "未中獎",
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
            return jsonify({"fulfillmentText": reply})

    except Exception as e:
        return jsonify({"fulfillmentText": f"錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run(port=5000)