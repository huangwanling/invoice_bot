from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os, json, re

app = Flask(__name__)

# 初始化 Firebase
if not firebase_admin._apps:
    cred_json = os.environ.get('FIREBASE_KEY_JSON')
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    # 直接抓取原始對話文字，避免被 Dialogflow 參數解析干擾
    text = req.get('queryResult', {}).get('queryText', '')
    digits = re.findall(r'\d+', str(text))
    
    if not digits:
        return jsonify({"fulfillmentText": "請輸入發票號碼數字喔！"})
    
    user_num = digits[-1] # 取最後一組數字

    # 讀取最新資料
    doc = db.collection('invoice_numbers').document("latest_invoice").get()
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統資料庫尚未更新，請稍後再試。"})
    
    data = doc.to_dict()
    special = data.get('special_prize', '')
    grand = data.get('grand_prize', '')
    first_list = data.get('first_prizes', [])

    # 判斷邏輯 (支援 8 碼完整比對或末 3 碼比對)
    if len(user_num) == 8:
        if user_num == special: reply = "🎉 恭喜中了特別獎 1,000 萬元！"
        elif user_num == grand: reply = "🎉 恭喜中了特獎 200 萬元！"
        else:
            # 檢查頭獎及後續各獎項
            reply = "❌ 殘念！號碼沒有中獎，再接再厲！"
            for f in first_list:
                if user_num == f: reply = "🎉 恭喜中了頭獎 20 萬元！"; break
                elif user_num[-3:] == f[-3:]: reply = "🎉 恭喜中了六獎 200 元！"; break
    else:
        # 末 3 碼比對邏輯
        three_digit = user_num[-3:].zfill(3)
        if three_digit in [special[-3:], grand[-3:]] + [f[-3:] for f in first_list]:
            reply = f"🔍 末3碼 【{three_digit}】 好像有機會！請輸入完整 8 碼確認是否中獎！"
        else:
            reply = f"❌ 號碼 【{three_digit}】 沒中，再接再厲！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run()