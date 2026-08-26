import os
import json
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
import requests


app = Flask(__name__, static_folder=".")


# =========================================================
# SETTINGS
# =========================================================

BALE_TOKEN = os.environ.get("BALE_TOKEN")
ADMIN_ID = 746740194

DATA_FILE = "data.json"


# =========================================================
# DATA STORAGE
# =========================================================

def empty_database():
    return {
        "requests": [],
        "chats": [],
        "products": [],
        "orders": []
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        return empty_database()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.setdefault("requests", [])
        data.setdefault("chats", [])
        data.setdefault("products", [])
        data.setdefault("orders", [])

        return data

    except Exception:
        return empty_database()


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# HELPERS
# =========================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def send_bale_message(text):
    if not BALE_TOKEN:
        return False

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

        return response.ok

    except requests.RequestException:
        return False


# =========================================================
# FRONTEND FILES
# =========================================================

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/index.html")
def index_html():
    return send_from_directory(".", "index.html")


@app.route("/shop.html")
def shop_html():
    return send_from_directory(".", "shop.html")


@app.route("/admin.html")
def admin_html():
    return send_from_directory(".", "admin.html")


@app.route("/<path:filename>")
def frontend_files(filename):

    allowed_extensions = (
        ".html",
        ".css",
        ".js",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".svg",
        ".gif",
        ".ico"
    )

    if filename.lower().endswith(allowed_extensions):
        return send_from_directory(".", filename)

    return jsonify({
        "success": False,
        "message": "File not found."
    }), 404


# =========================================================
# SERVICE REQUEST
# =========================================================

@app.route("/api/request", methods=["POST"])
def service_request():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    service = str(data.get("service", "")).strip()
    description = str(
        data.get("description", "")
    ).strip()

    if not name or not phone or not service:
        return jsonify({
            "success": False,
            "message": "لطفاً نام، شماره تماس و نوع خدمت را وارد کنید."
        }), 400

    item = {
        "id": str(uuid.uuid4()),
        "name": name,
        "phone": phone,
        "service": service,
        "description": description,
        "created_at": now(),
        "status": "new"
    }

    database = load_data()
    database["requests"].append(item)
    save_data(database)

    text = (
        "📥 درخواست جدید دکتر برودت\n\n"
        f"👤 نام مشتری: {name}\n"
        f"📱 شماره تماس: {phone}\n"
        f"🔧 خدمت: {service}\n"
        f"📝 توضیحات: {description or 'ثبت نشده'}"
    )

    bale_sent = send_bale_message(text)

    return jsonify({
        "success": True,
        "message": "درخواست شما با موفقیت ثبت شد ❤️",
        "bale_sent": bale_sent,
        "request": item
    })


# =========================================================
# CHAT — GET
# =========================================================

@app.route("/chat", methods=["GET"])
def get_chat():

    phone = request.args.get("phone", "").strip()

    database = load_data()

    if not phone:
        return jsonify({
            "success": True,
            "messages": []
        })

    chat = next(
        (
            item for item in database["chats"]
            if item.get("phone") == phone
        ),
        None
    )

    if not chat:
        return jsonify({
            "success": True,
            "messages": []
        })

    return jsonify({
        "success": True,
        "chat_id": chat["id"],
        "messages": chat.get("messages", [])
    })


# =========================================================
# CHAT — SEND CUSTOMER MESSAGE
# =========================================================

@app.route("/chat/send", methods=["POST"])
def send_chat():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name or not phone or not message:
        return jsonify({
            "success": False,
            "message": "نام، شماره تماس و پیام الزامی است."
        }), 400

    database = load_data()

    chat = next(
        (
            item for item in database["chats"]
            if item.get("phone") == phone
        ),
        None
    )

    if not chat:

        chat = {
            "id": str(uuid.uuid4()),
            "name": name,
            "phone": phone,
            "created_at": now(),
            "updated_at": now(),
            "messages": []
        }

        database["chats"].append(chat)

    else:

        chat["name"] = name
        chat["updated_at"] = now()

    customer_message = {
        "id": str(uuid.uuid4()),
        "sender": "customer",
        "message": message,
        "created_at": now()
    }

    chat.setdefault("messages", []).append(
        customer_message
    )

    chat["updated_at"] = now()

    save_data(database)

    bale_text = (
        "💬 پیام جدید پشتیبانی\n\n"
        f"👤 {name}\n"
        f"📱 {phone}\n\n"
        f"💬 {message}"
    )

    bale_sent = send_bale_message(bale_text)

    return jsonify({
        "success": True,
        "message": "پیام شما ارسال شد.",
        "chat_id": chat["id"],
        "bale_sent": bale_sent
    })


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/api/admin/dashboard", methods=["GET"])
def admin_dashboard():

    database = load_data()

    return jsonify({
        "success": True,
        "chats": database["chats"],
        "products": database["products"],
        "orders": database["orders"],
        "requests": database["requests"]
    })


# =========================================================
# ADMIN — CHAT REPLY
# =========================================================

@app.route("/api/admin/chat/reply", methods=["POST"])
def admin_chat_reply():

    data = request.get_json(silent=True) or {}

    chat_id = str(
        data.get("chat_id", "")
    ).strip()

    message = str(
        data.get("message", "")
    ).strip()

    if not chat_id or not message:
        return jsonify({
            "success": False,
            "message": "گفتگو و متن پاسخ الزامی است."
        }), 400

    database = load_data()

    chat = next(
        (
            item for item in database["chats"]
            if item.get("id") == chat_id
        ),
        None
    )

    if not chat:
        return jsonify({
            "success": False,
            "message": "گفتگو پیدا نشد."
        }), 404

    admin_message = {
        "id": str(uuid.uuid4()),
        "sender": "admin",
        "message": message,
        "created_at": now()
    }

    chat.setdefault("messages", []).append(
        admin_message
    )

    chat["updated_at"] = now()

    save_data(database)

    return jsonify({
        "success": True,
        "message": "پاسخ ارسال شد.",
        "chat_id": chat_id
    })


# =========================================================
# ADMIN — ADD PRODUCT
# =========================================================

@app.route("/api/admin/products", methods=["POST"])
def add_product():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    price = str(data.get("price", "")).strip()
    stock = str(data.get("stock", "0")).strip()
    category = str(data.get("category", "")).strip()
    description = str(
        data.get("description", "")
    ).strip()
    image = str(
        data.get("image", "")
    ).strip()

    if not name or not price or not category:
        return jsonify({
            "success": False,
            "message": "نام، قیمت و دسته‌بندی محصول الزامی است."
        }), 400

    product = {
        "id": str(uuid.uuid4()),
        "name": name,
        "price": price,
        "stock": stock,
        "category": category,
        "description": description,
        "image": image,
        "created_at": now()
    }

    database = load_data()
    database["products"].append(product)
    save_data(database)

    return jsonify({
        "success": True,
        "message": "محصول با موفقیت ثبت شد.",
        "product": product
    })


# =========================================================
# PRODUCTS — PUBLIC
# =========================================================

@app.route("/api/products", methods=["GET"])
def get_products():

    database = load_data()

    return jsonify({
        "success": True,
        "products": database["products"]
    })


# =========================================================
# ADMIN — UPDATE PRODUCT
# =========================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["PATCH"]
)
def update_product(product_id):

    data = request.get_json(silent=True) or {}

    database = load_data()

    product = next(
        (
            item for item in database["products"]
            if item.get("id") == product_id
        ),
        None
    )

    if not product:
        return jsonify({
            "success": False,
            "message": "محصول پیدا نشد."
        }), 404

    allowed_fields = [
        "name",
        "price",
        "stock",
        "category",
        "description",
        "image"
    ]

    for field in allowed_fields:

        if field in data:
            product[field] = str(
                data[field]
            ).strip()

    save_data(database)

    return jsonify({
        "success": True,
        "message": "محصول ویرایش شد.",
        "product": product
    })


