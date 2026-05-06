from fastapi import FastAPI, Form, HTTPException,Depends
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import requests
from fastapi import Request
from fastapi import Header
import hashlib
import razorpay
import dotenv
import os
import psycopg2

app = FastAPI()

dotenv.load_dotenv()


from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://meterflow-omega.vercel.app","https://meterflow-lu1q.vercel.app"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RAZORPAY_KEY_ID = os.getenv("api_key")
RAZORPAY_KEY_SECRET = os.getenv("secret_key")

from psycopg2.pool import SimpleConnectionPool

db_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=12,   
    dsn=os.getenv("DATABASE_URL")
)

def get_db():
    try:
        return db_pool.getconn()
    except Exception as e:
        print("DB ERROR:", e)
        raise HTTPException(status_code=500, detail="DB connection failed")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

SECRET_KEY = os.getenv("jwt_secret_key")
ALGORITHM = "HS256"

security = HTTPBearer()


from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)






def create_token(data: dict):
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.utcnow() + timedelta(hours=24)
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="User already exists")
    hashed = hash_password(password)
    cursor.execute(
        "INSERT INTO users (email, password) VALUES (%s, %s)",
        (email, hashed)
    )
    conn.commit()

    cursor.close()
    db_pool.putconn(conn)

    return {"message": "Signup successful"}


