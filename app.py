from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

app = Flask(__name__)

# 1. 初始化 Firebase
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    if firebase_config:
        cred = credentials.Certificate(json.loads(firebase_config))
    else:
        cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    
    try:
        # 2. 萃取參數並強力防禦：只留下純數字
        parameters = req.get('queryResult', {}).get('parameters', {})
        user_input = parameters.get('invoice_num') or parameters.get('number') or ""
        
        # 強制轉成字串，並用最穩固的方法把數字撈出來
        import re
        raw_digits = ''.join(re.findall(r'\d+', str(user_input)))
        
        # 取最後三碼
        if len(raw_digits) >= 3:
            user_num = raw_digits[-3:]
        else:
            user_num = raw_digits.zfill(3) # 不足3碼自動補零
            
    except Exception as e:
        return jsonify({"fulfillmentText": "哎呀，我沒聽懂號碼，請輸入發票的最後 3 碼數字（例如：520）"})

    if not user_num or user_num == "000":
        return jsonify({"fulfillmentText": "請輸入正確的發票末 3 碼數字喔（例如：810）！"})

    # 3. 去 Firebase 撈取爬蟲抓下來的完整中獎資料
    target_period = "1150304中獎號碼單" 
    doc_ref = db.collection('invoice_numbers').document(target_period)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統目前找不到開獎資料，請先執行爬蟲程式。"})
        
    data = doc.to_dict()
    special = str(data.get('special_prize', '')).strip()
    grand = str(data.get('grand_prize', '')).strip()
    first_list = [str(num).strip() for num in data.get('first_prizes', [])]

    # --- 4. 核心 3 碼直接對獎邏輯 ---
    win_prize = ""
    win_money = 0

    # A. 先比對是否中頭獎的末 3 碼（即六獎 200 元）
    for first_num in first_list:
        if len(first_num) == 8 and user_num == first_num[-3:]:
            win_prize = "頭獎的末3碼（六獎）"
            win_money = 200
            break  # 中了就跳出

    # B. 再比對特獎末 3 碼（如果頭獎沒中）
    if win_money == 0 and len(grand) == 8 and user_num == grand[-3:]:
        win_prize = "特獎的末3碼（有機會中200萬！）"
        win_money = 0  # 特獎必須8碼全中，先不給定額獎金

    # C. 再比對特別獎末 3 碼
    if win_money == 0 and len(special) == 8 and user_num == special[-3:]:
        win_prize = "特別獎的末3碼（有機會中1000萬！）"
        win_money = 0

    # --- 5. 根據結果打包回傳訊息 ---
    if win_money > 0:
        reply = f"🎉 恭喜！末3碼 【{user_num}】 對中 【{win_prize}】！恭喜獲得金額：{win_money} 元！請拿出紙本發票去領獎囉！"
    elif win_prize != "":
        # 針對特獎、特別獎末三碼相符的提示
        reply = f"🚨 喔喔喔！末3碼 【{user_num}】 居然中了 【{win_prize}】！因為這個獎項必須「8碼全中」，請立刻翻開紙本發票確認前面5個數字是不是完全一樣！"
    else:
        reply = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！加油！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)