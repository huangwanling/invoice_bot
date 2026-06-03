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
    
    # 1. 精確比對 (完整 8 碼)
    if len(user_num) == 8:
        if user_num == special: return "特別獎 (1,000萬元)"
        if user_num == grand: return "特獎 (200萬元)"
        if user_num in first_list: return "頭獎 (20萬元)"
        
    # 2. 比對二至六獎 (不論輸入幾碼)
    msg_list = []
    for f in first_list:
        if len(user_num) >= 7 and user_num[-7:] == f[-7:]: msg_list.append("二獎 (4萬元)")
        elif len(user_num) >= 6 and user_num[-6:] == f[-6:]: msg_list.append("三獎 (1萬元)")
        elif len(user_num) >= 5 and user_num[-5:] == f[-5:]: msg_list.append("四獎 (4,000元)")
        elif len(user_num) >= 4 and user_num[-4:] == f[-4:]: msg_list.append("五獎 (1,000元)")
        elif len(user_num) >= 3 and user_num[-3:] == f[-3:]: msg_list.append("六獎 (200元)")

    # 3. 智慧提示邏輯 (輸入不足 8 碼)
    if len(user_num) < 8:
        result_str = "、".join(list(set(msg_list))) if msg_list else ""
        
        # 檢查大獎尾數
        is_special = (user_num == special[-len(user_num):])
        is_grand = (user_num == grand[-len(user_num):])
        
        if is_special or is_grand or msg_list:
            hint = f"{result_str} " if result_str else ""
            return f"{hint}(該號碼亦有可能是頭獎、特別獎或特獎，請輸入完整8碼確認)"

    return "、".join(list(set(msg_list))) if msg_list else "未中獎"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        user_id = req.get('originalDetectIntentRequest', {}).get('payload', {}).get('data', {}).get('source', {}).get('userId')
        action = req.get('queryResult', {}).get('action')
        
        # 功能：查看最新開獎 (顯示格式優化)
        if action == 'get_latest_invoice':
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            msg = (f"【最新開獎號碼】\n開獎期別：115年 03-04月\n\n"
                   f"特別獎: {data['special_prize']} (1,000萬元)\n"
                   f"特獎: {data['grand_prize']} (200萬元)\n"
                   f"頭獎: {', '.join(data['first_prizes'])} (20萬元)\n\n"
                   f"【獎項說明】\n二獎：對中頭獎後7碼 (4萬元)\n"
                   f"三獎：對中頭獎後6碼 (1萬元)\n四獎：對中頭獎後5碼 (4,000元)\n"
                   f"五獎：對中頭獎後4碼 (1,000元)\n六獎：對中頭獎後3碼 (200元)")
            return jsonify({"fulfillmentText": msg})

        # 功能：查看個人紀錄 (含時間轉換)
        elif action == 'get_history':
            if not user_id: return jsonify({"fulfillmentText": "無法辨識身分。"})
            docs = db.collection('user_history').where('userId', '==', user_id).order_by('timestamp', direction='DESCENDING').limit(15).stream()
            msg = "【您的個人對獎紀錄】\n"
            records = [f"[{ (d.to_dict()['timestamp'].replace(tzinfo=None) + timedelta(hours=8)).strftime('%m/%d %H:%M') }] {d.to_dict()['number']}: {d.to_dict()['result']}" for d in docs]
            return jsonify({"fulfillmentText": msg + "\n".join(records) if records else "尚無紀錄。"})

        # 功能：對獎邏輯
        else:
            query_text = req.get('queryResult', {}).get('queryText', '')
            digits = re.findall(r'\d+', str(query_text))
            user_num = digits[-1] if digits else None
            if not user_num: return jsonify({"fulfillmentText": "請輸入有效數字。"})
            
            data = db.collection('invoice_numbers').document('latest').get().to_dict()
            result = get_prize_info(user_num, data)
            reply = f"🎉 恭喜！【{user_num}】 中了 【{result}】！" if result != "未中獎" else f"❌ 【{user_num}】 未中獎。"
            
            if user_id:
                db.collection('user_history').add({'userId': user_id, 'number': user_num, 'result': result, 'timestamp': firestore.SERVER_TIMESTAMP})
            return jsonify({"fulfillmentText": reply})

    except Exception as e:
        return jsonify({"fulfillmentText": f"系統錯誤: {str(e)}"})

if __name__ == '__main__':
    app.run(port=5000)