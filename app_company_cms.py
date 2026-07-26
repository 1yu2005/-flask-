'''
技术公司官方网站与内容管理系统 (CMS)
=========================================
基于 Flask + SQLite 的完整 CMS 系统。

前端页面：
  - GET  /           公司首页（公司简介 + 最新3条新闻）
  - GET  /news       新闻列表页（全部新闻，按时间倒序）
  - GET  /news/<id>  新闻详情页
  - GET  /login      管理员登录页面
  - GET  /manager    管理后台（需登录）

API 接口：
  前台（公开）：
    - GET  /api/news       获取新闻列表（按发布时间倒序）
    - GET  /api/news/<id>  获取新闻详情
  后台（需管理员权限）：
    - POST   /auth/login              管理员登录
    - POST   /auth/logout             管理员登出
    - POST   /manager/news-publish    发布新闻
    - DELETE /manager/news-delete/<id> 删除新闻

数据持久化：SQLite (cms.db)
管理员账号预设：admin / admin123
'''

import sqlite3
import os
from datetime import datetime
import secrets
from flask import Flask, request, jsonify, session, render_template
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# ==================== 应用初始化 ====================
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Session 加密密钥
app.json.ensure_ascii = False           # JSON 响应中文不转义

# 数据库文件路径（与脚本同目录）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cms.db')


# ==================== 数据库工具函数 ====================

def get_db():
    """获取数据库连接（自动开启外键约束）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让查询结果支持按列名访问
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库：创建 users 表和 news 表，并预设管理员账号"""
    conn = get_db()
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    # 新闻表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            publish_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    # 预设管理员账号（如不存在则创建）
    existing = cursor.execute(
        "SELECT id FROM users WHERE username = ?", ('admin',)
    ).fetchone()

    if not existing:
        password_hash = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ('admin', password_hash, 'admin')
        )

    conn.commit()
    conn.close()


# 应用启动时执行初始化
init_db()


# ==================== 登录校验装饰器 ====================

def login_required(f):
    """
    管理员登录校验装饰器。
    检查 session 中是否有 role='admin'，否则返回 403。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({"code": 403, "msg": "权限不足，请先以管理员身份登录"}), 403
        return f(*args, **kwargs)
    return decorated


# ==================== 身份认证接口 ====================

@app.route('/auth/login', methods=['POST'])
def auth_login():
    """管理员登录接口"""
    data = request.get_json()
    if not data:
        return jsonify({"code": 400, "msg": "请提供 JSON 格式的登录数据"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"code": 400, "msg": "用户名和密码不能为空"}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"code": 401, "msg": "用户名或密码错误"}), 401

    if not check_password_hash(user['password_hash'], password):
        return jsonify({"code": 401, "msg": "用户名或密码错误"}), 401

    # 登录成功：写入 session
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']

    return jsonify({
        "code": 200,
        "msg": "登录成功",
        "data": {"username": user['username'], "role": user['role']}
    })


@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    """管理员登出接口"""
    session.clear()
    return jsonify({"code": 200, "msg": "已退出登录"})


# ==================== 前台页面路由（公开访问） ====================

@app.route('/')
def page_index():
    """公司首页：公司简介 + 最新 3 条新闻"""
    conn = get_db()
    news_list = conn.execute(
        "SELECT * FROM news ORDER BY publish_time DESC LIMIT 3"
    ).fetchall()
    conn.close()

    # 将 Row 对象转为字典列表，方便模板使用
    news_dicts = [dict(row) for row in news_list]
    return render_template('index.html', news_list=news_dicts)


@app.route('/news')
def page_news_list():
    """新闻列表页：全部新闻，按发布时间倒序"""
    conn = get_db()
    news_list = conn.execute(
        "SELECT * FROM news ORDER BY publish_time DESC"
    ).fetchall()
    conn.close()

    news_dicts = [dict(row) for row in news_list]
    return render_template('news_list.html', news_list=news_dicts)


@app.route('/news/<int:news_id>')
def page_news_detail(news_id):
    """新闻详情页"""
    conn = get_db()
    news = conn.execute(
        "SELECT * FROM news WHERE id = ?", (news_id,)
    ).fetchone()
    conn.close()

    if not news:
        return render_template('news_detail.html', news=None, error="新闻不存在"), 404

    return render_template('news_detail.html', news=dict(news))


@app.route('/login')
def page_login():
    """管理员登录页面"""
    # 已登录则跳转到管理后台
    if session.get('role') == 'admin':
        return render_template('manager.html')
    return render_template('login.html')


@app.route('/manager')
def page_manager():
    """管理后台页面（需登录）"""
    if session.get('role') != 'admin':
        return render_template('login.html')  # 未登录则显示登录页
    return render_template('manager.html')


# ==================== 前台 API 接口（公开访问） ====================

@app.route('/api/news', methods=['GET'])
def api_news_list():
    """获取新闻列表（按发布时间倒序）"""
    conn = get_db()
    news_list = conn.execute(
        "SELECT * FROM news ORDER BY publish_time DESC"
    ).fetchall()
    conn.close()

    return jsonify({
        "code": 200,
        "msg": "获取成功",
        "data": [dict(row) for row in news_list]
    })


@app.route('/api/news/<int:news_id>', methods=['GET'])
def api_news_detail(news_id):
    """获取新闻详情"""
    conn = get_db()
    news = conn.execute(
        "SELECT * FROM news WHERE id = ?", (news_id,)
    ).fetchone()
    conn.close()

    if not news:
        return jsonify({"code": 404, "msg": "新闻不存在"}), 404

    return jsonify({
        "code": 200,
        "msg": "获取成功",
        "data": dict(news)
    })


# ==================== 后台管理 API 接口（需管理员权限） ====================

@app.route('/manager/news-publish', methods=['POST'])
@login_required
def api_publish_news():
    """发布新闻"""
    data = request.get_json()
    if not data:
        return jsonify({"code": 400, "msg": "请提供 JSON 格式数据"}), 400

    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    category = data.get('category', '').strip()

    # 字段完整性校验
    if not title or not content or not category:
        return jsonify({"code": 400, "msg": "title、content、category 均不能为空"}), 400

    publish_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO news (title, content, category, publish_time) VALUES (?, ?, ?, ?)",
        (title, content, category, publish_time)
    )
    news_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        "code": 200,
        "msg": "新闻发布成功",
        "data": {
            "id": news_id,
            "title": title,
            "content": content,
            "category": category,
            "publish_time": publish_time
        }
    })


@app.route('/manager/news-delete/<int:news_id>', methods=['DELETE'])
@login_required
def api_delete_news(news_id):
    """删除指定新闻"""
    conn = get_db()
    news = conn.execute(
        "SELECT id FROM news WHERE id = ?", (news_id,)
    ).fetchone()

    if not news:
        conn.close()
        return jsonify({"code": 404, "msg": "新闻不存在"}), 404

    conn.execute("DELETE FROM news WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()

    return jsonify({"code": 200, "msg": f"新闻 (ID: {news_id}) 已删除"})


# ==================== 启动应用 ====================

if __name__ == '__main__':
    print(f"数据库路径: {DB_PATH}")
    print("访问地址: http://127.0.0.1:5000")
    print("管理后台: http://127.0.0.1:5000/manager")
    print("管理员账号: admin / admin123")
    app.run(host='127.0.0.1', port=5000, debug=True)
