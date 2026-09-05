import os
import uuid
import json
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

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "videos")


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_database_url():

    url = os.environ.get("DATABASE_URL")

    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

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

            # -----------------------------------------
            # ORDER MIGRATION
            # -----------------------------------------

            cur.execute("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS address TEXT DEFAULT ''
            """)

            cur.execute("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS postal_code TEXT DEFAULT ''
            """)

            cur.execute("""
                ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS items TEXT DEFAULT '[]'
            """)

            # -----------------------------------------
            # REVIEWS
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'approved'
                )
            """)

            # -----------------------------------------
            # VIDEOS
            # -----------------------------------------

            cur.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    cover TEXT DEFAULT '',
                    video_url TEXT NOT NULL,
                    created_at TEXT NOT NULL
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

        print(
            "DATABASE: PostgreSQL connected successfully."
        )

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
# REVIEWS - CREATE
# =====================================================

@app.route(
    "/api/reviews",
    methods=["POST"]
)
def create_review():

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get("name", "")
    ).strip()

    comment = str(
        data.get(
            "comment",
            data.get(
                "text",
                ""
            )
        )
    ).strip()

    try:

        rating = int(
            data.get(
                "rating",
                5
            )
        )

    except Exception:

        rating = 5

    # -----------------------------------------
    # VALIDATION
    # -----------------------------------------

    if not name:

        return jsonify({

            "success": False,

            "message":
            "لطفاً نام خود را وارد کنید."

        }), 400

    if not comment:

        return jsonify({

            "success": False,

            "message":
            "لطفاً متن نظر را وارد کنید."

        }), 400

    if rating < 1 or rating > 5:

        return jsonify({

            "success": False,

            "message":
            "امتیاز باید بین ۱ تا ۵ باشد."

        }), 400

    review = {

        "id":
        str(uuid.uuid4()),

        "name":
        name,

        "rating":
        rating,

        "comment":
        comment,

        "created_at":
        now(),

        "status":
        "approved"

    }

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                INSERT INTO reviews
                (
                    id,
                    name,
                    rating,
                    comment,
                    created_at,
                    status
                )

                VALUES
                (%s,%s,%s,%s,%s,%s)

            """, (

                review["id"],

                review["name"],

                review["rating"],

                review["comment"],

                review["created_at"],

                review["status"]

            ))

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "REVIEW SAVE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "ثبت نظر انجام نشد."

        }), 500

    finally:

        connection.close()

    # -----------------------------------------
    # BALE NOTIFICATION
    # -----------------------------------------

    bale_sent = send_bale_message(

        "⭐ نظر جدید در سایت دکتر برودت\n\n"

        f"👤 نام: {name}\n"

        f"⭐ امتیاز: {rating}/5\n\n"

        f"💬 {comment}"

    )

    return jsonify({

        "success": True,

        "message":
        "نظر شما با موفقیت ثبت شد ❤️",

        "review":
        review,

        "bale_sent":
        bale_sent

    })


# =====================================================
# REVIEWS - GET
# =====================================================

@app.route(
    "/api/reviews",
    methods=["GET"]
)
def get_reviews():

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT
                    id,
                    name,
                    rating,
                    comment,
                    created_at,
                    status

                FROM reviews

                WHERE status = 'approved'

                ORDER BY created_at DESC

            """)

            rows = cur.fetchall()

            reviews = [

                {

                    "id": row[0],

                    "name": row[1],

                    "rating": row[2],

                    "comment": row[3],

                    "text": row[3],

                    "created_at": row[4],

                    "status": row[5]

                }

                for row in rows

            ]

            return jsonify({

                "success": True,

                "reviews":
                reviews,

                "count":
                len(reviews)

            })

    finally:

        connection.close()


# =====================================================
# ADMIN REVIEWS - GET
# =====================================================

@app.route(
    "/api/admin/reviews",
    methods=["GET"]
)
def admin_reviews():

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                SELECT
                    id,
                    name,
                    rating,
                    comment,
                    created_at,
                    status

                FROM reviews

                ORDER BY created_at DESC

            """)

            rows = cur.fetchall()

            reviews = [

                {

                    "id": row[0],

                    "name": row[1],

                    "rating": row[2],

                    "comment": row[3],

                    "text": row[3],

                    "created_at": row[4],

                    "status": row[5]

                }

                for row in rows

            ]

            return jsonify({

                "success": True,

                "reviews":
                reviews

            })

    finally:

        connection.close()


