import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
app = Flask(__name__)
# =========================
# Gemini API
# =========================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# اصلي Model
MODEL = "gemini-2.5-flash"
# که اصلي Model مصروف وي، دا Model وکاروه
FALLBACK_MODEL = "gemini-2.0-flash"
SYSTEM_PROMPT = """
تاسو د Mirwais Shop AI یاست.
لارښوونې:
- د کاروونکي د ژبې مطابق ځواب ورکړه.
- پښتو -> پښتو ځواب
- دري -> دري ځواب
- عربي -> عربي ځواب
- English -> English reply
- لنډ، واضح او دوستانه ځوابونه ورکړه.
- د جامو، ټوکر، دوکان او پیرودونکو پوښتنو کې مرسته وکړه.
- که معلومات نه لرې، په ادب سره ووایه.
- غیر ضروري اوږد ځواب مه ورکوه.
ته د Mirwais Shop استازی یې.
"""
# =========================
# Gemini Function
# =========================
def ask_gemini(customer_message):
    if not GEMINI_API_KEY:
        return "د Gemini API Key نه دی تنظیم شوی."
    prompt = f"""
{SYSTEM_PROMPT}
Customer Message:
{customer_message}
Reply in the same language as the customer.
"""
    models = [
        MODEL,
        FALLBACK_MODEL
    ]
    for current_model in models:
        url = (
            f"https://generativelanguage.googleapis.com/"
            f"v1beta/models/{current_model}:generateContent"
            f"?key={GEMINI_API_KEY}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }
        # 3 attempts
        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=30
                )
                # =========================
                # Success
                # =========================
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            if text:
                                return text
                    return "بښنه غواړم، ځواب ترلاسه نه شو."
                # =========================
                # Gemini Server Busy - 503
                # =========================
                if response.status_code == 503:
                    # لومړی 2 ثانیې، بیا 4، بیا 8
                    wait_time = 2 ** (attempt + 1)
                    time.sleep(wait_time)
                    continue
                # =========================
                # Rate Limit - 429
                # =========================
                if response.status_code == 429:
                    time.sleep(5)
                    continue
                # =========================
                # Other errors
                # =========================
                print(
                    f"Gemini Error {response.status_code}: "
                    f"{response.text}"
                )
                break
            except requests.exceptions.Timeout:
                time.sleep(2)
                continue
            except requests.exceptions.RequestException as e:
                print("Request Error:", e)
                time.sleep(2)
                continue
    return None
# =========================
# Home
# =========================
@app.route("/", methods=["GET"])
def home():
    return "Mirwais WhatsApp Shop Agent Running"
# =========================
# WhatsApp Webhook
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    resp = MessagingResponse()
    reply = resp.message()
    # که پیغام خالي وي
    if not incoming_msg:
        reply.body(
            "مهرباني وکړئ خپل پیغام ولیکئ."
        )
        return str(resp)
    try:
        # Gemini ته پیغام واستوه
        answer = ask_gemini(incoming_msg)
        # =========================
        # Gemini جواب
        # =========================
        if answer:
            # WhatsApp اوږد متن محدودوو
            reply.body(answer[:1500])
        else:
            reply.body(
                "اوس مهال زموږ AI سرور مصروف دی. "
                "لږ وروسته بیا هڅه وکړئ."
            )
    except Exception as e:
        print("Webhook Error:", e)
        reply.body(
            "موقتي ستونزه رامنځته شوه، "
            "لږ وروسته بیا هڅه وکړئ."
        )
    return str(resp)
# =========================
# Run Server
# =========================
if __name__ == "__main__":
    port = int(
        os.environ.get("PORT", 10000)
    )
    app.run(
        host="0.0.0.0",
        port=port
    )
