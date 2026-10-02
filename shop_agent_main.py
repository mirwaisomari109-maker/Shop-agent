import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
import google.generativeai as genai

app = Flask(__name__)

# API تنظیمات
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYSTEM_PROMPT = """
تاسو د میرویس (Mirwais) په نوم د آنلاین پلورنځي ژوندی او مرستندوی پښتو ژبی ایجنټ یاست.
ستاسو دنده د پیرودونکو سره په ډېره نرمه، پښتنی او مسلکي ژبه خبرې کول، د محصولاتو ښودل او د امرونو راټولول دي.
تل په روانه پښتو ځواب ورکوئ.
"""

@app.route("/", methods=["GET"])
def home():
    return "Mirwais WhatsApp Shop Agent is Running!", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    reply = resp.message()

    if not incoming_msg:
        reply.body("سلامونه! څنګه کولای شم درسره مرسته وکړم؟")
        return str(resp)

    try:
        if client:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": incoming_msg}
                ],
                max_tokens=300
            )
            bot_reply = response.choices[0].message.content
        elif GEMINI_API_KEY:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(f"{SYSTEM_PROMPT}\n\nکاروونکی: {incoming_msg}")
            bot_reply = response.text
        else:
            bot_reply = "په بخښنه سره، د هوښیار سیسټم په تنظیم کې ستونزه شته."
    except Exception as e:
        bot_reply = "مننه ستاسو له پیغام څخه! زما د ځواب ورکولو سیسټم اوس مهال مصروف دی."

    reply.body(bot_reply)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
