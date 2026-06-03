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
    
    # 1. 完整八碼對獎
    if len(user_num) == 8:
        if user_num == special: return "特別獎 (1,000萬元)"
        if user_num == grand: return "特獎 (200萬元)"
        if user_num in first_list: return "頭獎 (20萬元)"
        
    # 2. 比對二至六獎
    msg_list = []
    for f in first_list:
        if len(user_num) >= 7 and user_num[-7:] == f[-7:]: msg_list.append("二獎 (4萬元)")
        elif len(user_num) >= 6 and user_num[-6:] == f[-6:]: msg_list.append("三獎 (1萬元)")
        elif len(user_num) >= 5 and user_num[-5:] == f[-5:]: msg_list.append("四獎 (4,000元)")
        elif len(user_num) >= 4 and user_num[-4:] == f[-4:]: msg_list.append("五獎 (1,000元)")
        elif len(user_num) >= 3 and user_num[-3:] == f[-3:]: msg_list.append("六獎 (200元)")

    # 3. 智慧提示
    if len(user_num) < 8:
        if msg_list:
            base_msg = "、".join(list(set(msg_list)))
            return f"{base_msg} (該號碼亦有可能是頭獎或更高獎項，請輸入完整8碼確認)"
        if user_num == special[-len(user_num):]: return f"疑似特別獎 (末{len(user_num)}碼相符，請輸入完整8碼確認)"
        if user_num == grand[-len(user_num):]: return f"疑似特獎 (末{len(user_num)}碼相符，請輸入完整8碼確認)"
            
    return "未中獎" if not msg_list else "、".join(list(set(msg_list)))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        user_id = req.get('originalDetectIntentRequest', {}).get('payload', {}).get('data', {}).get('source', {}).get('userId')
        action = req.get('queryResult', {}).get('action')
        
        # 功能：查看最新開獎
        if action == 'get_latest_invoice':
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            msg = (f"【最新開獎號碼】\n期別：{data.get('period', '115年 03-04月')}\n\n"
                   f"特別獎: {data['special_prize']} (1,000萬元)\n"
                   f"特獎: {data['grand_prize']} (200萬元)\n"
                   f"頭獎: {', '.join(data['first_prizes'])} (20萬元)\n\n"
                   f"【獎項說明】\n二獎：對中頭獎後7碼 (4萬元)\n三獎：對中頭獎後6碼 (1萬元)\n"
                   f"四獎：對中頭獎後5碼 (4,000元)\n五獎：對中頭獎後4碼 (1,000元)\n六獎：對中頭獎後3碼 (200元)")
            return jsonify({"fulfillmentText": msg})

        # 功能：查看個人當月紀錄 (簡潔清爽版)
        elif action == 'get_history':
            if not user_id: return jsonify({"fulfillmentText": "無法辨識身分。"})
            now = datetime.now()
            start_date = datetime(now.year, now.month, 1)
            docs = db.collection('user_history').where('userId', '==', user_id).where('timestamp', '>=', start_date).order_by('timestamp', direction='DESCENDING').limit(20).stream()
            
            win_records, lose_records = [], []
            for d in docs:
                item = d.to_dict()
                res = item['result']
                if "未中獎" not in res and "疑似" not in res: win_records.append(f"{item['number']} -> {res}")
                else: lose_records.append(item['number'])
            
            msg = f"【{now.month}月份 對獎紀錄】\n\n"
            if win_records: msg += "🎉 中獎：\n" + "\n".join(win_records) + "\n\n"
            if lose_records: msg += "❌ 未中獎：\n" + ", ".join(lose_records)
            return jsonify({"fulfillmentText": msg if (win_records or lose_records) else "本月尚無紀錄。"})

        # 功能：對獎
        else:
            query_text = req.get('queryResult', {}).get('queryText', '')
            digits = re.findall(r'\d+', str(query_text))
            user_num = digits[-1] if digits else None
            if not user_num: return jsonify({"fulfillmentText": "請輸入有效數字。"})
            
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            result = get_prize_info(user_num, data)
            reply = f"🎉 恭喜！【{user_num}】 中了 【{result}】！" if ("未中獎" not in result and "疑似" not in result) else f"❌ 【{user_num}】 {result}。"
            
            if user_id:
                db.collection('user_history').add({'userId': user_id, 'number': user_num, 'result': result, 'timestamp': firestore.SERVER_TIMESTAMP})
            return jsonify({"fulfillmentText": reply})

    except Exception as e:
        return jsonify({"fulfillmentText": f"系統錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run(port=5000)