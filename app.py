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
        # 2. 精準抓取 Dialogflow 參數，轉為字串並移除前後空白
        parameters = req.get('queryResult', {}).get('parameters', {})
        user_input = parameters.get('invoice_num') or parameters.get('number') or ""
        user_num = str(user_input).strip()
    except Exception as e:
        return jsonify({"fulfillmentText": "請輸入發票號碼數字（例如：520 或完整 8 碼）"})

    if not user_num.isdigit():
        return jsonify({"fulfillmentText": "請輸入純數字的發票號碼喔！"})

    # 3. 去 Firebase 撈取最新一期完整中獎資料
    target_period = "1150304中獎號碼單" 
    doc_ref = db.collection('invoice_numbers').document(target_period)
    doc = doc_ref.get()
    
    if not doc.exists:
        return jsonify({"fulfillmentText": "系統目前找不到開獎資料，請先確認爬蟲有成功執行。"})
        
    data = doc.to_dict()
    special = str(data.get('special_prize', '')).strip()
    grand = str(data.get('grand_prize', '')).strip()
    first_list = [str(num).strip() for num in data.get('first_prizes', [])]

    # --- 核心對獎邏輯 (支援 8 碼與 3 碼) ---
    
    # 情況 A：使用者輸入完整 8 碼
    if len(user_num) == 8:
        if user_num == special:
            reply = f"🎉 哇！！！恭喜你中了 【特別獎】 1,000 萬元！快去買透天厝了！"
        elif user_num == grand:
            reply = f"🎉 恭喜中了 【特獎】 200 萬元！太幸運了吧！"
        else:
            # 頭獎到六獎比對
            win_prize = ""
            win_money = 0
            
            for first_num in first_list:
                if len(first_num) != 8:
                    continue
                if user_num == first_num:
                    win_prize, win_money = "頭獎", 200000
                    break
                elif user_num[-7:] == first_num[-7:]:
                    win_prize, win_money = "二獎", 40000
                elif user_num[-6:] == first_num[-6:]:
                    win_prize, win_money = "三獎", 10000
                elif user_num[-5:] == first_num[-5:]:
                    win_prize, win_money = "四獎", 4000
                elif user_num[-4:] == first_num[-4:]:
                    win_prize, win_money = "五獎", 1000
                elif user_num[-3:] == first_num[-3:]:
                    if win_money < 200: # 避免蓋掉更高的頭/二/三/四/五獎
                        win_prize, win_money = "六獎", 200

            if win_money > 0:
                reply = f"🎉 恭喜！號碼 【{user_num}】 對中 【{win_prize}】！可獲得金額：{win_money:,} 元！"
            else:
                reply = f"❌ 殘念！完整號碼 【{user_num}】 沒有中獎，下一張會更好！"

    # 情況 B：使用者只輸入末 3 碼（標準快捷對獎）
    elif len(user_num) == 3:
        # 收集所有開獎號碼的末三碼
        possible_3_digits = [special[-3:], grand[-3:]] + [f[-3:] for f in first_list if len(f) == 8]
        
        if user_num in possible_3_digits:
            reply = f"🔍 💡 喔喔喔！末3碼 【{user_num}】 有機會中獎喔！請輸入「完整的 8 位數發票號碼」，我幫你算算看中什麼獎、拿多少錢！"
        else:
            reply = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！加油！"
            
    else:
        reply = f"請輸入「3位數」或「8位數」的發票號碼才可以幫你對獎喔！"

    return jsonify({"fulfillmentText": reply})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)