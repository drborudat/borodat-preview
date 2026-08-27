import os
import uuid
from datetime import datetime

import requests
import psycopg
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

DATABASE_URL = os.environ.get("DATABASE_URL")


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_database_url():
    url = os.environ.get("DATABASE_URL")

    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    # Render/PostgreSQL sometimes provides postgres://
    # psycopg accepts postgresql:// reliably.
    if url.startswith("postgres://"):
        url = url.replace(
            "postgres://",
            "postgresql://",
            1
        )

    return url


def get_connection():
    return psycopg.connect(
        get_database_url(),
        connect_timeout=15
    )


# =====================================================
# DATABASE INITIALIZATION
# =====================================================

def init_database():

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            # -----------------------------------------
            # REQUESTS
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    service TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'new'
                )
            """)

            # -----------------------------------------
            # CHATS
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # -----------------------------------------
            # CHAT MESSAGES
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(chat_id)
                        REFERENCES chats(id)
                        ON DELETE CASCADE
                )
            """)

            # -----------------------------------------
            # PRODUCTS
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    price TEXT NOT NULL,
                    stock TEXT DEFAULT '0',
                    category TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    image TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)

            # -----------------------------------------
            # ORDERS
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    product_id TEXT DEFAULT '',
                    product_name TEXT NOT NULL,
                    quantity TEXT DEFAULT '1',
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'new'
                )
            """)

        connection.commit()

    finally:

        connection.close()


# =====================================================
# STARTUP DATABASE
# =====================================================

try:

    if DATABASE_URL:
        init_database()
        print("DATABASE: PostgreSQL connected successfully.")

    else:
        print(
            "DATABASE ERROR: DATABASE_URL is not configured."
        )

except Exception as e:

    print(
        "DATABASE INITIALIZATION ERROR:",
        e
    )


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

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    database_ok = False

    try:

        connection = get_connection()

        connection.close()

        database_ok = True

    except Exception as e:

        print(
            "HEALTH DATABASE ERROR:",
            e
        )

    return jsonify({

        "success": True,

        "status": "online",

        "panel": True,

        "database": database_ok

    })


# =====================================================
# SERVICE REQUEST
# =====================================================

@app.route(
    "/api/request",
    methods=["POST"]
)
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

        "id": str(uuid.uuid4()),

        "name": name,

        "phone": phone,

        "service": service,

        "description": description,

        "created_at": now(),

        "status": "new"

    }

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                INSERT INTO requests
                (
                    id,
                    name,
                    phone,
                    service,
                    description,
                    created_at,
                    status
                )

                VALUES
                (%s,%s,%s,%s,%s,%s,%s)

            """, (

                item["id"],
                item["name"],
                item["phone"],
                item["service"],
                item["description"],
                item["created_at"],
                item["status"]

            ))

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "REQUEST SAVE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره درخواست انجام نشد."

        }), 500

    finally:

        connection.close()

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

