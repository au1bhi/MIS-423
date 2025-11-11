from decimal import Decimal

from flask import Flask, render_template_string, request, redirect, url_for, session, abort
import mysql.connector
from mysql.connector import pooling


app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = "Just for MySQL in MIS - 423"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "PASSword@0",
    "database": "mis_423",
    "charset": "utf8mb4",
}


STUDENT_TICKET_NAMES = (
    "QUIE本校学生票",
    "泉州本校学生票",
)


_connection_pool = None


def get_connection():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name="mis_423_pool",
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG,
        )
    return _connection_pool.get_connection()
def fetch_ticket_types():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
      SELECT id, name, price, description
      FROM ticket_types
      ORDER BY id
      """
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def get_ticket_type(ticket_type_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, name, price, description FROM ticket_types WHERE id = %s",
            (ticket_type_id,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def get_user_by_phone(phone):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
      "SELECT id, user_type, phone, password FROM users WHERE phone = %s",
      (phone,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def fetch_users():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
    SELECT id, user_type, phone, created_at
      FROM users
      ORDER BY created_at DESC
      """
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def fetch_orders_with_details():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
      SELECT
        o.id,
        o.user_id,
        u.phone,
        o.status,
        o.total_amount,
        o.created_at,
        o.paid_at,
        od.id AS detail_id,
        od.ticket_type_id,
        od.quantity,
        od.unit_price,
        tt.name AS ticket_name
      FROM orders o
      LEFT JOIN users u ON o.user_id = u.id
      LEFT JOIN order_details od ON od.order_id = o.id
      LEFT JOIN ticket_types tt ON od.ticket_type_id = tt.id
      ORDER BY o.created_at DESC, od.id ASC
      """
        )
        rows = cursor.fetchall()
        orders = []
        order_map = {}
        for row in rows:
            order_id = row["id"]
            order = order_map.get(order_id)
            if order is None:
                order = {
                    "id": order_id,
                    "user_id": row["user_id"],
          "phone": row.get("phone"),
                    "status": row["status"],
                    "total_amount": row["total_amount"],
                    "created_at": row["created_at"],
                    "paid_at": row.get("paid_at"),
                    "details": [],
                }
                order_map[order_id] = order
                orders.append(order)
            if row["detail_id"]:
                order["details"].append(
                    {
                        "ticket_type_id": row["ticket_type_id"],
                        "name": row.get("ticket_name"),
                        "quantity": row["quantity"],
                        "unit_price": row["unit_price"],
                    }
                )
        return orders
    finally:
        cursor.close()
        conn.close()


def fetch_order_summary(order_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
      SELECT
        o.id,
        o.user_id,
        o.status,
        o.total_amount,
        o.created_at,
        o.paid_at,
        od.id AS detail_id,
        od.ticket_type_id,
        od.quantity,
        od.unit_price,
        tt.name AS ticket_name
      FROM orders o
      LEFT JOIN order_details od ON od.order_id = o.id
      LEFT JOIN ticket_types tt ON od.ticket_type_id = tt.id
      WHERE o.id = %s
      ORDER BY od.id ASC
      """,
            (order_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        header = rows[0]
        order = {
            "id": header["id"],
            "user_id": header["user_id"],
            "status": header["status"],
            "total_amount": header["total_amount"],
            "created_at": header["created_at"],
            "paid_at": header.get("paid_at"),
            "details": [],
        }

        for row in rows:
            if row["detail_id"]:
                order["details"].append(
                    {
                        "ticket_type_id": row["ticket_type_id"],
                        "name": row.get("ticket_name"),
                        "quantity": row["quantity"],
                        "unit_price": row["unit_price"],
                    }
                )

        return order
    finally:
        cursor.close()
        conn.close()


ADMIN_TEMPLATE = """
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="utf-8">
    <title>管理后台 - 泉州野区大花园</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
  </head>
  <body>
    <div class="page">
      <div class="page__inner">
        <div class="nav-bar">
          <span>欢迎回来，管理员</span>
          <a href="{{ url_for('login') }}">返回登录</a>
        </div>
  <div class="hero hero--nowrap">
          <span class="hero__badge">Admin Console</span>
          <h1 class="hero__title">泉州野区大花园 · 订单管理</h1>
          <p class="hero__subtitle">管理用户类型、订单状态与支付进度，保持运营顺畅。</p>
        </div>
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-card__label">注册用户</span>
            <span class="stat-card__value">{{ total_users }}</span>
            <span class="stat-card__meta">{{ student_users }} 位本校学生</span>
          </div>
          <div class="stat-card">
            <span class="stat-card__label">订单总数</span>
            <span class="stat-card__value">{{ total_orders }}</span>
            <span class="stat-card__meta">待支付 {{ pending_orders }} 单 · 已支付 {{ paid_orders }} 单</span>
          </div>
          <div class="stat-card">
            <span class="stat-card__label">已收款</span>
            <span class="stat-card__value">￥{{ '%.2f'|format(total_revenue) }}</span>
            <span class="stat-card__meta">平均客单价 ￥{{ '%.2f'|format(avg_ticket_value) }}</span>
          </div>
        </div>
        {% if message %}
        <div class="alert alert--{{ message_type|default('info') }}">{{ message }}</div>
        {% endif %}
        <div class="admin-grid admin-grid--split">
          <div class="card card--full">
            <div class="card__header">
              <h2 class="card__title">用户管理</h2>
              <span class="card__subtitle">维护用户信息与身份类型</span>
            </div>
            {% if users %}
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>用户 ID</th>
                    <th>手机号</th>
                    <th>身份类型</th>
                    <th>注册时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {% for user in users %}
                  <tr>
                    <td>{{ user.id }}</td>
                    <td>{{ user.phone }}</td>
                    <td>{{ '泉州本校学生' if user.user_type == 'QUIE_STUDENT' else user.user_type }}</td>
                    <td>{{ user.created_at }}</td>
                    <td>
                      <div class="table-actions">
                        <form method="post" class="inline-form">
                          <input type="hidden" name="action" value="update_user_type">
                          <input type="hidden" name="user_id" value="{{ user.id }}">
                          <select name="user_type">
                            <option value="REGULAR" {% if user.user_type == 'REGULAR' %}selected{% endif %}>REGULAR</option>
                            <option value="QUIE_STUDENT" {% if user.user_type == 'QUIE_STUDENT' %}selected{% endif %}>泉州本校学生</option>
                          </select>
                          <button type="submit" class="btn btn--sm btn--ghost">更新</button>
                        </form>
                        <form method="post" class="inline-form" onsubmit="return confirm('确认删除该用户？');">
                          <input type="hidden" name="action" value="delete_user">
                          <input type="hidden" name="user_id" value="{{ user.id }}">
                          <button type="submit" class="btn btn--sm btn--danger">删除</button>
                        </form>
                      </div>
                    </td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            {% else %}
            <div class="empty-state">暂无用户数据</div>
            {% endif %}
          </div>
          <div class="card card--full">
            <div class="card__header">
              <h2 class="card__title">订单列表</h2>
              <span class="card__subtitle">查看订单详情与票务构成</span>
            </div>
            {% if orders %}
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>订单 ID</th>
                    <th>用户手机号</th>
                    <th>状态</th>
                    <th>总金额</th>
                    <th>创建时间</th>
                    <th>支付时间</th>
                    <th>详情</th>
                  </tr>
                </thead>
                <tbody>
                  {% for order in orders %}
                  <tr>
                    <td>{{ order.id }}</td>
                    <td>{{ order.phone }}</td>
                    <td>{{ order.status }}</td>
                    <td>￥{{ order.total_amount }}</td>
                    <td>{{ order.created_at }}</td>
                    <td>{{ order.paid_at or '—' }}</td>
                    <td>
                      {% if order.details %}
                      <ul class="detail-list">
                        {% for detail in order.details %}
                        <li>{{ detail.name }} x {{ detail.quantity }} (￥{{ detail.unit_price }})</li>
                        {% endfor %}
                      </ul>
                      {% else %}
                      无
                      {% endif %}
                    </td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            {% else %}
            <div class="empty-state">暂无订单</div>
            {% endif %}
          </div>
          <div class="card card--wide">
            <div class="card__header">
              <h2 class="card__title">运营操作台</h2>
              <span class="card__subtitle">快速处理线下订单与状态变更</span>
            </div>
            <div class="quick-actions">
              <div class="form-block">
                <div class="form-block__title">创建订单</div>
                <p class="form-block__desc">用于现场售票或后台补录。</p>
                <form method="post" class="form form--dense">
                  <input type="hidden" name="action" value="create_order">
                  <div class="form-field">
                    <label for="user_id">用户 ID</label>
                    <input type="number" id="user_id" name="user_id" min="1" placeholder="输入用户 ID">
                  </div>
                  <div class="form-field">
                    <label for="ticket_type_id">票种</label>
                    <select id="ticket_type_id" name="ticket_type_id">
                      <option value="">选择票种</option>
                      {% for ticket in ticket_types %}
                      <option value="{{ ticket.id }}">{{ ticket.name }}</option>
                      {% endfor %}
                    </select>
                  </div>
                  <div class="form-field">
                    <label for="quantity">数量</label>
                    <input type="number" id="quantity" name="quantity" min="1" value="1">
                  </div>
                  <div class="card__actions">
                    <button type="submit">创建订单</button>
                  </div>
                </form>
              </div>
              <div class="form-block">
                <div class="form-block__title">更新订单状态</div>
                <p class="form-block__desc">调整订单流程节点。</p>
                <form method="post" class="form form--dense">
                  <input type="hidden" name="action" value="update_order_status">
                  <div class="form-field">
                    <label for="order_id_status">订单 ID</label>
                    <input type="number" id="order_id_status" name="order_id" min="1" placeholder="输入订单 ID">
                  </div>
                  <div class="form-field">
                    <label for="status">订单状态</label>
                    <select id="status" name="status">
                      {% for status in status_options %}
                      <option value="{{ status }}">{{ status }}</option>
                      {% endfor %}
                    </select>
                  </div>
                  <div class="card__actions">
                    <button type="submit">更新状态</button>
                  </div>
                </form>
              </div>
              <div class="form-block">
                <div class="form-block__title">标记已支付</div>
                <p class="form-block__desc">确认线下收款后同步状态。</p>
                <form method="post" class="form form--dense">
                  <input type="hidden" name="action" value="mark_order_paid">
                  <div class="form-field">
                    <label for="order_id_paid">订单 ID</label>
                    <input type="number" id="order_id_paid" name="order_id" min="1" placeholder="输入订单 ID">
                  </div>
                  <div class="card__actions">
                    <button type="submit">标记为已支付</button>
                  </div>
                </form>
              </div>
              <div class="form-block">
                <div class="form-block__title">删除订单</div>
                <p class="form-block__desc">慎重操作，删除后不可恢复。</p>
                <form method="post" class="form form--dense" onsubmit="return confirm('确认删除订单？');">
                  <input type="hidden" name="action" value="delete_order">
                  <div class="form-field">
                    <label for="order_id_delete">订单 ID</label>
                    <input type="number" id="order_id_delete" name="order_id" min="1" placeholder="输入订单 ID">
                  </div>
                  <div class="card__actions">
                    <button type="submit" class="btn btn--danger">删除订单</button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def create_user(phone, password, user_type="REGULAR"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_type, phone, password) VALUES (%s, %s, %s)",
            (user_type, phone, password),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def get_user_type(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()
        conn.close()


def create_order(user_id, selections, total_amount, status="PENDING"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO orders (user_id, status, total_amount) VALUES (%s, %s, %s)",
            (user_id, status, str(total_amount)),
        )
        order_id = cursor.lastrowid

        detail_sql = (
            "INSERT INTO order_details (order_id, ticket_type_id, quantity, unit_price) "
            "VALUES (%s, %s, %s, %s)"
        )
        for item in selections:
            cursor.execute(
                detail_sql,
        (
          order_id,
          item["ticket_type_id"],
          item["quantity"],
          str(item["unit_price"]),
        ),
            )

        conn.commit()
        return order_id
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def update_order_status(order_id, status):
    if status not in {"PENDING", "COMPLETED", "PAID", "CANCELLED"}:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if status == "PAID":
            cursor.execute(
                "UPDATE orders SET status = %s, paid_at = COALESCE(paid_at, NOW()) WHERE id = %s",
                (status, order_id),
            )
        else:
            cursor.execute(
                "UPDATE orders SET status = %s, paid_at = NULL WHERE id = %s",
                (status, order_id),
            )

        if cursor.rowcount:
            conn.commit()
            return True

        conn.rollback()
        return False
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def mark_order_paid(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE orders SET status = 'PAID', paid_at = COALESCE(paid_at, NOW()) WHERE id = %s",
            (order_id,),
        )
        if cursor.rowcount:
            conn.commit()
            return True

        conn.rollback()
        return False
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def delete_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM order_details WHERE order_id = %s", (order_id,))
        cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        if cursor.rowcount:
            conn.commit()
            return True

        conn.rollback()
        return False
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def update_user_type(user_id, user_type):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET user_type = %s WHERE id = %s",
            (user_type, user_id),
        )
        if cursor.rowcount:
            conn.commit()
            return True
        conn.rollback()
        return False
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def delete_user_and_orders(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM orders WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cursor.rowcount:
            conn.commit()
            return True
        conn.rollback()
        return False
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        is_student = request.form.get("is_quie_student") == "on"
        student_id = request.form.get("student_id", "").strip()
        student_name = request.form.get("student_name", "").strip()

        context = {
            "phone": phone,
            "is_student": is_student,
            "student_id": student_id,
            "student_name": student_name,
        }

        if not phone or not password:
            return render_template_string(
                SIGNUP_TEMPLATE,
                error="手机号和密码均不能为空",
                **context,
            )

        if is_student and (not student_id or not student_name):
            return render_template_string(
                SIGNUP_TEMPLATE,
                error="请填写本校学生的姓名和学号",
                **context,
            )

        if get_user_by_phone(phone):
            return render_template_string(
                SIGNUP_TEMPLATE,
                error="该手机号已注册",
                **context,
            )

        user_type = "QUIE_STUDENT" if is_student else "REGULAR"
        create_user(phone, password, user_type=user_type)
        return redirect(url_for("login"))

    return render_template_string(SIGNUP_TEMPLATE)


@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_phone(phone)
        if user and user["password"] == password:
            session["user_id"] = user["id"]
            session["phone"] = user["phone"]
            session["user_type"] = user.get("user_type")
            return redirect(url_for("order"))

        error = "登录失败，请检查手机号或密码"

    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/order", methods=["GET", "POST"])
def order():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_type = get_user_type(session["user_id"]) or "REGULAR"
    session["user_type"] = user_type

    ticket_types = fetch_ticket_types()
    if user_type != "QUIE_STUDENT":
        ticket_types = [
            ticket
            for ticket in ticket_types
            if ticket["name"] not in STUDENT_TICKET_NAMES
        ]

    if request.method == "POST":
        total_amount = Decimal("0.00")
        selections = []

        for ticket in ticket_types:
            qty_raw = request.form.get(str(ticket["id"]))
            try:
                quantity = int(qty_raw) if qty_raw is not None else 0
            except ValueError:
                quantity = 0

            if quantity > 0:
                unit_price = Decimal(str(ticket["price"]))
                line_total = unit_price * quantity
                total_amount += line_total
                selections.append(
                    {
                        "ticket_type_id": ticket["id"],
                        "name": ticket["name"],
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                    }
                )

        if not selections:
            return render_template_string(
                ORDER_TEMPLATE,
                ticket_types=ticket_types,
                error="请至少选择一张票",
                user_type=user_type,
            )

        order_id = create_order(
            session["user_id"],
            selections,
            total_amount,
        )
        return redirect(url_for("order_summary", order_id=order_id, pending="1"))

    return render_template_string(
        ORDER_TEMPLATE,
        ticket_types=ticket_types,
        user_type=user_type,
    )


@app.route("/order/<int:order_id>/summary", methods=["GET"])
def order_summary(order_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    order_record = fetch_order_summary(order_id)
    if not order_record or order_record["user_id"] != session["user_id"]:
        abort(404)

    selections = []
    for item in order_record["details"]:
        unit_price = Decimal(str(item["unit_price"]))
        line_total = unit_price * item["quantity"]
        selections.append(
            {
                "name": item["name"],
                "quantity": item["quantity"],
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    status_message = None
    status_type = "info"
    error_code = request.args.get("error")
    if error_code == "db":
        status_message = "支付确认失败，请稍后重试。"
        status_type = "error"
    elif error_code == "not_found":
        status_message = "未找到订单，请刷新后重试。"
        status_type = "error"
    elif request.args.get("paid") == "1":
        status_message = "支付成功，订单已完成。"
        status_type = "success"
    elif request.args.get("pending") == "1":
        status_message = "订单已创建，请支付完成后点击“已支付”。"

    is_paid = order_record["status"] == "PAID"
    total_amount = Decimal(str(order_record["total_amount"]))

    return render_template_string(
        ORDER_SUCCESS_TEMPLATE,
        selections=selections,
        total_amount=total_amount,
        order_id=order_record["id"],
        is_paid=is_paid,
        paid_at=order_record.get("paid_at"),
        order_status=order_record["status"],
        status_message=status_message,
        status_type=status_type,
    )


@app.route("/order/<int:order_id>/pay", methods=["POST"])
def confirm_order_payment(order_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    order_record = fetch_order_summary(order_id)
    if not order_record or order_record["user_id"] != session["user_id"]:
        abort(404)

    if order_record["status"] == "PAID":
        return redirect(url_for("order_summary", order_id=order_id, paid="1"))

    try:
        if mark_order_paid(order_id):
            return redirect(url_for("order_summary", order_id=order_id, paid="1"))
        return redirect(url_for("order_summary", order_id=order_id, error="not_found"))
    except mysql.connector.Error:
        return redirect(url_for("order_summary", order_id=order_id, error="db"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    message = None
    message_type = "info"

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        if action == "update_user_type":
            user_id_raw = request.form.get("user_id", "").strip()
            if user_id_raw.isdigit():
                new_type = request.form.get("user_type", "").strip()
                if new_type in {"REGULAR", "QUIE_STUDENT"}:
                    try:
                        if update_user_type(int(user_id_raw), new_type):
                            message = "用户类型已更新"
                            message_type = "success"
                        else:
                            message = "未找到对应的用户"
                            message_type = "error"
                    except mysql.connector.Error as exc:
                        message = f"数据库错误：{exc.msg}"
                        message_type = "error"
                else:
                    message = "无效的用户类型"
                    message_type = "error"
            else:
                message = "无效的用户标识"
                message_type = "error"
        elif action == "delete_user":
            user_id_raw = request.form.get("user_id", "").strip()
            if user_id_raw.isdigit():
                try:
                    if delete_user_and_orders(int(user_id_raw)):
                        message = "用户已删除"
                        message_type = "success"
                    else:
                        message = "未找到对应的用户"
                        message_type = "error"
                except mysql.connector.Error as exc:
                    message = f"删除失败：{exc.msg}"
                    message_type = "error"
            else:
                message = "无效的用户标识"
                message_type = "error"
        elif action == "create_order":
            user_id_raw = request.form.get("user_id", "").strip()
            ticket_type_raw = request.form.get("ticket_type_id", "").strip()
            quantity_raw = request.form.get("quantity", "").strip()
            if user_id_raw.isdigit() and ticket_type_raw.isdigit():
                try:
                    quantity = int(quantity_raw) if quantity_raw else 0
                except ValueError:
                    quantity = 0

                if quantity <= 0:
                    message = "数量必须大于 0"
                    message_type = "error"
                else:
                    existing_user_type = get_user_type(int(user_id_raw))
                    if existing_user_type is None:
                        message = "未找到对应的用户"
                        message_type = "error"
                    else:
                        ticket = get_ticket_type(int(ticket_type_raw))
                        if not ticket:
                            message = "未找到所选票种"
                            message_type = "error"
                        else:
                            try:
                                unit_price = Decimal(str(ticket["price"]))
                                line_total = unit_price * quantity
                                selections = [
                                    {
                                        "ticket_type_id": ticket["id"],
                                        "name": ticket["name"],
                                        "quantity": quantity,
                                        "unit_price": unit_price,
                                        "line_total": line_total,
                                    }
                                ]
                                create_order(
                                    int(user_id_raw),
                                    selections,
                                    line_total,
                                    status="PENDING",
                                )
                                message = "订单已创建"
                                message_type = "success"
                            except mysql.connector.Error as exc:
                                message = f"创建订单失败：{exc.msg}"
                                message_type = "error"
            else:
                message = "请选择有效的用户和票种"
                message_type = "error"
        elif action == "update_order_status":
            order_id_raw = request.form.get("order_id", "").strip()
            new_status = request.form.get("status", "").strip()
            if order_id_raw.isdigit() and new_status:
                try:
                    if update_order_status(int(order_id_raw), new_status):
                        message = "订单状态已更新"
                        message_type = "success"
                    else:
                        message = "未找到对应的订单"
                        message_type = "error"
                except mysql.connector.Error as exc:
                    message = f"更新失败：{exc.msg}"
                    message_type = "error"
            else:
                message = "无效的订单或状态"
                message_type = "error"
        elif action == "delete_order":
            order_id_raw = request.form.get("order_id", "").strip()
            if order_id_raw.isdigit():
                try:
                    if delete_order(int(order_id_raw)):
                        message = "订单已删除"
                        message_type = "success"
                    else:
                        message = "未找到对应的订单"
                        message_type = "error"
                except mysql.connector.Error as exc:
                    message = f"删除订单失败：{exc.msg}"
                    message_type = "error"
            else:
                message = "无效的订单编号"
                message_type = "error"
        elif action == "mark_order_paid":
            order_id_raw = request.form.get("order_id", "").strip()
            if order_id_raw.isdigit():
                try:
                    if mark_order_paid(int(order_id_raw)):
                        message = "订单已标记为支付完成"
                        message_type = "success"
                    else:
                        message = "未找到对应的订单"
                        message_type = "error"
                except mysql.connector.Error as exc:
                    message = f"更新支付状态失败：{exc.msg}"
                    message_type = "error"
            else:
                message = "无效的订单编号"
                message_type = "error"
        elif action:
            message = "未知的操作"
            message_type = "error"

    orders = fetch_orders_with_details()
    users = fetch_users()
    ticket_types = fetch_ticket_types()
    status_options = ["PENDING", "COMPLETED", "PAID", "CANCELLED"]

    total_users = len(users)
    student_users = sum(1 for user in users if user.get(
        "user_type") == "QUIE_STUDENT")
    total_orders = len(orders)
    pending_orders = sum(
        1 for order in orders if order.get("status") == "PENDING")
    paid_orders = sum(1 for order in orders if order.get("status") == "PAID")

    total_revenue = Decimal("0.00")
    for order in orders:
        amount = order.get("total_amount")
        if amount is not None:
            total_revenue += Decimal(str(amount))

    avg_ticket_value = Decimal("0.00")
    if total_orders:
        avg_ticket_value = total_revenue / Decimal(total_orders)

    return render_template_string(
        ADMIN_TEMPLATE,
        orders=orders,
        users=users,
        ticket_types=ticket_types,
        status_options=status_options,
        message=message,
        message_type=message_type,
        total_users=total_users,
        student_users=student_users,
        total_orders=total_orders,
        pending_orders=pending_orders,
        paid_orders=paid_orders,
        total_revenue=total_revenue,
        avg_ticket_value=avg_ticket_value,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


LOGIN_TEMPLATE = """
<!doctype html>
<html lang=\"zh\">
  <head>
    <meta charset=\"utf-8\">
    <title>登录 - 泉州野区大花园</title>
    <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='styles.css') }}\">
  </head>
  <body>
    <div class=\"page page--auth\">
      <div class=\"page__inner\">
        <div class=\"hero\">
          <span class=\"hero__badge\">Quanzhou Garden</span>
          <h1 class=\"hero__title\">泉州野区大花园</h1>
          <p class=\"hero__subtitle\">登录以继续管理和购买活动门票</p>
        </div>
        <div class=\"card card--compact auth-panels\">
          {% if error %}
          <div class=\"alert alert--error\">{{ error }}</div>
          {% endif %}
          <form method=\"post\" class=\"form\">
            <div class=\"form-field\">
              <label for=\"phone\">手机号</label>
              <input type=\"text\" id=\"phone\" name=\"phone\" required>
            </div>
            <div class=\"form-field\">
              <label for=\"password\">密码</label>
              <input type=\"password\" id=\"password\" name=\"password\" required>
            </div>
            <button type=\"submit\">立即登录</button>
          </form>
          <div class=\"meta-text\">还没有账号？<a href=\"{{ url_for('signup') }}\">马上注册</a></div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