@app.get("/")
def root():
    return {"message": "API is running 🚀"}

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        stored_password = user[2]


        if not stored_password:
            raise HTTPException(status_code=500, detail="Corrupted user data")


        if stored_password.startswith("$2"):
            try:
                if not verify_password(password, stored_password):
                    raise HTTPException(status_code=401, detail="Wrong password")
            except Exception as e:
                print("BCRYPT ERROR:", e)
                raise HTTPException(status_code=500, detail="Password verification failed")

        else:
            if password != stored_password:
                raise HTTPException(status_code=401, detail="Wrong password")


            new_hashed = hash_password(password)

            cursor.execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (new_hashed, email)
            )
            conn.commit()

        token = create_token({"sub": email})
        return {"access_token": token}

    except HTTPException as e:
        raise e

    except Exception as e:
        print("LOGIN ERROR:", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        cursor.close()
        db_pool.putconn(conn)



@app.get("/my-dashboard")
def my_dashboard(user=Depends(verify_token)):
    conn = get_db()
    cursor = conn.cursor()
    email = user["sub"]

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user_id = cursor.fetchone()[0]


    cursor.execute("SELECT api_key, api_id FROM api_keys WHERE user_id=%s", (user_id,))
    keys = cursor.fetchall()

    result = []

    for key, api_id in keys:

    
        cursor.execute("SELECT name FROM apis WHERE id=%s", (api_id,))
        api_name = cursor.fetchone()[0]


        cursor.execute(
            "SELECT total_requests FROM usage_summary WHERE api_id=%s AND api_key=%s",
            (api_id, key)
        )
        usage = cursor.fetchone()
        usage = usage[0] if usage else 0


        cursor.execute(
            "SELECT balance FROM wallet WHERE api_key=%s",
            (key,)
        )
        wallet = cursor.fetchone()
        balance = wallet[0] if wallet else 0

        result.append({
            "api_name": api_name,
            "api_key": key,
            "usage": usage,
            "balance": balance
        })

    return {"data": result}

@app.get("/apis")
def get_apis():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM apis")
    data = cursor.fetchall()

    cursor.close()
    db_pool.putconn(conn)

    return {"apis": data}


def generate_api_key():
    return secrets.token_hex(16)

@app.post("/generate-key")
def generate_key(api_id: int = Form(...), user=Depends(verify_token)):

    conn = get_db()
    cursor = conn.cursor()

    email = user["sub"]

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user_id = cursor.fetchone()[0]

    cursor.execute(
        "SELECT api_key FROM api_keys WHERE api_id=%s AND user_id=%s",
        (api_id, user_id)
    )
    existing = cursor.fetchone()

    if existing:
        return {"api_key": existing[0]}

    key = generate_api_key()

    cursor.execute(
        "INSERT INTO api_keys (api_id, user_id, api_key) VALUES (%s, %s, %s)",
        (api_id, user_id, key)
    )
    conn.commit()

    cursor.close()
    db_pool.putconn(conn)    

    return {"api_key": key}



@app.get("/gateway/{slug}/{path:path}")
def gateway(
    slug: str,
    path: str,
    request: Request
):
    conn = get_db()
    cursor = conn.cursor()

    api_key = request.query_params.get("api_key")

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
        
    cursor.execute("SELECT id, base_url FROM apis WHERE slug=%s", (slug,))
    api = cursor.fetchone()

    if not api:
        raise HTTPException(status_code=404, detail="API not found")

    api_id, base_url = api


    cursor.execute(
        "SELECT * FROM api_keys WHERE api_id=%s AND api_key=%s",
        (api_id, api_key)
    )
    if not cursor.fetchone():
        raise HTTPException(status_code=403, detail="Invalid API key")

    cursor.execute(
        "SELECT total_requests FROM usage_summary WHERE api_id=%s AND api_key=%s",
        (api_id, api_key)
    )
    data = cursor.fetchone()

    total_requests = data[0] if data else 0

    # Free tier (100 requests)
    if total_requests >= 100:


        cursor.execute(
            "SELECT balance FROM wallet WHERE api_key=%s",
            (api_key,)
        )
        wallet = cursor.fetchone()

        if not wallet or wallet[0] <= 0:
            raise HTTPException(
                status_code=402,
                detail="Limit exhausted. Please recharge."
            )

        new_balance = wallet[0] - 1

        cursor.execute(
            "UPDATE wallet SET balance=%s WHERE api_key=%s",
            (new_balance, api_key)
        )

    params = dict(request.query_params)
    params.pop("api_key", None)

    url = f"{base_url}/{path}"



    cursor.execute(
        "INSERT INTO usage_logs (api_id, api_key) VALUES (%s, %s)",
        (api_id, api_key)
    )

    cursor.execute("""
        INSERT INTO usage_summary (api_id, api_key, total_requests)
        VALUES (%s, %s, 1)
        ON CONFLICT (api_id, api_key)
        DO UPDATE SET total_requests = usage_summary.total_requests + 1
    """, (api_id, api_key))

    conn.commit()


    try:
        response = requests.get(url, params=params, timeout=5)
    except requests.exceptions.RequestException as e:
        return {"error": "External API failed", "details": str(e)}


    if response.status_code != 200:
        return {
            "error": "API returned error",
            "status_code": response.status_code,
            "response": response.text
        }


    try:
        return response.json()
    except:
        return {"response": response.text}

@app.get("/my-usage")
def get_usage(user=Depends(verify_token)):
    conn = get_db()
    cursor = conn.cursor()

    email = user["sub"]

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user_id = cursor.fetchone()[0]

    cursor.execute("""
        SELECT apis.name, usage_summary.total_requests, api_keys.api_key
        FROM usage_summary
        JOIN api_keys ON usage_summary.api_key = api_keys.api_key
        JOIN apis ON usage_summary.api_id = apis.id
        WHERE api_keys.user_id = %s
    """, (user_id,))

    data = cursor.fetchall()

    return {"usage": data}

@app.post("/create-order")
def create_order(amount: float = Form(...), api_key: str = Form(...),user=Depends(verify_token)):
    try:
        conn = get_db()
        cursor = conn.cursor()
        email = user["sub"]

        # 2. Get the User ID of the logged-in user
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        user_record = cursor.fetchone()
        if not user_record:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user_record[0]

        # 3. VERIFY OWNERSHIP: Does this api_key belong to this user_id?
        cursor.execute(
            "SELECT 1 FROM api_keys WHERE api_key=%s AND user_id=%s",
            (api_key, user_id)
        )
        if not cursor.fetchone():
            cursor.close()
            db_pool.putconn(conn)
            raise HTTPException(
                status_code=403, 
                detail="Unauthorized: This API key does not belong to your account."
            )
        order = client.order.create({
            "amount": int(amount * 100),
            "currency": "INR",
            "payment_capture": 1,

            "notes": {
                "user_id": str(user_id),
                "api_key": api_key,
                "amount": str(amount)
            }
        })

        return {
            "order_id": order["id"],
            "key": RAZORPAY_KEY_ID
        }

    except Exception as e:
        print("PAYMENT ERROR:", e)
        raise HTTPException(status_code=400, detail="Payment verification failed")

@app.post("/verify-payment")
def verify_payment(
    razorpay_order_id: str = Form(...),
    razorpay_payment_id: str = Form(...),
    razorpay_signature: str = Form(...),
    user=Depends(verify_token)
):
    conn = get_db()
    cursor = conn.cursor()

    try:

        # ---------------- VERIFY SIGNATURE ----------------
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        # ---------------- CURRENT USER ----------------
        email = user["sub"]

        cursor.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        current_user = cursor.fetchone()

        if not current_user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        current_user_id = current_user[0]

        # ---------------- FETCH ORDER FROM RAZORPAY ----------------
        order = client.order.fetch(razorpay_order_id)

        notes = order.get("notes", {})

        stored_user_id = int(notes.get("user_id"))
        api_key = notes.get("api_key")
        amount = float(notes.get("amount"))

        # ---------------- OWNERSHIP VALIDATION ----------------
        if current_user_id != stored_user_id:
            raise HTTPException(
                status_code=403,
                detail="Unauthorized payment verification"
            )

        # ---------------- DUPLICATE PAYMENT CHECK ----------------
        cursor.execute(
            """
            SELECT 1
            FROM payments
            WHERE razorpay_payment_id=%s
            """,
            (razorpay_payment_id,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Payment already processed"
            )

        # ---------------- CALCULATE CREDITS ----------------
        credits = int(amount * 500)

        # ---------------- UPDATE WALLET ----------------
        cursor.execute(
            """
            SELECT balance
            FROM wallet
            WHERE api_key=%s
            """,
            (api_key,)
        )

        wallet = cursor.fetchone()

        if wallet:

            cursor.execute(
                """
                UPDATE wallet
                SET balance = balance + %s
                WHERE api_key=%s
                """,
                (credits, api_key)
            )

        else:

            cursor.execute(
                """
                INSERT INTO wallet
                (api_key, balance)
                VALUES (%s, %s)
                """,
                (api_key, credits)
            )

        # ---------------- STORE PAYMENT HISTORY ----------------
        cursor.execute(
            """
            INSERT INTO payments
            (
                api_key,
                amount,
                credits,
                razorpay_payment_id
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                api_key,
                amount,
                credits,
                razorpay_payment_id
            )
        )

        conn.commit()

        return {
            "message": "Payment successful ✅"
        }

    except HTTPException as e:
        conn.rollback()
        raise e

    except Exception as e:

        conn.rollback()

        print("VERIFY PAYMENT ERROR:", e)

        raise HTTPException(
            status_code=500,
            detail="Payment verification failed"
        )

    finally:
        cursor.close()
        db_pool.putconn(conn)
from fastapi import Depends
from datetime import datetime, timedelta
@app.get("/analytics")
def analytics(user=Depends(verify_token)):

    conn = get_db()
    cursor = conn.cursor()

    email = user["sub"]


    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user_id = cursor.fetchone()[0]


    cursor.execute("SELECT api_key FROM api_keys WHERE user_id=%s", (user_id,))
    keys = [k[0] for k in cursor.fetchall()]

    if not keys:
        return {"data": []}

    format_strings = ','.join(['%s'] * len(keys))

    query = f"""
        SELECT DATE(timestamp) as day, COUNT(*) as total
        FROM usage_logs
        WHERE api_key IN ({format_strings})
        AND timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day
    """

    cursor.execute(query, tuple(keys))
    rows = cursor.fetchall()

    cursor.close()
    db_pool.putconn(conn)

    return {"data": rows}

@app.get("/payments")
def get_payments(user=Depends(verify_token)):

    conn = get_db()
    cursor = conn.cursor()

    email = user["sub"]

    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    user_id = cursor.fetchone()[0]

    cursor.execute("""
        SELECT amount, credits, razorpay_payment_id, created_at
        FROM payments
        WHERE api_key IN (
            SELECT api_key FROM api_keys WHERE user_id=%s
        )
        ORDER BY created_at DESC
    """, (user_id,))
    data = cursor.fetchall()


    return {"payments": data}


