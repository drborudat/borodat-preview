import os
import json
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests


# =====================================================
# APP
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False
)

BALE_TOKEN = os.environ.get("BALE_TOKEN")
ADMIN_ID = 746740194

DATA_FILE = os.path.join(BASE_DIR, "data.json")


# =====================================================
# DATABASE
# =====================================================

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

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            return empty_database()

        for key in [
            "requests",
            "chats",
            "products",
            "orders"
        ]:

            if not isinstance(
                data.get(key),
                list
            ):

                data[key] = []

        return data

    except Exception as e:

        print(
            "LOAD DATA ERROR:",
            repr(e)
        )

        return empty_database()


def save_data(data):

    try:

        temp_file = DATA_FILE + ".tmp"

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_file,
            DATA_FILE
        )

        return True

    except Exception as e:

        print(
            "SAVE DATA ERROR:",
            repr(e)
        )

        return False


def now():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )


# =====================================================
# BALE
# =====================================================

def send_bale_message(text):

    if not BALE_TOKEN:

        print(
            "BALE_TOKEN is not configured."
        )

        return False

    try:

        url = (
            f"https://tapi.bale.ai/"
            f"bot{BALE_TOKEN}/sendMessage"
        )

        response = requests.post(
            url,
            json={
                "chat_id": ADMIN_ID,
                "text": text
            },
            timeout=15
        )

        print(
            "BALE STATUS:",
            response.status_code
        )

        print(
            "BALE RESPONSE:",
            response.text[:500]
        )

        return response.ok

    except Exception as e:

        print(
            "BALE ERROR:",
            repr(e)
        )

        return False


# =====================================================
# PAGES
# =====================================================

@app.route("/")
def home():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/admin")
def admin():

    return send_from_directory(
        BASE_DIR,
        "admin.html"
    )


@app.route("/admin.html")
def admin_html():

    return send_from_directory(
        BASE_DIR,
        "admin.html"
    )


@app.route("/index.html")
def index_html():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/shop.html")
def shop_html():

    return send_from_directory(
        BASE_DIR,
        "shop.html"
    )


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "status": "online"
    }), 200


# =====================================================
# SERVICE REQUEST
# =====================================================

@app.route(
    "/api/request",
    methods=["POST", "OPTIONS"]
)
def service_request():

    # برای CORS / OPTIONS
    if request.method == "OPTIONS":

        return (
            "",
            204,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "POST, OPTIONS"
            }
        )

    try:

        print(
            "================================"
        )

        print(
            "SERVICE REQUEST RECEIVED"
        )

        print(
            "METHOD:",
            request.method
        )

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        # ---------------------------------------------
        # دریافت JSON
        # ---------------------------------------------

        data = request.get_json(
            silent=True
        )

        print(
            "REQUEST DATA:",
            data
        )

        if not isinstance(data, dict):

            return jsonify({
                "success": False,
                "message": "اطلاعات ارسالی نامعتبر است."
            }), 400

        # ---------------------------------------------
        # اطلاعات فرم
        # ---------------------------------------------

        name = str(
            data.get("name", "")
        ).strip()

        phone = str(
            data.get("phone", "")
        ).strip()

        service = str(
            data.get("service", "")
        ).strip()

        description = str(
            data.get("description", "")
        ).strip()

        print(
            "NAME:",
            name
        )

        print(
            "PHONE:",
            phone
        )

        print(
            "SERVICE:",
            service
        )

        # ---------------------------------------------
        # اعتبارسنجی
        # ---------------------------------------------

        if not name:

            return jsonify({
                "success": False,
                "message": "لطفاً نام و نام خانوادگی را وارد کنید."
            }), 400

        if not phone:

            return jsonify({
                "success": False,
                "message": "لطفاً شماره تماس را وارد کنید."
            }), 400

        if not service:

            return jsonify({
                "success": False,
                "message": "لطفاً نوع خدمت را انتخاب کنید."
            }), 400

        # ---------------------------------------------
        # ساخت درخواست
        # ---------------------------------------------

        item = {

            "id": str(
                uuid.uuid4()
            ),

            "name": name,

            "phone": phone,

            "service": service,

            "description": description,

            "created_at": now(),

            "status": "new"
        }

        # ---------------------------------------------
        # ذخیره
        # ---------------------------------------------

        database = load_data()

        database["requests"].append(
            item
        )

        saved = save_data(
            database
        )

        print(
            "DATA SAVED:",
            saved
        )

        if not saved:

            return jsonify({
                "success": False,
                "message": "ذخیره درخواست روی سرور انجام نشد."
            }), 500

        # ---------------------------------------------
        # ارسال به بله
        # ---------------------------------------------

        bale_sent = send_bale_message(

            "📥 درخواست جدید دکتر برودت\n\n"

            f"👤 نام مشتری: {name}\n"

            f"📱 شماره تماس: {phone}\n"

            f"🔧 خدمت: {service}\n"

            f"📝 توضیحات: "
            f"{description or 'ثبت نشده'}"
        )

        print(
            "BALE SENT:",
            bale_sent
        )

        # ---------------------------------------------
        # پاسخ قطعی JSON
        # ---------------------------------------------

        result = {

            "success": True,

            "message":
                "درخواست شما با موفقیت ثبت شد ❤️",

            "bale_sent":
                bale_sent,

            "request":
                item
        }

        print(
            "SERVICE REQUEST RESPONSE:",
            result
        )

        print(
            "================================"
        )

        return jsonify(
            result
        ), 200

    except Exception as e:

        print(
            "SERVICE REQUEST ERROR:",
            repr(e)
        )

        print(
            "================================"
        )

        return jsonify({
            "success": False,
            "message":
                "خطایی هنگام ثبت درخواست رخ داد.",
            "error":
                str(e)
        }), 500