# =====================================================
# ADMIN REVIEWS - UPDATE
# =====================================================

@app.route(
    "/api/admin/reviews/<review_id>",
    methods=["PATCH"]
)
def update_review(review_id):

    data = request.get_json(
        silent=True
    ) or {}

    status = str(
        data.get(
            "status",
            ""
        )
    ).strip()

    if status not in [
        "approved",
        "pending",
        "rejected"
    ]:

        return jsonify({

            "success": False,

            "message":
            "وضعیت نظر نامعتبر است."

        }), 400

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                UPDATE reviews

                SET status = %s

                WHERE id = %s

            """, (

                status,

                review_id

            ))

            updated = cur.rowcount

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "REVIEW UPDATE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "تغییر وضعیت نظر انجام نشد."

        }), 500

    finally:

        connection.close()

    if updated == 0:

        return jsonify({

            "success": False,

            "message":
            "نظر پیدا نشد."

        }), 404

    return jsonify({

        "success": True,

        "message":
        "وضعیت نظر تغییر کرد.",

        "review_id":
        review_id,

        "status":
        status

    })


# =====================================================
# ADMIN REVIEWS - DELETE
# =====================================================

@app.route(
    "/api/admin/reviews/<review_id>",
    methods=["DELETE"]
)
def delete_review(review_id):

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""

                DELETE FROM reviews

                WHERE id = %s

            """, (review_id,))

            deleted = cur.rowcount

        connection.commit()

    except Exception as e:

        connection.rollback()

        print(
            "REVIEW DELETE ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "حذف نظر انجام نشد."

        }), 500

    finally:

        connection.close()

    if deleted == 0:

        return jsonify({

            "success": False,

            "message":
            "نظر پیدا نشد."

        }), 404

    return jsonify({

        "success": True,

        "message":
        "نظر حذف شد."

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
                    status,
                    address,
                    postal_code,
                    items

                FROM orders

                ORDER BY created_at DESC

            """)

            order_rows = cur.fetchall()

            orders_data = []

            for row in order_rows:

                items = []

                try:

                    if row[10]:

                        items = json.loads(
                            row[10]
                        )

                except Exception:

                    items = []

                orders_data.append({

                    "id": row[0],

                    "name": row[1],

                    "phone": row[2],

                    "product_id": row[3],

                    "product_name": row[4],

                    "quantity": row[5],

                    "created_at": row[6],

                    "status": row[7],

                    "address": row[8] or "",

                    "postal_code": row[9] or "",

                    "items": items

                })

            # -----------------------------------------
            # REVIEWS
            # -----------------------------------------

            cur.execute("""

                SELECT
                    id,
                    name,
                    rating,
                    comment,
                    created_at,
                    status

                FROM reviews

                ORDER BY created_at DESC

            """)

            review_rows = cur.fetchall()

            reviews_data = [

                {

                    "id": row[0],

                    "name": row[1],

                    "rating": row[2],

                    "comment": row[3],

                    "text": row[3],

                    "created_at": row[4],

                    "status": row[5]

                }

                for row in review_rows

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
                orders_data,

                "reviews":
                reviews_data

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
# =====================================================
# SUPABASE STORAGE HELPERS
# =====================================================

def upload_to_supabase(file_storage, folder):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("تنظیمات Supabase در Render کامل نیست.")

    filename = file_storage.filename or "file"
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in filename
    )
    path = f"{folder}/{uuid.uuid4()}_{safe_name}"

    url = (
        f"{SUPABASE_URL}/storage/v1/object/"
        f"{SUPABASE_BUCKET}/{path}"
    )

    content_type = file_storage.mimetype or "application/octet-stream"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": content_type,
            "x-upsert": "false"
        },
        data=file_storage.stream,
        timeout=120
    )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Supabase upload failed: {response.text}"
        )

    return (
        f"{SUPABASE_URL}/storage/v1/object/public/"
        f"{SUPABASE_BUCKET}/{path}"
    )


# VIDEOS
# =====================================================

@app.route(
    "/api/videos",
    methods=["GET"]
)
def get_videos():

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    title,
                    description,
                    cover,
                    video_url,
                    created_at
                FROM videos
                ORDER BY created_at DESC
            """)

            rows = cur.fetchall()

            videos = [
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "cover": row[3],
                    "video_url": row[4],
                    "created_at": row[5]
                }
                for row in rows
            ]

        return jsonify({
            "success": True,
            "videos": videos
        })

    except Exception as e:

        print(
            "VIDEOS LOAD ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "دریافت ویدیوها انجام نشد."
        }), 500

    finally:

        connection.close()


