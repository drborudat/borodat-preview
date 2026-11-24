import os
import urllib.parse
import hashlib
import stat
from pathlib import Path
import uuid
import json
import hmac
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import requests
import psycopg
from flask import Flask, request, jsonify, send_from_directory, session, Response
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash


# =====================================================
# CONFIG
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Public storefront APIs: allow read-only requests from the official store.
CORS(
    app,
    resources={
        r"/api/(products|categories|latest-products|store-best|slides|magazine)$": {
            "origins": ["https://drborudat.ir"],
            "methods": ["GET"],
        }
    },
    supports_credentials=False,
    vary_header=True,
)

LOCAL_PROXY_MODE = os.environ.get("LOCAL_ADMIN_PROXY") == "1"
LOCAL_ADMIN_DEV = os.environ.get("LOCAL_ADMIN_DEV") == "1"

if LOCAL_PROXY_MODE:
    local_secret_file = os.path.join(BASE_DIR, ".local-flask-secret")
    if not os.path.exists(local_secret_file):
        with open(local_secret_file, "w") as secret_file:
            secret_file.write(secrets.token_urlsafe(48))
        os.chmod(local_secret_file, 0o600)
    with open(local_secret_file) as secret_file:
        app.secret_key = secret_file.read().strip()
else:
    app.secret_key = os.environ.get("FLASK_SECRET_KEY")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=not (LOCAL_PROXY_MODE or LOCAL_ADMIN_DEV),
    SESSION_COOKIE_SAMESITE="Lax" if LOCAL_PROXY_MODE else "Strict",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12)
)

BALE_TOKEN = os.environ.get("BALE_TOKEN")
ADMIN_ID = 746740194

