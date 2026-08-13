# Furigana Studio

一个可自建的日文振假名 Web 工具：**输入日文 → 自动识别读音 → 只给汉字加平假名 → 人工校正 → 成品页预览 → 下载 PNG / A4 打印 / 导出带原生 Word Ruby 的 DOCX**。

这个项目对应的就是“歌词/文章中只标汉字，并把平假名放在汉字正上方”的工作流。它不是把读音另起一行模拟出来，而是：

- 浏览器端使用 HTML `<ruby><rt>`；
- Word 端写入 WordprocessingML `w:ruby / w:rt / w:rubyBase`；
- 所以导出的 `.docx` 在 Microsoft Word 中仍然是真正的“拼音指南 / 振假名”。

## 功能

- 日文文本批量标注。
- 只给汉字部分加振假名，不重复标已有平假名/片假名。
- 送假名对齐，例如：
  - `白い / シロイ` → `白(しろ) + い`
  - `握り / ニギリ` → `握(にぎ) + り`
  - `明日 / アシタ` → `明日(あした)`
- 浏览器实时 `<ruby>` 成品页预览，包含标题、作者/歌手、年份。
- 一键下载高分辨率 PNG 图片，图片内容与成品页一致。
- 一键调用浏览器打印，自动隐藏编辑器与操作按钮，按 A4 页面排版。
- 点击某个振假名手工修改。
- 将特殊读法保存为当前句、当前项目或全局规则，保存后立即同步预览。
- 查看、直接编辑、删除以及 JSON 导入/导出读音规则。
- 对多音词显示 Sudachi 词典候选和可信度提示，例如 `明日` 可选择 `あす / あした / みょうにち`。
- 振假名编辑支持撤销、重做和常用键盘快捷键。
- SQLite 保存读音规则和历史项目。
- 项目支持覆盖更新、重命名和浏览器自动草稿恢复。
- 输入歌曲名和歌手后可从 LRCLIB 搜索、预览并导入歌词；同时提供 Google 备用搜索并保留手工粘贴。
- 标题、作者/歌手、年份元数据。
- 可调整字号、行距、振假名大小、页边距、字体以及横排/竖排；横排支持单栏/双栏，竖排在页面内从右向左排列，排满后向下换组，并可调整上下两组之间的间距。通用设置同步用于预览、PNG、打印和 Word；竖排组间距用于网页预览、PNG 和浏览器打印，Word 使用自身的竖排分页。
- 可选择中文或英文逐句译文，支持手工编辑；配置 OpenAI API Key 后可自动翻译空白行或重新翻译全部。
- 导出 `.docx`，正文为原生 Word Ruby。
- Docker Compose 一键启动。

---

## 技术栈

### Web

- Next.js
- React
- TypeScript
- 原生 CSS
- HTML `<ruby>` / `<rt>`
- `html-to-image`（将成品页导出为 PNG）
- CSS `@media print` / `@page`（A4 打印）

### API

- FastAPI
- SudachiPy
- `sudachidict_core`
- 自定义 Kanji/Kana reading aligner
- `python-docx` + OOXML
- SQLite

整体结构：

```text
furigana-web/
├── api/
│   ├── app/
│   │   ├── analyzer/
│   │   │   ├── aligner.py
│   │   │   └── sudachi.py
│   │   ├── exporters/
│   │   │   └── docx.py
│   │   ├── db.py
│   │   ├── main.py
│   │   └── models.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── web/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── Dockerfile
│   └── package.json
├── data/
├── docker-compose.yml
├── Makefile
└── README.md
```

---

# 1. 最快启动：Docker Compose

前提：安装 Docker Desktop，或 Linux 上安装 Docker Engine + Compose Plugin。

在项目根目录运行：

```bash
docker compose up --build
```

也可以使用系统启动脚本，它会自动创建 `.env`、等待服务就绪并打开浏览器：

Windows PowerShell：

```powershell
.\scripts\start-windows.ps1
```

macOS（终端运行或双击 Finder 中的文件）：

```bash
./scripts/start-macos.command
```

启动后：

```text
Web: http://localhost:3000
API: http://localhost:8000
API Swagger: http://localhost:8000/docs
```

停止：

```bash
docker compose down
```

数据库保存在：

```text
./data/furigana.sqlite3
```

因此重建 Docker 容器不会丢掉你的历史读音规则和项目。

### 使用 Release 镜像

