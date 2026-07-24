'''
技术公司官方网站与内容管理系统
接口：
1. 前台展示接口：
   - GET /：展示公司首页（公司简介、最新 3 条新闻）。
   - GET /api/news：获取新闻列表（支持按发布时间倒序）。
   - GET /api/news/<id>：获取新闻详情。
2. 后台管理接口（需管理员权限）：
   - 管理员账号预设：admin / admin123。
   - POST /manager/news-publish：发布新闻（字段：title, content, category）。
   - DELETE /manager/news-delete/<id>：删除指定新闻。
   - 必须实现登录校验装饰器，非 admin 角色访问后台接口返回 403 Forbidden。
'''

from datetime import datetime
import secrets
from flask import Flask, request, jsonify, session
from functools import wraps

app = Flask(__name__)  # 创建Flask应用实例 作用：后续启动应用时使用
app.secret_key = secrets.token_hex(16)  # 生成随机密钥 作用：加密会话数据
app.json.ensure_ascii = False # 使JSON响应中的中文字符不被转义，正常显示

# 模拟数据库
posts_db = {}  # 全局变量，用于存储新闻数据  字典中key为新闻id，value为新闻信息字典(字典嵌套字典)
next_post_id = 1  # 用于生成唯一新闻ID的计数器  初始值为1

#后台-管理员账号预设  登录
@app.route('/manager/login', methods=['POST'])
def login_temp():         #后台管理员临时登录，模拟登录
    session['manager_name'] = 'admin'   
    session['role'] = 'manager'
    return jsonify({"code":200,"msg":"后台模拟登录成功(manager:admin)"})

def login_required(f):
    @wraps(f)
    def decorated(*args,**kwargs):
        if 'manager_name' not in session or session['role'] != 'manager':
            return jsonify({"code":403,"msg":"未登录或角色错误"}),403
        return f(*args,**kwargs)
    return decorated

# 后台-发布新闻
@app.route('/manager/news-publish', methods=['POST'])
@login_required
def publish_news():
    global next_post_id  # 新闻id
    data = request.get_json()   # 获取POST请求体JSON数据  type(data) = dict

    # 校验请求体中的数据是否完整
    if 'title' not in data or 'content' not in data or 'category' not in data:
        return jsonify({"code":400,"msg":"请求体数据不完整,title,content,category任一字段都不能为空"}),400
    
    # 构建发布新闻信息字典
    publish_info = {
        'id': next_post_id,
        'title': data['title'],
        'content': data['content'],
        'category': data['category'],
        'publish_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    posts_db[next_post_id] = publish_info  # 存储到数据库中
    next_post_id += 1  # 新闻id自增
    return jsonify({"code":200,"msg":"新闻发布成功","id":next_post_id,"info":publish_info})

# 后台-删除新闻
@app.route('/manager/news-delete/<int:id>', methods=['DELETE'])
@login_required
def delete_news(id):
    # 校验要删除的新闻id是否存在
    if id not in posts_db:
        return jsonify({"code":404,"msg":"该新闻不存在"}),404

    # 删除新闻
    del posts_db[id]  # del 删除字典中的指定键值对;del 是一个语句，用于删除变量或字典中的键值对或列表中的元素等
    return jsonify({"code":200,"msg":f"新闻id为{id}的新闻删除成功"})

# 前台-展示公司首页（公司简介、最新 3 条新闻）
@app.route('/', methods=['GET'])
@login_required
def index():
    # 从数据库中获取最新 3 条新闻
    latest_news = sorted(posts_db.values(), key=lambda x: x['publish_time'], reverse=True)[:3]
    
    return jsonify({"code":200,"msg":"展示公司首页(公司简介、最新 3 条新闻)","data":latest_news})

# 前台-获取新闻列表（支持按发布时间倒序）
@app.route('/api/news', methods=['GET'])
@login_required
def get_news_list():
    # 从数据库中获取所有新闻
    news_list = sorted(posts_db.values(), key=lambda x: x['publish_time'], reverse=True)
    return jsonify({"code":200,"msg":"获取新闻列表成功","data":news_list})

# 前台-获取单篇新闻详情
@app.route('/api/news/<int:id>', methods=['GET'])
@login_required
def get_news_detail(id):
    # 校验要获取的新闻id是否存在
    if id not in posts_db:
        return jsonify({"code":404,"msg":"该新闻不存在"}),404
        
    # 从数据库中获取指定新闻详情
    return jsonify({"code":200,"msg":"获取新闻详情成功","data":posts_db[id]})

if __name__ == '__main__':
    app.run(host='127.0.0.1',port=5000, debug=True)  # 启动Flask应用 
