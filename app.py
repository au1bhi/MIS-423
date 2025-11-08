import uuid
from decimal import Decimal

from flask import Flask, render_template_string, request, redirect, url_for, session, abort
import mysql.connector
from mysql.connector import pooling


app = Flask(__name__)
app.secret_key = "replace-with-a-secret-key"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "PASSword@0",
    "database": "mis_423",
    "charset": "utf8mb4",
}

connection_pool = pooling.MySQLConnectionPool(
    pool_name="mis_423_pool",
    pool_size=5,
    pool_reset_session=True,
    **DB_CONFIG,
)


def get_connection():
    return connection_pool.get_connection()


def ensure_password_column():
  conn = get_connection()
  cursor = conn.cursor()
  try:
    cursor.execute("SHOW COLUMNS FROM users LIKE 'password'")
    has_column = cursor.fetchone()
    if not has_column:
      cursor.execute(
        "ALTER TABLE users ADD COLUMN password VARCHAR(128) NOT NULL AFTER identifier"
      )
      conn.commit()
  finally:
    cursor.close()
    conn.close()


def ensure_order_status_columns():
  conn = get_connection()
  cursor = conn.cursor()
  altered = False
  try:
    cursor.execute("SHOW COLUMNS FROM orders LIKE 'status'")
    status_column = cursor.fetchone()
    if status_column:
      column_type = status_column[1] if len(status_column) > 1 else ""
      desired_enum = "enum('PENDING','COMPLETED','PAID','CANCELLED')"
      if desired_enum not in column_type.lower():
        cursor.execute(
          "ALTER TABLE orders MODIFY COLUMN status ENUM('PENDING','COMPLETED','PAID','CANCELLED') NOT NULL DEFAULT 'PENDING'"
        )
        altered = True

    cursor.execute("SHOW COLUMNS FROM orders LIKE 'paid_at'")
    has_paid_at = cursor.fetchone()
    if not has_paid_at:
      cursor.execute("ALTER TABLE orders ADD COLUMN paid_at DATETIME NULL AFTER created_at")
      altered = True

    if altered:
      conn.commit()
  finally:
    cursor.close()
    conn.close()


