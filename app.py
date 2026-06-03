from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import re

app = Flask(__name__)

# 1. 初始化 Firebase
if not firebase_admin._apps:
    # 如果部署在 Vercel，讀取環境變數裡的 JSON 金鑰
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        # 如果在本機測試，讀取本地的 json 檔案
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    
    # 2. 獲取使用者訊息並提取數字
    user_raw_text = req.get('queryResult', {}).get('queryText', '')
    digits = re.findall(r'\d+', str(user_raw_text))
    
    if not digits:
        return jsonify({"fulfillmentText": "請輸入發票號碼數字（例如：810）"})
    
    # 取最後一組數字的後 3 碼
    user_num = digits[-1][-3:].zfill(3)

    # 3. 讀取 Firebase 最新資料
    doc_ref = db.collection('invoice_numbers').document("latest_invoice")
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統目前沒有開獎資料，請先執行爬蟲程式。"})
        
    data = doc.to_dict()
    special = str(data.get('special_prize', '')).strip()
    grand = str(data.get('grand_prize', '')).strip()
    first_list = [str(num).strip() for num in data.get('first_prizes', [])]

    # 4. 對獎邏輯 (優先從頭獎末三碼判斷六獎)
    win_prize = ""
    win_money = 0

    # 比對頭獎末三碼 (六獎)
    for first_num in first_list:
        if len(first_num) >= 3 and user_num == first_num[-3:]:
            win_prize = "頭獎末3碼 (六獎)"
            win_money = 200
            break

    # 比對特獎末三碼
    if win_money == 0 and len(grand) >= 3 and user_num == grand[-3:]:
        win_prize = "特獎末3碼 (有機會中200萬)"
        win_money = 0

    # 比對特別獎末三碼
    if win_money == 0 and len(special) >= 3 and user_num == special[-3:]:
        win_prize = "特別獎末3碼 (有機會中1000萬)"
        win_money = 0

    # 5. 回傳結果
    if win_money > 0:
        reply = f"🎉 恭喜！末3碼 【{user_num}】 對中 【{win_prize}】！獎金：{win_money} 元！"
    elif win_prize != "":
        reply = f"🚨 末3碼 【{user_num}】 中了 【{win_prize}】！這需要8碼全對才能領獎，請翻開紙本發票確認前面的數字！"
    else:
        reply = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)