@app.route(
    "/chat",
    methods=["GET"]
)
def get_chat():

    phone = request.args.get(
        "phone",
        ""
    ).strip()

    if not phone:

        return jsonify({

            "success": True,

            "messages": []

        })

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT
                    id,
                    name,
                    phone,
                    created_at,
                    updated_at

                FROM chats

                WHERE phone = %s

                LIMIT 1

            """, (phone,))

            chat_row = cur.fetchone()

            if not chat_row:

                return jsonify({

                    "success": True,

                    "messages": []

                })

            chat_id = chat_row[0]

            cur.execute("""

                SELECT
                    id,
                    sender,
                    message,
                    created_at

                FROM chat_messages

                WHERE chat_id = %s

                ORDER BY created_at ASC

            """, (chat_id,))

            rows = cur.fetchall()

            messages = [

                {

                    "id": row[0],

                    "sender": row[1],

                    "message": row[2],

                    "created_at": row[3]

                }

                for row in rows

            ]

            return jsonify({

                "success": True,

                "chat_id": chat_id,

                "name": chat_row[1],

                "phone": chat_row[2],

                "messages": messages

            })

    finally:

        connection.close()


# =====================================================
# CHAT SEND
# =====================================================

@app.route(
    "/chat/send",
    methods=["POST"]
)
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

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT
                    id

                FROM chats

                WHERE phone = %s

                LIMIT 1

            """, (phone,))

            row = cur.fetchone()

            if row:

                chat_id = row[0]

                cur.execute("""

                    UPDATE chats

                    SET
                        name = %s,
                        updated_at = %s

                    WHERE id = %s

                """, (

                    name,
                    now(),
                    chat_id

                ))

            else:

                chat_id = str(
                    uuid.uuid4()
                )

                cur.execute("""

                    INSERT INTO chats
                    (
                        id,
                        name,
                        phone,
                        created_at,
                        updated_at
                    )

                    VALUES
                    (%s,%s,%s,%s,%s)

                """, (

                    chat_id,
                    name,
                    phone,
                    now(),
                    now()

                ))

            message_id = str(
                uuid.uuid4()
            )

            cur.execute("""

                INSERT INTO chat_messages
                (
                    id,
                    chat_id,
                    sender,
                    message,
                    created_at
                )

                VALUES
                (%s,%s,%s,%s,%s)

            """, (

                message_id,
                chat_id,
                "customer",
                message,
                now()

            ))

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "CHAT SAVE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره پیام انجام نشد."

        }), 500

    finally:

        connection.close()

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

        "chat_id": chat_id,

        "bale_sent": bale_sent

    })


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route(
    "/api/admin/dashboard",
    methods=["GET"]
)
def admin_dashboard():

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            # -----------------------------------------
            # REQUESTS
            # -----------------------------------------

            cur.execute("""

                SELECT
                    id,
                    name,
                    phone,
                    service,
                    description,
                    created_at,
                    status

                FROM requests

                ORDER BY created_at DESC

            """)

            request_rows = cur.fetchall()

            requests_data = [

                {

                    "id": row[0],
                    "name": row[1],
                    "phone": row[2],
                    "service": row[3],
                    "description": row[4],
                    "created_at": row[5],
                    "status": row[6]

                }

                for row in request_rows

            ]

            # -----------------------------------------
            # CHATS
            # -----------------------------------------

            cur.execute("""

                SELECT
                    id,
                    name,
                    phone,
                    created_at,
                    updated_at

                FROM chats

                ORDER BY updated_at DESC

            """)

            chat_rows = cur.fetchall()

            chats_data = []

            for row in chat_rows:

                chat_id = row[0]

                cur.execute("""

                    SELECT
                        id,
                        sender,
                        message,
                        created_at

                    FROM chat_messages

                    WHERE chat_id = %s

                    ORDER BY created_at ASC

                """, (chat_id,))

                message_rows = cur.fetchall()

                messages = [

                    {

                        "id": msg[0],

                        "sender": msg[1],

                        "message": msg[2],

                        "created_at": msg[3]

                    }

                    for msg in message_rows

                ]

                chats_data.append({

                    "id": chat_id,

                    "name": row[1],

                    "phone": row[2],

                    "created_at": row[3],

                    "updated_at": row[4],

                    "messages": messages

                })

            # -----------------------------------------
            # PRODUCTS
            # -----------------------------------------

            cur.execute("""

                SELECT
                    id,
                    name,
                    price,
                    stock,
                    category,
                    description,
                    image,
                    created_at

                FROM products

                ORDER BY created_at DESC

            """)

            product_rows = cur.fetchall()

            products_data = [

                {

                    "id": row[0],

                    "name": row[1],

                    "price": row[2],

                    "stock": row[3],

                    "category": row[4],

                    "description": row[5],

                    "image": row[6],

                    "created_at": row[7]

                }

                for row in product_rows

            ]

            # -----------------------------------------
            # ORDERS
            # -----------------------------------------

            cur.execute("""

                SELECT
                    id,
                    name,
                    phone,
                    product_id,
                    product_name,
                    quantity,
                    created_at,
                    status

                FROM orders

                ORDER BY created_at DESC

            """)

            order_rows = cur.fetchall()

            orders_data = [

                {

                    "id": row[0],

                    "name": row[1],

                    "phone": row[2],

                    "product_id": row[3],

                    "product_name": row[4],

                    "quantity": row[5],

                    "created_at": row[6],

                    "status": row[7]

                }

                for row in order_rows

            ]

            return jsonify({

                "success": True,

                "requests":
                requests_data,

                "chats":
                chats_data,

                "products":
                products_data,

                "orders":
                orders_data

            })

    finally:

        connection.close()


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

    admin_message = {

        "id": str(uuid.uuid4()),

        "sender": "admin",

        "message": message,

        "created_at": now()

    }

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT id

                FROM chats

                WHERE id = %s

                LIMIT 1

            """, (chat_id,))

            chat = cur.fetchone()

            if not chat:

                return jsonify({

                    "success": False,

                    "message":
                    "گفتگو پیدا نشد."

                }), 404

            cur.execute("""

                INSERT INTO chat_messages
                (
                    id,
                    chat_id,
                    sender,
                    message,
                    created_at
                )

                VALUES
                (%s,%s,%s,%s,%s)

            """, (

                admin_message["id"],

                chat_id,

                "admin",

                message,

                admin_message["created_at"]

            ))

            cur.execute("""

                UPDATE chats

                SET updated_at = %s

                WHERE id = %s

            """, (

                now(),

                chat_id

            ))

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "ADMIN CHAT ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره پاسخ انجام نشد."

        }), 500

    finally:

        connection.close()

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

    # IMPORTANT:
    # Every product receives a completely new UUID.
    # Therefore two products with the same name
    # are still stored as separate products.

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

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                INSERT INTO products
                (
                    id,
                    name,
                    price,
                    stock,
                    category,
                    description,
                    image,
                    created_at
                )

                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s)

            """, (

                product["id"],

                product["name"],

                product["price"],

                product["stock"],

                product["category"],

                product["description"],

                product["image"],

                product["created_at"]

            ))

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "PRODUCT SAVE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره محصول انجام نشد."

        }), 500

    finally:

        connection.close()

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

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT
                    id,
                    name,
                    price,
                    stock,
                    category,
                    description,
                    image,
                    created_at

                FROM products

                ORDER BY created_at DESC

            """)

            rows = cur.fetchall()

            products = [

                {

                    "id": row[0],

                    "name": row[1],

                    "price": row[2],

                    "stock": row[3],

                    "category": row[4],

                    "description": row[5],

                    "image": row[6],

                    "created_at": row[7]

                }

                for row in rows

            ]

            return jsonify({

                "success": True,

                "products": products,

                "count": len(products)

            })

    finally:

        connection.close()


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

    allowed_fields = [

        "name",
        "price",
        "stock",
        "category",
        "description",
        "image"

    ]

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT id

                FROM products

                WHERE id = %s

                LIMIT 1

            """, (product_id,))

            product = cur.fetchone()

            if not product:

                return jsonify({

                    "success": False,

                    "message":
                    "محصول پیدا نشد."

                }), 404

            updates = []

            values = []

            for field in allowed_fields:

                if field in data:

                    updates.append(
                        f"{field} = %s"
                    )

                    values.append(
                        str(
                            data[field]
                        ).strip()
                    )

            if updates:

                values.append(
                    product_id
                )

                query = """

                    UPDATE products

                    SET
                        {fields}

                    WHERE id = %s

                """.format(

                    fields=", ".join(
                        updates
                    )

                )

                cur.execute(
                    query,
                    values
                )

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "PRODUCT UPDATE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره تغییرات محصول انجام نشد."

        }), 500

    finally:

        connection.close()

    return jsonify({

        "success": True,

        "message":
        "محصول ویرایش شد.",

        "product_id":
        product_id

    })