DATABASE_URL = os.environ.get("DATABASE_URL")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "videos")
SUPABASE_PRODUCT_BUCKET = os.environ.get("SUPABASE_PRODUCT_BUCKET", "products")


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

            cur.execute("""
                ALTER TABLE products
                ADD COLUMN IF NOT EXISTS is_special BOOLEAN NOT NULL DEFAULT FALSE
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


            # -----------------------------------------
            # HOMEPAGE SLIDES
            # -----------------------------------------
            cur.execute("""
                CREATE TABLE IF NOT EXISTS homepage_slides (
                    slot SMALLINT PRIMARY KEY
                        CHECK (slot BETWEEN 1 AND 3),
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT DEFAULT '',
                    image_url TEXT DEFAULT '',
                    button_text TEXT DEFAULT '',
                    button_url TEXT DEFAULT '',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute(
                "CREATE TABLE IF NOT EXISTS admin_users ("
                "username TEXT PRIMARY KEY, "
                "password_hash TEXT NOT NULL, "
                "role TEXT NOT NULL, "
                "created_at TEXT NOT NULL)"
            )

            cur.execute(
                "ALTER TABLE admin_users "
                "ADD COLUMN IF NOT EXISTS session_version "
                "INTEGER NOT NULL DEFAULT 1"
            )

            print(
                "ADMIN ENV CHECK: master_username=%s master_hash=%s "
                "admin2_username=%s admin2_hash=%s" % (
                    bool(os.environ.get("MASTER_USERNAME")),
                    bool(os.environ.get("MASTER_PASSWORD_HASH")),
                    bool(os.environ.get("ADMIN2_USERNAME")),
                    bool(os.environ.get("ADMIN2_PASSWORD_HASH"))
                )
            )

            admin_seeds = [
                (os.environ.get("MASTER_USERNAME"),
                 os.environ.get("MASTER_PASSWORD_HASH"), "master"),
                (os.environ.get("ADMIN2_USERNAME"),
                 os.environ.get("ADMIN2_PASSWORD_HASH"), "admin2")
            ]

            for username, password_hash, role in admin_seeds:
                if username and password_hash:
                    if os.environ.get("RESET_ADMIN_PASSWORDS") == "1":
                        conflict_sql = (
                            "ON CONFLICT (username) DO UPDATE SET "
                            "password_hash = EXCLUDED.password_hash, "
                            "role = EXCLUDED.role, "
                            "session_version = admin_users.session_version + 1"
                        )
                        print("ADMIN RESET: password reset requested for role=%s" % role)
                    else:
                        conflict_sql = "ON CONFLICT (username) DO NOTHING"
                    cur.execute(
                        "INSERT INTO admin_users "
                        "(username, password_hash, role, created_at) "
                        "VALUES (%s, %s, %s, %s) " + conflict_sql,
                        (username, password_hash, role,
                         datetime.utcnow().isoformat())
                    )
                    app.logger.info(
                        "ADMIN SEED: account preserved or created; role=%s", role
                    )

            cur.execute(
                "CREATE TABLE IF NOT EXISTS master_recovery_rate_limits ("
                "source_hash TEXT PRIMARY KEY, "
                "window_started_at TIMESTAMPTZ NOT NULL, "
                "attempts INTEGER NOT NULL DEFAULT 0)"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS admin_security_audit ("
                "id BIGSERIAL PRIMARY KEY, "
                "event_type TEXT NOT NULL, "
                "account_username TEXT, "
                "source_hash TEXT, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )


            # FOUR NEW ADMIN FEATURES - DATABASE
            cur.execute("""
                ALTER TABLE products
                ADD COLUMN IF NOT EXISTS original_price TEXT NOT NULL DEFAULT ''
            """)
            cur.execute("""
                ALTER TABLE products
                ADD COLUMN IF NOT EXISTS discount_percent INTEGER NOT NULL DEFAULT 0
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS product_categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                ALTER TABLE product_categories
                ADD COLUMN IF NOT EXISTS image_url TEXT NOT NULL DEFAULT ''
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS latest_products_settings (
                    singleton_id SMALLINT PRIMARY KEY CHECK (singleton_id = 1),
                    mode TEXT NOT NULL DEFAULT 'auto'
                        CHECK (mode IN ('auto', 'manual', 'mixed')),
                    product_ids TEXT NOT NULL DEFAULT '[]',
                    display_count INTEGER NOT NULL DEFAULT 8,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS store_best_sections (
                    section_key TEXT PRIMARY KEY
                        CHECK (section_key IN ('bestseller', 'discounted', 'newest')),
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'auto'
                        CHECK (mode IN ('auto', 'manual', 'mixed')),
                    product_ids TEXT NOT NULL DEFAULT '[]',
                    display_count INTEGER NOT NULL DEFAULT 8,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS online_magazine (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    excerpt TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    image_url TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'published')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            cur.execute("""
                ALTER TABLE online_magazine
                ADD COLUMN IF NOT EXISTS video_url TEXT NOT NULL DEFAULT ''
            """)

            stamp = datetime.utcnow().isoformat()

            cur.execute("""
                INSERT INTO latest_products_settings
                    (singleton_id, mode, product_ids, display_count,
                     is_active, updated_at)
                VALUES (1, 'auto', '[]', 8, TRUE, %s)
                ON CONFLICT (singleton_id) DO NOTHING
            """, (stamp,))

            for key, title in (
                ("bestseller", "پرفروش‌ترین‌ها"),
                ("discounted", "پرتخفیف‌ترین‌ها"),
                ("newest", "جدیدترین‌ها"),
            ):
                cur.execute("""
                    INSERT INTO store_best_sections
                        (section_key, title, mode, product_ids,
                         display_count, is_active, updated_at)
                    VALUES (%s, %s, 'auto', '[]', 8, TRUE, %s)
                    ON CONFLICT (section_key) DO NOTHING
                """, (key, title, stamp))

            # Preserve existing product categories in the new manager.
            cur.execute("""
                SELECT DISTINCT TRIM(category)
                FROM products
                WHERE category IS NOT NULL AND TRIM(category) <> ''
            """)
            existing_categories = cur.fetchall()

            for row in existing_categories:
                category_name = row[0]
                cur.execute("""
                    INSERT INTO product_categories
                        (id, name, sort_order, is_active, created_at)
                    VALUES (%s, %s, 0, TRUE, %s)
                    ON CONFLICT (name) DO NOTHING
                """, (str(uuid.uuid4()), category_name, stamp))

        connection.commit()

        with connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM admin_users WHERE role = %s",
                ("master",)
            )
            master_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM admin_users WHERE role = %s",
                ("admin2",)
            )
            admin2_count = cur.fetchone()[0]

        print(
            "ADMIN SEED VERIFY: master_name_is_admin=%s "
            "admin2_name_is_admin2=%s master_rows=%s admin2_rows=%s" % (
                os.environ.get("MASTER_USERNAME") == "admin",
                os.environ.get("ADMIN2_USERNAME") == "admin2",
                master_count,
                admin2_count
            )
        )

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
                    created_at,
                    is_special,
                    original_price,
                    discount_percent

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

                    "created_at": row[7],
                    "is_special": bool(row[8]),
                    "original_price": row[9] or "",
                    "discount_percent": row[10] or 0

                }

                for row in product_rows

            ]

            # Admin2 receives product data only.
            if session.get("admin_role") == "admin2":
                return jsonify({
                    "success": True,
                    "requests": [],
                    "chats": [],
                    "products": products_data,
                    "orders": [],
                    "reviews": []
                })


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

def upload_to_supabase(file_storage, folder, bucket=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("تنظیمات Supabase در Render کامل نیست.")

    storage_bucket = bucket or SUPABASE_BUCKET

    filename = file_storage.filename or "file"
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in filename
    )
    path = f"{folder}/{uuid.uuid4()}_{safe_name}"

    url = (
        f"{SUPABASE_URL}/storage/v1/object/"
        f"{storage_bucket}/{path}"
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
        f"{storage_bucket}/{path}"
    )


def delete_storage_image(image_url, allowed_folder, local_prefix, local_dir, allowed_bucket=None):
    """Delete only files belonging to the specified storage folder."""
    if not image_url:
        return True

    image_url = str(image_url).strip()

    if image_url.startswith(local_prefix):
        filename = image_url[len(local_prefix):]
        if (
            not filename
            or filename in (".", "..")
            or "/" in filename
            or "\\" in filename
            or "\x00" in filename
        ):
            print("LOCAL MEDIA DELETE BLOCKED: unsafe path")
            return False

        target = os.path.realpath(os.path.join(local_dir, filename))
        base = os.path.realpath(local_dir)

        if os.path.dirname(target) != base:
            return False

        try:
            if os.path.isfile(target):
                os.remove(target)
            return True
        except OSError as exc:
            print("LOCAL MEDIA DELETE ERROR:", exc)
            return False

    if SUPABASE_URL:
        buckets = {SUPABASE_PRODUCT_BUCKET, SUPABASE_BUCKET}

        for bucket in buckets:
            if not bucket:
                continue
            if allowed_bucket and bucket != allowed_bucket:
                continue

            public_prefix = (
                f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/"
            )
            if not image_url.startswith(public_prefix):
                continue

            file_path = urllib.parse.unquote(
                image_url[len(public_prefix):]
            )
            parts = file_path.split("/")
            expected_parts = str(allowed_folder).split("/")

            if (
                len(parts) <= len(expected_parts)
                or parts[:len(expected_parts)] != expected_parts
                or any(part in ("", ".", "..") for part in parts)
                or "\\" in file_path
                or "\x00" in file_path
            ):
                print("MEDIA DELETE BLOCKED: unsafe path")
                return False

            if not SUPABASE_KEY:
                print("MEDIA DELETE ERROR: Supabase key is not configured")
                return False

            safe_path = urllib.parse.quote(file_path, safe="/-._~")
            delete_url = (
                f"{SUPABASE_URL}/storage/v1/object/{bucket}/{safe_path}"
            )

            try:
                response = requests.delete(
                    delete_url,
                    headers={
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    },
                    timeout=30
                )
                if response.status_code in (200, 204, 404):
                    return True

                print(
                    "SUPABASE MEDIA DELETE ERROR:",
                    response.status_code,
                    response.text
                )
                return False
            except Exception as exc:
                print("SUPABASE MEDIA DELETE ERROR:", exc)
                return False

    # External and unknown URLs are deliberately left untouched.
    return True



def delete_product_image(image_url):
    return delete_storage_image(
        image_url, "products", "/uploads/products/", PRODUCT_IMAGE_DIR
    )


def delete_category_image(image_url):
    return delete_storage_image(
        image_url, "categories", "/uploads/categories/", CATEGORY_IMAGE_DIR
    )




def delete_magazine_image(image_url):
    return delete_storage_image(
        image_url, "magazine/images",
        "/uploads/magazine/images/", MAGAZINE_IMAGE_DIR,
        SUPABASE_PRODUCT_BUCKET
    )


def delete_magazine_video(video_url):
    return delete_storage_image(
        video_url, "magazine/videos",
        "/uploads/magazine/videos/", MAGAZINE_VIDEO_DIR,
        SUPABASE_BUCKET
    )


# HOMEPAGE SLIDES API
SLIDER_IMAGE_DIR = os.path.join(BASE_DIR, "uploads", "sliders")
os.makedirs(SLIDER_IMAGE_DIR, exist_ok=True)


@app.route("/uploads/sliders/<path:filename>")
def slider_image_file(filename):
    return send_from_directory(SLIDER_IMAGE_DIR, filename)


def save_slider_image(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    if not (file_storage.mimetype or "").lower().startswith("image/"):
        raise ValueError("فایل انتخاب‌شده تصویر معتبر نیست.")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0:
        raise ValueError("فایل تصویر خالی است.")
    if size > 8 * 1024 * 1024:
        raise ValueError("حجم تصویر نباید بیشتر از ۸ مگابایت باشد.")
    safe = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in os.path.basename(file_storage.filename)
    ).strip("._")
    ext = os.path.splitext(safe)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        raise ValueError("فرمت تصویر باید JPG، PNG، WEBP، GIF یا AVIF باشد.")
    if SUPABASE_URL and SUPABASE_KEY:
        return upload_to_supabase(file_storage, "sliders", SUPABASE_PRODUCT_BUCKET)
    name = uuid.uuid4().hex + "_" + (safe or "slide" + ext)
    file_storage.save(os.path.join(SLIDER_IMAGE_DIR, name))
    return "/uploads/sliders/" + name


def slide_to_dict(r):
    return {"slot": r[0], "title": r[1], "description": r[2],
            "image_url": r[3], "button_text": r[4], "button_url": r[5],
            "is_active": r[6], "updated_at": r[7]}


SLIDE_COLS = ("slot, title, description, image_url, button_text, "
              "button_url, is_active, updated_at")


def load_slides(only_active):
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            where = "WHERE is_active = TRUE AND image_url <> '' " if only_active else ""
            cur.execute("SELECT " + SLIDE_COLS + " FROM homepage_slides "
                        + where + "ORDER BY slot ASC")
            return [slide_to_dict(r) for r in cur.fetchall()]
    finally:
        connection.close()


@app.route("/api/slides", methods=["GET"])
def get_public_slides():
    try:
        return jsonify({"success": True, "slides": load_slides(True)})
    except Exception:
        app.logger.exception("PUBLIC SLIDES LOAD ERROR")
        return jsonify({"success": False, "slides": []}), 500


@app.route("/api/admin/slides", methods=["GET"])
def get_admin_slides():
    try:
        return jsonify({"success": True, "slides": load_slides(False)})
    except Exception:
        app.logger.exception("ADMIN SLIDES LOAD ERROR")
        return jsonify({"success": False, "message": "دریافت اسلایدر انجام نشد."}), 500


@app.route("/api/admin/slides/<int:slot>", methods=["POST"])
def save_admin_slide(slot):
    if slot not in (1, 2, 3):
        return jsonify({"success": False, "message": "شماره اسلاید باید بین ۱ تا ۳ باشد."}), 400
    form = request.form
    title = str(form.get("title", "")).strip()
    description = str(form.get("description", "")).strip()
    button_text = str(form.get("button_text", "")).strip()
    button_url = str(form.get("button_url", "")).strip()
    is_active = str(form.get("is_active", "true")).lower() in ("1", "true", "yes", "on")
    if not title:
        return jsonify({"success": False, "message": "عنوان اسلاید الزامی است."}), 400
    if button_url:
        parsed = urlsplit(button_url)
        ok_https = parsed.scheme == "https" and bool(parsed.netloc)
        ok_rel = (button_url.startswith("/") and not button_url.startswith("//")
                  and not parsed.scheme)
        ok_anchor = button_url.startswith("#")
        if not (ok_https or ok_rel or ok_anchor):
            return jsonify({"success": False, "message": "لینک دکمه باید آدرس HTTPS یا مسیر داخلی سایت باشد."}), 400
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT image_url FROM homepage_slides WHERE slot = %s", (slot,))
            old = cur.fetchone()
            image_url = old[0] if old else ""
            image_file = request.files.get("image")
            if image_file and image_file.filename:
                image_url = save_slider_image(image_file)
            cur.execute(
                "INSERT INTO homepage_slides (slot, title, description, image_url, "
                "button_text, button_url, is_active, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (slot) DO UPDATE SET title=EXCLUDED.title, "
                "description=EXCLUDED.description, image_url=EXCLUDED.image_url, "
                "button_text=EXCLUDED.button_text, button_url=EXCLUDED.button_url, "
                "is_active=EXCLUDED.is_active, updated_at=EXCLUDED.updated_at",
                (slot, title, description, image_url, button_text, button_url,
                 is_active, datetime.utcnow().isoformat()))
        connection.commit()
        return jsonify({"success": True, "message": "اسلاید با موفقیت ذخیره شد.",
                        "slot": slot, "image_url": image_url})
    except ValueError as error:
        connection.rollback()
        return jsonify({"success": False, "message": str(error)}), 400
    except Exception:
        connection.rollback()
        app.logger.exception("ADMIN SLIDE SAVE ERROR")
        return jsonify({"success": False, "message": "ذخیره اسلاید انجام نشد."}), 500
    finally:
        connection.close()


@app.route("/api/admin/slides/<int:slot>", methods=["DELETE"])
def delete_admin_slide(slot):
    if slot not in (1, 2, 3):
        return jsonify({"success": False, "message": "شماره اسلاید نامعتبر است."}), 400
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute("DELETE FROM homepage_slides WHERE slot = %s", (slot,))
        connection.commit()
        return jsonify({"success": True, "message": "اطلاعات اسلاید حذف شد."})
    except Exception:
        connection.rollback()
        app.logger.exception("ADMIN SLIDE DELETE ERROR")
        return jsonify({"success": False, "message": "حذف اسلاید انجام نشد."}), 500
    finally:
        connection.close()


# PRODUCT IMAGE STORAGE
# =====================================================

PRODUCT_IMAGE_DIR = os.path.join(BASE_DIR, "uploads", "products")
os.makedirs(PRODUCT_IMAGE_DIR, exist_ok=True)

@app.route("/uploads/products/<path:filename>")
def product_image_file(filename):
    return send_from_directory(PRODUCT_IMAGE_DIR, filename)


def save_product_image(file_storage):
    if not file_storage or not file_storage.filename:
        return ""

    if not (file_storage.mimetype or "").lower().startswith("image/"):
        raise ValueError("فایل انتخاب‌شده تصویر معتبر نیست.")

    try:
        file_storage.stream.seek(0, os.SEEK_END)
        file_size = file_storage.stream.tell()
        file_storage.stream.seek(0)
    except Exception:
        file_size = 0

    if file_size > 8 * 1024 * 1024:
        raise ValueError("حجم تصویر نباید بیشتر از ۸ مگابایت باشد.")

    original = os.path.basename(file_storage.filename)
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in original
    ).strip("._")

    if not safe_name:
        safe_name = "product-image"

    extension = os.path.splitext(safe_name)[1].lower()
    allowed_extensions = {
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"
    }

    if extension not in allowed_extensions:
        raise ValueError("فرمت تصویر باید JPG، PNG، WEBP، GIF یا AVIF باشد.")

    if SUPABASE_URL and SUPABASE_KEY:
        return upload_to_supabase(file_storage, "products", SUPABASE_PRODUCT_BUCKET)

    filename = f"{uuid.uuid4().hex}_{safe_name}"
    destination = os.path.join(PRODUCT_IMAGE_DIR, filename)

    file_storage.save(destination)

    return "/uploads/products/" + filename


# CATEGORY IMAGE STORAGE
CATEGORY_IMAGE_DIR = os.path.join(BASE_DIR, "uploads", "categories")
os.makedirs(CATEGORY_IMAGE_DIR, exist_ok=True)

@app.route("/uploads/categories/<path:filename>")
def category_image_file(filename):
    return send_from_directory(CATEGORY_IMAGE_DIR, filename)


def save_category_image(file_storage):
    if not file_storage or not file_storage.filename:
        return ""

    if not (file_storage.mimetype or "").lower().startswith("image/"):
        raise ValueError("فایل انتخاب‌شده تصویر معتبر نیست.")

    try:
        file_storage.stream.seek(0, os.SEEK_END)
        file_size = file_storage.stream.tell()
        file_storage.stream.seek(0)
    except Exception:
        file_size = 0

    if file_size > 8 * 1024 * 1024:
        raise ValueError("حجم تصویر نباید بیشتر از ۸ مگابایت باشد.")

    original = os.path.basename(file_storage.filename)
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in original
    ).strip("._")

    if not safe_name:
        safe_name = "category-image"

    extension = os.path.splitext(safe_name)[1].lower()
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}

    if extension not in allowed_extensions:
        raise ValueError("فرمت تصویر باید JPG، PNG، WEBP، GIF یا AVIF باشد.")

    if SUPABASE_URL and SUPABASE_KEY:
        return upload_to_supabase(file_storage, "categories", SUPABASE_PRODUCT_BUCKET)

    filename = f"{uuid.uuid4().hex}_{safe_name}"
    destination = os.path.join(CATEGORY_IMAGE_DIR, filename)
    file_storage.save(destination)
    return "/uploads/categories/" + filename


# =====================================================
# PUBLIC PRODUCTS API
# =====================================================


# MAGAZINE MEDIA STORAGE
MAGAZINE_IMAGE_DIR = os.path.join(BASE_DIR, "uploads", "magazine", "images")
MAGAZINE_VIDEO_DIR = os.path.join(BASE_DIR, "uploads", "magazine", "videos")
os.makedirs(MAGAZINE_IMAGE_DIR, exist_ok=True)
os.makedirs(MAGAZINE_VIDEO_DIR, exist_ok=True)

@app.route("/uploads/magazine/images/<path:filename>")
def magazine_image_file(filename):
    return send_from_directory(MAGAZINE_IMAGE_DIR, filename)

@app.route("/uploads/magazine/videos/<path:filename>")
def magazine_video_file(filename):
    return send_from_directory(MAGAZINE_VIDEO_DIR, filename)

def save_magazine_media(file_storage, media_type):
    if not file_storage or not file_storage.filename:
        return ""

    original = os.path.basename(file_storage.filename)
    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in original
    ).strip("._")

    if not safe_name:
        raise ValueError("نام فایل معتبر نیست.")

    extension = os.path.splitext(safe_name)[1].lower()
    mime = (file_storage.mimetype or "").lower()

    if media_type == "image":
        allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
        max_size = 8 * 1024 * 1024
        folder = "magazine/images"
        bucket = SUPABASE_PRODUCT_BUCKET
        local_dir = MAGAZINE_IMAGE_DIR
        local_url = "/uploads/magazine/images/"
        if extension not in allowed or not mime.startswith("image/"):
            raise ValueError("فرمت عکس معتبر نیست. JPG، PNG، WEBP، GIF یا AVIF انتخاب کنید.")
        size_message = "حجم عکس نباید بیشتر از ۸ مگابایت باشد."
    elif media_type == "video":
        allowed = {".mp4", ".mov", ".webm", ".m4v", ".ogv"}
        max_size = 100 * 1024 * 1024
        folder = "magazine/videos"
        bucket = SUPABASE_BUCKET
        local_dir = MAGAZINE_VIDEO_DIR
        local_url = "/uploads/magazine/videos/"
        if extension not in allowed or not mime.startswith("video/"):
            raise ValueError("فرمت ویدئو معتبر نیست. MP4، MOV یا WEBM انتخاب کنید.")
        size_message = "حجم ویدئو نباید بیشتر از ۱۰۰ مگابایت باشد."
    else:
        raise ValueError("نوع رسانه معتبر نیست.")

    try:
        file_storage.stream.seek(0, os.SEEK_END)
        file_size = file_storage.stream.tell()
        file_storage.stream.seek(0)
    except Exception:
        file_size = 0

    if file_size <= 0:
        raise ValueError("فایل انتخاب‌شده خالی یا غیرقابل‌خواندن است.")
    if file_size > max_size:
        raise ValueError(size_message)

    if SUPABASE_URL and SUPABASE_KEY:
        file_storage.stream.seek(0)
        return upload_to_supabase(file_storage, folder, bucket)

    filename = f"{uuid.uuid4().hex}_{safe_name}"
    file_storage.stream.seek(0)
    file_storage.save(os.path.join(local_dir, filename))
    return local_url + filename



@app.route("/api/magazine", methods=["GET"])
def public_magazine():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT id, title, slug, excerpt, content,
                       image_url, video_url, created_at, updated_at
                FROM online_magazine
                WHERE status = 'published'
                ORDER BY created_at DESC
            """)
            columns = [item[0] for item in cur.description]
            posts = [dict(zip(columns, row)) for row in cur.fetchall()]

        return jsonify({"success": True, "posts": posts})
    except Exception:
        app.logger.exception("Public magazine API failed")
        return jsonify({
            "success": False,
            "message": "دریافت مطالب مجله ناموفق بود."
        }), 500
    finally:
        connection.close()


@app.route("/api/products", methods=["GET"])
def public_products():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT id, name, price, stock, category, description,
                       image, created_at, is_special, original_price,
                       discount_percent
                FROM products
                ORDER BY created_at DESC
            """)
            rows = cur.fetchall()

        products = [{
            "id": r[0], "name": r[1], "price": r[2], "stock": r[3],
            "category": r[4], "description": r[5], "image": r[6],
            "created_at": r[7], "is_special": bool(r[8]),
            "original_price": r[9], "discount_percent": r[10]
        } for r in rows]
        return jsonify({"success": True, "products": products})
    except Exception:
        app.logger.exception("Public products API failed")
        return jsonify({"success": False, "message": "دریافت محصولات ناموفق بود."}), 500
    finally:
        connection.close()


# =====================================================


# =====================================================
# PUBLIC STORE FEATURE APIs
# =====================================================

def public_feature_rows(cur, query, params=None):
    cur.execute(query, params or ())
    rows = cur.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return [dict(row) for row in rows]
    columns = [column.name for column in cur.description]
    return [dict(zip(columns, row)) for row in rows]


def public_feature_order(products, mode, selected_ids, count, sort_key):
    by_id = {str(item.get("id")): item for item in products}
    selected = [by_id[x] for x in selected_ids if x in by_id]

    if mode == "manual":
        return selected[:count]

    automatic = sorted(
        products,
        key=lambda item: item.get(sort_key) or 0,
        reverse=True
    )

    if mode == "mixed":
        selected_set = {str(item.get("id")) for item in selected}
        automatic = selected + [
            item for item in automatic
            if str(item.get("id")) not in selected_set
        ]

    return automatic[:count]


def public_feature_setting(cur, table, key=None):
    if key is None:
        cur.execute(f"SELECT * FROM {table} LIMIT 1")
    else:
        cur.execute(
            f"SELECT * FROM {table} WHERE section_key=%s LIMIT 1",
            (key,)
        )
    row = cur.fetchone()
    return admin_feature_row_dict(cur, row) if row is not None else {}


def public_feature_products(cur):
    return public_feature_rows(cur, """
        SELECT id, name, price, stock, category, description, image,
               created_at, is_special, original_price, discount_percent
        FROM products
        ORDER BY created_at DESC
    """)


@app.route("/api/categories", methods=["GET"])
def public_categories():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            categories = public_feature_rows(cur, """
                SELECT id, name, sort_order, image_url
                FROM product_categories
                WHERE is_active=TRUE
                ORDER BY sort_order ASC, name ASC
            """)
        return jsonify({"success": True, "categories": categories})
    except Exception:
        app.logger.exception("Public categories API failed")
        return jsonify({"success": False, "categories": []}), 500
    finally:
        connection.close()


@app.route("/api/latest-products", methods=["GET"])
def public_latest_products():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            settings = public_feature_setting(cur, "latest_products_settings")
            products = public_feature_products(cur)

            active = bool(settings.get("is_active", False))
            mode = settings.get("mode") or "auto"
            count = max(1, min(50, int(settings.get("display_count") or 8)))
            ids = [
                str(x) for x in
                admin_feature_product_ids(settings.get("product_ids", []))
            ]

            result = public_feature_order(
                products, mode, ids, count, "created_at"
            ) if active else []

        return jsonify({
            "success": True,
            "active": active,
            "mode": mode,
            "display_count": count,
            "products": result
        })
    except Exception:
        app.logger.exception("Public latest products API failed")
        return jsonify({"success": False, "products": []}), 500
    finally:
        connection.close()


@app.route("/api/store-best", methods=["GET"])
def public_store_best():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            products = public_feature_products(cur)

            orders = public_feature_rows(cur, """
                SELECT product_id, quantity, items
                FROM orders
                WHERE status='done'
            """)

            sales = {}
            for order in orders:
                parsed = False
                raw = order.get("items")

                if raw:
                    try:
                        items = raw if isinstance(raw, list) else json.loads(raw)
                        if isinstance(items, list):
                            for item in items:
                                if not isinstance(item, dict):
                                    continue
                                pid = str(item.get("id") or "")
                                qty = int(item.get("quantity") or 0)
                                if pid and qty > 0:
                                    sales[pid] = sales.get(pid, 0) + qty
                                    parsed = True
                    except (TypeError, ValueError):
                        parsed = False

                if not parsed:
                    pid = str(order.get("product_id") or "")
                    try:
                        qty = int(order.get("quantity") or 0)
                    except (TypeError, ValueError):
                        qty = 0
                    if pid and qty > 0:
                        sales[pid] = sales.get(pid, 0) + qty

            valid_ids = {str(p.get("id")) for p in products}
            sales = {k: v for k, v in sales.items() if k in valid_ids}

            definitions = (
                ("bestseller", "sales_count"),
                ("discounted", "discount_percent"),
                ("newest", "created_at"),
            )
            sections = {}

            for key, sort_key in definitions:
                settings = public_feature_setting(
                    cur, "store_best_sections", key
                )
                active = bool(settings.get("is_active", False))
                mode = settings.get("mode") or "auto"
                count = max(
                    1, min(50, int(settings.get("display_count") or 8))
                )
                ids = [
                    str(x) for x in
                    admin_feature_product_ids(settings.get("product_ids", []))
                ]

                source = []
                for product in products:
                    item = dict(product)
                    item["sales_count"] = sales.get(str(item.get("id")), 0)
                    source.append(item)

                by_id = {
                    str(item.get("id")): item for item in source
                }
                selected = [
                    by_id[pid] for pid in ids if pid in by_id
                ]

                if not active:
                    result = []
                elif mode == "manual":
                    result = selected[:count]
                else:
                    automatic_source = source

                    if key == "discounted":
                        automatic_source = [
                            item for item in source
                            if int(item.get("discount_percent") or 0) > 0
                        ]
                    elif key == "bestseller":
                        automatic_source = [
                            item for item in source
                            if item.get("sales_count", 0) > 0
                        ]

                    automatic = public_feature_order(
                        automatic_source, "auto", [], count, sort_key
                    )

                    if mode == "mixed":
                        selected_ids = {
                            str(item.get("id")) for item in selected
                        }
                        result = (
                            selected + [
                                item for item in automatic
                                if str(item.get("id")) not in selected_ids
                            ]
                        )[:count]
                    else:
                        result = automatic

                sections[key] = {
                    "title": settings.get("title") or "",
                    "active": active,
                    "mode": mode,
                    "display_count": count,
                    "products": result
                }

        return jsonify({"success": True, "sections": sections})
    except Exception:
        app.logger.exception("Public store best API failed")
        return jsonify({"success": False, "sections": {}}), 500
    finally:
        connection.close()


# PRODUCTS - CREATE
# =====================================================

@app.route(
    "/api/admin/products",
    methods=["POST"]
)
def add_product():
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    name = str(data.get("name", "")).strip()
    price = str(data.get("price", "")).strip()
    stock = str(data.get("stock", "0")).strip()
    category = str(data.get("category", "")).strip()
    description = str(data.get("description", "")).strip()
    image = str(data.get("image", "")).strip()
    original_price = str(data.get("original_price", "")).strip()
    try:
        discount_percent = int(str(data.get("discount_percent", "0")).strip() or "0")
        if not 0 <= discount_percent <= 100:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "درصد تخفیف باید بین صفر تا صد باشد."}), 400
    is_special = str(data.get("is_special", "")).strip().lower() in ("1", "true", "yes", "on")

    if not name or not price or not category:
        return jsonify({
            "success": False,
            "message": "نام، قیمت و دسته‌بندی محصول الزامی است."
        }), 400

    try:
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            image = save_product_image(image_file)

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e) or "ذخیره تصویر محصول انجام نشد."
        }), 400

    product = {
        "id": str(uuid.uuid4()),
        "name": name,
        "price": price,
        "stock": stock,
        "category": category,
        "description": description,
        "image": image,
        "original_price": original_price,
        "discount_percent": discount_percent,
        "is_special": is_special,
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
                    created_at,
                    is_special,
                    original_price,
                    discount_percent
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                product["id"],
                product["name"],
                product["price"],
                product["stock"],
                product["category"],
                product["description"],
                product["image"],
                product["created_at"],
                product["is_special"],
                product["original_price"],
                product["discount_percent"]
            ))

        connection.commit()

    except Exception as e:
        connection.rollback()
        print("PRODUCT SAVE ERROR:", e)

        return jsonify({
            "success": False,
            "message": "ذخیره محصول انجام نشد."
        }), 500

    finally:
        connection.close()

    return jsonify({
        "success": True,
        "message": "محصول با موفقیت ثبت شد.",
        "product": product
    })


# =====================================================
# PRODUCTS - UPDATE
# =====================================================

# =====================================================
# PRODUCTS - UPDATE
# =====================================================


@app.route(
    "/api/admin/products/<product_id>",
    methods=["PATCH"]
)
def update_product(product_id):
    data = request.get_json(silent=True) or {} if request.is_json else request.form
    allowed_fields = [
        "name", "price", "stock", "category",
        "description", "image", "is_special",
        "original_price", "discount_percent"
    ]

    connection = get_connection()
    new_image = None
    old_image = None

    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, image FROM products WHERE id = %s LIMIT 1",
                (product_id,)
            )
            product = cur.fetchone()

            if not product:
                return jsonify({
                    "success": False,
                    "message": "محصول پیدا نشد."
                }), 404

            old_image = product["image"] if isinstance(product, dict) else product[1]

            image_file = request.files.get("image")
            if image_file and image_file.filename:
                new_image = save_product_image(image_file)
                data = dict(data)
                data["image"] = new_image

            updates = []
            values = []

            for field in allowed_fields:
                if field in data:
                    updates.append(f"{field} = %s")
                    if field == "is_special":
                        values.append(
                            str(data[field]).strip().lower()
                            in ("1", "true", "yes", "on")
                        )
                    elif field == "discount_percent":
                        try:
                            discount = int(str(data[field]).strip() or "0")
                            if not 0 <= discount <= 100:
                                raise ValueError
                        except (TypeError, ValueError):
                            if new_image:
                                delete_product_image(new_image)
                            return jsonify({
                                "success": False,
                                "message": "درصد تخفیف باید بین صفر تا صد باشد."
                            }), 400
                        values.append(discount)
                    else:
                        values.append(str(data[field]).strip())

            if updates:
                values.append(product_id)
                cur.execute(
                    "UPDATE products SET " + ", ".join(updates) +
                    " WHERE id = %s",
                    values
                )

        connection.commit()

    except Exception as e:
        connection.rollback()
        print("PRODUCT UPDATE ERROR:", e)

        if new_image:
            try:
                delete_product_image(new_image)
            except Exception as cleanup_error:
                print("NEW PRODUCT IMAGE CLEANUP ERROR:", cleanup_error)

        return jsonify({
            "success": False,
            "message": "ذخیره تغییرات محصول انجام نشد."
        }), 500

    finally:
        connection.close()

    if new_image and old_image and old_image != new_image:
        if not delete_product_image(old_image):
            print("OLD PRODUCT IMAGE COULD NOT BE DELETED:", old_image)

    return jsonify({
        "success": True,
        "message": "محصول ویرایش شد.",
        "product_id": product_id
    })


# =====================================================
# PRODUCTS - DELETE
# =====================================================

# =====================================================
# PRODUCTS - DELETE
# =====================================================

@app.route(
    "/api/admin/products/<product_id>",
    methods=["DELETE"]
)
def delete_product(product_id):
    connection = get_connection()
    old_image = None

    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT image FROM products WHERE id = %s LIMIT 1",
                (product_id,)
            )
            product = cur.fetchone()

            if not product:
                return jsonify({
                    "success": False,
                    "message": "محصول پیدا نشد."
                }), 404

            old_image = product["image"] if isinstance(product, dict) else product[0]

            cur.execute(
                "DELETE FROM products WHERE id = %s",
                (product_id,)
            )

        connection.commit()

    except Exception as e:
        connection.rollback()
        print("PRODUCT DELETE ERROR:", e)
        return jsonify({
            "success": False,
            "message": "حذف محصول ذخیره نشد."
        }), 500

    finally:
        connection.close()

    if old_image and not delete_product_image(old_image):
        print("PRODUCT IMAGE COULD NOT BE DELETED:", old_image)

    return jsonify({
        "success": True,
        "message": "محصول حذف شد."
    })



# =====================================================
# FOUR NEW ADMIN FEATURES - API
# =====================================================

def admin_feature_row_dict(cursor, row):
    if isinstance(row, dict):
        return dict(row)
    return {
        column.name: value
        for column, value in zip(cursor.description, row)
    }


def admin_feature_product_ids(raw_ids):
    if isinstance(raw_ids, str):
        try:
            raw_ids = json.loads(raw_ids)
        except (TypeError, ValueError):
            raw_ids = []
    if not isinstance(raw_ids, list):
        raise ValueError("فهرست محصولات معتبر نیست.")
    ids = []
    for value in raw_ids:
        value = str(value).strip()
        if value and value not in ids:
            ids.append(value)
    return ids


def admin_feature_validate_products(cur, ids):
    if not ids:
        return
    cur.execute("SELECT id FROM products WHERE id = ANY(%s)", (ids,))
    found = {str(row[0]) for row in cur.fetchall()}
    missing = [value for value in ids if value not in found]
    if missing:
        raise ValueError("یک یا چند محصول انتخاب‌شده وجود ندارد.")


# CATEGORIES
@app.route("/api/admin/categories", methods=["GET", "POST"])
def admin_categories():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            if request.method == "GET":
                cur.execute("""
                    SELECT id, name, sort_order, is_active, created_at, image_url
                    FROM product_categories
                    ORDER BY sort_order, name
                """)
                rows = [admin_feature_row_dict(cur, row) for row in cur.fetchall()]
                return jsonify({"success": True, "categories": rows})

            data = request.form if request.form else (request.get_json(silent=True) or {})
            name = str(data.get("name", "")).strip()
            if not name:
                return jsonify({"success": False, "message": "نام دسته‌بندی الزامی است."}), 400

            image_url = save_category_image(request.files.get("image"))
            category_id = str(uuid.uuid4())

            cur.execute("""
                INSERT INTO product_categories
                    (id, name, sort_order, is_active, created_at, image_url)
                VALUES (%s, %s, %s, TRUE, %s, %s)
                RETURNING id, name, sort_order, is_active, created_at, image_url
            """, (category_id, name, int(data.get("sort_order", 0)), now(), image_url))

            category = admin_feature_row_dict(cur, cur.fetchone())
            connection.commit()

        return jsonify({"success": True, "category": category}), 201

    except Exception as exc:
        connection.rollback()
        app.logger.exception("ADMIN CATEGORY ERROR")
        message = str(exc) if isinstance(exc, ValueError) else "ذخیره دسته‌بندی انجام نشد."
        return jsonify({"success": False, "message": message}), 400
    finally:
        connection.close()


@app.route("/api/admin/categories/<category_id>", methods=["PATCH", "DELETE"])
def admin_category_item(category_id):
    connection = get_connection()
    old_image_url = None
    new_image_url = None

    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, name, image_url FROM product_categories WHERE id = %s",
                (category_id,)
            )
            category = cur.fetchone()

            if not category:
                return jsonify({
                    "success": False,
                    "message": "دسته‌بندی پیدا نشد."
                }), 404

            if isinstance(category, dict):
                old_name = category["name"]
                old_image_url = category.get("image_url")
            else:
                old_name = category[1]
                old_image_url = category[2]

            if request.method == "DELETE":
                cur.execute(
                    "SELECT COUNT(*) FROM products WHERE category = %s",
                    (old_name,)
                )
                if cur.fetchone()[0]:
                    return jsonify({
                        "success": False,
                        "message": "این دسته‌بندی به محصولات متصل است؛ ابتدا محصولات را به دسته دیگری منتقل کنید."
                    }), 409

                cur.execute(
                    "DELETE FROM product_categories WHERE id = %s",
                    (category_id,)
                )

            else:
                data = (
                    request.form if request.form
                    else (request.get_json(silent=True) or {})
                )
                fields, values = [], []

                if "name" in data:
                    name = str(data["name"]).strip()
                    if not name:
                        return jsonify({
                            "success": False,
                            "message": "نام دسته‌بندی نمی‌تواند خالی باشد."
                        }), 400

                    if name != old_name:
                        cur.execute(
                            "UPDATE products SET category = %s WHERE category = %s",
                            (name, old_name)
                        )

                    fields.append("name = %s")
                    values.append(name)

                if "sort_order" in data:
                    fields.append("sort_order = %s")
                    values.append(int(data["sort_order"]))

                if "is_active" in data:
                    active_value = data["is_active"]
                    if isinstance(active_value, str):
                        active_value = active_value.strip().lower() in (
                            "1", "true", "yes", "on"
                        )
                    fields.append("is_active = %s")
                    values.append(bool(active_value))

                image = request.files.get("image")
                if image and image.filename:
                    new_image_url = save_category_image(image)
                    fields.append("image_url = %s")
                    values.append(new_image_url)

                if fields:
                    values.append(category_id)
                    cur.execute(
                        "UPDATE product_categories SET "
                        + ", ".join(fields)
                        + " WHERE id = %s",
                        values
                    )

        connection.commit()

    except Exception:
        connection.rollback()

        if new_image_url:
            try:
                delete_category_image(new_image_url)
            except Exception as cleanup_error:
                print("NEW CATEGORY IMAGE CLEANUP ERROR:", cleanup_error)

        app.logger.exception("ADMIN CATEGORY UPDATE ERROR")
        return jsonify({
            "success": False,
            "message": "ذخیره تغییر دسته‌بندی انجام نشد."
        }), 400

    finally:
        connection.close()

    if request.method == "DELETE":
        if old_image_url and not delete_category_image(old_image_url):
            print("OLD CATEGORY IMAGE COULD NOT BE DELETED:", old_image_url)

    elif new_image_url and old_image_url and old_image_url != new_image_url:
        if not delete_category_image(old_image_url):
            print("OLD CATEGORY IMAGE COULD NOT BE DELETED:", old_image_url)

    return jsonify({
        "success": True,
        "message": "انجام شد."
    })


# LATEST PRODUCTS
@app.route("/api/admin/latest-products", methods=["GET", "PUT"])
def admin_latest_products():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            if request.method == "GET":
                cur.execute("SELECT * FROM latest_products_settings WHERE singleton_id = 1")
                row = cur.fetchone()
                return jsonify({"success": True, "settings": admin_feature_row_dict(cur, row)})

            data = request.get_json(silent=True) or {}
            mode = str(data.get("mode", "auto"))
            if mode not in ("auto", "manual", "mixed"):
                return jsonify({"success": False, "message": "حالت نمایش معتبر نیست."}), 400
            ids = admin_feature_product_ids(data.get("product_ids", []))
            count = int(data.get("display_count", 8))
            if not 1 <= count <= 50:
                return jsonify({"success": False, "message": "تعداد نمایش باید بین ۱ تا ۵۰ باشد."}), 400
            admin_feature_validate_products(cur, ids)
            cur.execute("""
                UPDATE latest_products_settings
                SET mode = %s, product_ids = %s, display_count = %s,
                    is_active = %s, updated_at = %s
                WHERE singleton_id = 1
            """, (mode, json.dumps(ids), count, bool(data.get("is_active", True)), now()))
        connection.commit()
        return jsonify({"success": True, "message": "تنظیمات جدیدترین محصولات ذخیره شد."})
    except Exception as exc:
        connection.rollback()
        app.logger.exception("ADMIN LATEST PRODUCTS ERROR")
        return jsonify({"success": False, "message": str(exc) if isinstance(exc, ValueError) else "ذخیره تنظیمات انجام نشد."}), 400
    finally:
        connection.close()


# STORE BEST SECTIONS
@app.route("/api/admin/store-best", methods=["GET", "PUT"])
def admin_store_best():
    connection = get_connection()
    try:
        with connection.cursor() as cur:
            if request.method == "GET":
                cur.execute("SELECT * FROM store_best_sections ORDER BY section_key")
                rows = [admin_feature_row_dict(cur, row) for row in cur.fetchall()]
                return jsonify({"success": True, "sections": rows})

            data = request.get_json(silent=True) or {}
            sections = data.get("sections", [])
            if not isinstance(sections, list):
                return jsonify({"success": False, "message": "ساختار بخش‌ها معتبر نیست."}), 400
            for section in sections:
                key = str(section.get("section_key", ""))
                if key not in ("bestseller", "discounted", "newest"):
                    raise ValueError("شناسه بخش معتبر نیست.")
                mode = str(section.get("mode", "auto"))
                if mode not in ("auto", "manual", "mixed"):
                    raise ValueError("حالت نمایش معتبر نیست.")
                ids = admin_feature_product_ids(section.get("product_ids", []))
                count = int(section.get("display_count", 8))
                if not 1 <= count <= 50:
                    raise ValueError("تعداد نمایش باید بین ۱ تا ۵۰ باشد.")
                admin_feature_validate_products(cur, ids)
                cur.execute("""
                    UPDATE store_best_sections
                    SET mode = %s, product_ids = %s, display_count = %s,
                        is_active = %s, updated_at = %s
                    WHERE section_key = %s
                """, (mode, json.dumps(ids), count, bool(section.get("is_active", True)), now(), key))
        connection.commit()
        return jsonify({"success": True, "message": "تنظیمات ترین‌های فروشگاه ذخیره شد."})
    except Exception as exc:
        connection.rollback()
        app.logger.exception("ADMIN STORE BEST ERROR")
        return jsonify({"success": False, "message": str(exc) if isinstance(exc, ValueError) else "ذخیره تنظیمات انجام نشد."}), 400
    finally:
        connection.close()


# ONLINE MAGAZINE

# ONLINE MAGAZINE
@app.route("/api/admin/magazine", methods=["GET", "POST"])
def admin_magazine():
    connection = get_connection()
    image_url = ""
    video_url = ""

    def cleanup_new_media():
        for url, deleter in (
            (image_url, delete_magazine_image),
            (video_url, delete_magazine_video),
        ):
            if url:
                try:
                    if not deleter(url):
                        app.logger.error("NEW MAGAZINE MEDIA CLEANUP FAILED: %s", url)
                except Exception:
                    app.logger.exception("NEW MAGAZINE MEDIA CLEANUP ERROR")

    try:
        with connection.cursor() as cur:
            if request.method == "GET":
                cur.execute(
                    "SELECT * FROM online_magazine ORDER BY created_at DESC"
                )
                rows = [
                    admin_feature_row_dict(cur, row)
                    for row in cur.fetchall()
                ]
                return jsonify({"success": True, "posts": rows})

            title = str(request.form.get("title", "")).strip()
            if not title:
                return jsonify({
                    "success": False,
                    "message": "عنوان مطلب الزامی است."
                }), 400

            status = str(request.form.get("status", "draft"))
            if status not in ("draft", "published"):
                return jsonify({
                    "success": False,
                    "message": "وضعیت مطلب معتبر نیست."
                }), 400

            image_url = save_magazine_media(
                request.files.get("image"), "image"
            )
            video_url = save_magazine_media(
                request.files.get("video"), "video"
            )

            post_id = str(uuid.uuid4())
            slug = str(request.form.get("slug", "")).strip() or post_id
            stamp = now()

            cur.execute("""
                INSERT INTO online_magazine
                    (id, title, slug, excerpt, content, image_url,
                     video_url, status, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING *
            """, (
                post_id,
                title,
                slug,
                str(request.form.get("excerpt", "")),
                str(request.form.get("content", "")),
                image_url,
                video_url,
                status,
                stamp,
                stamp
            ))
            post = admin_feature_row_dict(cur, cur.fetchone())

        connection.commit()
        return jsonify({"success": True, "post": post}), 201

    except ValueError as exc:
        connection.rollback()
        cleanup_new_media()
        return jsonify({"success": False, "message": str(exc)}), 400

    except Exception:
        connection.rollback()
        cleanup_new_media()
        app.logger.exception("ADMIN MAGAZINE CREATE ERROR")
        return jsonify({
            "success": False,
            "message": "ذخیره مطلب مجله انجام نشد."
        }), 400

    finally:
        connection.close()


@app.route("/api/admin/magazine/<post_id>", methods=["PATCH", "DELETE"])
def admin_magazine_item(post_id):
    connection = get_connection()
    old_image_url = ""
    old_video_url = ""
    new_image_url = ""
    new_video_url = ""

    def cleanup_new_media():
        for url, deleter in (
            (new_image_url, delete_magazine_image),
            (new_video_url, delete_magazine_video),
        ):
            if url:
                try:
                    if not deleter(url):
                        app.logger.error("NEW MAGAZINE MEDIA CLEANUP FAILED: %s", url)
                except Exception:
                    app.logger.exception("NEW MAGAZINE MEDIA CLEANUP ERROR")

    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, image_url, video_url FROM online_magazine WHERE id = %s",
                (post_id,)
            )
            post = cur.fetchone()

            if not post:
                return jsonify({
                    "success": False,
                    "message": "مطلب پیدا نشد."
                }), 404

            if isinstance(post, dict):
                old_image_url = post.get("image_url") or ""
                old_video_url = post.get("video_url") or ""
            else:
                old_image_url = post[1] or ""
                old_video_url = post[2] or ""

            if request.method == "DELETE":
                cur.execute(
                    "DELETE FROM online_magazine WHERE id = %s",
                    (post_id,)
                )

            else:
                fields = []
                values = []

                for field in ("title", "slug", "excerpt", "content", "status"):
                    if field in request.form:
                        value = str(request.form.get(field, "")).strip()

                        if field == "title" and not value:
                            return jsonify({
                                "success": False,
                                "message": "عنوان مطلب الزامی است."
                            }), 400

                        if field == "status" and value not in ("draft", "published"):
                            return jsonify({
                                "success": False,
                                "message": "وضعیت مطلب معتبر نیست."
                            }), 400

                        fields.append(field + " = %s")
                        values.append(value)

                image_file = request.files.get("image")
                if image_file and image_file.filename:
                    new_image_url = save_magazine_media(image_file, "image")
                    fields.append("image_url = %s")
                    values.append(new_image_url)

                video_file = request.files.get("video")
                if video_file and video_file.filename:
                    new_video_url = save_magazine_media(video_file, "video")
                    fields.append("video_url = %s")
                    values.append(new_video_url)

                if fields:
                    fields.append("updated_at = %s")
                    values.append(now())
                    values.append(post_id)

                    cur.execute(
                        "UPDATE online_magazine SET "
                        + ", ".join(fields)
                        + " WHERE id = %s",
                        values
                    )

        connection.commit()

    except ValueError as exc:
        connection.rollback()
        cleanup_new_media()
        return jsonify({"success": False, "message": str(exc)}), 400

    except Exception:
        connection.rollback()
        cleanup_new_media()
        app.logger.exception("ADMIN MAGAZINE UPDATE ERROR")
        return jsonify({
            "success": False,
            "message": "ذخیره تغییرات مطلب انجام نشد."
        }), 400

    finally:
        connection.close()

    def cleanup_old_media(url, deleter, label):
        if not url:
            return
        try:
            if not deleter(url):
                app.logger.error("%s MEDIA COULD NOT BE REMOVED: %s", label, url)
        except Exception:
            app.logger.exception("%s MEDIA CLEANUP ERROR: %s", label, url)

    if request.method == "DELETE":
        cleanup_old_media(old_image_url, delete_magazine_image, "DELETED MAGAZINE IMAGE")
        cleanup_old_media(old_video_url, delete_magazine_video, "DELETED MAGAZINE VIDEO")
    else:
        if new_image_url and old_image_url and old_image_url != new_image_url:
            cleanup_old_media(old_image_url, delete_magazine_image, "OLD MAGAZINE IMAGE")

        if new_video_url and old_video_url and old_video_url != new_video_url:
            cleanup_old_media(old_video_url, delete_magazine_video, "OLD MAGAZINE VIDEO")

    return jsonify({"success": True, "message": "انجام شد."})


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



def local_api_proxy():
    upstream = "https://borodat-panel.onrender.com" + request.full_path
    if upstream.endswith("?"):
        upstream = upstream[:-1]

    headers = {}
    for name in ("Accept", "Content-Type"):
        value = request.headers.get(name)
        if value:
            headers[name] = value

    remote_cookie = session.get("upstream_cookie")
    if remote_cookie:
        headers["Cookie"] = remote_cookie

    try:
        remote = requests.request(
            method=request.method,
            url=upstream,
            headers=headers,
            data=request.get_data(),
            timeout=45,
            allow_redirects=False
        )

        if request.path == "/api/auth/login":
            if remote.ok:
                cookie_value = remote.cookies.get("session")
                if cookie_value:
                    session.clear()
                    session.permanent = True
                    session["upstream_cookie"] = "session=" + cookie_value
                else:
                    session.clear()
            else:
                session.clear()

        if request.path == "/api/auth/logout":
            session.clear()

        response_headers = {}
        for name in ("Content-Type", "Cache-Control", "Content-Disposition"):
            value = remote.headers.get(name)
            if value:
                response_headers[name] = value

        return Response(
            remote.content,
            status=remote.status_code,
            headers=response_headers
        )

    except requests.RequestException:
        app.logger.exception("Local API proxy connection failed")
        return jsonify({
            "success": False,
            "error": "ارتباط با سرور آنلاین برقرار نشد."
        }), 502


def validate_admin_session():
    username = session.get("admin_username")
    role = session.get("admin_role")
    version = session.get("admin_session_version")

    if not username or role not in ("master", "admin2") or version is None:
        session.clear()
        return False

    with get_connection() as connection:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT role, session_version "
                "FROM admin_users WHERE username = %s",
                (username,)
            )
            account = cur.fetchone()

    if (
        not account
        or account[0] != role
        or account[1] != version
    ):
        session.clear()
        return False

    return True


@app.before_request
def protect_admin_api():
    if LOCAL_PROXY_MODE and request.path.startswith("/api/"):
        return local_api_proxy()

    if request.method == "OPTIONS":
        return None

    csrf_protected = (
        request.path.startswith("/api/admin/")
        or request.path in ("/api/auth/login", "/api/auth/logout", "/api/auth/master-recovery")
    )

    if csrf_protected and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        expected_token = session.get("csrf_token", "")
        supplied_token = request.headers.get("X-CSRF-Token", "")

        if not expected_token or not supplied_token or not hmac.compare_digest(
            expected_token, supplied_token
        ):
            return jsonify({
                "success": False,
                "error": "درخواست امنیتی نامعتبر است. صفحه را تازه‌سازی کنید."
            }), 403

        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        source = origin or referer

        if source:
            try:
                parsed_source = urlsplit(source)
                if not parsed_source.netloc or parsed_source.netloc.lower() != request.host.lower():
                    return jsonify({
                        "success": False,
                        "error": "مبدأ درخواست معتبر نیست."
                    }), 403
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "مبدأ درخواست معتبر نیست."
                }), 403

    if not request.path.startswith("/api/admin/"):
        return None

    try:
        if not validate_admin_session():
            return jsonify({
                "success": False,
                "error": "نشست شما معتبر نیست؛ دوباره وارد شوید."
            }), 401
    except Exception:
        app.logger.exception("Admin session validation failed")
        return jsonify({
            "success": False,
            "error": "بررسی امنیت نشست موقتاً امکان‌پذیر نیست."
        }), 503

    role = session.get("admin_role")

    if role == "master":
        return None

    if role == "admin2":
        path_parts = request.path.strip("/").split("/")

        # Admin2 may load the dashboard, but receives products only.
        if request.path == "/api/admin/dashboard" and request.method == "GET":
            return None

        if request.path == "/api/admin/products" and request.method == "POST":
            return None
        if (
            len(path_parts) == 4
            and path_parts[:3] == ["api", "admin", "products"]
            and request.method in ("PATCH", "DELETE")
        ):
            return None

        return jsonify({"success": False,
                        "error": "فقط بخش محصولات مجاز است."}), 403

    return jsonify({"success": False,
                    "error": "ابتدا وارد پنل شوید."}), 401


@app.route("/api/auth/csrf", methods=["GET"])
def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return jsonify({"success": True, "csrf_token": token})




def get_master_recovery_connection():
    return psycopg.connect(
        get_database_url(),
        connect_timeout=5,
        options="-c statement_timeout=10000 -c lock_timeout=3000"
    )


@app.route("/api/auth/master-recovery", methods=["POST"])
def master_recovery():
    if not app.secret_key:
        return jsonify({
            "success": False,
            "error": "سرویس بازیابی موقتاً در دسترس نیست."
        }), 503

    data = request.get_json(silent=True) or {}
    recovery_code = data.get("recovery_code")
    new_password = data.get("new_password")
    confirm_password = data.get("confirm_password")

    if not all(isinstance(value, str) for value in (
        recovery_code, new_password, confirm_password
    )):
        return jsonify({
            "success": False,
            "error": "اطلاعات واردشده معتبر نیست."
        }), 400

    if not recovery_code or len(recovery_code) > 512:
        return jsonify({
            "success": False,
            "error": "اطلاعات بازیابی معتبر نیست."
        }), 400

    if len(new_password) < 12 or len(new_password) > 128:
        return jsonify({
            "success": False,
            "error": "رمز جدید باید حداقل ۱۲ و حداکثر ۱۲۸ نویسه باشد."
        }), 400

    if new_password != confirm_password:
        return jsonify({
            "success": False,
            "error": "تکرار رمز جدید مطابقت ندارد."
        }), 400

    app.logger.info("Master recovery stage: request validated")
    source = request.remote_addr or "unknown"
    source_hash = hmac.new(
        app.secret_key.encode("utf-8"),
        source.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    try:
        with get_master_recovery_connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO master_recovery_rate_limits
                        (source_hash, window_started_at, attempts)
                    VALUES (%s, NOW(), 1)
                    ON CONFLICT (source_hash) DO UPDATE SET
                        attempts = CASE
                            WHEN master_recovery_rate_limits.window_started_at
                                 < NOW() - INTERVAL '15 minutes'
                            THEN 1
                            ELSE master_recovery_rate_limits.attempts + 1
                        END,
                        window_started_at = CASE
                            WHEN master_recovery_rate_limits.window_started_at
                                 < NOW() - INTERVAL '15 minutes'
                            THEN NOW()
                            ELSE master_recovery_rate_limits.window_started_at
                        END
                    RETURNING attempts
                    """,
                    (source_hash,)
                )
                attempts = cur.fetchone()[0]

                if attempts > 5:
                    cur.execute(
                        """
                        INSERT INTO admin_security_audit
                            (event_type, account_username, source_hash)
                        VALUES (%s, %s, %s)
                        """,
                        ("master_recovery_rate_limited", None, source_hash)
                    )
                    connection.commit()
                    return jsonify({
                        "success": False,
                        "error": "تعداد تلاش‌ها بیش از حد مجاز است؛ ۱۵ دقیقه دیگر دوباره تلاش کنید."
                    }), 429

            connection.commit()
            app.logger.info("Master recovery stage: rate limit passed")

    except Exception:
        app.logger.exception("Master recovery rate-limit database error")
        return jsonify({
            "success": False,
            "error": "سرویس بازیابی موقتاً در دسترس نیست."
        }), 503

    recovery_file = (
        Path.home() / ".config" / "drborudat" / "master-recovery.hash"
    )

    try:
        file_info = recovery_file.lstat()

        if (
            not stat.S_ISREG(file_info.st_mode)
            or file_info.st_uid != os.getuid()
            or (file_info.st_mode & 0o077) != 0
        ):
            raise RuntimeError("Recovery file permissions are not acceptable")

        recovery_hash = recovery_file.read_text(
            encoding="utf-8"
        ).strip()

        if not recovery_hash.startswith(("scrypt:", "pbkdf2:")):
            raise RuntimeError("Recovery hash format is not acceptable")
        app.logger.info("Master recovery stage: recovery file validated")

    except Exception:
        app.logger.exception("Master recovery secret unavailable or invalid")
        return jsonify({
            "success": False,
            "error": "سرویس بازیابی موقتاً در دسترس نیست."
        }), 503

    try:
        code_matches = check_password_hash(recovery_hash, recovery_code)
        app.logger.info("Master recovery stage: hash verification completed")
    except Exception:
        app.logger.exception("Master recovery hash verification error")
        return jsonify({
            "success": False,
            "error": "سرویس بازیابی موقتاً در دسترس نیست."
        }), 503

    if not code_matches:
        try:
            with get_master_recovery_connection() as connection:
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO admin_security_audit
                            (event_type, account_username, source_hash)
                        VALUES (%s, %s, %s)
                        """,
                        ("master_recovery_failed", None, source_hash)
                    )
                connection.commit()
        except Exception:
            app.logger.exception("Master recovery failure audit error")

        return jsonify({
            "success": False,
            "error": "اطلاعات بازیابی معتبر نیست."
        }), 401

    app.logger.info("Master recovery stage: account transaction starting")
    try:
        new_password_hash = generate_password_hash(new_password)

        with get_master_recovery_connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT username
                    FROM admin_users
                    WHERE role = %s
                    FOR UPDATE
                    """,
                    ("master",)
                )
                master_rows = cur.fetchall()

                if len(master_rows) != 1:
                    connection.rollback()
                    app.logger.error(
                        "Master recovery stopped: expected exactly one master account"
                    )
                    return jsonify({
                        "success": False,
                        "error": "بازیابی انجام نشد؛ وضعیت حساب مالک نیاز به بررسی دارد."
                    }), 503

                master_username = master_rows[0][0]

                cur.execute(
                    """
                    UPDATE admin_users
                    SET password_hash = %s,
                        session_version = session_version + 1
                    WHERE username = %s AND role = %s
                    RETURNING username
                    """,
                    (new_password_hash, master_username, "master")
                )

                if cur.fetchone() is None:
                    connection.rollback()
                    return jsonify({
                        "success": False,
                        "error": "بازیابی انجام نشد."
                    }), 503

                cur.execute(
                    """
                    INSERT INTO admin_security_audit
                        (event_type, account_username, source_hash)
                    VALUES (%s, %s, %s)
                    """,
                    ("master_password_recovered", master_username, source_hash)
                )

            connection.commit()

        session.clear()
        app.logger.info("Master recovery stage: transaction committed")

        return jsonify({
            "success": True,
            "message": "رمز حساب مالک با موفقیت تغییر کرد. اکنون با رمز جدید وارد شوید."
        })

    except Exception:
        app.logger.exception("Master password recovery database error")
        return jsonify({
            "success": False,
            "error": "بازیابی موقتاً انجام نشد؛ وضعیت حساب را دوباره بررسی کنید."
        }), 503


@app.route("/api/auth/login", methods=["POST"])
def admin_login():
    if not app.secret_key:
        return jsonify({"success": False,
                        "error": "تنظیمات امنیتی کامل نیست."}), 503

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"success": False,
                        "error": "نام کاربری و رمز را وارد کنید."}), 400

    try:
        with get_connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT username, password_hash, role, session_version "
                    "FROM admin_users WHERE username = %s",
                    (username,)
                )
                user = cur.fetchone()
    except Exception:
        app.logger.exception("Admin login database error")
        return jsonify({"success": False,
                        "error": "خطای پایگاه داده."}), 500

    password_matches = bool(
        user and check_password_hash(user[1], password)
    )

    if not user or not password_matches:
        return jsonify({"success": False,
                        "error": "نام کاربری یا رمز اشتباه است."}), 401

    if user[2] not in ("master", "admin2"):
        return jsonify({"success": False,
                        "error": "نقش نامعتبر است."}), 403

    session.clear()
    session.permanent = True
    session["admin_username"] = user[0]
    session["admin_role"] = user[2]
    session["admin_session_version"] = user[3]
    session["csrf_token"] = secrets.token_urlsafe(32)

    return jsonify({
        "success": True,
        "username": user[0],
        "role": user[2],
        "csrf_token": session["csrf_token"]
    })


@app.route("/api/auth/me", methods=["GET"])
def admin_me():
    try:
        if not validate_admin_session():
            return jsonify({
                "success": False,
                "authenticated": False
            }), 401
    except Exception:
        app.logger.exception("Admin identity validation failed")
        return jsonify({
            "success": False,
            "authenticated": False,
            "error": "بررسی حساب موقتاً امکان‌پذیر نیست."
        }), 503

    return jsonify({
        "success": True,
        "authenticated": True,
        "username": session.get("admin_username"),
        "role": session.get("admin_role"),
        "csrf_token": session.get("csrf_token")
    })

@app.route("/api/auth/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"success": True})


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