def fetch_ticket_types():
  conn = get_connection()
  cursor = conn.cursor(dictionary=True)
  try:
    cursor.execute(
      "SELECT id, name, price, description FROM ticket_types WHERE is_active = 1 ORDER BY id"
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
      SELECT o.id, o.order_sn, o.status, o.total_amount, o.created_at, o.paid_at,
           u.identifier
      FROM orders o
      JOIN users u ON o.user_id = u.id
      ORDER BY o.created_at DESC
      """
    )
    orders = cursor.fetchall()

    cursor.execute(
      """
      SELECT od.order_id, tt.name, od.quantity, od.unit_price
      FROM order_details od
      JOIN ticket_types tt ON od.ticket_type_id = tt.id
      ORDER BY od.order_id
      """
    )
    details = cursor.fetchall()
  finally:
    cursor.close()
    conn.close()

  detail_map = {}
  for row in details:
    detail_map.setdefault(row["order_id"], []).append(row)

  for order in orders:
    order["details"] = detail_map.get(order["id"], [])

  return orders


def fetch_order_summary(order_id):
  conn = get_connection()
  cursor = conn.cursor(dictionary=True)
  try:
    cursor.execute(
      """
      SELECT id, order_sn, user_id, status, total_amount, created_at, paid_at
      FROM orders
      WHERE id = %s
      """,
      (order_id,),
    )
    order = cursor.fetchone()
    if not order:
      return None

    cursor.execute(
      """
      SELECT od.ticket_type_id, tt.name, od.quantity, od.unit_price
      FROM order_details od
      JOIN ticket_types tt ON od.ticket_type_id = tt.id
      WHERE od.order_id = %s
      ORDER BY tt.id
      """,
      (order_id,),
    )
    order["details"] = cursor.fetchall()
    return order
  finally:
    cursor.close()
    conn.close()


def fetch_users():
  conn = get_connection()
  cursor = conn.cursor(dictionary=True)
  try:
    cursor.execute(
      "SELECT id, identifier, user_type, created_at FROM users ORDER BY created_at DESC"
    )
    return cursor.fetchall()
  finally:
    cursor.close()
    conn.close()


def get_user_by_identifier(identifier):
  conn = get_connection()
  cursor = conn.cursor(dictionary=True)
  try:
    query = "SELECT id, identifier, password, user_type FROM users WHERE identifier = %s"
    cursor.execute(query, (identifier,))
    return cursor.fetchone()
  finally:
    cursor.close()
    conn.close()


def get_ticket_type(ticket_type_id):
  conn = get_connection()
  cursor = conn.cursor(dictionary=True)
  try:
    cursor.execute(
      "SELECT id, name, price FROM ticket_types WHERE id = %s",
      (ticket_type_id,),
    )
    return cursor.fetchone()
  finally:
    cursor.close()
    conn.close()


def update_order_status(order_id, status):
  conn = get_connection()
  cursor = conn.cursor()
  try:
    cursor.execute(
      "UPDATE orders SET status = %s WHERE id = %s",
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
      "UPDATE orders SET status = %s, paid_at = NOW() WHERE id = %s",
      ("PAID", order_id),
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
    cursor.execute("DELETE FROM order_details WHERE order_id = %s", (order_id,))
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


ADMIN_TEMPLATE = """
<!doctype html>
<html lang=\"zh\">
  <head>
    <meta charset=\"utf-8\">
    <title>管理后台 - QUIE野区大花园</title>
    <style>
      :root {
        color-scheme: dark;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at left top, #2b205c 0%, #0c1324 55%, #04060c 100%);
        color: #e6edf6;
      }
      .wrapper {
        min-height: 100vh;
        padding: 48px 40px 64px;
        display: flex;
        flex-direction: column;
        gap: 32px;
      }
      .header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 16px;
        color: #94a3b8;
      }
      .header a {
        color: #60a5fa;
        text-decoration: none;
      }
      .header a:hover {
        text-decoration: underline;
      }
      h1 {
        margin: 0;
        font-size: 34px;
        color: #f8fafc;
      }
      .grid {
        display: grid;
        gap: 28px;
      }
      .card {
        padding: 36px;
        border-radius: 26px;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.16);
        box-shadow: 0 34px 130px rgba(15, 23, 42, 0.76);
        backdrop-filter: blur(20px);
      }
      h2 {
        margin: 0 0 20px;
        font-size: 20px;
        letter-spacing: 0.01em;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(10, 14, 23, 0.55);
      }
      th,
      td {
        padding: 14px 18px;
        text-align: left;
        font-size: 14px;
      }
      th {
        background: rgba(96, 165, 250, 0.12);
        color: #cbd5f5;
        font-weight: 600;
      }
      tr + tr td {
        border-top: 1px solid rgba(148, 163, 184, 0.1);
      }
      select,
      input[type=\"text\"] {
        padding: 8px 12px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: rgba(15, 23, 42, 0.65);
        color: inherit;
        font-size: 13px;
      }
      select:focus,
      input[type=\"text\"]:focus {
        outline: none;
        border-color: rgba(96, 165, 250, 0.65);
        box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.22);
      }
      button {
        padding: 8px 14px;
        border-radius: 10px;
        border: none;
        font-size: 13px;
        font-weight: 600;
        color: #0b1220;
        background: linear-gradient(135deg, #38bdf8 0%, #6366f1 45%, #a855f7 100%);
        cursor: pointer;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
      }
      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 16px 55px rgba(99, 102, 241, 0.35);
      }
      form.inline {
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }
      .message {
        margin-bottom: 24px;
        padding: 14px 16px;
        border-radius: 14px;
        font-size: 14px;
      }
      .message.success {
        background: rgba(34, 197, 94, 0.14);
        border: 1px solid rgba(34, 197, 94, 0.28);
        color: #bbf7d0;
      }
      .message.error {
        background: rgba(239, 68, 68, 0.14);
        border: 1px solid rgba(239, 68, 68, 0.28);
        color: #fca5a5;
      }
      .message.info {
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(59, 130, 246, 0.22);
        color: #bfdbfe;
      }
      ul {
        margin: 0;
        padding-left: 18px;
      }
      li {
        margin-bottom: 4px;
      }
      @media (max-width: 820px) {
        .wrapper {
          padding: 32px 20px 48px;
        }
        table {
          font-size: 13px;
        }
        th,
        td {
          padding: 12px 14px;
        }
        form.inline {
          flex-direction: column;
          align-items: flex-start;
        }
      }
    </style>
  </head>
  <body>
    <div class=\"wrapper\">
      <div class=\"header\">
        <h1>订单管理</h1>
        <a href=\"{{ url_for('login') }}\">返回登录</a>
      </div>
      <div class=\"grid\">
        <div class=\"card\">
          <h2>用户管理</h2>
          {% if message %}
          <div class=\"message {{ message_type }}\">{{ message }}</div>
          {% endif %}
          <table>
            <thead>
              <tr>
                <th>用户 ID</th>
                <th>手机号</th>
                <th>当前类型</th>
                <th>注册时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {% for user in users %}
              <tr>
                <td>{{ user.id }}</td>
                <td>{{ user.identifier }}</td>
                <td>{{ user.user_type }}</td>
                <td>{{ user.created_at }}</td>
                <td>
                  <form method=\"post\" class=\"inline\">
                    <input type=\"hidden\" name=\"action\" value=\"update_user_type\">
                    <input type=\"hidden\" name=\"user_id\" value=\"{{ user.id }}\">
                    <select name=\"user_type\">
                      <option value=\"REGULAR\" {% if user.user_type == 'REGULAR' %}selected{% endif %}>REGULAR</option>
                      <option value=\"QUIE_STUDENT\" {% if user.user_type == 'QUIE_STUDENT' %}selected{% endif %}>QUIE_STUDENT</option>
                    </select>
                    <button type=\"submit\">更新</button>
                  </form>
                  <form method=\"post\" class=\"inline\" onsubmit=\"return confirm('确认删除该用户？');\">
                    <input type=\"hidden\" name=\"action\" value=\"delete_user\">
                    <input type=\"hidden\" name=\"user_id\" value=\"{{ user.id }}\">
                    <button type=\"submit\">删除</button>
                  </form>
                </td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        <div class=\"card\">
          <h2>订单列表</h2>
          <table>
            <thead>
              <tr>
                <th>订单 ID</th>
                <th>订单编号</th>
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
                <td>{{ order.order_sn }}</td>
                <td>{{ order.identifier }}</td>
                <td>{{ order.status }}</td>
                <td>￥{{ order.total_amount }}</td>
                <td>{{ order.created_at }}</td>
                <td>{{ order.paid_at or '' }}</td>
                <td>
                  {% if order.details %}
                  <ul>
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
      </div>
    </div>
  </body>