# =====================================================
# CHAT GET
# =====================================================

@app.route(
    "/chat",
    methods=["GET"]
)
def get_chat():

    try:

        phone = request.args.get(
            "phone",
            ""
        ).strip()

        database = load_data()

        if not phone:

            return jsonify({
                "success": True,
                "messages": []
            }), 200

        chat = next(
            (
                item
                for item in database["chats"]
                if item.get("phone") == phone
            ),
            None
        )

        if not chat:

            return jsonify({
                "success": True,
                "messages": []
            }), 200

        return jsonify({

            "success": True,

            "chat_id":
                chat.get("id"),

            "name":
                chat.get("name", ""),

            "phone":
                chat.get("phone", ""),

            "messages":
                chat.get("messages", [])
        }), 200

    except Exception as e:

        print(
            "GET CHAT ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "دریافت گفتگو انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# CHAT SEND
# =====================================================

@app.route(
    "/chat/send",
    methods=["POST", "OPTIONS"]
)
def send_chat():

    if request.method == "OPTIONS":

        return (
            "",
            204,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "POST, OPTIONS"
            }
        )

    try:

        data = request.get_json(
            silent=True
        )

        if not isinstance(data, dict):

            return jsonify({
                "success": False,
                "message":
                    "اطلاعات ارسالی نامعتبر است."
            }), 400

        name = str(
            data.get("name", "")
        ).strip()

        phone = str(
            data.get("phone", "")
        ).strip()

        message = str(
            data.get("message", "")
        ).strip()

        if not name or not phone or not message:

            return jsonify({
                "success": False,
                "message":
                    "نام، شماره تماس و پیام الزامی است."
            }), 400

        database = load_data()

        chat = next(
            (
                item
                for item in database["chats"]
                if item.get("phone") == phone
            ),
            None
        )

        if not chat:

            chat = {

                "id":
                    str(uuid.uuid4()),

                "name":
                    name,

                "phone":
                    phone,

                "created_at":
                    now(),

                "updated_at":
                    now(),

                "messages":
                    []
            }

            database["chats"].append(
                chat
            )

        else:

            chat["name"] = name

            chat["updated_at"] = now()

        customer_message = {

            "id":
                str(uuid.uuid4()),

            "sender":
                "customer",

            "message":
                message,

            "created_at":
                now()
        }

        chat.setdefault(
            "messages",
            []
        ).append(
            customer_message
        )

        chat["updated_at"] = now()

        saved = save_data(
            database
        )

        if not saved:

            return jsonify({
                "success": False,
                "message":
                    "ذخیره پیام انجام نشد."
            }), 500

        bale_sent = send_bale_message(

            "💬 پیام جدید پشتیبانی\n\n"

            f"👤 {name}\n"

            f"📱 {phone}\n\n"

            f"💬 {message}"
        )

        return jsonify({

            "success": True,

            "message":
                "پیام شما ارسال شد.",

            "chat_id":
                chat["id"],

            "bale_sent":
                bale_sent

        }), 200

    except Exception as e:

        print(
            "SEND CHAT ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "ارسال پیام انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route(
    "/api/admin/dashboard",
    methods=["GET"]
)
def admin_dashboard():

    try:

        database = load_data()

        return jsonify({

            "success": True,

            "requests":
                database["requests"],

            "chats":
                database["chats"],

            "products":
                database["products"],

            "orders":
                database["orders"]

        }), 200

    except Exception as e:

        print(
            "DASHBOARD ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "دریافت اطلاعات پنل انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# ADMIN CHAT REPLY
# =====================================================

@app.route(
    "/api/admin/chat/reply",
    methods=["POST"]
)
def admin_chat_reply():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        chat_id = str(
            data.get("chat_id", "")
        ).strip()

        message = str(
            data.get("message", "")
        ).strip()

        if not chat_id or not message:

            return jsonify({
                "success": False,
                "message":
                    "گفتگو و متن پاسخ الزامی است."
            }), 400

        database = load_data()

        chat = next(
            (
                item
                for item in database["chats"]
                if item.get("id") == chat_id
            ),
            None
        )

        if not chat:

            return jsonify({
                "success": False,
                "message":
                    "گفتگو پیدا نشد."
            }), 404

        admin_message = {

            "id":
                str(uuid.uuid4()),

            "sender":
                "admin",

            "message":
                message,

            "created_at":
                now()
        }

        chat.setdefault(
            "messages",
            []
        ).append(
            admin_message
        )

        chat["updated_at"] = now()

        save_data(
            database
        )

        return jsonify({

            "success": True,

            "message":
                "پاسخ ارسال شد.",

            "chat_id":
                chat_id,

            "reply":
                admin_message

        }), 200

    except Exception as e:

        print(
            "ADMIN CHAT REPLY ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "ارسال پاسخ انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# PRODUCTS - ADD
# =====================================================

@app.route(
    "/api/admin/products",
    methods=["POST"]
)
def add_product():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        name = str(
            data.get("name", "")
        ).strip()

        price = str(
            data.get("price", "")
        ).strip()

        stock = str(
            data.get("stock", "0")
        ).strip()

        category = str(
            data.get("category", "")
        ).strip()

        description = str(
            data.get("description", "")
        ).strip()

        image = str(
            data.get("image", "")
        ).strip()

        if not name or not price or not category:

            return jsonify({
                "success": False,
                "message":
                    "نام، قیمت و دسته‌بندی محصول الزامی است."
            }), 400

        product = {

            "id":
                str(uuid.uuid4()),

            "name":
                name,

            "price":
                price,

            "stock":
                stock,

            "category":
                category,

            "description":
                description,

            "image":
                image,

            "created_at":
                now()
        }

        database = load_data()

        database["products"].append(
            product
        )

        if not save_data(database):

            return jsonify({
                "success": False,
                "message":
                    "ذخیره محصول انجام نشد."
            }), 500

        return jsonify({

            "success": True,

            "message":
                "محصول با موفقیت ثبت شد.",

            "product":
                product

        }), 200

    except Exception as e:

        print(
            "ADD PRODUCT ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "ثبت محصول انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# PRODUCTS - GET
# =====================================================

@app.route(
    "/api/products",
    methods=["GET"]
)
def get_products():

    try:

        database = load_data()

        return jsonify({

            "success": True,

            "products":
                database["products"]

        }), 200

    except Exception as e:

        print(
            "GET PRODUCTS ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "دریافت محصولات انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# PRODUCTS - UPDATE
# =====================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["PATCH"]
)
def update_product(product_id):

    try:

        data = request.get_json(
            silent=True
        ) or {}

        database = load_data()

        product = next(
            (
                item
                for item in database["products"]
                if item.get("id") == product_id
            ),
            None
        )

        if not product:

            return jsonify({
                "success": False,
                "message":
                    "محصول پیدا نشد."
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

        if not save_data(database):

            return jsonify({
                "success": False,
                "message":
                    "ذخیره تغییرات محصول انجام نشد."
            }), 500

        return jsonify({

            "success": True,

            "message":
                "محصول ویرایش شد.",

            "product":
                product

        }), 200

    except Exception as e:

        print(
            "UPDATE PRODUCT ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "ویرایش محصول انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# PRODUCTS - DELETE
# =====================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["DELETE"]
)
def delete_product(product_id):

    try:

        database = load_data()

        old_count = len(
            database["products"]
        )

        database["products"] = [

            product
            for product in database["products"]

            if product.get("id")
            != product_id

        ]

        if len(
            database["products"]
        ) == old_count:

            return jsonify({
                "success": False,
                "message":
                    "محصول پیدا نشد."
            }), 404

        if not save_data(database):

            return jsonify({
                "success": False,
                "message":
                    "حذف محصول ذخیره نشد."
            }), 500

        return jsonify({

            "success": True,

            "message":
                "محصول حذف شد."

        }), 200

    except Exception as e:

        print(
            "DELETE PRODUCT ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "حذف محصول انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# ORDERS
# =====================================================

@app.route(
    "/api/order",
    methods=["POST", "OPTIONS"]
)
def create_order():

    if request.method == "OPTIONS":

        return (
            "",
            204,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "POST, OPTIONS"
            }
        )

    try:

        data = request.get_json(
            silent=True
        ) or {}

        name = str(
            data.get("name", "")
        ).strip()

        phone = str(
            data.get("phone", "")
        ).strip()

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
                "message":
                    "نام، شماره تماس و محصول الزامی است."
            }), 400

        database = load_data()

        product = None

        if product_id:

            product = next(
                (
                    item
                    for item in database["products"]
                    if item.get("id")
                    == product_id
                ),
                None
            )

        order = {

            "id":
                str(uuid.uuid4()),

            "name":
                name,

            "phone":
                phone,

            "product_id":
                product_id,

            "product_name":
                product_name,

            "quantity":
                quantity,

            "created_at":
                now(),

            "status":
                "new"
        }

        database["orders"].append(
            order
        )

        if not save_data(database):

            return jsonify({
                "success": False,
                "message":
                    "ذخیره سفارش انجام نشد."
            }), 500

        bale_sent = send_bale_message(

            "🛒 سفارش جدید دکتر برودت\n\n"

            f"👤 نام: {name}\n"

            f"📱 شماره: {phone}\n"

            f"📦 محصول: {product_name}\n"

            f"🔢 تعداد: {quantity}"
        )

        return jsonify({

            "success": True,

            "message":
                "سفارش شما با موفقیت ثبت شد.",

            "order":
                order,

            "bale_sent":
                bale_sent,

            "product_found":
                product is not None

        }), 200

    except Exception as e:

        print(
            "CREATE ORDER ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "ثبت سفارش انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# ORDER UPDATE
# =====================================================

@app.route(
    "/api/admin/orders/<order_id>",
    methods=["PATCH"]
)
def update_order(order_id):

    try:

        data = request.get_json(
            silent=True
        ) or {}

        status = str(
            data.get("status", "")
        ).strip()

        if not status:

            return jsonify({
                "success": False,
                "message":
                    "وضعیت سفارش مشخص نشده است."
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
                "message":
                    "سفارش پیدا نشد."
            }), 404

        order["status"] = status

        if not save_data(database):

            return jsonify({
                "success": False,
                "message":
                    "ذخیره وضعیت سفارش انجام نشد."
            }), 500

        return jsonify({

            "success": True,

            "message":
                "وضعیت سفارش تغییر کرد.",

            "order":
                order

        }), 200

    except Exception as e:

        print(
            "UPDATE ORDER ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "تغییر وضعیت سفارش انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# ADMIN REQUESTS
# =====================================================

@app.route(
    "/api/admin/requests",
    methods=["GET"]
)
def admin_requests():

    try:

        database = load_data()

        return jsonify({

            "success": True,

            "requests":
                database["requests"]

        }), 200

    except Exception as e:

        print(
            "ADMIN REQUESTS ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "دریافت درخواست‌ها انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# UPDATE SERVICE REQUEST
# =====================================================

@app.route(
    "/api/admin/requests/<request_id>",
    methods=["PATCH"]
)
def update_service_request(request_id):

    try:

        data = request.get_json(
            silent=True
        ) or {}

        status = str(
            data.get("status", "")
        ).strip()

        if not status:

            return jsonify({
                "success": False,
                "message":
                    "وضعیت درخواست مشخص نشده است."
            }), 400

        database = load_data()

        item = next(
            (
                x
                for x in database["requests"]
                if x.get("id")
                == request_id
            ),
            None
        )

        if not item:

            return jsonify({
                "success": False,
                "message":
                    "درخواست پیدا نشد."
            }), 404

        item["status"] = status

        if not save_data(database):

            return jsonify({
                "success": False,
                "message":
                    "ذخیره وضعیت درخواست انجام نشد."
            }), 500

        return jsonify({

            "success": True,

            "message":
                "وضعیت درخواست تغییر کرد.",

            "request":
                item

        }), 200

    except Exception as e:

        print(
            "UPDATE REQUEST ERROR:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "message":
                "تغییر وضعیت درخواست انجام نشد.",
            "error":
                str(e)
        }), 500


# =====================================================
# GLOBAL ERRORS
# =====================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "message":
            "مسیر موردنظر پیدا نشد."
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({
        "success": False,
        "message":
            "متد درخواست مجاز نیست."
    }), 405


@app.errorhandler(500)
def internal_error(error):

    print(
        "GLOBAL 500:",
        repr(error)
    )

    return jsonify({
        "success": False,
        "message":
            "خطای داخلی سرور."
    }), 500


# =====================================================
# RUN
# =====================================================

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
