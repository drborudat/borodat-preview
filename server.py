import os
import json
import uuid
import base64
from datetime import datetime

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS


# =====================================================
# CONFIG
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)

BALE_TOKEN = os.environ.get("BALE_TOKEN")
ADMIN_ID = 746740194

DATA_FILE = os.path.join(BASE_DIR, "data.json")

# =====================================================
# GITHUB PERSISTENT STORAGE
# =====================================================

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get(
    "GITHUB_REPO",
    "drborudat/borodat-preview"
)
GITHUB_BRANCH = os.environ.get(
    "GITHUB_BRANCH",
    "main"
)

GITHUB_DATA_PATH = "data.json"


# =====================================================
# DATABASE DEFAULT
# =====================================================

def empty_database():
    return {
        "requests": [],
        "chats": [],
        "products": [],
        "orders": []
    }


# =====================================================
# GITHUB HELPERS
# =====================================================

def github_headers():

    if not GITHUB_TOKEN:
        return None

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


def load_data_from_github():

    headers = github_headers()

    if not headers:
        print("GITHUB_TOKEN is not configured.")
        return None

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPO}/contents/{GITHUB_DATA_PATH}"
    )

    try:

        response = requests.get(
            url,
            headers=headers,
            params={
                "ref": GITHUB_BRANCH
            },
            timeout=15
        )

        print(
            "GITHUB LOAD:",
            response.status_code
        )

        if response.status_code == 404:
            print("GitHub data.json does not exist yet.")
            return None

        if not response.ok:
            print(
                "GITHUB LOAD ERROR:",
                response.text
            )
            return None

        result = response.json()

        encoded_content = result.get(
            "content",
            ""
        )

        encoded_content = (
            encoded_content
            .replace("\n", "")
            .replace("\r", "")
        )

        if not encoded_content:
            return None

        decoded = base64.b64decode(
            encoded_content
        ).decode("utf-8")

        data = json.loads(decoded)

        if not isinstance(data, dict):
            return None

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
            "GITHUB LOAD EXCEPTION:",
            e
        )

        return None


def save_data_to_github(data):

    headers = github_headers()

    if not headers:
        print(
            "GITHUB_TOKEN is not configured. "
            "Using local storage."
        )
        return False

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_REPO}/contents/{GITHUB_DATA_PATH}"
    )

    try:

        content = json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )

        encoded = base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii")

        # -------------------------------------------------
        # Get current file SHA
        # -------------------------------------------------

        current = requests.get(
            url,
            headers=headers,
            params={
                "ref": GITHUB_BRANCH
            },
            timeout=15
        )

        sha = None

        if current.status_code == 200:

            sha = current.json().get(
                "sha"
            )

        elif current.status_code != 404:

            print(
                "GITHUB SHA ERROR:",
                current.status_code,
                current.text
            )

            return False

        # -------------------------------------------------
        # Create / Update file
        # -------------------------------------------------

        payload = {
            "message": "Update persistent site data",
            "content": encoded,
            "branch": GITHUB_BRANCH
        }

        if sha:
            payload["sha"] = sha

        response = requests.put(
            url,
            headers=headers,
            json=payload,
            timeout=20
        )

        print(
            "GITHUB SAVE:",
            response.status_code,
            response.text[:500]
        )

        return response.ok

    except Exception as e:

        print(
            "GITHUB SAVE EXCEPTION:",
            e
        )

        return False


# =====================================================
# LOCAL STORAGE
# =====================================================

def load_local_data():

    if not os.path.exists(DATA_FILE):

        data = empty_database()

        save_local_data(data)

        return data

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):

            data = empty_database()

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
            "LOCAL LOAD ERROR:",
            e
        )

        return empty_database()


