import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

app = Flask(__name__)

# Gemini API تنظیمول
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
            # د ماډل سمه بڼه
            model = genai.GenerativeModel('models/gemini-1.5-flash')
            prompt = f"{SYSTEM_PROMPT}\n\nUser: {incoming_msg}\nMirwais:"
            response = model.generate_content(prompt)
            reply.body(response.text)
        else:
            reply.body("په بخښنه سره، د هوښیار سیستم په تنظیم کې ستونزه شته.")
    except Exception as e:
        print(f"Error: {e}")
        reply.body("مننه ستاسو له پیغام څخه! زما د ځواب ورکولو سیستم اوس مهال مصروف دی.")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