每个 `v*` Git 标签都会在 GitHub Actions 校验通过后自动创建同名 Release，并发布 API、Web 两个 GHCR 镜像。Release 页面会附带 Windows ZIP、macOS TAR、`docker-compose.release.yml` 和 `SHA256SUMS.txt`；解压对应平台的压缩包后可直接运行其中的启动脚本。

也可以只下载 Compose 文件并启动最新版本：

```bash
docker compose -f docker-compose.release.yml up -d
```

要固定到某个版本（例如 `v1.3.0`）：

macOS / Linux：

```bash
FURIGANA_VERSION=v1.3.0 docker compose -f docker-compose.release.yml up -d
```

Windows PowerShell：

```powershell
$env:FURIGANA_VERSION="v1.3.0"
docker compose -f docker-compose.release.yml up -d
```

维护者创建发布版本：

```bash
git tag -a v1.3.0 -m "v1.3.0"
git push origin v1.3.0
```

流水线会依次运行后端测试、前端类型检查和生产构建；全部成功后发布容器镜像并生成 GitHub Release。

---

# 2. 本地开发

Docker Compose 使用构建后的镜像，源码修改后通常需要重新运行 `docker compose up --build` 才会生效。需要边修改边预览时，推荐使用开发启动脚本：

Windows PowerShell：

```powershell
.\scripts\dev-windows.ps1
```

macOS（终端运行或双击 Finder 中的文件）：

```bash
chmod +x scripts/dev-macos.command
./scripts/dev-macos.command
```

脚本会首次创建 `api/.venv`、检查依赖并同时启动前后端。前端支持热更新，后端使用 Uvicorn 自动重载。脚本优先使用 Web 端口 3000 和 API 端口 8000；端口被 Docker 或其他程序占用时会自动向后寻找可用端口，并同步配置前端 API 地址和后端 CORS。Windows 会打开两个服务窗口，关闭它们即可停止；macOS 在启动终端按 `Ctrl+C` 即可同时停止。

以下是等效的手动启动步骤：

## 后端

建议 Python 3.12。

```bash
cd api
python -m venv .venv
```

macOS / Linux：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

安装：

```bash
pip install -r requirements-dev.txt
```

设置数据库路径。如果不设置，默认使用 `/data/furigana.sqlite3`，所以本地开发建议显式指定：

macOS / Linux：

```bash
export DB_PATH=../data/furigana.sqlite3
export CORS_ORIGINS=http://localhost:3000
```

Windows PowerShell：

```powershell
$env:DB_PATH="../data/furigana.sqlite3"
$env:CORS_ORIGINS="http://localhost:3000"
```

启动：

```bash
uvicorn app.main:app --reload --port 8000
```

## 前端

另开一个终端：

```bash
cd web
npm install
```

默认 API 地址就是：

```text
http://localhost:8000
```

所以通常直接：

```bash
npm run dev
```

打开：

```text
http://localhost:3000
```

如果 API 在其他地址：

```bash
NEXT_PUBLIC_API_BASE_URL=https://your-api.example.com npm run dev
```

注意：`NEXT_PUBLIC_*` 会进入浏览器 bundle，生产部署时应在 **build 阶段** 配好正确 API 地址。

---

# 3. 使用方式

1. 在 **获取歌词** 中输入歌曲名和可选歌手名，从 LRCLIB 候选中预览并导入；也可以使用 Google 备用搜索后手工粘贴。
2. 导入结果会自动填写标题和歌手；也可以自行填写标题、歌手/作者与年份。
3. 如果不使用歌词搜索，直接在左侧粘贴日文歌词或文章。
4. 点击 **自动标注**。
5. 右侧检查振假名。
6. 点击某个带振假名的汉字/汉字词，可以修改读音或选择词典候选。
7. 对歌词特殊读法，可保存为 **当前句 / 当前项目 / 全局** 规则。
8. 顶部 **读音规则** 可编辑、删除或导入/导出规则，**排版设置** 可调整成品样式。
9. 在 **逐句翻译** 中选择中文或英文，可手工编辑译文；配置 OpenAI 后可自动生成。
10. 点击 **下载 PNG** 可把当前成品页保存为图片。
11. 点击 **打印** 可打开浏览器打印窗口；打印样式只保留成品内容。
12. 点击 **导出 Word** 可生成原生 Word Ruby 的 `.docx`，并包含已启用的译文。

## 自动翻译配置