# =========================================================
# ADMIN — DELETE PRODUCT
# =========================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["DELETE"]
)
def delete_product(product_id):

    database = load_data()

    old_count = len(database["products"])

    database["products"] = [
        product
        for product in database["products"]
        if product.get("id") != product_id
    ]

    if len(database["products"]) == old_count:
        return jsonify({
            "success": False,
            "message": "محصول پیدا نشد."
        }), 404

    save_data(database)

    return jsonify({
        "success": True,
        "message": "محصول حذف شد."
    })


# =========================================================
# CREATE ORDER
# =========================================================

@app.route("/api/order", methods=["POST"])
def create_order():

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()

    product_id = str(
        data.get("product_id", "")
    ).strip()

    product_name = str(
        data.get("product_name", "")
    ).strip()

    quantity = str(
        data.get("quantity", "1")
    ).strip()

    if not name or not phone or not product_name:
        return jsonify({
            "success": False,
            "message": "نام، شماره تماس و محصول الزامی است."
        }), 400

    database = load_data()

    product = None

    if product_id:

        product = next(
            (
                item
                for item in database["products"]
                if item.get("id") == product_id
            ),
            None
        )

    order = {
        "id": str(uuid.uuid4()),
        "name": name,
        "phone": phone,
        "product_id": product_id,
        "product_name": product_name,
        "quantity": quantity,
        "created_at": now(),
        "status": "new"
    }

    database["orders"].append(order)
    save_data(database)

    text = (
        "🛒 سفارش جدید دکتر برودت\n\n"
        f"👤 نام: {name}\n"
        f"📱 شماره: {phone}\n"
        f"📦 محصول: {product_name}\n"
        f"🔢 تعداد: {quantity}"
    )

    bale_sent = send_bale_message(text)

    return jsonify({
        "success": True,
        "message": "سفارش شما با موفقیت ثبت شد.",
        "order": order,
        "bale_sent": bale_sent,
        "product_found": product is not None
    })


