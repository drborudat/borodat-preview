import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

BALE_TOKEN = os.environ.get("BALE_TOKEN")
ADMIN_ID = 746740194


@app.route("/")
def home():
    return "Dr Borodat Preview Server is running."


@app.route("/api/request", methods=["POST"])
def service_request():

    data = request.get_json(silent=True) or {}

    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    service = data.get("service", "").strip()
    description = data.get("description", "").strip()

    if not name or not phone or not service:
        return jsonify({
            "success": False,
            "message": "لطفاً نام، شماره تماس و نوع خدمت را وارد کنید."
        }), 400

    if not BALE_TOKEN:
        return jsonify({
            "success": False,
            "message": "توکن ربات روی سرور تنظیم نشده است."
        }), 500

    text = (
        "📥 درخواست جدید دکتر برودت\n\n"
        f"👤 نام مشتری: {name}\n"
        f"📱 شماره تماس: {phone}\n"
        f"🔧 خدمت: {service}\n"
        f"📝 توضیحات: {description or 'ثبت نشده'}"
    )

    url = f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"

    try:
        response = requests.post(
            url,
            json={
                "chat_id": ADMIN_ID,
                "text": text
            },
            timeout=15
        )

        if response.ok:
            return jsonify({
                "success": True,
                "message": "درخواست شما با موفقیت ثبت شد ❤️"
            })

        return jsonify({
            "success": False,
            "message": "ارسال درخواست انجام نشد."
        }), 502

    except requests.RequestException:
        return jsonify({
            "success": False,
            "message": "ارتباط با سرور برقرار نشد."
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
