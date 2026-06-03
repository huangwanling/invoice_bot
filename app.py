from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

app = Flask(__name__)

# 1. 安全初始化 Firebase (支援雲端環境變數與本機檔案)
if not firebase_admin._apps:
    # 優先讀取 Vercel 雲端環境變數
    firebase_config = os.environ.get('FIREBASE_KEY_JSON')
    
    if firebase_config:
        try:
            # 雲端環境：將 Vercel 的字串密鑰轉回 JSON 字典
            cred_dict = json.loads(firebase_config)
            cred = credentials.Certificate(cred_dict)
        except Exception as e:
            print(f"解析環境變數失敗: {e}")
            cred = None
    else:
        # 本地電腦測試環境：直接讀取 D:\invoice_bot 裡面的實體檔案
        if os.path.exists("firebase_key.json"):
            cred = credentials.Certificate("firebase_key.json")
        else:
            cred = None
            print("找不到任何 Firebase 金鑰設定！")

    if cred:
        firebase_admin.initialize_app(cred)

db = firestore.client()

@app.route('/webhook', methods=['POST'])
def webhook():
    # 2. 接收從 Dialogflow 傳過來的 JSON 資料
    req = request.get_json(silent=True, force=True)
    
    try:
        # 3. 萃取出使用者輸入的發票號碼參數
        user_input = req.get('queryResult').get('parameters').get('invoice_num')
        
        # 防呆機制：自動補足成三位數
        user_num = str(int(user_input)).zfill(3)
    except Exception as e:
        return jsonify({"fulfillmentText": "哎呀，我沒聽懂號碼，請輸入發票的最後 3 碼數字（例如：520）"})

    # 4. 去 Firebase 撈取最新一期的中獎資料
    target_period = "1150304中獎號碼單" 
    doc_ref = db.collection('invoice_numbers').document(target_period)
    doc = doc_ref.get()
    
    if doc.exists:
        three_digits_list = doc.to_dict().get('three_digits', [])
        
        # 5. 核心對獎邏輯比對
        if user_num in three_digits_list:
            reply = f"🎉 恭喜！末3碼 【{user_num}】 有機會中獎，請拿出紙本發票確認完整頭獎號碼！"
        else:
            reply = f"❌ 號碼 【{user_num}】 沒中，下張再接再厲！加油！"
    else:
        reply = f"系統目前找不到 {target_period} 的開獎資料，請先確認爬蟲程式有成功更新資料庫。"

    # 6. 打包成 Dialogflow 看得懂的格式回傳
    return jsonify({"fulfillmentText": reply})

# 7. Vercel 雲端動態 Port 設定
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)