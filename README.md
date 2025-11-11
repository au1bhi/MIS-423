# MIS-423 Course Demo

This repository contains the demo application used in the MIS-423 coursework to illustrate database design concepts with a small Flask application. It is intended **solely** for instructional purposes.

## Important Notice

- The code is not hardened for security, reliability, or operational concerns.
- Configuration values (such as database credentials) are provided openly for classroom experimentation.
- **Do not deploy this project to production environments.**

## Repository Structure

```
MIS-423/
├── app.py             # Flask application with inline templates and routes
├── database.sql       # Sample MySQL schema and seed data for the exercises
├── static/
│   └── styles.css     # Shared styles used by the inline templates
├── __pycache__/       # Python bytecode cache (ignored via .gitignore)
└── README.md          # Project overview and usage notes
```

## Getting Started (Classroom Use Only)

1. Create and configure a MySQL database using the statements in `database.sql`.
2. Update `DB_CONFIG` inside `app.py` if your local database settings differ.
3. (Recommended) Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Launch the Flask development server:
   ```bash
   python app.py
   ```
5. Access the application via `http://localhost:5000` for demonstration.
6. Use the `/admin` route with an administrator account to review users, orders, and perform maintenance tasks (update user type, create orders, adjust status, mark paid, delete records).


Remember: this project supports the MIS-423 coursework and should not be repurposed for live deployments.

---

# MIS-423

本仓库是 MIS-423 课程中用于演示数据库设计的 Flask 示例应用，仅供教学参考。

## 重要提示

- 当前代码未针对安全性、稳定性或可运维性进行加固。
- 示例中包含的配置（例如数据库账号、密码）仅供课堂实验使用。
- **请勿在生产环境中部署或使用本项目。**

## 仓库结构

```
MIS-423/
├── app.py             # Flask 应用主入口，包含路由与内联模板
├── database.sql       # 课程使用的 MySQL 示例库结构与种子数据
├── static/
│   └── styles.css     # 内联模板共享的样式文件
├── __pycache__/       # Python 字节码缓存（已在 .gitignore 中忽略）
└── README.md          # 项目概述与注意事项
```

## 使用方式（仅限课堂环境）

1. 使用 `database.sql` 创建并初始化 MySQL 数据库。
2. 如果本地数据库配置不同，请在 `app.py` 中调整 `DB_CONFIG`。
3. 建议创建虚拟环境并安装依赖：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. 在命令行运行：
   ```bash
   python app.py
   ```
5. 在浏览器访问 `http://localhost:5000` 测试示例功能。
6. 管理后台位于 `/admin`，可在此查看用户、订单并执行更新、创建、标记支付或删除等操作。


请注意：本项目仅为 MIS-423 课程教学示例，不建议用于任何真实生产场景。