# =========================================================
# ADMIN — UPDATE ORDER STATUS
# =========================================================

@app.route(
    "/api/admin/orders/<order_id>",
    methods=["PATCH"]
)
def update_order(order_id):

    data = request.get_json(silent=True) or {}

    status = str(
        data.get("status", "")
    ).strip()

    if not status:
        return jsonify({
            "success": False,
            "message": "وضعیت سفارش مشخص نشده است."
        }), 400

    database = load_data()

    order = next(
        (
            item
            for item in database["orders"]
            if item.get("id") == order_id
        ),
        None
    )

    if not order:
        return jsonify({
            "success": False,
            "message": "سفارش پیدا نشد."
        }), 404

    order["status"] = status

    save_data(database)

    return jsonify({
        "success": True,
        "message": "وضعیت سفارش تغییر کرد.",
        "order": order
    })


# =========================================================
# ADMIN — SERVICE REQUESTS
# =========================================================

@app.route(
    "/api/admin/requests",
    methods=["GET"]
)
def admin_requests():

    database = load_data()

    return jsonify({
        "success": True,
        "requests": database["requests"]
    })


# =========================================================
# ADMIN — UPDATE SERVICE REQUEST
# =========================================================

@app.route(
    "/api/admin/requests/<request_id>",
    methods=["PATCH"]
)
def update_service_request(request_id):

    data = request.get_json(silent=True) or {}

    status = str(
        data.get("status", "")
    ).strip()

    if not status:
        return jsonify({
            "success": False,
            "message": "وضعیت درخواست مشخص نشده است."
        }), 400

    database = load_data()

    item = next(
        (
            request_item
            for request_item in database["requests"]
            if request_item.get("id") == request_id
        ),
        None
    )

    if not item:
        return jsonify({
            "success": False,
            "message": "درخواست پیدا نشد."
        }), 404

    item["status"] = status

    save_data(database)

    return jsonify({
        "success": True,
        "message": "وضعیت درخواست تغییر کرد.",
        "request": item
    })


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "status": "online"
    })


# =========================================================
# RUN
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