自动翻译是可选功能，API Key 只由后端读取，不会发送到浏览器。复制 `.env.example` 为 `.env`，填写：

```dotenv
OPENAI_API_KEY=你的_API_Key
OPENAI_TRANSLATION_MODEL=gpt-5.6-terra
```

然后重新启动服务。没有 API Key 时，中文/英文译文仍可逐句手工填写、保存和导出。

自动翻译采用模块化引擎，可在界面中选择所有已配置的服务。除 OpenAI 外，也可以在 `.env` 中配置任意一组：

```dotenv
# Azure Translator
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_REGION=

# 自部署 LibreTranslate，例如 http://localhost:5000
LIBRETRANSLATE_URL=
LIBRETRANSLATE_API_KEY=

# 百度翻译开放平台
BAIDU_TRANSLATE_APP_ID=
BAIDU_TRANSLATE_SECRET=

# 有道智云
YOUDAO_TRANSLATE_APP_KEY=
YOUDAO_TRANSLATE_SECRET=

# Google Cloud Translation Basic API Key
GOOGLE_TRANSLATE_API_KEY=

# DeepL API Free；Pro 用户可同时覆盖 DEEPL_API_URL
DEEPL_API_KEY=
```

密钥仅由 API 服务读取。翻译状态接口只向浏览器返回引擎名称和是否已配置，不会返回密钥内容。

导出的 Word 里没有“汉字上方振假名”之类说明行；标题后直接进入正文。

---

# 4. PNG 图片与打印

右侧预览不是普通文本框，而是一张独立的 `documentSheet` 成品页。标题、作者/歌手、年份和振假名正文都在这张页面里，因此三种输出共享同一份人工校正后的 Ruby AST。

## 下载 PNG

前端使用 `html-to-image` 的 `toPng()` 对成品页 DOM 做浏览器端截图：

```ts
const { toPng } = await import("html-to-image");
const dataUrl = await toPng(documentSheet, {
  pixelRatio: 2,
  backgroundColor: "#ffffff",
});
```

默认 `pixelRatio: 2`，适合分享、手机查看和普通打印。图片生成完全在浏览器完成，不需要把歌词再次上传到额外的图片服务。

如果歌词很长，PNG 会是一张纵向长图；需要严格分页时建议直接使用“打印”或 Word 导出。

## A4 打印

打印按钮直接调用：

```ts
window.print();
```

同时 `globals.css` 提供专用打印样式：

```css
@page {
  size: A4;
  margin: 16mm 17mm;
}

@media print {
  /* 隐藏输入区、按钮、历史项目、编辑浮层等 */
}
```

浏览器进入打印模式后：

- 只显示右侧成品内容；
- 去掉网页卡片边框、阴影和滚动区域；
- 标题与正文自动分页；
- Ruby 仍使用浏览器原生 `<ruby><rt>` 排版；
- 可以选择实体打印机，也可以在浏览器里“另存为 PDF”。

> 浏览器打印结果会受到操作系统字体和浏览器打印引擎影响。Chrome / Edge 通常效果最好。

---

# 5. 为什么要有自定义 Aligner

Sudachi 会告诉我们词语的 reading，例如：

```text
surface: 白い
reading: シロイ
```

但我们的产品要求不是给整个 `白い` 标 `しろい`，而是只给汉字：

```text
白 -> しろ
い -> 无 ruby
```

`api/app/analyzer/aligner.py` 会：

1. 把 surface 分成连续的汉字、假名、其他字符组；
2. 把原 surface 已有的假名当作 reading 的固定锚点；
3. 汉字组捕获锚点之间的读音；
4. 输出结构化 Segment。

例如：

```json
[
  {"text": "白", "ruby": "しろ"},
  {"text": "い", "ruby": null}
]
```

再比如：

```text
お茶 / オチャ
```

会得到：

```json
[
  {"text": "お", "ruby": null},
  {"text": "茶", "ruby": "ちゃ"}
]
```

如果遇到非常规词形且无法可靠对齐，代码采用保守策略，不会随便给多个汉字组编造读音。

---

# 6. 特殊读法 / 歌词读法

歌词、姓名、地名、当て字等无法完全依赖词典。

系统提供：

```text
surface + context -> reading
```

例如：

```text
surface = 家
context = 坂の上 白い家
reading = うち
```

再次标注包含该完整上下文的行时，会优先使用 `うち`，而不是 Sudachi 的默认结果。

SQLite 表：

