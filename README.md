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
- 将特殊读法保存为“上下文规则”，以后优先使用。例如 `白い家` 中把 `家` 保存为 `うち`。
- SQLite 保存读音规则和历史项目。
- 标题、作者/歌手、年份元数据。
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

---

# 2. 本地开发

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

1. 填写标题，例如 `Light Dance (ライトダンス)`。
2. 填写歌手/作者、年份，可留空。
3. 左侧粘贴日文歌词或文章。
4. 点击 **自动标注**。
5. 右侧检查振假名。
6. 点击某个带振假名的汉字/汉字词，可以修改读音。
7. 对歌词特殊读法，可以点击 **保存为该句读音规则**。
8. 点击 **下载 PNG** 可把当前成品页保存为图片。
9. 点击 **打印** 可打开浏览器打印窗口；打印样式只保留成品内容。
10. 点击 **导出 Word** 可生成原生 Word Ruby 的 `.docx`。

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
