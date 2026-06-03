from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os, json, re
from datetime import datetime, timedelta

app = Flask(__name__)

# Firebase 初始化
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    cred = credentials.Certificate(json.loads(firebase_config)) if firebase_config else credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def get_prize_info(user_num, data):
    special = data.get('special_prize')
    grand = data.get('grand_prize')
    first_list = data.get('first_prizes', [])
    
    # 1. 精確比對 (需8碼)
    if len(user_num) == 8:
        if user_num == special: return "特別獎 (1,000萬元)"
        if user_num == grand: return "特獎 (200萬元)"
        if user_num in first_list: return "頭獎 (20萬元)"
        
    # 2. 比對二至六獎
    for f in first_list:
        if len(user_num) >= 7 and user_num[-7:] == f[-7:]: return "二獎 (4萬元)"
        if len(user_num) >= 6 and user_num[-6:] == f[-6:]: return "三獎 (1萬元)"
        if len(user_num) >= 5 and user_num[-5:] == f[-5:]: return "四獎 (4,000元)"
        if len(user_num) >= 4 and user_num[-4:] == f[-4:]: return "五獎 (1,000元)"
        if len(user_num) >= 3 and user_num[-3:] == f[-3:]: return "六獎 (200元)"
            
    # 3. 智慧提示 (大獎尾數)
    if len(user_num) < 8:
        if user_num == special[-len(user_num):]: return f"疑似特別獎 (末{len(user_num)}碼相符，請核對完整8碼)"
        if user_num == grand[-len(user_num):]: return f"疑似特獎 (末{len(user_num)}碼相符，請核對完整8碼)"
            
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        user_id = req.get('originalDetectIntentRequest', {}).get('payload', {}).get('data', {}).get('source', {}).get('userId')
        action = req.get('queryResult', {}).get('action')
        
        # 功能：查看開獎號碼
        if action == 'get_latest_invoice':
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            msg = f"【最新開獎號碼】\n特別獎: {data['special_prize']}\n特獎: {data['grand_prize']}\n頭獎: {', '.join(data['first_prizes'])}"
            return jsonify({"fulfillmentText": msg})

        # 功能：查看個人紀錄
        elif action == 'get_history':
            if not user_id: return jsonify({"fulfillmentText": "無法辨識身分。"})
            docs = db.collection('user_history').where('userId', '==', user_id).order_by('timestamp', direction='DESCENDING').limit(15).stream()
            msg = "【您的個人對獎紀錄】\n"
            records = [f"[{ (d.to_dict()['timestamp'].replace(tzinfo=None) + timedelta(hours=8)).strftime('%m/%d %H:%M') }] {d.to_dict()['number']}: {d.to_dict()['result']}" for d in docs]
            return jsonify({"fulfillmentText": msg + "\n".join(records) if records else "尚無紀錄。"})

        # 功能：對獎
        else:
            query_text = req.get('queryResult', {}).get('queryText', '')
            digits = re.findall(r'\d+', str(query_text))
            user_num = digits[-1] if digits else None
            if not user_num: return jsonify({"fulfillmentText": "請輸入有效數字。"})
            
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            result = get_prize_info(user_num, data)
            reply = f"🎉 恭喜！【{user_num}】 中了 【{result}】！" if result else f"❌ 【{user_num}】 未中獎。"
            
            if user_id:
                db.collection('user_history').add({'userId': user_id, 'number': user_num, 'result': result or "未中獎", 'timestamp': firestore.SERVER_TIMESTAMP})
            return jsonify({"fulfillmentText": reply})

    except Exception as e:
        return jsonify({"fulfillmentText": f"系統錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run(port=5000)