```sql
ruby_overrides(
    id,
    surface,
    context,
    reading,
    created_at
)
```

相同 `surface + context` 再次保存时会覆盖 reading。

如果 `context` 为空，就相当于全局规则。

当前 UI 默认保存为“该句上下文规则”，防止你对一个歌词特殊读法的修改污染所有文章。

---

# 7. 数据结构

前后端的核心不是 HTML，而是 Ruby AST：

```json
{
  "source": "でも明日が見えなくて",
  "segments": [
    {"text": "でも", "ruby": null},
    {"text": "明日", "ruby": "あした"},
    {"text": "が", "ruby": null},
    {"text": "見", "ruby": "み"},
    {"text": "えなくて", "ruby": null}
  ]
}
```

这样有一个重要好处：

> 浏览器里人工校正后的结果，就是 PNG、打印页和 DOCX 导出使用的结果。

PNG 和打印直接读取当前浏览器成品页；DOCX 导出时后端也不会重新跑一次 Sudachi，因此不会发生“网页里已经把 `家` 改成 `うち`，导出时又变回 `いえ`”的问题。

---

# 8. API

## 自动标注

```http
POST /api/annotate
Content-Type: application/json
```

```json
{
  "text": "でも明日が見えなくて"
}
```

返回：

```json
{
  "lines": [
    {
      "source": "でも明日が見えなくて",
      "segments": [
        {"text": "でも", "ruby": null},
        {"text": "明日", "ruby": "あした"},
        {"text": "が", "ruby": null},
        {"text": "見", "ruby": "み"},
        {"text": "えなくて", "ruby": null}
      ]
    }
  ]
}
```

## 导出 DOCX

```http
POST /api/export/docx
```

```json
{
  "meta": {
    "title": "Light Dance (ライトダンス)",
    "artist": "Sakanaction",
    "year": "2009"
  },
  "lines": [
    {
      "source": "でも明日が見えなくて",
      "segments": [
        {"text": "でも"},
        {"text": "明日", "ruby": "あした"},
        {"text": "が"},
        {"text": "見", "ruby": "み"},
        {"text": "えなくて"}
      ]
    }
  ]
}
```

响应为 `.docx`。

## 保存读音规则

```http
POST /api/overrides
```

```json
{
  "surface": "家",
  "reading": "うち",
  "context": "坂の上 白い家"
}
```

其他 API 可以直接查看：

```text
http://localhost:8000/docs
```

---

# 9. Word Ruby 实现

`python-docx` 负责创建普通段落、标题、字体、页边距。

振假名部分直接插入 OOXML：

```xml
<w:ruby>
  <w:rubyPr>...</w:rubyPr>
  <w:rt>
    <w:r>あした</w:r>
  </w:rt>
  <w:rubyBase>
    <w:r>明日</w:r>
  </w:rubyBase>
</w:ruby>
```

对应实现：

```text
api/app/exporters/docx.py
```

这样 Word 会把 `あした` 当作 `明日` 的 phonetic guide，而不是普通文本。

如果要调整 Word 显示尺寸，可以修改：

```python
hps.set(..., "16")          # Ruby 8pt
hps_base.set(..., "24")     # Base 12pt
```

OOXML 使用 half-point，所以 16 = 8pt，24 = 12pt。

---

# 10. 测试

安装开发依赖后：

```bash
cd api
pytest -q
```

当前测试覆盖：

- `白い` 送假名对齐；
- `握り` 送假名对齐；
- `明日` 复合汉字；
- `お茶` 前置假名；
- 纯假名不标 Ruby；
- 生成的 DOCX XML 中实际存在 `w:ruby / w:rt / w:rubyBase`。

---

# 11. 生产部署建议

## 最简单

一台 Linux VPS：

```text
Nginx / Caddy
      ↓
Next.js :3000
FastAPI :8000
SQLite volume
```

个人自用、低并发场景 SQLite 足够。

如果未来多人使用：

- SQLite → PostgreSQL；
- 加登录；
- 每个用户自己的 overrides；
- Word 模板存储；
- 项目版本历史；
- Nginx/Caddy HTTPS；
- 队列化大批量文档导出。

## API 地址

如果部署在：

```text
https://furigana.example.com
```

而 API 是：

```text
https://api.furigana.example.com
```

