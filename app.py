from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
import re

app = Flask(__name__)

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
        parameters = req.get('queryResult', {}).get('parameters', {})
        user_input = parameters.get('invoice_num') or parameters.get('number') or ""
        # 僅保留數字
        user_num = ''.join(re.findall(r'\d+', str(user_input)))
    except Exception as e:
        return jsonify({"fulfillmentText": "請輸入發票號碼數字（例如：520 或完整 8 碼）"})

    if not user_num:
        return jsonify({"fulfillmentText": "請輸入正確的發票號碼數字。"})

    # 撈取 Firebase 完整資料
    target_period = "1150304中獎號碼單" 
    doc_ref = db.collection('invoice_numbers').document(target_period)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統目前找不到開獎資料，請先執行爬蟲。"})
        
    data = doc.to_dict()
    special = data.get('special_prize', '')
    grand = data.get('grand_prize', '')
    first_list = data.get('first_prizes', [])

    # --- 判斷邏輯開始 ---
    
    # 情況一：使用者輸入完整的 8 位數號碼
    if len(user_num) == 8:
        if user_num == special:
            reply = f"🎉 哇！恭喜中了 【特別獎】 1,000 萬元！天啊快去領獎！"
        elif user_num == grand:
            reply = f"🎉 恭喜中了 【特獎】 200 萬元！太幸運了！"
        else:
            # 比對頭獎到六獎
            max_prize_name = ""
            max_prize_money = 0
            
            for first_num in first_list:
                if user_num == first_num:
                    max_prize_name, max_prize_money = "頭獎", 200000
                    break
                elif user_num[-7:] == first_num[-7:]:
                    max_prize_name, max_prize_money = "二獎", 40000
                elif user_num[-6:] == first_num[-6:]:
                    max_prize_name, max_prize_money = "三獎", 10000
                elif user_num[-5:] == first_num[-5:]:
                    max_prize_name, max_prize_money = "四獎", 4000
                elif user_num[-4:] == first_num[-4:]:
                    max_prize_name, max_prize_money = "五獎", 1000
                elif user_num[-3:] == first_num[-3:]:
                    if max_prize_money < 200: # 確保不蓋掉更高的獎
                        max_prize_name, max_prize_money = "六獎", 200

            if max_prize_money > 0:
                reply = f"🎉 恭喜！號碼 【{user_num}】 對中 【{max_prize_name}】！可獲得金額：{max_prize_money:,} 元！"
            else:
                reply = f"❌ 殘念！完整號碼 【{user_num}】 沒有中獎，再接再厲！"

    # 情況二：使用者只輸入末 3 碼
    else:
        three_digit = user_num[-3:].zfill(3)
        # 收集所有中獎號碼的末三碼
        possible_3_digits = [special[-3:], grand[-3:]] + [f[-3:] for f in first_list]
        
        if three_digit in possible_3_digits:
            reply = f"🔍 💡 喔！末3碼 【{three_digit}】 好像有機會喔！請輸入「完整的8位數發票號碼」，我幫你算算看中了什麼獎跟多少錢！"
        else:
            reply = f"❌ 號碼 【{three_digit}】 沒中，下張再接再厲！加油！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)