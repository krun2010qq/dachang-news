# 大场镇新闻汇总

聚合上海市宝山区大场镇相关新闻，参考 Polymarket 深色卡片风格展示。每日 **08:00** 与 **14:00**（上海时区）自动抓取更新。

## 功能

- 多平台汇总：Google 新闻、Bing 新闻（RSS 源，稳定不阻塞）
- 平台筛选、关键词搜索
- 手动刷新接口
- 独立部署在 **8080** 端口，不影响 80 端口现有网站

## 本地运行

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8081
```

浏览器访问 `http://127.0.0.1:8081/`。

## 部署

```bash
# 首次部署
set DEPLOY_PASSWORD=your_password
python deploy_remote.py

# 代码更新
python remote_update.py
```

生产地址：

- 主地址（8080 端口）：`http://49.51.195.205:8080/`
- 备用地址（80 端口，不影响原有网站）：`http://49.51.195.205/dachang/`

若 8080 外网无法访问，请在腾讯云安全组中放行 TCP 8080。

## API

- `GET /api/health` — 健康检查
- `GET /api/news` — 新闻列表（支持 `platform`、`category`、`q`）
- `GET /api/stats` — 统计信息
- `POST /api/refresh` — 手动触发抓取