SIGNUP_TEMPLATE = """
<!doctype html>
<html lang=\"zh\">
  <head>
    <meta charset=\"utf-8\">
    <title>注册 - 泉州野区大花园</title>
    <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='styles.css') }}\">
  </head>
  <body>
    <div class=\"page page--auth\">
      <div class=\"page__inner\">
        <div class=\"hero\">
          <span class=\"hero__badge\">Join Quanzhou Garden</span>
          <h1 class=\"hero__title\">创建新账号</h1>
          <p class=\"hero__subtitle\">加入泉州野区大花园，探索更多精彩活动</p>
        </div>
        <div class=\"card card--compact auth-panels\">
          {% if error %}
          <div class=\"alert alert--error\">{{ error }}</div>
          {% endif %}
          <form method=\"post\" class=\"form\">
            <div class=\"form-field\">
              <label for=\"phone\">手机号</label>
              <input type=\"text\" id=\"phone\" name=\"phone\" value=\"{{ phone|default('') }}\" required>
            </div>
            <div class=\"form-field\">
              <label for=\"password\">密码</label>
              <input type=\"password\" id=\"password\" name=\"password\" required>
            </div>
            <label class=\"checkbox\" for=\"is_quie_student\">
              <input type=\"checkbox\" name=\"is_quie_student\" id=\"is_quie_student\" {{ 'checked' if is_student|default(False) else '' }}>
              我是QUIE本校学生
            </label>
            <div id=\"student_fields\" class=\"student-fields\" {% if not is_student|default(False) %}style=\"display: none;\"{% endif %}>
              <div class=\"form-field\">
                <label for=\"student_name\">姓名</label>
                <input type=\"text\" id=\"student_name\" name=\"student_name\" value=\"{{ student_name|default('') }}\">
              </div>
              <div class=\"form-field\">
                <label for=\"student_id\">学号</label>
                <input type=\"text\" id=\"student_id\" name=\"student_id\" value=\"{{ student_id|default('') }}\">
              </div>
              <small>由于项目仅供运行数据库，暂不做验证。</small>
            </div>
            <button type=\"submit\">完成注册</button>
          </form>
          <div class=\"meta-text\">已有账号？<a href=\"{{ url_for('login') }}\">返回登录</a></div>
        </div>
      </div>
    </div>
    <script>
      const studentCheckbox = document.getElementById('is_quie_student');
      const studentFields = document.getElementById('student_fields');
      if (studentCheckbox && studentFields) {
        const toggleStudentFields = () => {
          studentFields.style.display = studentCheckbox.checked ? 'grid' : 'none';
        };
        toggleStudentFields();
        studentCheckbox.addEventListener('change', toggleStudentFields);
      }
    </script>
  </body>
</html>
"""


