import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"

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

@app.route("/", methods=["GET"])
def home():
    return "Mirwais WhatsApp Shop Agent Running"

@app.route("/webhook", methods=["POST"])
def webhook():

    incoming_msg = request.values.get("Body", "").strip()

    resp = MessagingResponse()
    reply = resp.message()

    if not incoming_msg:
        reply.body("مهرباني وکړئ خپل پیغام ولیکئ.")
        return str(resp)

    try:

        prompt = f"""
{SYSTEM_PROMPT}

Customer Message:
{incoming_msg}

Reply in the same language as the customer.
"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        answer = None

        for _ in range(3):

            response = requests.post(
                url,
                json=payload,
                timeout=20
            )

            if response.status_code == 200:
                data = response.json()

                answer = data["candidates"][0]["content"]["parts"][0]["text"]
                break

        if answer:
            reply.body(answer[:1500])
        else:
            reply.body("سرور مصروف دی، لږ وروسته بیا هڅه وکړئ.")

    except Exception:
        reply.body("موقتي ستونزه رامنځته شوه، وروسته بیا هڅه وکړئ.")

    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
