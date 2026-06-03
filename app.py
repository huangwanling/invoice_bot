from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os, json, re
from datetime import datetime

# ... (Firebase 初始化代碼保持不變) ...

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        req = request.get_json(silent=True, force=True)
        action = req.get('queryResult', {}).get('action')
        
        # --- 優化 1: 查看最新開獎號碼 ---
        if action == 'get_latest_invoice':
            doc = db.collection('invoice_numbers').document('latest').get()
            if not doc.exists: return jsonify({"fulfillmentText": "暫無開獎資料。"})
            data = doc.to_dict()
            msg = (f"【最新開獎號碼】\n"
                   f"開獎期別：115年 03-04月\n\n"
                   f"特別獎: {data['special_prize']}\n"
                   f"特獎: {data['grand_prize']}\n"
                   f"頭獎: {', '.join(data['first_prizes'])}\n\n"
                   f"【獎項說明】\n二獎：對中頭獎後7碼\n三獎：對中頭獎後6碼\n"
                   f"四獎：對中頭獎後5碼\n五獎：對中頭獎後4碼\n六獎：對中頭獎後3碼")
            return jsonify({"fulfillmentText": msg})

        # --- 優化 2: 查看當月對獎記錄 (顯示所有紀錄 + 時間 + 中獎金額) ---
        elif action == 'get_history':
            # 設定本月範圍 (以 2026 年 6 月為例)
            start_date = datetime(2026, 6, 1)
            
            history_ref = db.collection('user_history').where('timestamp', '>=', start_date).order_by('timestamp', direction='DESCENDING')
            docs = history_ref.stream()
            
            msg = f"【{start_date.strftime('%Y/%m')}月 對獎記錄】\n"
            has_record = False
            for d in docs:
                item = d.to_dict()
                ts = item['timestamp'].strftime('%m/%d %H:%M') if hasattr(item['timestamp'], 'strftime') else "未知時間"
                msg += f"[{ts}] 號碼: {item['number']} -> {item['result']}\n"
                has_record = True
            
            return jsonify({"fulfillmentText": msg if has_record else "本月尚無對獎紀錄。"})

        # --- 既有對獎邏輯 ---
        else:
            # ... (保持原本的對獎存入邏輯，存入 'result' 時請直接包含金額) ...
            # 例如：result = "二獎 (4萬元)"
            # db.collection('user_history').add({'number': user_num, 'result': result, 'timestamp': firestore.SERVER_TIMESTAMP})