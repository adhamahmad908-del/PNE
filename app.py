import os
import sqlite3
import time
import re
import requests
import secrets
from urllib.parse import unquote_plus
from flask import Flask, request, jsonify, render_template, session, abort

base_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=base_dir, static_folder=base_dir)
app.secret_key = "techzone-lab-secret"
DB_PATH = os.path.join(base_dir, 'users.db')
UPLOAD_FOLDER = os.path.join(base_dir, 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, role TEXT, balance REAL DEFAULT 500.0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL, category TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, content TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, body TEXT)''')
    
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role, balance) VALUES ('administrator', 'admin123', 'admin', 9999.0)")
        cursor.execute("INSERT INTO users (username, password, role, balance) VALUES ('wiener', 'peter', 'user', 500.0)")
        cursor.execute("INSERT INTO products (name, price, category) VALUES ('حاسوب محمول Pro 15', 1200.0, 'Laptops')")
        cursor.execute("INSERT INTO products (name, price, category) VALUES ('سماعة لاسلكية VIP', 150.0, 'Audio')")
        cursor.execute("INSERT INTO documents (user_id, title, content) VALUES (1, 'تقارير أرباح الإدارة السرية', 'FLAG{TechZone_Enterprise_Master_2026}')")
        cursor.execute("INSERT INTO documents (user_id, title, content) VALUES (2, 'فاتورة مشتريات وينر الشخصية', 'تم شراء سماعة لاسلكية بنجاح.')")
        cursor.execute("INSERT INTO comments (author, body) VALUES ('الإدارة', 'أهلاً بكم في متجر TechZone!')")
        conn.commit()
    conn.close()

init_db()

def weak_csrf_check():
    if "csrf" not in request.form:
        return True
    return request.form.get("csrf") == session.get("csrf_token")

@app.route('/')
def index():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return render_template('index.html', csrf_token=session["csrf_token"])

# SQL Injection
@app.route('/api/auth/login', methods=['POST'])
def login():
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = f"SELECT username, role FROM users WHERE username = '{username}' AND password = '{password}'"
    try:
        cursor.execute(query)
        user = cursor.fetchone()
        conn.close()
        if user:
            session['role'] = user[1]
            return jsonify({"status": "success", "message": f"تم تسجيل الدخول بنجاح كـ {user[0]}"})
        return jsonify({"status": "failed", "message": "بيانات الدخول غير صحيحة"}), 401
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": "خطأ في السيرفر"}), 500

# SSRF
@app.route('/api/stock/check', methods=['POST'])
def check_stock():
    stock_api = request.form.get("stockApi", "").strip()
    try:
        resp = requests.get(stock_api, timeout=3)
        return jsonify({"status": "success", "message": str(resp.text[:500])})
    except:
        return jsonify({"status": "error", "message": "فشل الاتصال بمزود المخزون."}), 502

@app.route('/admin')
def internal_admin():
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        abort(401)
    return "FLAG{SSRF_ADMIN_PANEL_REACHED}"

# Command Injection
@app.route('/api/support/ticket', methods=['POST'])
def submit_feedback():
    email = request.form.get('email', '')
    decoded_email = unquote_plus(email)
    if 'ping' in decoded_email:
        match = re.search(r'-[cn]\s+(\d+)', decoded_email)
        seconds = int(match.group(1)) if match else 5
        time.sleep(seconds)
    return jsonify({"status": "success", "message": "تم إرسال التذكرة بنجاح!"})

# CSRF
@app.route('/my-account/change-email', methods=['POST'])
def change_email():
    if not weak_csrf_check():
        return jsonify({"status": "error", "message": "طلب غير صالح"}), 403
    email = request.form.get("email", "")
    return jsonify({"status": "success", "message": f"تم تغيير الإيميل بنجاح إلى: {email}"})

# DOM XSS
@app.route('/api/products/search', methods=['GET'])
def search_products():
    query = request.args.get('q', '')
    return jsonify({"results": [], "query": query})

# Reflected XSS
@app.route('/track')
def track_order():
    order_id = request.args.get('order_id', '')
    # الكود هنا يعكس المدخلات مباشرة في المتصفح بدون تنظيف (Reflected XSS)
    html_response = f"""
    <!DOCTYPE html><html lang='ar' dir='rtl'>
    <head><meta charset='utf-8'><title>تتبع الطلب</title></head>
    <body style='font-family:sans-serif; padding:40px; background:#f8fafc;'>
        <h2>حالة الشحنة للطلب رقم: {order_id}</h2>
        <p>جاري تجهيز الشحنة في المستودع...</p>
        <br><a href='/' style='color:#2563eb;'>العودة للرئيسية</a>
    </body></html>
    """
    return html_response

# Stored XSS
@app.route('/api/comments', methods=['GET', 'POST'])
def handle_comments():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if request.method == 'POST':
        author = request.form.get('author', 'مجهول')
        body = request.form.get('body', '')
        cursor.execute("INSERT INTO comments (author, body) VALUES (?, ?)", (author, body))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "تم نشر التقييم بنجاح."})
    else:
        cursor.execute("SELECT author, body FROM comments")
        comments = [{"author": r[0], "body": r[1]} for r in cursor.fetchall()]
        conn.close()
        return jsonify({"status": "success", "comments": comments})

# Information Disclosure
@app.route('/robots.txt')
def serve_robots():
    return "User-agent: *\nDisallow: /admin-panel/\nDisallow: /backup/config.json\nDisallow: /api/v1/debug-logs\n", 200, {'Content-Type': 'text/plain'}

# Broken Access Control
@app.route('/admin-panel/', methods=['GET'])
def admin_panel():
    role = request.args.get('role', session.get('role', 'User'))
    if role == 'admin' or role == 'Administrator':
        return jsonify({"status": "success", "message": "أهلاً بك في لوحة الإدارة!", "flag": "FLAG{BAC_Bypassed}"}), 200
    return jsonify({"status": "error", "message": "غير مصرح لك بالوصول."}), 403

# Business Logic
@app.route('/api/purchase', methods=['POST'])
def purchase():
    try:
        qty = int(request.form.get('quantity', 1))
        price = 1200.0
        total = qty * price
        if total < 0:
            return jsonify({"status": "success", "message": "رصيد إضافي تمت إضافته بنجاح!"})
        return jsonify({"status": "success", "message": f"تم إتمام الشراء بقيمة: ${total}"})
    except:
        return jsonify({"status": "error", "message": "خطأ في الكمية"}), 400

# IDOR
@app.route('/api/documents/view', methods=['GET'])
def view_document():
    doc_id = request.args.get('id', '1')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content FROM documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    conn.close()
    if doc:
        return jsonify({"status": "success", "document": {"title": doc[0], "content": doc[1]}})
    return jsonify({"status": "error", "message": "المستند غير موجود"}), 404

# File Upload
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "لم يتم إرفاق ملف"}), 400
    f = request.files['file']
    filename = f.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    f.save(filepath)
    return jsonify({"status": "success", "message": f"تم رفع الملف: {filename}"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