def save_local_data(data):

    try:

        with open(
            DATA_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception as e:

        print(
            "LOCAL SAVE ERROR:",
            e
        )

        return False


# =====================================================
# MAIN DATABASE FUNCTIONS
# =====================================================

def load_data():

    # -------------------------------------------------
    # If GitHub is configured, GitHub is the main DB
    # -------------------------------------------------

    if GITHUB_TOKEN:

        github_data = load_data_from_github()

        if github_data is not None:

            # Keep local copy too
            save_local_data(
                github_data
            )

            return github_data

    # -------------------------------------------------
    # Fallback to local data
    # -------------------------------------------------

    return load_local_data()


def save_data(data):

    # -------------------------------------------------
    # Always keep local copy
    # -------------------------------------------------

    local_saved = save_local_data(
        data
    )

    # -------------------------------------------------
    # Persistent GitHub storage
    # -------------------------------------------------

    if GITHUB_TOKEN:

        github_saved = save_data_to_github(
            data
        )

        if github_saved:
            return True

        print(
            "GitHub save failed."
        )

    return local_saved


# =====================================================
# TIME
# =====================================================

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
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as e:

        print(
            "BALE ERROR:",
            e
        )

        return False


# =====================================================
# HOME / ADMIN
# =====================================================

@app.route("/")
def home():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/admin")
def admin_page():

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


@app.route("/shop.html")
def shop_html():

    return send_from_directory(
        BASE_DIR,
        "shop.html"
    )


@app.route("/index.html")
def index_html():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


# =====================================================
# HEALTH
# =====================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "status": "online",
        "panel": True,
        "persistent_storage":
            bool(GITHUB_TOKEN)
    })


# =====================================================
# SERVICE REQUEST
# =====================================================

@app.route("/api/request", methods=["POST"])
def service_request():

    data = request.get_json(
        silent=True
    ) or {}

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

    if not name or not phone or not service:

        return jsonify({
            "success": False,
            "message":
                "لطفاً نام، شماره تماس و نوع خدمت را وارد کنید."
        }), 400

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

    database = load_data()

    database[
        "requests"
    ].append(item)

    if not save_data(database):

        return jsonify({
            "success": False,
            "message":
                "ذخیره درخواست انجام نشد."
        }), 500

    bale_sent = send_bale_message(

        "📥 درخواست جدید دکتر برودت\n\n"

        f"👤 نام مشتری: {name}\n"

        f"📱 شماره تماس: {phone}\n"

        f"🔧 خدمت: {service}\n"

        f"📝 توضیحات: "
        f"{description or 'ثبت نشده'}"
    )

    return jsonify({

        "success": True,

        "message":
            "درخواست شما با موفقیت ثبت شد ❤️",

        "bale_sent": bale_sent,

        "request": item

    })


# =====================================================
# CHAT GET
# =====================================================

@app.route("/chat", methods=["GET"])
def get_chat():

    phone = request.args.get(
        "phone",
        ""
    ).strip()

    database = load_data()

    if not phone:

        return jsonify({
            "success": True,
            "messages": []
        })

    chat = next(
        (
            item
            for item in database[
                "chats"
            ]
            if item.get(
                "phone"
            ) == phone
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

        "chat_id":
            chat.get("id"),

        "name":
            chat.get("name", ""),

        "phone":
            chat.get("phone", ""),

        "messages":
            chat.get("messages", [])

    })


# =====================================================
# CHAT SEND
# =====================================================

@app.route("/chat/send", methods=["POST"])
def send_chat():

    data = request.get_json(
        silent=True
    ) or {}

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
            for item in database[
                "chats"
            ]
            if item.get(
                "phone"
            ) == phone
        ),
        None
    )

    if not chat:

        chat = {

            "id": str(
                uuid.uuid4()
            ),

            "name": name,

            "phone": phone,

            "created_at": now(),

            "updated_at": now(),

            "messages": []

        }

        database[
            "chats"
        ].append(chat)

    else:

        chat["name"] = name

        chat["updated_at"] = now()

    customer_message = {

        "id": str(
            uuid.uuid4()
        ),

        "sender": "customer",

        "message": message,

        "created_at": now()

    }

    chat.setdefault(
        "messages",
        []
    ).append(
        customer_message
    )

    chat["updated_at"] = now()

    if not save_data(database):

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

    })


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route(
    "/api/admin/dashboard",
    methods=["GET"]
)
def admin_dashboard():

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

    })


