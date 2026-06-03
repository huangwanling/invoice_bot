from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import re

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
        # 🔥【終極解法】不拿 parameters，改成直接拿使用者在 LINE 輸入的「整句原始文字」
        user_raw_text = req.get('queryResult', {}).get('queryText', '')
        
        # 用正規表達式，只把這句話裡面的「連續數字」抓出來
        # 例如："幫我對810" -> "810"
        digits_list = re.findall(r'\d+', str(user_raw_text))
        
        if digits_list:
            # 抓出對話中的第一組數字，並確保只取最後 3 碼
            user_num = digits_list[0][-3:].zfill(3)
        else:
            user_num = ""
            
    except Exception as e:
        return jsonify({"fulfillmentText": "系統忙碌中，請輸入發票最後 3 碼數字（例如：810）"})

    # 防呆：如果使用者打的句子裡根本沒有數字
    if not user_num:
        return jsonify({"fulfillmentText": "請在訊息中輸入正確的 3 碼發票數字喔！"})

    # 2. 去 Firebase 撈取爬蟲抓下來的完整中獎資料
    target_period = "1150304中獎號碼單" 
    doc_ref = db.collection('invoice_numbers').document(target_period)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統目前找不到開獎資料，請先確認爬蟲有成功執行。"})
        
    data = doc.to_dict()
    special = str(data.get('special_prize', '')).strip()
    grand = str(data.get('grand_prize', '')).strip()
    first_list = [str(num).strip() for num in data.get('first_prizes', [])]

    # --- 3. 核心 3 碼直接對獎與獎金判定邏輯 ---
    win_prize = ""
    win_money = 0

    # A. 先比對是否中頭獎的末 3 碼（即六獎 200 元）
    for first_num in first_list:
        if len(first_num) == 8 and user_num == first_num[-3:]:
            win_prize = "頭獎的末3碼（六獎）"
            win_money = 200
            break

    # B. 再比對特獎末 3 碼
    if win_money == 0 and len(grand) == 8 and user_num == grand[-3:]:
        win_prize = "特獎的末3碼（極高機率中特獎200萬！）"
        win_money = 0

    # C. 再比對特別獎末 3 碼
    if win_money == 0 and len(special) == 8 and user_num == special[-3:]:
        win_prize = "特別獎的末3碼（極高機率中特別獎1000萬！）"
        win_money = 0

    # --- 4. 打包回傳訊息 ---
    if win_money > 0:
        reply = f"🎉 恭喜！末3碼 【{user_num}】 對中 【{win_prize}】！恭喜獲得金額：{win_money} 元！請拿出紙本發票去領獎囉！"
    elif win_prize != "":
        reply = f"🚨 喔喔喔！末3碼 【{user_num}】 中了 【{win_prize}】！因為這個大獎必須「8碼全中」，請趕快翻開紙本發票確認前面5個數字是不是完全一樣！"
    else:
        reply = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！加油！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)