# =====================================================
# PRODUCTS - DELETE
# =====================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["DELETE"]
)
def delete_product(product_id):

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                DELETE FROM products

                WHERE id = %s

            """, (product_id,))

            deleted = cur.rowcount

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "PRODUCT DELETE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "حذف محصول ذخیره نشد."

        }), 500

    finally:

        connection.close()

    if deleted == 0:

        return jsonify({

            "success": False,

            "message":
            "محصول پیدا نشد."

        }), 404

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

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            product = None

            if product_id:

                cur.execute("""

                    SELECT id

                    FROM products

                    WHERE id = %s

                    LIMIT 1

                """, (product_id,))

                product = cur.fetchone()

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

            cur.execute("""

                INSERT INTO orders
                (
                    id,
                    name,
                    phone,
                    product_id,
                    product_name,
                    quantity,
                    created_at,
                    status
                )

                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s)

            """, (

                order["id"],

                order["name"],

                order["phone"],

                order["product_id"],

                order["product_name"],

                order["quantity"],

                order["created_at"],

                order["status"]

            ))

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "ORDER SAVE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره سفارش انجام نشد."

        }), 500

    finally:

        connection.close()

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

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                UPDATE orders

                SET status = %s

                WHERE id = %s

            """, (

                status,

                order_id

            ))

            updated = cur.rowcount

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "ORDER UPDATE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره وضعیت سفارش انجام نشد."

        }), 500

    finally:

        connection.close()

    if updated == 0:

        return jsonify({

            "success": False,

            "message":
            "سفارش پیدا نشد."

        }), 404

    return jsonify({

        "success": True,

        "message":
        "وضعیت سفارش تغییر کرد.",

        "order_id":
        order_id,

        "status":
        status

    })


# =====================================================
# ADMIN REQUESTS - GET
# =====================================================

@app.route(
    "/api/admin/requests",
    methods=["GET"]
)
def admin_requests():

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT
                    id,
                    name,
                    phone,
                    service,
                    description,
                    created_at,
                    status

                FROM requests

                ORDER BY created_at DESC

            """)

            rows = cur.fetchall()

            requests_data = [

                {

                    "id": row[0],

                    "name": row[1],

                    "phone": row[2],

                    "service": row[3],

                    "description": row[4],

                    "created_at": row[5],

                    "status": row[6]

                }

                for row in rows

            ]

            return jsonify({

                "success": True,

                "requests":
                requests_data

            })

    finally:

        connection.close()


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

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                UPDATE requests

                SET status = %s

                WHERE id = %s

            """, (

                status,

                request_id

            ))

            updated = cur.rowcount

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "REQUEST UPDATE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ذخیره وضعیت درخواست انجام نشد."

        }), 500

    finally:

        connection.close()

    if updated == 0:

        return jsonify({

            "success": False,

            "message":
            "درخواست پیدا نشد."

        }), 404

    return jsonify({

        "success": True,

        "message":
        "وضعیت درخواست تغییر کرد.",

        "request_id":
        request_id,

        "status":
        status

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