</html>
"""
 
def create_user(identifier, password, user_type="REGULAR"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_type, identifier, password) VALUES (%s, %s, %s)",
            (user_type, identifier, password),
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
    order_sn = uuid.uuid4().hex[:16]
    cursor.execute(
      "INSERT INTO orders (order_sn, user_id, status, total_amount) VALUES (%s, %s, %s, %s)",
      (order_sn, user_id, status, str(total_amount)),
    )
    order_id = cursor.lastrowid

    detail_sql = (
      "INSERT INTO order_details (order_id, ticket_type_id, quantity, unit_price) "
      "VALUES (%s, %s, %s, %s)"
    )
    for item in selections:
      cursor.execute(
        detail_sql,
        (order_id, item["ticket_type_id"], item["quantity"], str(item["unit_price"])),
      )

    conn.commit()
    return order_id, order_sn
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


ensure_password_column()
ensure_order_status_columns()


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        is_student = request.form.get("is_quie_student") == "on"
        student_id = request.form.get("student_id", "").strip()
        student_name = request.form.get("student_name", "").strip()

        context = {
            "identifier": identifier,
            "is_student": is_student,
            "student_id": student_id,
            "student_name": student_name,
        }

        if not identifier or not password:
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

        if get_user_by_identifier(identifier):
            return render_template_string(
                SIGNUP_TEMPLATE,
                error="该手机号已注册",
                **context,
            )

        user_type = "QUIE_STUDENT" if is_student else "REGULAR"
        create_user(identifier, password, user_type=user_type)
        return redirect(url_for("login"))

    return render_template_string(SIGNUP_TEMPLATE)


@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_identifier(identifier)
        if user and user["password"] == password:
            session["user_id"] = user["id"]
            session["identifier"] = user["identifier"]
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
            if ticket["name"] != "QUIE本校学生票"
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

        order_id, _order_sn = create_order(
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
    order_sn=order_record["order_sn"],
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
                            _order_id, _order_sn = create_order(
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

    return render_template_string(
        ADMIN_TEMPLATE,
        orders=orders,
        users=users,
        ticket_types=ticket_types,
        status_options=status_options,
        message=message,
        message_type=message_type,
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
    <title>登录 - QUIE野区大花园</title>
    <style>
      :root {
        color-scheme: dark;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at top, #20194d 0%, #0b1220 55%, #05060b 100%);
        color: #e6edf6;
      }
      .wrapper {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        padding: 32px;
      }
      .card {
        width: min(420px, 100%);
        padding: 36px;
        border-radius: 24px;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 32px 120px rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(22px);
      }
      h1 {
        margin: 0 0 16px;
        font-size: 28px;
        letter-spacing: 0.02em;
      }
      .subhead {
        margin: 0 0 32px;
        color: #94a3b8;
        font-size: 15px;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 20px;
      }
      label {
        font-size: 14px;
        color: #cbd5f5;
      }
      input[type="text"],
      input[type="password"] {
        width: 100%;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background-color: rgba(15, 23, 42, 0.65);
        color: inherit;
        transition: border 0.15s ease, box-shadow 0.15s ease;
      }
      input[type="text"]:focus,
      input[type="password"]:focus {
        outline: none;
        border-color: rgba(99, 102, 241, 0.7);
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
      }
      button {
        width: 100%;
        padding: 12px 16px;
        border: none;
        border-radius: 14px;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: 0.01em;
        color: #0b1220;
        background: linear-gradient(135deg, #7dd3fc 0%, #60a5fa 45%, #a855f7 100%);
        cursor: pointer;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
      }
      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 18px 50px rgba(96, 165, 250, 0.35);
      }
      .alert {
        margin-bottom: 20px;
        padding: 12px 14px;
        border-radius: 12px;
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
        font-size: 14px;
      }
      .meta {
        margin-top: 28px;
        font-size: 14px;
        color: #94a3b8;
        text-align: center;
      }
      a {
        color: #60a5fa;
        text-decoration: none;
      }
      a:hover {
        text-decoration: underline;
      }
    </style>
  </head>
  <body>
    <div class=\"wrapper\">
      <div class=\"card\">
        <h1>QUIE野区大花园</h1>
        <p class=\"subhead\">登录以继续管理和购买活动门票</p>
        {% if error %}
        <div class=\"alert\">{{ error }}</div>
        {% endif %}
        <form method=\"post\">
          <div class=\"field\">
            <label for=\"identifier\">手机号</label>
            <input type=\"text\" id=\"identifier\" name=\"identifier\" required>
          </div>
          <div class=\"field\">
            <label for=\"password\">密码</label>
            <input type=\"password\" id=\"password\" name=\"password\" required>
          </div>
          <button type=\"submit\">立即登录</button>
        </form>
        <p class=\"meta\">还没有账号？<a href=\"{{ url_for('signup') }}\">马上注册</a></p>
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
    <title>注册 - QUIE野区大花园</title>
    <style>
      :root {
        color-scheme: dark;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at 20% -20%, #2f265f 0%, #11152b 55%, #06070d 100%);
        color: #e6edf6;
      }
      .wrapper {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        padding: 32px;
      }
      .card {
        width: min(520px, 100%);
        padding: 40px;
        border-radius: 26px;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 32px 120px rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(22px);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 30px;
        letter-spacing: 0.02em;
      }
      .subhead {
        margin: 0 0 32px;
        color: #94a3b8;
        font-size: 15px;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 20px;
      }
      label {
        font-size: 14px;
        color: #cbd5f5;
      }
      input[type="text"],
      input[type="password"] {
        width: 100%;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background-color: rgba(15, 23, 42, 0.65);
        color: inherit;
        transition: border 0.15s ease, box-shadow 0.15s ease;
      }
      input[type="text"]:focus,
      input[type="password"]:focus {
        outline: none;
        border-color: rgba(99, 102, 241, 0.7);
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
      }
      .checkbox {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 20px;
        font-size: 14px;
        color: #cbd5f5;
      }
      input[type="checkbox"] {
        width: 18px;
        height: 18px;
        accent-color: #818cf8;
      }
      .student-fields {
        margin-bottom: 24px;
        padding: 18px;
        border-radius: 16px;
        background: rgba(99, 102, 241, 0.08);
        border: 1px solid rgba(99, 102, 241, 0.25);
      }
      .student-fields small {
        color: #94a3b8;
      }
      button {
        width: 100%;
        padding: 12px 16px;
        border: none;
        border-radius: 14px;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: 0.01em;
        color: #0b1220;
        background: linear-gradient(135deg, #22d3ee 0%, #6366f1 40%, #a855f7 100%);
        cursor: pointer;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
      }
      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 18px 50px rgba(99, 102, 241, 0.35);
      }
      .alert {
        margin-bottom: 20px;
        padding: 12px 14px;
        border-radius: 12px;
        background: rgba(239, 68, 68, 0.13);
        border: 1px solid rgba(239, 68, 68, 0.26);
        color: #fca5a5;
        font-size: 14px;
      }
      .meta {
        margin-top: 28px;
        font-size: 14px;
        color: #94a3b8;
        text-align: center;
      }
      a {
        color: #60a5fa;
        text-decoration: none;
      }
      a:hover {
        text-decoration: underline;
      }
    </style>
  </head>
  <body>
    <div class=\"wrapper\">
      <div class=\"card\">
        <h1>创建新账号</h1>
        <p class=\"subhead\">加入 QUIE 野区大花园，探索更多精彩活动</p>
        {% if error %}
        <div class=\"alert\">{{ error }}</div>
        {% endif %}
        <form method=\"post\">
          <div class=\"field\">
            <label for=\"identifier\">手机号</label>
            <input type=\"text\" id=\"identifier\" name=\"identifier\" value=\"{{ identifier|default('') }}\" required>
          </div>
          <div class=\"field\">
            <label for=\"password\">密码</label>
            <input type=\"password\" id=\"password\" name=\"password\" required>
          </div>
          <label class=\"checkbox\">
            <input type=\"checkbox\" name=\"is_quie_student\" id=\"is_quie_student\" {{ 'checked' if is_student|default(False) else '' }}>
            我是 QUIE 本校学生
          </label>
          <div id=\"student_fields\" class=\"student-fields\" style=\"{% if not is_student|default(False) %}display: none;{% endif %}\">
            <div class=\"field\">
              <label for=\"student_name\">姓名</label>
              <input type=\"text\" id=\"student_name\" name=\"student_name\" value=\"{{ student_name|default('') }}\">
            </div>
            <div class=\"field\">
              <label for=\"student_id\">学号</label>
              <input type=\"text\" id=\"student_id\" name=\"student_id\" value=\"{{ student_id|default('') }}\">
            </div>
            <small>填写后将进入人工审核流程，系统将优先认定为本校认证。</small>
          </div>
          <button type=\"submit\">完成注册</button>
        </form>
        <p class=\"meta\">已有账号？<a href=\"{{ url_for('login') }}\">返回登录</a></p>
      </div>
    </div>
    <script>
      const studentCheckbox = document.getElementById('is_quie_student');
      const studentFields = document.getElementById('student_fields');
      if (studentCheckbox && studentFields) {
        studentCheckbox.addEventListener('change', function () {
          studentFields.style.display = this.checked ? 'block' : 'none';
        });
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
    <title>购票 - QUIE野区大花园</title>
    <style>
      :root {
        color-scheme: dark;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at right top, #2c1f59 0%, #0d1324 55%, #05070d 100%);
        color: #e6edf6;
      }
      .wrapper {
        min-height: 100vh;
        padding: 48px 32px 64px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 32px;
      }
      .nav {
        width: min(1040px, 100%);
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #94a3b8;
      }
      .card {
        width: min(1040px, 100%);
        padding: 40px;
        border-radius: 28px;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.16);
        box-shadow: 0 35px 140px rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(20px);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 32px;
      }
      .subhead {
        margin: 0 0 28px;
        color: #94a3b8;
        font-size: 15px;
      }
      .alert {
        margin-bottom: 24px;
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(239, 68, 68, 0.14);
        border: 1px solid rgba(239, 68, 68, 0.28);
        color: #fca5a5;
        font-size: 14px;
      }
      .notice {
        margin-bottom: 24px;
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(96, 165, 250, 0.25);
        color: #bfdbfe;
        font-size: 14px;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 18px;
        overflow: hidden;
        margin-bottom: 28px;
        background: rgba(10, 14, 23, 0.55);
      }
      th,
      td {
        padding: 14px 18px;
        text-align: left;
        font-size: 14px;
      }
      th {
        background: rgba(96, 165, 250, 0.12);
        color: #cbd5f5;
        font-weight: 600;
      }
      tr + tr td {
        border-top: 1px solid rgba(148, 163, 184, 0.12);
      }
      input[type="number"] {
        width: 100%;
        max-width: 120px;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.3);
        background: rgba(15, 23, 42, 0.65);
        color: inherit;
        font-size: 14px;
      }
      input[type="number"]:focus {
        outline: none;
        border-color: rgba(96, 165, 250, 0.65);
        box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.25);
      }
      button {
        width: 100%;
        padding: 14px 16px;
        border: none;
        border-radius: 16px;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: 0.01em;
        color: #0b1220;
        background: linear-gradient(135deg, #38bdf8 0%, #6366f1 45%, #a855f7 100%);
        cursor: pointer;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
      }
      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 22px 70px rgba(99, 102, 241, 0.35);
      }
      .link {
        color: #60a5fa;
        text-decoration: none;
      }
      .link:hover {
        text-decoration: underline;
      }
    </style>
  </head>
  <body>
    <div class=\"wrapper\">
      <div class=\"nav\">
        <span>当前用户：{{ session['identifier'] }}</span>
        <a class=\"link\" href=\"{{ url_for('logout') }}\">退出登录</a>
      </div>
      <div class=\"card\">
        <h1>选择票种</h1>
        {% if user_type|default('REGULAR') != 'QUIE_STUDENT' %}
        <div class=\"notice\">温馨提示：普通用户无法选择 QUIE 本校学生专属票种。</div>
        {% else %}
        <p class=\"subhead\">享受本校学生专属优惠票价。</p>
        {% endif %}
        {% if error %}
        <div class=\"alert\">{{ error }}</div>
        {% endif %}
        <form method=\"post\">
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
          <button type=\"submit\">提交订单</button>
        </form>
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
    <title>订单支付确认 - QUIE野区大花园</title>
    <style>
      :root {
        color-scheme: dark;
      }
      * {
        box-sizing: border-box;
      }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
        background: radial-gradient(circle at 80% -20%, #2d2a5f 0%, #10162a 55%, #05060d 100%);
        color: #e6edf6;
      }
      .wrapper {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 48px 32px;
      }
      .card {
        width: min(640px, 100%);
        padding: 44px;
        border-radius: 28px;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 40px 160px rgba(15, 23, 42, 0.76);
        backdrop-filter: blur(20px);
      }
      h1 {
        margin: 0 0 12px;
        font-size: 32px;
      }
      .order-sn {
        margin-bottom: 12px;
        font-size: 15px;
        color: #94a3b8;
      }
      .status {
        margin-bottom: 24px;
        font-size: 14px;
        color: #cbd5f5;
      }
      .flash {
        margin-bottom: 24px;
        padding: 14px 16px;
        border-radius: 16px;
        font-size: 14px;
      }
      .flash.info {
        background: rgba(59, 130, 246, 0.12);
        border: 1px solid rgba(96, 165, 250, 0.24);
        color: #bfdbfe;
      }
      .flash.success {
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid rgba(34, 197, 94, 0.26);
        color: #bbf7d0;
      }
      .flash.error {
        background: rgba(239, 68, 68, 0.14);
        border: 1px solid rgba(239, 68, 68, 0.28);
        color: #fca5a5;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        border-radius: 18px;
        overflow: hidden;
        background: rgba(10, 14, 23, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.16);
        margin-bottom: 28px;
      }
      th,
      td {
        padding: 14px 18px;
        text-align: left;
        font-size: 14px;
      }
      th {
        background: rgba(96, 165, 250, 0.14);
        color: #cbd5f5;
      }
      tr + tr td {
        border-top: 1px solid rgba(148, 163, 184, 0.12);
      }
      .total {
        font-size: 18px;
        font-weight: 600;
        color: #f8fafc;
        margin-bottom: 20px;
      }
      .meta {
        margin-bottom: 24px;
        font-size: 14px;
        color: #94a3b8;
      }
      .actions {
        display: flex;
        gap: 14px;
        flex-wrap: wrap;
        margin-top: 24px;
      }
      .actions form {
        flex: 1 1 200px;
      }
      .btn,
      .actions button {
        width: 100%;
        padding: 14px 16px;
        border-radius: 16px;
        text-align: center;
        font-weight: 600;
        font-size: 15px;
        letter-spacing: 0.01em;
        border: none;
        color: #0b1220;
        background: linear-gradient(135deg, #38bdf8 0%, #6366f1 45%, #a855f7 100%);
        box-shadow: 0 20px 70px rgba(99, 102, 241, 0.32);
        cursor: pointer;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }
      .btn:hover,
      .actions button:hover {
        transform: translateY(-1px);
        box-shadow: 0 24px 90px rgba(99, 102, 241, 0.4);
      }
      .btn.secondary {
        background: rgba(148, 163, 184, 0.18);
        color: #cbd5f5;
        box-shadow: none;
      }
      .btn.secondary:hover {
        background: rgba(148, 163, 184, 0.3);
      }
      .actions .secondary {
        text-decoration: none;
      }
    </style>
  </head>
  <body>
    <div class=\"wrapper\">
      <div class=\"card\">
        <h1>订单支付确认</h1>
        <div class=\"order-sn\">订单号：{{ order_sn }}</div>
        <div class=\"status\">当前状态：{{ order_status }}</div>
        {% if paid_at %}
        <div class=\"meta\">支付时间：{{ paid_at }}</div>
        {% endif %}
        {% if status_message %}
        <div class=\"flash {{ status_type|default('info') }}\">{{ status_message }}</div>
        {% endif %}
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
        <div class=\"total\">总金额：￥{{ total_amount }}</div>
        <div class=\"actions\">
          {% if not is_paid %}
          <form method=\"post\" action=\"{{ url_for('confirm_order_payment', order_id=order_id) }}\">
            <button type=\"submit\">已支付</button>
          </form>
          {% endif %}
          <a class=\"btn\" href=\"{{ url_for('order') }}\">继续购票</a>
          <a class=\"btn secondary\" href=\"{{ url_for('logout') }}\">退出登录</a>
        </div>
      </div>
    </div>
  </body>
</html>
"""




if __name__ == "__main__":
    app.run(debug=True)
