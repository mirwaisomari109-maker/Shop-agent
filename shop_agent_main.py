import os
import re
import sqlite3
from datetime import datetime

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# =========================================================
# DATABASE
# =========================================================

DB_PATH = os.getenv("DB_PATH", "debt_book.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# HELPERS
# =========================================================

def clean_number(text):
    """
    Convert Arabic/Persian numbers to English numbers.
    """
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )
    return text.translate(table)


def money(value):
    return f"{value:.3f}".rstrip("0").rstrip(".")


def add_transaction(customer, amount, transaction_type, note=""):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO transactions
        (customer, amount, type, note, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            customer,
            amount,
            transaction_type,
            note,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    )

    conn.commit()
    conn.close()


def get_balance(customer):

    conn = get_db()

    row = conn.execute(
        """
        SELECT
        COALESCE(SUM(
            CASE
                WHEN type = 'debt' THEN amount
                WHEN type = 'payment' THEN -amount
                ELSE 0
            END
        ), 0) AS balance
        FROM transactions
        WHERE customer = ?
        """,
        (customer,)
    ).fetchone()

    conn.close()

    return float(row["balance"])


def get_all_balances():

    conn = get_db()

    rows = conn.execute(
        """
        SELECT customer,
        SUM(
            CASE
                WHEN type = 'debt' THEN amount
                WHEN type = 'payment' THEN -amount
                ELSE 0
            END
        ) AS balance
        FROM transactions
        GROUP BY customer
        HAVING balance != 0
        ORDER BY balance DESC
        """
    ).fetchall()

    conn.close()

    return rows


def get_history(customer):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT amount, type, note, created_at
        FROM transactions
        WHERE customer = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (customer,)
    ).fetchall()

    conn.close()

    return rows


# =========================================================
# CUSTOMER NAME EXTRACTION
# =========================================================

def find_customer_name(text):

    text = clean_number(text.strip())

    patterns = [
        r"^(.+?)\s+\d+(?:\.\d+)?\s*(?:ریال|ریال عمانی|عمانی|OMR)?\s*(?:قرض|پور|پورته|واخیست|واخیستل)$",

        r"^(.+?)\s+\d+(?:\.\d+)?\s*(?:ریال|ریال عمانی|عمانی|OMR)?\s*(?:راکړل|ورکړل|ورکړه|وصول|وصول شو|پیسې راکړې)$",

        r"^(?:حساب|قرض|تاریخ)\s+(.+)$",

        r"^(.+?)\s+(?:حساب|قرض|تاریخ)$",
    ]

    for pattern in patterns:

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            name = match.group(1).strip()

            if name:
                return name

    return None


# =========================================================
# AMOUNT
# =========================================================

def find_amount(text):

    text = clean_number(text)

    match = re.search(r"(\d+(?:\.\d+)?)", text)

    if not match:
        return None

    try:
        return float(match.group(1))
    except:
        return None


# =========================================================
# TYPE DETECTION
# =========================================================

def is_payment(text):

    payment_words = [
        "راکړل",
        "ورکړل",
        "ورکړه",
        "راکړه",
        "وصول",
        "وصول شو",
        "پیسې راکړې",
        "پیسې ورکړې",
        "ادا",
        "اداء",
        "payment",
        "paid"
    ]

    text_lower = text.lower()

    return any(word.lower() in text_lower for word in payment_words)


def is_debt(text):

    debt_words = [
        "قرض",
        "پور",
        "پورته",
        "واخیست",
        "واخیستل",
        "debt",
        "credit"
    ]

    text_lower = text.lower()

    return any(word.lower() in text_lower for word in debt_words)


# =========================================================
# CUSTOMER ACCOUNT
# =========================================================

def customer_account(customer):

    balance = get_balance(customer)
    history = get_history(customer)

    if not history:
        return f"❌ د «{customer}» لپاره کوم حساب پیدا نه شو."

    total_debt = sum(
        float(row["amount"])
        for row in history
        if row["type"] == "debt"
    )

    total_payment = sum(
        float(row["amount"])
        for row in history
        if row["type"] == "payment"
    )

    text = f"👤 مشتری: {customer}\n\n"

    text += f"➕ ټول قرض: {money(total_debt)} OMR\n"
    text += f"➖ ټول وصول: {money(total_payment)} OMR\n"

    if balance > 0:
        text += f"🔴 پاتې قرض: {money(balance)} OMR"
    elif balance < 0:
        text += f"🟢 د مشتری اضافي کریډیټ: {money(abs(balance))} OMR"
    else:
        text += "✅ حساب تصفیه شوی."

    return text


# =========================================================
# CUSTOMER HISTORY
# =========================================================

def customer_history(customer):

    history = get_history(customer)

    if not history:
        return f"❌ د «{customer}» لپاره تاریخ پیدا نه شو."

    text = f"📋 د {customer} د حساب تاریخ:\n\n"

    for row in history:

        if row["type"] == "debt":
            sign = "➕ قرض"
        else:
            sign = "➖ وصول"

        text += (
            f"{sign}: {money(float(row['amount']))} OMR\n"
            f"📅 {row['created_at']}\n\n"
        )

    balance = get_balance(customer)

    text += "----------------\n"

    if balance > 0:
        text += f"🔴 پاتې: {money(balance)} OMR"
    elif balance == 0:
        text += "✅ حساب تصفیه شوی."
    else:
        text += f"🟢 کریډیټ: {money(abs(balance))} OMR"

    return text