ORDER_TEMPLATE = """
<!doctype html>
<html lang=\"zh\">
  <head>
    <meta charset=\"utf-8\">
    <title>购票 - 泉州野区大花园</title>
    <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='styles.css') }}\">
  </head>
  <body>
    <div class=\"page\">
      <div class=\"page__inner\">
        <div class=\"nav-bar\">
          <span>当前用户：{{ session.get('phone', '访客') }}</span>
          <a href=\"{{ url_for('logout') }}\">退出登录</a>
        </div>
        <div class=\"hero\">
          <span class=\"hero__badge\">Ticket Center</span>
          <h1 class=\"hero__title\">选择票种</h1>
          <p class=\"hero__subtitle\">根据来访身份选择合适票种，确认数量后提交订单。</p>
        </div>
        <div class=\"card\">
          {% if user_type|default('REGULAR') != 'QUIE_STUDENT' %}
          <div class=\"notice\">温馨提示：普通用户无法选择泉州本校学生专属票种。</div>
          {% else %}
          <div class=\"notice\">欢迎本校学生，验证通过后可享受专属票价。</div>
          {% endif %}
          {% if error %}
          <div class=\"alert alert--error\">{{ error }}</div>
          {% endif %}
          <form method=\"post\" class=\"form\">
            <div class=\"table-container\">
              <table>
                <thead>
                  <tr>
                    <th>票种</th>
                    <th>价格</th>
                    <th>描述</th>
                    <th style=\"width: 120px;\">数量</th>
                  </tr>
                </thead>
                <tbody>
                  {% for ticket in ticket_types %}
                  <tr>
                    <td>{{ ticket.name }}</td>
                    <td>￥{{ ticket.price }}</td>
                    <td>{{ ticket.description or '—' }}</td>
                    <td>
                      <input type=\"number\" min=\"0\" value=\"0\" name=\"{{ ticket.id }}\">
                    </td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            <div class=\"card__actions\">
              <button type=\"submit\">提交订单</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </body>
</html>
"""