@app.route(
    "/api/admin/videos",
    methods=["POST"]
)
def add_video():

    title = str(request.form.get("title", "")).strip()
    description = str(request.form.get("description", "")).strip()

    video_file = request.files.get("video")
    cover_file = request.files.get("cover")

    if not title or not video_file or not video_file.filename:
        return jsonify({
            "success": False,
            "message": "عنوان و فایل ویدیو الزامی است."
        }), 400

    if not video_file.mimetype.startswith("video/"):
        return jsonify({
            "success": False,
            "message": "فایل انتخاب‌شده ویدیو نیست."
        }), 400

    if cover_file and cover_file.filename:
        if not cover_file.mimetype.startswith("image/"):
            return jsonify({
                "success": False,
                "message": "فایل کاور باید تصویر باشد."
            }), 400

    try:
        video_url = upload_to_supabase(video_file, "videos")

        cover_url = ""
        if cover_file and cover_file.filename:
            cover_url = upload_to_supabase(cover_file, "covers")

        video = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "cover": cover_url,
            "video_url": video_url,
            "created_at": now()
        }

        connection = get_connection()

        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO videos
                    (
                        id,
                        title,
                        description,
                        cover,
                        video_url,
                        created_at
                    )
                    VALUES
                    (%s,%s,%s,%s,%s,%s)
                """, (
                    video["id"],
                    video["title"],
                    video["description"],
                    video["cover"],
                    video["video_url"],
                    video["created_at"]
                ))

            connection.commit()

        finally:
            connection.close()

        return jsonify({
            "success": True,
            "message": "ویدیو با موفقیت آپلود و ثبت شد.",
            "video": video
        })

    except Exception as e:
        print("VIDEO UPLOAD ERROR:", e)

        return jsonify({
            "success": False,
            "message": "آپلود ویدیو انجام نشد."
        }), 500


@app.route(
    "/api/admin/videos/<video_id>",
    methods=["PATCH"]
)
def update_video(video_id):

    title = str(request.form.get("title", "")).strip()
    description = str(request.form.get("description", "")).strip()

    video_file = request.files.get("video")
    cover_file = request.files.get("cover")

    if not title:
        return jsonify({
            "success": False,
            "message": "عنوان ویدیو الزامی است."
        }), 400

    connection = get_connection()

    try:
        with connection.cursor() as cur:

            cur.execute("""
                SELECT cover, video_url
                FROM videos
                WHERE id = %s
            """, (video_id,))

            old = cur.fetchone()

            if not old:
                return jsonify({
                    "success": False,
                    "message": "ویدیو پیدا نشد."
                }), 404

            old_cover = old[0] or ""
            old_video_url = old[1] or ""

            video_url = old_video_url
            cover_url = old_cover

            if video_file and video_file.filename:
                if not video_file.mimetype.startswith("video/"):
                    return jsonify({
                        "success": False,
                        "message": "فایل جدید باید ویدیو باشد."
                    }), 400

                video_url = upload_to_supabase(
                    video_file,
                    "videos"
                )

            if cover_file and cover_file.filename:
                if not cover_file.mimetype.startswith("image/"):
                    return jsonify({
                        "success": False,
                        "message": "فایل کاور باید تصویر باشد."
                    }), 400

                cover_url = upload_to_supabase(
                    cover_file,
                    "covers"
                )

            cur.execute("""
                UPDATE videos
                SET
                    title = %s,
                    description = %s,
                    cover = %s,
                    video_url = %s
                WHERE id = %s
            """, (
                title,
                description,
                cover_url,
                video_url,
                video_id
            ))

        connection.commit()

    except Exception as e:
        connection.rollback()

        print(
            "VIDEO UPDATE ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "ویرایش ویدیو انجام نشد."
        }), 500

    finally:
        connection.close()

    return jsonify({
        "success": True,
        "message": "ویدیو با موفقیت ویرایش شد."
    })


@app.route(
    "/api/admin/videos/<video_id>",
    methods=["DELETE"]
)
def delete_video(video_id):

    connection = get_connection()

    try:
        with connection.cursor() as cur:

            cur.execute("""
                SELECT cover, video_url
                FROM videos
                WHERE id = %s
            """, (video_id,))

            row = cur.fetchone()

            if not row:
                return jsonify({
                    "success": False,
                    "message": "ویدیو پیدا نشد."
                }), 404

            cover_url = row[0] or ""
            video_url = row[1] or ""

            cur.execute("""
                DELETE FROM videos
                WHERE id = %s
            """, (video_id,))

        connection.commit()

        for file_url in (video_url, cover_url):
            if file_url and SUPABASE_URL in file_url:
                try:
                    prefix = (
                        f"{SUPABASE_URL}/storage/v1/object/"
                        f"public/{SUPABASE_BUCKET}/"
                    )

                    if file_url.startswith(prefix):
                        file_path = file_url[len(prefix):]

                        delete_url = (
                            f"{SUPABASE_URL}/storage/v1/object/"
                            f"{SUPABASE_BUCKET}/{file_path}"
                        )

                        requests.delete(
                            delete_url,
                            headers={
                                "Authorization":
                                    f"Bearer {SUPABASE_KEY}",
                                "apikey": SUPABASE_KEY
                            }
                        )
                except Exception as storage_error:
                    print(
                        "STORAGE DELETE ERROR:",
                        storage_error
                    )

    except Exception as e:
        connection.rollback()

        print(
            "VIDEO DELETE ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": "حذف ویدیو انجام نشد."
        }), 500

    finally:
        connection.close()

    return jsonify({
        "success": True,
        "message": "ویدیو و فایل‌های آن با موفقیت حذف شدند."
    })


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

    address = str(
        data.get("address", "")
    ).strip()

    postal_code = str(
        data.get("postal_code", "")
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

    raw_items = data.get(
        "items",
        []
    )

    if not isinstance(
        raw_items,
        list
    ):

        raw_items = []

    items = []

    for item in raw_items:

        if not isinstance(
            item,
            dict
        ):

            continue

        item_id = str(
            item.get(
                "id",
                item.get(
                    "product_id",
                    ""
                )
            )
        ).strip()

        item_name = str(
            item.get(
                "name",
                item.get(
                    "product_name",
                    ""
                )
            )
        ).strip()

        item_price = str(
            item.get(
                "price",
                ""
            )
        ).strip()

        item_quantity = str(
            item.get(
                "quantity",
                "1"
            )
        ).strip()

        if not item_name:

            continue

        items.append({

            "id": item_id,

            "name": item_name,

            "price": item_price,

            "quantity": item_quantity

        })

    if not items and product_name:

        items.append({

            "id": product_id,

            "name": product_name,

            "price": "",

            "quantity": quantity

        })

    if not name:

        return jsonify({

            "success": False,

            "message":
            "نام و نام خانوادگی الزامی است."

        }), 400

    if not phone:

        return jsonify({

            "success": False,

            "message":
            "شماره تلفن الزامی است."

        }), 400

    if not address:

        return jsonify({

            "success": False,

            "message":
            "آدرس کامل الزامی است."

        }), 400

    if not postal_code:

        return jsonify({

            "success": False,

            "message":
            "کد پستی الزامی است."

        }), 400

    if not items:

        return jsonify({

            "success": False,

            "message":
            "سبد خرید خالی است."

        }), 400

    first_item = items[0]

    first_product_id = str(
        first_item.get(
            "id",
            ""
        )
    ).strip()

    first_product_name = str(
        first_item.get(
            "name",
            ""
        )
    ).strip()

    if len(items) == 1:

        order_product_name = first_product_name

    else:

        order_product_name = (
            f"{first_product_name} "
            f"+ {len(items) - 1} محصول دیگر"
        )

    order_quantity = str(
        sum(
            int(
                item.get(
                    "quantity",
                    1
                )
            )
            if str(
                item.get(
                    "quantity",
                    1
                )
            ).isdigit()
            else 1
            for item in items
        )
    )

    order = {

        "id":
        str(uuid.uuid4()),

        "name":
        name,

        "phone":
        phone,

        "product_id":
        first_product_id,

        "product_name":
        order_product_name,

        "quantity":
        order_quantity,

        "address":
        address,

        "postal_code":
        postal_code,

        "items":
        items,

        "created_at":
        now(),

        "status":
        "new"

    }

    connection = get_connection()

    try:

        with connection.cursor() as cur:

            verified_product_ids = []

            for item in items:

                item_id = str(
                    item.get(
                        "id",
                        ""
                    )
                ).strip()

                if not item_id:

                    continue

                cur.execute("""

                    SELECT id

                    FROM products

                    WHERE id = %s

                    LIMIT 1

                """, (item_id,))

                found = cur.fetchone()

                if found:

                    verified_product_ids.append(
                        item_id
                    )

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
                    status,
                    address,
                    postal_code,
                    items
                )

                VALUES
                (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )

            """, (

                order["id"],
                order["name"],
                order["phone"],
                order["product_id"],
                order["product_name"],
                order["quantity"],
                order["created_at"],
                order["status"],
                order["address"],
                order["postal_code"],
                json.dumps(
                    order["items"],
                    ensure_ascii=False
                )

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

    bale_text = (
        "🛒 سفارش جدید دکتر برودت\n\n"
        f"👤 نام: {name}\n"
        f"📱 شماره: {phone}\n"
        f"🏠 آدرس: {address}\n"
        f"📮 کد پستی: {postal_code}\n\n"
        "📦 محصولات:\n"
    )

    for index, item in enumerate(
        items,
        start=1
    ):

        item_name = item.get(
            "name",
            "محصول"
        )

        item_quantity = item.get(
            "quantity",
            "1"
        )

        item_price = item.get(
            "price",
            ""
        )

        bale_text += (
            f"{index}. {item_name}"
            f" × {item_quantity}"
        )

        if item_price:

            bale_text += (
                f" — {item_price}"
            )

        bale_text += "\n"

    bale_text += (
        f"\n🧾 شماره سفارش: {order['id']}"
    )

    bale_sent = send_bale_message(
        bale_text
    )

    return jsonify({

        "success": True,

        "message":
        "سفارش شما با موفقیت ثبت شد. ❤️",

        "order":
        order,

        "bale_sent":
        bale_sent,

        "product_found":
        len(verified_product_ids) > 0

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