Web build 时设置：

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.furigana.example.com npm run build
```

FastAPI：

```bash
CORS_ORIGINS=https://furigana.example.com
```

多个 Origin 用逗号：

```bash
CORS_ORIGINS=https://a.example.com,https://b.example.com
```

## 完整部署到 Vercel

仓库支持同时保留两种后端：

- 原有 `app.main:app`：Docker/VPS + SQLite，本地模式默认不要求登录；
- `api/index.py`：Vercel FastAPI Function + Supabase Auth/Data API，要求登录并按用户隔离数据。

两种入口由同一个 `create_app(database)` 应用工厂创建，共享路由、Sudachi、翻译和 DOCX 代码，不需要维护两套业务实现。

### 1. 创建 Supabase 项目

在 Supabase 中创建项目并启用 Email 登录。记录：

- Project URL；
- Publishable/anon key（只能用于浏览器的公开 Key）；
- Secret key（只用于 Vercel API 的敏感环境变量）。

不要把 Supabase `service_role` Key 设置为任何 `NEXT_PUBLIC_*` 环境变量。

### 2. 创建 Vercel API 项目

从本仓库创建项目，Root Directory 选择 `api`。配置：

```env
AUTH_REQUIRED=true
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
CORS_ORIGINS=https://your-web.vercel.app
```

如果 Supabase 项目仍使用 Legacy HS256 JWT，可额外设置仅后端可见的：

```env
SUPABASE_JWT_SECRET=...
```

使用 Preview Deployment 时，可以把明确的预览域名加入 `CORS_ORIGINS`；也可以谨慎设置：

```env
CORS_ORIGIN_REGEX=https://.*\.vercel\.app
```

部署前执行 `api/migrations/001_initial.sql`，创建 `app_users`、`projects` 和 `ruby_overrides` 并启用 RLS。Vercel Function 不在冷启动时执行 DDL。

### 3. 创建 Vercel Web 项目

再次从同一仓库创建项目，Root Directory 选择 `web`。配置：

```env
NEXT_PUBLIC_API_BASE_URL=https://your-api.vercel.app
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-publishable-or-anon-key
```

部署后，页面会显示注册/登录界面。FastAPI 会验证 Supabase access token，并同步最小用户资料到 `app_users`。项目、句级/项目级/全局读音规则都带 `user_id`；这里的“全局”只代表该用户的所有项目，不会影响其他账户。

### 4. 导入原有 SQLite 数据（可选）

先在 Supabase Authentication 用户列表中取得目标用户 UUID，然后在 `api` 目录运行：

```bash
DATABASE_URL='postgresql://...' python scripts/migrate_sqlite_to_postgres.py \
  ../data/furigana.sqlite3 --user-id '用户 UUID' --email 'user@example.com'
```

迁移脚本会导入历史项目和读音规则，并把旧项目规则关联到新项目 ID。建议向空数据库导入，并在操作前备份 SQLite 文件。

### 身份与接口边界

- `/health` 和 `/api/auth/config` 可匿名访问；
- 标注、歌词搜索、翻译、DOCX、项目和规则接口在云端模式全部要求 Bearer Token；
- 本地模式 `AUTH_REQUIRED=false` 时使用 `LOCAL_USER_ID=local`，保持原有无需登录的使用方式；
- 浏览器草稿也按用户 ID 分开保存，切换账户不会共用草稿。

---

# 12. 当前实现边界

日语读音不是纯机械转换，所以仍存在这些情况：

- 歌词特殊唱法；
- 人名、地名；
- 当て字；
- 作者故意改变读音；
- 字典没有的新词；
- 很复杂的汉字/假名混写 token。

因此正确产品逻辑应该是：

```text
自动分析 90%+
      ↓
人工快速校正
      ↓
把校正记成规则
      ↓
以后越来越准
```

而不是追求一个永远不需要人工审核的“100% 自动注音器”。

---

# 13. 下一步可以扩展什么

比较值得做的功能：

- 导入 `.txt` / `.md` / `.docx`；
- Ruby 字号/位置设置；
- 不同 Word 模板；
- 按词 / 按单字振假名切换；
- Jisho / JMdict 辅助候选读音；
- 用户自定义词典导入导出；
- 一键导出 HTML；
- 项目编辑版本历史；
- 日语罗马音显示模式；
- OAuth 登录与多用户隔离。

如果只是自己使用，这个仓库当前版本已经覆盖主流程，不需要先引入富文本编辑器、Redis、PostgreSQL 或 Kubernetes。

---

## License

代码可按你自己的项目需要修改和部署。第三方依赖分别遵循其各自许可证。