ORDER_SUCCESS_TEMPLATE = """
<!doctype html>
<html lang=\"zh\">
  <head>
    <meta charset=\"utf-8\">
    <title>订单支付确认 - 泉州野区大花园</title>
    <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='styles.css') }}\">
  </head>
  <body>
    <div class=\"page\">
      <div class=\"page__inner\">
        <div class=\"nav-bar\">
          <span>当前用户：{{ session.get('phone', '访客') }}</span>
          <a href=\"{{ url_for('logout') }}\">退出登录</a>
        </div>
        <div class=\"hero\">
          <span class=\"hero__badge\">Order Center</span>
          <h1 class=\"hero__title\">订单支付确认</h1>
          <p class=\"hero__subtitle\">核对订单详情并完成支付确认。</p>
        </div>
        <div class=\"card\">
          <div class=\"order-summary\">
            <div>订单 ID：{{ order_id }}</div>
            <div>当前状态：{{ order_status }}</div>
            {% if paid_at %}
            <div>支付时间：{{ paid_at }}</div>
            {% endif %}
          </div>
          {% if status_message %}
          <div class=\"alert alert--{{ status_type|default('info') }}\">{{ status_message }}</div>
          {% endif %}
          <div class=\"table-container\">
            <table>
              <thead>
                <tr>
                  <th>票种</th>
                  <th>数量</th>
                  <th>单价</th>
                  <th>小计</th>
                </tr>
              </thead>
              <tbody>
                {% for item in selections %}
                <tr>
                  <td>{{ item.name }}</td>
                  <td>{{ item.quantity }}</td>
                  <td>￥{{ item.unit_price }}</td>
                  <td>￥{{ item.line_total }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
          <div class=\"total\">总金额：￥{{ total_amount }}</div>
          <div class=\"actions\">
            {% if not is_paid %}
            <form method=\"post\" action=\"{{ url_for('confirm_order_payment', order_id=order_id) }}\">
              <button type=\"submit\">已支付</button>
            </form>
            {% endif %}
            <a class=\"btn\" href=\"{{ url_for('order') }}\">继续购票</a>
            <a class=\"btn btn--secondary\" href=\"{{ url_for('logout') }}\">退出登录</a>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True)