# =====================================================
# ADMIN CHAT REPLY
# =====================================================

@app.route(
    "/api/admin/chat/reply",
    methods=["POST"]
)
def admin_chat_reply():

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
            for item in database[
                "chats"
            ]
            if item.get(
                "id"
            ) == chat_id
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

        "id": str(
            uuid.uuid4()
        ),

        "sender": "admin",

        "message": message,

        "created_at": now()

    }

    chat.setdefault(
        "messages",
        []
    ).append(
        admin_message
    )

    chat["updated_at"] = now()

    if not save_data(database):

        return jsonify({
            "success": False,
            "message":
                "ذخیره پاسخ انجام نشد."
        }), 500

    return jsonify({

        "success": True,

        "message":
            "پاسخ ارسال شد.",

        "chat_id":
            chat_id,

        "reply":
            admin_message

    })


# =====================================================
# PRODUCTS - ADD
# =====================================================

@app.route(
    "/api/admin/products",
    methods=["POST"]
)
def add_product():

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

    # -------------------------------------------------
    # هر ثبت محصول یک ID کاملاً جدید می‌گیرد
    # -------------------------------------------------

    product = {

        "id": str(
            uuid.uuid4()
        ),

        "name": name,

        "price": price,

        "stock": stock,

        "category": category,

        "description": description,

        "image": image,

        "created_at": now()

    }

    database = load_data()

    database[
        "products"
    ].append(product)

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

    })


# =====================================================
# PRODUCTS - GET
# =====================================================

@app.route(
    "/api/products",
    methods=["GET"]
)
def get_products():

    database = load_data()

    return jsonify({

        "success": True,

        "products":
            database["products"]

    })


# =====================================================
# PRODUCTS - UPDATE
# =====================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["PATCH"]
)
def update_product(product_id):

    data = request.get_json(
        silent=True
    ) or {}

    database = load_data()

    product = next(
        (
            item
            for item in database[
                "products"
            ]
            if item.get(
                "id"
            ) == product_id
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

    })


# =====================================================
# PRODUCTS - DELETE
# =====================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["DELETE"]
)
def delete_product(product_id):

    database = load_data()

    old_count = len(
        database["products"]
    )

    database["products"] = [

        product

        for product in database[
            "products"
        ]

        if product.get(
            "id"
        ) != product_id

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

    })


# =====================================================
# ORDERS - CREATE
# =====================================================

@app.route(
    "/api/order",
    methods=["POST"]
)
def create_order():

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
                for item in database[
                    "products"
                ]
                if item.get(
                    "id"
                ) == product_id
            ),
            None
        )

    order = {

        "id": str(
            uuid.uuid4()
        ),

        "name": name,

        "phone": phone,

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

    database[
        "orders"
    ].append(order)

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

    })


# =====================================================
# ORDERS - UPDATE
# =====================================================

@app.route(
    "/api/admin/orders/<order_id>",
    methods=["PATCH"]
)
def update_order(order_id):

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
            for item in database[
                "orders"
            ]
            if item.get(
                "id"
            ) == order_id
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

    })


# =====================================================
# ADMIN REQUESTS - GET
# =====================================================

@app.route(
    "/api/admin/requests",
    methods=["GET"]
)
def admin_requests():

    database = load_data()

    return jsonify({

        "success": True,

        "requests":
            database["requests"]

    })


# =====================================================
# ADMIN REQUESTS - UPDATE
# =====================================================

@app.route(
    "/api/admin/requests/<request_id>",
    methods=["PATCH"]
)
def update_service_request(request_id):

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
            for x in database[
                "requests"
            ]
            if x.get(
                "id"
            ) == request_id
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

    })


# =====================================================
# ERROR HANDLERS
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
            "10000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
