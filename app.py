import os
import json
import firebase_admin
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore

app = Flask(__name__)

# 初始化 Firebase
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        # 雲端 Vercel 環境使用
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        # 本地測試使用
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    try:
        user_number = req['queryResult']['parameters']['number']
        user_number = str(int(user_number))
    except:
        return jsonify({"fulfillmentText": "抱歉，無法識別您輸入的號碼。"})

    # 讀取 Firebase 最新資料
    doc = db.collection('invoice_numbers').document('latest').get()
    if not doc.exists:
        return jsonify({"fulfillmentText": "資料庫尚未更新，請稍後。"})

    data = doc.to_dict()
    # 確保這些欄位名稱與您 Firestore 截圖中的名稱一致
    special = data.get('special_prize')
    grand = data.get('grand_prize')
    first = data.get('first_prize', [])

    if user_number == special:
        reply = f"恭喜！號碼【{user_number}】中了特別獎！"
    elif user_number == grand:
        reply = f"恭喜！號碼【{user_number}】中了特獎！"
    elif user_number in first:
        reply = f"恭喜！號碼【{user_number}】中了頭獎！"
    else:
        reply = f"號碼【{user_number}】沒中獎，加油！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    app.run()