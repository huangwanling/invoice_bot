from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import re

app = Flask(__name__)

# 初始化 Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def get_prize_info(user_num, data):
    special = data.get('special_prize')
    grand = data.get('grand_prize')
    first_list = data.get('first_prizes', [])
    
    # 8碼完全比對
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
    
    # 僅輸入3碼比對 (對中頭獎的末三碼)
    elif len(user_num) == 3:
        for f in first_list:
            if user_num == f[-3:]: return "六獎 (200元)"
            
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    params = req.get('queryResult', {}).get('parameters', {})
    
    # 優先抓取 Dialogflow 的 number 參數，若無則用正規表達式補抓
    user_num = params.get('number')
    if user_num is None or user_num == "":
        query_text = req.get('queryResult', {}).get('queryText', '')
        digits = re.findall(r'\d+', str(query_text))
        user_num = digits[-1] if digits else None
    
    # 格式化數字
    if user_num:
        user_num = str(int(float(user_num)))
    else:
        return jsonify({"fulfillmentText": "請輸入有效的發票號碼"})

    # 從 Firebase 讀取開獎資料
    doc = db.collection('invoice_numbers').document('latest').get()
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統暫無開獎資料，請稍後。"})
        
    data = doc.to_dict()
    result = get_prize_info(user_num, data)
    
    if result:
        reply = f"🎉 恭喜！號碼 {user_num} 對中 【{result}】！"
    else:
        reply = f"❌ 號碼 {user_num} 未中獎，再接再厲！"
        
    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run(port=5000)