# =========================================================
# ALL DEBTS
# =========================================================

def all_debts():

    rows = get_all_balances()

    if not rows:
        return "✅ اوس مهال هېڅ پاتې قرض نشته."

    text = "📋 د ټولو پاتې قرضونو راپور:\n\n"

    total = 0

    for row in rows:

        balance = float(row["balance"])

        if balance > 0:
            text += f"👤 {row['customer']}: {money(balance)} OMR\n"
            total += balance

    text += "\n----------------\n"
    text += f"💰 ټول پاتې قرض: {money(total)} OMR"

    return text


# =========================================================
# PROCESS MESSAGE
# =========================================================

def process_message(message):

    original = message.strip()

    if not original:
        return "مهرباني وکړئ خپل پیغام ولیکئ."

    text = clean_number(original)

    # -----------------------------------------
    # ALL DEBTS
    # -----------------------------------------

    if text in [
        "ټول قرض",
        "ټول پور",
        "ټول قرضونه",
        "ټول پورونه",
        "all debt",
        "all debts"
    ]:
        return all_debts()

    # -----------------------------------------
    # CUSTOMER NAME
    # -----------------------------------------

    customer = find_customer_name(text)

    # -----------------------------------------
    # ACCOUNT
    # -----------------------------------------

    if "حساب" in text and customer:

        return customer_account(customer)

    # -----------------------------------------
    # HISTORY
    # -----------------------------------------

    if "تاریخ" in text and customer:

        return customer_history(customer)

    # -----------------------------------------
    # ADD TRANSACTION
    # -----------------------------------------

    amount = find_amount(text)

    if customer and amount:

        # Payment
        if is_payment(text):

            old_balance = get_balance(customer)

            add_transaction(
                customer,
                amount,
                "payment",
                "WhatsApp وصول"
            )

            new_balance = get_balance(customer)

            reply = (
                f"✅ وصول ثبت شو\n\n"
                f"👤 مشتری: {customer}\n"
                f"➖ وصول: {money(amount)} OMR\n"
                f"📌 مخکې پاتې: {money(old_balance)} OMR\n"
                f"🔴 اوس پاتې: {money(new_balance)} OMR"
            )

            if new_balance < 0:
                reply += (
                    f"\n\n🟢 د مشتری اضافي کریډیټ: "
                    f"{money(abs(new_balance))} OMR"
                )

            return reply

        # Debt
        if is_debt(text):

            old_balance = get_balance(customer)

            add_transaction(
                customer,
                amount,
                "debt",
                "WhatsApp قرض"
            )

            new_balance = get_balance(customer)

            return (
                f"✅ قرض ثبت شو\n\n"
                f"👤 مشتری: {customer}\n"
                f"➕ نوی قرض: {money(amount)} OMR\n"
                f"📌 مخکې پاتې: {money(old_balance)} OMR\n"
                f"🔴 اوس ټول پاتې: {money(new_balance)} OMR"
            )

    # -----------------------------------------
    # HELP
    # -----------------------------------------

    if text in [
        "سلام",
        "hello",
        "hi",
        "مرحبا",
        "help",
        "مرسته"
    ]:

        return (
            "وعلیکم سلام 🌷\n\n"
            "زه د قرضونو حساب ساتم.\n\n"
            "مثالونه:\n"
            "➕ احمد 50 قرض\n"
            "➖ احمد 20 راکړل\n"
            "📋 احمد حساب\n"
            "📋 احمد تاریخ\n"
            "💰 ټول قرض"
        )

    # -----------------------------------------
    # UNKNOWN
    # -----------------------------------------

    return (
        "زه یوازې د قرضونو حساب ساتم.\n\n"
        "مثال:\n"
        "➕ احمد 50 قرض\n"
        "➖ احمد 20 راکړل\n"
        "📋 احمد حساب\n"
        "💰 ټول قرض"
    )


# =========================================================
# HOME
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    message = request.values.get("Body", "").strip()
    phone = request.values.get("From", "")

    print("CUSTOMER:", phone)
    print("MESSAGE:", message)

    reply_text = process_message(message)

    print("REPLY:", reply_text)

    response = MessagingResponse()
    response.message(reply_text)

    xml = str(response)

    print("TWILIO XML:", xml)

    return xml, 200, {
        "Content-Type": "text/xml; charset=utf-8"
    }


# =========================================================
# WHATSAPP WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    message = request.values.get("Body", "").strip()

    phone = request.values.get("From", "")

    print("===================================")
    print("CUSTOMER:", phone)
    print("MESSAGE:", message)
    print("===================================")

    reply_text = process_message(message)

    print("REPLY:", reply_text)

    response = MessagingResponse()

    response.message(reply_text)

    return str(response)


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
