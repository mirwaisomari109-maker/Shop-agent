import os
import time
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
app = Flask(__name__)
# =========================================================
# OPENROUTER
# =========================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# OpenRouter Free Router
MODEL = "openrouter/free"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
# =========================================================
# MIRWAIS SHOP AI
# =========================================================
SYSTEM_PROMPT = """
You are Mirwais Shop AI WhatsApp Assistant.
You represent Mirwais Shop.
Business:
- Women's clothing
- Fabrics
- Wholesale and retail
- Customer support
- Product information
- Prices and availability
LANGUAGE RULE:
If customer writes Pashto:
Reply in Pashto.
If customer writes Dari/Persian:
Reply in Dari/Persian.
If customer writes Arabic:
Reply in Arabic.
If customer writes English:
Reply in English.
IMPORTANT:
- Keep answers short and clear.
- Be polite and friendly.
- Do not give information that you do not know.
- Never invent prices, stock, colors, sizes or products.
- If you don't know something, politely say that the shop needs to confirm it.
- Do not give long unnecessary explanations.
- Talk naturally like a real shop employee.
- For simple questions, give a quick answer.
- Use emojis only when useful.
- Never mention that you are using OpenRouter, Gemini, an API, Python or an AI model.
Example:
Customer: سلام
Answer: وعلیکم سلام، ښه راغلاست 🌷 څنګه مرسته درسره وکړم؟
Customer: قیمت چند است؟
Answer: مهرباني وکړئ د هغه لباس عکس یا نوم راولېږئ، قیمت به درته معلوم کړم.
Customer: هل لديكم ملابس نسائية؟
Answer: نعم، لدينا ملابس نسائية. إذا أردت، أرسل لك الموديلات المتوفرة.
"""
# =========================================================
# ASK AI
# =========================================================
def ask_ai(customer_message):
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY is missing")
        return "د AI سیستم API Key تنظیم شوی نه دی."
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mirwais-shop.onrender.com",
        "X-Title": "Mirwais Shop WhatsApp AI"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": customer_message
            }
        ],
        "temperature": 0.5,
        "max_tokens": 300
    }
    # -----------------------------------------------------
    # Retry 3 times
    # -----------------------------------------------------
    for attempt in range(3):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=25
            )
            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    print("AI returned no choices")
                    return None
                message = choices[0].get("message", {})
                answer = message.get("content", "")
                if answer:
                    return answer.strip()
                return None
            # ------------------------------------------------
            # TOO MANY REQUESTS
            # ------------------------------------------------
            if response.status_code == 429:
                print("OpenRouter 429 - rate limit")
                time.sleep(2 + attempt * 2)
                continue
            # ------------------------------------------------
            # SERVER BUSY
            # ------------------------------------------------
            if response.status_code in [500, 502, 503, 504]:
                print(
                    f"OpenRouter server error: "
                    f"{response.status_code}"
                )
                time.sleep(2 + attempt * 2)
                continue
            # ------------------------------------------------
            # AUTH ERROR
            # ------------------------------------------------
            if response.status_code in [401, 403]:
                print(
                    "OpenRouter authentication error:",
                    response.text
                )
                return "د AI API Key ستونزه لري."
            # ------------------------------------------------
            # OTHER ERROR
            # ------------------------------------------------
            print(
                "OpenRouter Error:",
                response.status_code,
                response.text
            )
            return None
        except requests.exceptions.Timeout:
            print("OpenRouter timeout")
            time.sleep(2)
            continue
        except requests.exceptions.RequestException as e:
            print("Request error:", e)
            time.sleep(2)
            continue
        except Exception as e:
            print("Unexpected AI error:", e)
            return None
    return None
# =========================================================
# HOME PAGE
# =========================================================
@app.route("/", methods=["GET"])
def home():
    return "Mirwais WhatsApp Shop AI is Running"
# =========================================================
# TWILIO WHATSAPP WEBHOOK
# =========================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get(
        "Body",
        ""
    ).strip()
    # Twilio response
    resp = MessagingResponse()
    reply = resp.message()
    # -------------------------------------------------------
    # Empty message
    # -------------------------------------------------------
    if not incoming_msg:
        reply.body(
            "مهرباني وکړئ خپل پیغام ولیکئ."
        )
        return str(resp)
    print(
        "Customer:",
        incoming_msg
    )
    # -------------------------------------------------------
    # Ask AI
    # -------------------------------------------------------
    try:
        answer = ask_ai(
            incoming_msg
        )
        if answer:
            # WhatsApp message length protection
            reply.body(
                answer[:1500]
            )
        else:
            reply.body(
                "بښنه غواړو، سیستم اوس مهال مصروف دی. "
                "لږ وروسته بیا هڅه وکړئ."
            )
    except Exception as e:
        print(
            "Webhook Error:",
            e
        )
        reply.body(
            "موقتي ستونزه رامنځته شوه. "
            "لږ وروسته بیا هڅه وکړئ."
        )
    return str(resp)
# =========================================================
# START SERVER
# =========================================================
if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )
    app.run(
        host="0.0.0.0",
        port=port
    )
