import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """
تاسو د میرویس (Mirwais) په نوم د آنلاین پلورنځي مرستیال یاست.
تل په درانه، دوستانه او روانو پښتو خبرو ځواب ورکړئ.
د پیرودونکو له پوښتنو سره مرسته وکړئ.
"""

@app.route("/", methods=["GET"])
def home():
    return "Mirwais WhatsApp Shop Agent is Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    reply = resp.message()

    if not incoming_msg:
        reply.body("سلام! څنګه کولای شم ستاسو مرسته وکړم؟")
        return str(resp)

    try:
        if GEMINI_API_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            payload = {
                "contents": [{
                    "parts": [{"text": f"{SYSTEM_PROMPT}\n\nUser: {incoming_msg}\nMirwais:"}]
                }]
            }
            
            response = requests.post(url, json=payload, headers=headers)
            res_data = response.json()
            
            if response.status_code == 200 and 'candidates' in res_data:
                ai_text = res_data['candidates'][0]['content']['parts'][0]['text']
                reply.body(ai_text)
            else:
                print("Gemini API Error:", res_data)
                reply.body("مننه ستاسو له پیغام څخه! زما د ځواب ورکولو سیستم اوس مهال مصروف دی.")
        else:
            reply.body("په بخښنه سره، د هوښیار سیستم په تنظیم کې ستونزه شته.")
    except Exception as e:
        print(f"Error: {e}")
        reply.body("مننه ستاسو له پیغام څخه! زما د ځواب ورکولو سیستم اوس مهال مصروف دی.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
