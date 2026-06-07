# -*- coding: utf-8 -*-
"""
练字字帖 Web 前端 - 完整版
从原脚本导入示例数据，支持页数预校验（超过30页警告），显示作者信息
作者：hongge  shenjitask@163.com
"""
import os
import sys
import tempfile
import shutil
import threading
import webbrowser
import importlib.util
import math
import re
from flask import Flask, request, send_file, render_template_string

# ---------- 导入原脚本 ----------
script_dir = os.path.dirname(os.path.abspath(__file__))
original_file = os.path.join(script_dir, "幼小衔接字帖.py")
if not os.path.exists(original_file):
    sys.exit("错误：找不到原脚本 '幼小衔接字帖.py'，请确保放在同一目录下")

# 动态导入模块
spec = importlib.util.spec_from_file_location("calligraphy_module", original_file)
calligraphy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calligraphy_module)
CalligraphyConfig = calligraphy_module.CalligraphyConfig
CalligraphyGenerator = calligraphy_module.CalligraphyGenerator

# 导入预设示例数据（从原脚本中定义的三个变量）
DEMO_HANZI_STR = calligraphy_module.DEMO_HANZI_STR
DEMO_ARTICLE = calligraphy_module.DEMO_ARTICLE
DEMO_STORIES = calligraphy_module.DEMO_STORIES
print("[INFO] 成功从原脚本加载预设示例数据")

# ---------- Flask 应用 ----------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

TEMP_DIR = os.path.join(script_dir, "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)

import atexit
def cleanup_temp():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
atexit.register(cleanup_temp)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0,2,4))
    return (70, 175, 70)

# ---------- 页数估算函数（复用原脚本的计算逻辑） ----------
def estimate_pages(mode, content, config_params):
    """
    根据模式、内容和配置参数预估总页数
    返回整数页数
    """
    # 创建临时配置对象
    config = CalligraphyConfig(
        char_list=["占"],  # 占位
        gray_factor=config_params['gray_factor'],
        cols_per_row=config_params['cols_per_row'],
        page_size=config_params['page_size'],
        dpi=config_params['dpi'],
        margin_mm=config_params['margin_mm'],
        title=config_params.get('title') or None,
        font_path=None,
        border_color=(0,0,0),
        dash_color=(0,0,0),
        cell_spacing=config_params['cell_spacing'],
        line_spacing=config_params['line_spacing'],
        char_font_ratio=config_params['char_font_ratio']
    )
    generator = CalligraphyGenerator(config)
    generator._compute_cell_size()  # 确保格子尺寸计算
    
    if mode == 'basic':
        chars = [ch for ch in content if ch.strip() and not ch.isspace()]
        total_chars = len(chars)
        if total_chars == 0:
            return 0
        rows_per_page = generator._compute_rows_per_page()
        chars_per_page = max(1, rows_per_page // 2)
        pages = math.ceil(total_chars / chars_per_page)
        return pages
    
    elif mode == 'article':
        lines = generator._split_article_into_lines(content)
        total_lines = len(lines)
        if total_lines == 0:
            return 0
        max_lines_per_page = generator._compute_text_rows_per_page()
        pages = math.ceil(total_lines / max_lines_per_page)
        return pages
    
    elif mode == 'stories':
        raw_stories = re.split(r'\n\s*\n', content.strip())
        raw_stories = [s.strip() for s in raw_stories if s.strip()]
        if not raw_stories:
            return 0
        max_lines_per_page = generator._compute_text_rows_per_page()
        total_pages = 0
        current_page_lines = 0
        for story in raw_stories:
            story_lines = generator._split_article_into_lines(story)
            if not story_lines:
                continue
            if total_pages > 0 and current_page_lines > 0:
                total_pages += 1
                current_page_lines = 0
            for line in story_lines:
                if current_page_lines >= max_lines_per_page:
                    total_pages += 1
                    current_page_lines = 0
                current_page_lines += 1
        if current_page_lines > 0:
            total_pages += 1
        return max(1, total_pages)
    
    return 1

# ---------- HTML 模板 ----------
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>练字字帖生成器</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: #f5f7fa;
            margin: 0;
            padding: 20px;
            color: #1e293b;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 24px;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
            padding: 24px 28px;
        }
        h1 { font-size: 1.8rem; margin-top: 0; margin-bottom: 0.25rem; color: #0f3b2c; }
        .sub { color: #475569; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 24px; }
        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 18px;
            background: #f8fafc;
            padding: 20px;
            border-radius: 20px;
            margin-bottom: 24px;
        }
        .param-group label { display: block; font-weight: 600; font-size: 0.85rem; margin-bottom: 6px; color: #0f3b2c; }
        .param-group input, .param-group select {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            font-size: 0.9rem;
            background: white;
        }
        .param-group input[type="color"] { height: 38px; padding: 2px; }
        .param-group small { font-size: 0.7rem; color: #64748b; }
        .button-row {
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .btn {
            flex: 1;
            background: #1e4620;
            border: none;
            padding: 12px 16px;
            border-radius: 40px;
            font-weight: bold;
            font-size: 1rem;
            color: white;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn:hover { background: #2d6a2d; transform: translateY(-1px); }
        .example-buttons {
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }
        .example-btn {
            background: #eef2ff;
            border: 1px solid #cbd5e1;
            padding: 6px 14px;
            border-radius: 40px;
            font-size: 0.8rem;
            font-weight: 500;
            color: #1e4620;
            cursor: pointer;
        }
        .example-btn:hover { background: #d9e6d9; border-color: #1e4620; }
        .text-area-box { margin: 20px 0; }
        textarea {
            width: 100%;
            min-height: 220px;
            padding: 14px;
            font-family: monospace;
            font-size: 14px;
            border: 1px solid #cbd5e1;
            border-radius: 20px;
            resize: vertical;
        }
        .status {
            margin-top: 20px;
            background: #f1f5f9;
            padding: 12px 16px;
            border-radius: 28px;
            font-size: 0.9rem;
            color: #0f3b2c;
        }
        footer { margin-top: 30px; text-align: center; font-size: 0.75rem; color: #94a3b8; }
        .author { margin-top: 20px; padding-top: 12px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 0.75rem; color: #475569; }
    </style>
</head>
<body>
<div class="container">
    <h1>📝 练字字帖生成器</h1>
    <div class="sub">田字格描红｜页数预校验（超过30页会提示）</div>

    <form id="genForm" enctype="multipart/form-data">
        <div class="config-grid">
            <div class="param-group">
                <label>📁 本地字体 (.ttf/.otf)</label>
                <input type="file" name="font_file" accept=".ttf,.otf">
            </div>
            <div class="param-group">
                <label>🎨 格子边框颜色</label>
                <input type="color" name="border_color" value="#47af47">
            </div>
            <div class="param-group">
                <label>📏 灰度系数 (0黑~1淡)</label>
                <input type="range" name="gray_factor" min="0" max="1" step="0.01" value="0.20">
                <span id="grayVal">0.20</span>
            </div>
            <div class="param-group">
                <label>🔢 每行格子数</label>
                <input type="number" name="cols_per_row" min="5" max="20" value="16" step="1">
            </div>
            <div class="param-group">
                <label>📄 纸张</label>
                <select name="page_size">
                    <option value="A4">A4</option>
                    <option value="custom">自定义(mm)</option>
                </select>
                <div id="customSize" style="display:none; margin-top:6px;">
                    <input type="number" name="width_mm" placeholder="宽度mm" value="210" step="1"> x
                    <input type="number" name="height_mm" placeholder="高度mm" value="297" step="1">
                </div>
            </div>
            <div class="param-group">
                <label>📐 边距 (mm)</label>
                <input type="number" name="margin_mm" value="12" step="1" min="5">
            </div>
            <div class="param-group">
                <label>✍️ 字体比例</label>
                <input type="number" name="char_font_ratio" value="0.72" step="0.02" min="0.5" max="0.85">
            </div>
            <div class="param-group">
                <label>🏷️ 标题</label>
                <input type="text" name="title" value="幼小衔接练字帖">
            </div>
            <div class="param-group">
                <label>📏 格子间距(px)</label>
                <input type="number" name="cell_spacing" value="0" step="1">
            </div>
            <div class="param-group">
                <label>📐 行间距(px)</label>
                <input type="number" name="line_spacing" value="0" step="1">
            </div>
            <div class="param-group">
                <label>🎨 辅助线颜色</label>
                <input type="color" name="dash_color" value="#c0c0c0">
            </div>
            <div class="param-group">
                <label>🖨️ DPI</label>
                <input type="number" name="dpi" value="300" step="50" min="150">
            </div>
        </div>

        <div class="button-row">
            <button type="button" data-mode="basic" class="btn">📖 基础字帖 (单字列表)</button>
            <button type="button" data-mode="article" class="btn">📜 文章字帖</button>
            <button type="button" data-mode="stories" class="btn">📚 多故事字帖</button>
        </div>

        <div class="text-area-box">
            <div class="example-buttons">
                <button type="button" class="example-btn" id="loadHanziBtn">🔤 加载汉字练习</button>
                <button type="button" class="example-btn" id="loadPoemBtn">📜 加载古诗</button>
                <button type="button" class="example-btn" id="loadStoriesBtn">📖 加载小故事</button>
                <button type="button" class="example-btn" id="clearTextBtn">🗑️ 清空文本框</button>
            </div>
            <label style="font-weight:600;">✏️ 文本内容</label>
            <textarea name="content_text" id="content_text" placeholder="【基础模式】输入汉字序列（自动按字符拆分）
【文章模式】输入整篇文章（支持古诗/短文）
【故事模式】输入多个故事，用空行分隔">天地人你我他</textarea>
        </div>
    </form>

    <div id="status" class="status">⚙️ 配置好参数后，点击上方按钮生成 PDF</div>
    <footer>生成后自动下载 PDF | 临时文件会在程序关闭后清理</footer>
    <div class="author">项目作者：hongge &nbsp;&nbsp; 联系邮箱：<a href="mailto:shenjitask@163.com">shenjitask@163.com</a></div>
</div>

<script>
    // 预设内容从后端注入
    const DEMO_HANZI = {{ hanzi_preset|tojson }};
    const DEMO_POEM = {{ poem_preset|tojson }};
    const DEMO_STORIES = {{ stories_preset|tojson }};

    const textarea = document.getElementById('content_text');
    const statusDiv = document.getElementById('status');

    document.getElementById('loadHanziBtn').onclick = () => {
        textarea.value = DEMO_HANZI;
        statusDiv.innerHTML = '✅ 已加载汉字练习（共 ' + DEMO_HANZI.length + ' 个字符）';
    };
    document.getElementById('loadPoemBtn').onclick = () => {
        textarea.value = DEMO_POEM;
        statusDiv.innerHTML = '✅ 已加载古诗文章';
    };
    document.getElementById('loadStoriesBtn').onclick = () => {
        textarea.value = DEMO_STORIES;
        statusDiv.innerHTML = '✅ 已加载小故事合集';
    };
    document.getElementById('clearTextBtn').onclick = () => {
        textarea.value = '';
        statusDiv.innerHTML = '🗑️ 文本框已清空';
    };

    // 获取表单参数的函数
    function getConfigParams() {
        return {
            gray_factor: parseFloat(document.querySelector('input[name="gray_factor"]').value),
            cols_per_row: parseInt(document.querySelector('input[name="cols_per_row"]').value),
            margin_mm: parseInt(document.querySelector('input[name="margin_mm"]').value),
            dpi: parseInt(document.querySelector('input[name="dpi"]').value),
            title: document.querySelector('input[name="title"]').value,
            char_font_ratio: parseFloat(document.querySelector('input[name="char_font_ratio"]').value),
            cell_spacing: parseInt(document.querySelector('input[name="cell_spacing"]').value),
            line_spacing: parseInt(document.querySelector('input[name="line_spacing"]').value),
            page_size: document.querySelector('select[name="page_size"]').value === 'custom' ? 
                [parseInt(document.querySelector('input[name="width_mm"]').value), 
                 parseInt(document.querySelector('input[name="height_mm"]').value)] : 'A4',
            border_color: document.querySelector('input[name="border_color"]').value,
            dash_color: document.querySelector('input[name="dash_color"]').value,
            font_file: document.querySelector('input[name="font_file"]').files[0]
        };
    }

    async function generate(mode) {
        const content = textarea.value.trim();
        if (!content) {
            statusDiv.innerHTML = '❌ 请先在文本框中输入内容';
            return;
        }

        // 获取配置参数用于页数预估
        const configParams = getConfigParams();
        statusDiv.innerHTML = '⏳ 正在估算页数...';
        
        try {
            // 调用后端页数预估接口
            const estimateRes = await fetch('/estimate_pages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: mode,
                    content: content,
                    config: {
                        gray_factor: configParams.gray_factor,
                        cols_per_row: configParams.cols_per_row,
                        margin_mm: configParams.margin_mm,
                        dpi: configParams.dpi,
                        title: configParams.title,
                        char_font_ratio: configParams.char_font_ratio,
                        cell_spacing: configParams.cell_spacing,
                        line_spacing: configParams.line_spacing,
                        page_size: configParams.page_size
                    }
                })
            });
            const estimateData = await estimateRes.json();
            if (estimateData.pages > 30) {
                const confirm = window.confirm(`⚠️ 当前内容预计生成 ${estimateData.pages} 页字帖，超过30页。\n是否继续生成？`);
                if (!confirm) {
                    statusDiv.innerHTML = '❌ 已取消生成（页数过多）';
                    return;
                }
            }
        } catch (e) {
            console.warn('页数预估失败，继续生成', e);
        }

        // 正式生成
        const formData = new FormData(document.getElementById('genForm'));
        formData.append('action', mode);
        statusDiv.innerHTML = '⏳ 正在生成字帖，请稍等...';
        try {
            const response = await fetch('/generate', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                const err = await response.text();
                throw new Error(err || '生成失败');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `字帖练习_${mode}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            statusDiv.innerHTML = '✅ 生成成功！PDF 已下载。';
        } catch (err) {
            statusDiv.innerHTML = `❌ 错误：${err.message}`;
        }
    }

    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('click', () => generate(btn.dataset.mode));
    });

    // 灰度系数显示联动
    const graySlider = document.querySelector('input[name="gray_factor"]');
    const graySpan = document.getElementById('grayVal');
    graySlider.addEventListener('input', () => {
        graySpan.innerText = parseFloat(graySlider.value).toFixed(2);
    });
    // 纸张自定义显示
    const pageSizeSelect = document.querySelector('select[name="page_size"]');
    const customDiv = document.getElementById('customSize');
    pageSizeSelect.addEventListener('change', () => {
        customDiv.style.display = pageSizeSelect.value === 'custom' ? 'flex' : 'none';
    });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(
        HTML_TEMPLATE,
        hanzi_preset=DEMO_HANZI_STR,
        poem_preset=DEMO_ARTICLE,
        stories_preset=DEMO_STORIES
    )

@app.route('/estimate_pages', methods=['POST'])
def estimate_pages_api():
    """页数预估接口"""
    data = request.get_json()
    mode = data.get('mode')
    content = data.get('content', '')
    config = data.get('config', {})
    if not content:
        return {'pages': 0}
    pages = estimate_pages(mode, content, config)
    return {'pages': pages}

@app.route('/generate', methods=['POST'])
def generate_pdf_web():
    try:
        action = request.form.get('action')
        if not action or action not in ('basic', 'article', 'stories'):
            return "无效的生成模式", 400

        content = request.form.get('content_text', '').strip()
        if not content:
            return "文本内容不能为空", 400

        # 读取参数
        gray_factor = float(request.form.get('gray_factor', 0.28))
        cols_per_row = int(request.form.get('cols_per_row', 16))
        margin_mm = int(request.form.get('margin_mm', 12))
        dpi = int(request.form.get('dpi', 300))
        title = request.form.get('title', '').strip()
        char_font_ratio = float(request.form.get('char_font_ratio', 0.72))
        cell_spacing = int(request.form.get('cell_spacing', 0))
        line_spacing = int(request.form.get('line_spacing', 0))
        border_color_hex = request.form.get('border_color', '#47af47')
        dash_color_hex = request.form.get('dash_color', '#c0c0c0')

        page_size_val = request.form.get('page_size', 'A4')
        if page_size_val == 'custom':
            try:
                w_mm = int(request.form.get('width_mm', 210))
                h_mm = int(request.form.get('height_mm', 297))
                page_size = (w_mm, h_mm)
            except:
                page_size = 'A4'
        else:
            page_size = 'A4'

        font_path = None
        uploaded_font = request.files.get('font_file')
        if uploaded_font and uploaded_font.filename:
            ext = os.path.splitext(uploaded_font.filename)[1].lower()
            if ext in ['.ttf', '.otf']:
                temp_font = os.path.join(TEMP_DIR, f"user_font_{os.urandom(4).hex()}{ext}")
                uploaded_font.save(temp_font)
                font_path = temp_font

        border_color = hex_to_rgb(border_color_hex)
        dash_color = hex_to_rgb(dash_color_hex)

        out_pdf = os.path.join(TEMP_DIR, f"output_{action}_{os.urandom(6).hex()}.pdf")

        if action == 'basic':
            char_list = [ch for ch in content if ch.strip() and not ch.isspace()]
            if not char_list:
                return "基础模式需要至少一个有效汉字", 400
            config = CalligraphyConfig(
                char_list=char_list, gray_factor=gray_factor, cols_per_row=cols_per_row,
                page_size=page_size, dpi=dpi, margin_mm=margin_mm, title=title if title else None,
                font_path=font_path, border_color=border_color, dash_color=dash_color,
                cell_spacing=cell_spacing, line_spacing=line_spacing, char_font_ratio=char_font_ratio
            )
            generator = CalligraphyGenerator(config)
            generator.generate_pdf(out_pdf)

        elif action == 'article':
            config = CalligraphyConfig(
                char_list=["占"], gray_factor=gray_factor, cols_per_row=cols_per_row,
                page_size=page_size, dpi=dpi, margin_mm=margin_mm, title=title if title else None,
                font_path=font_path, border_color=border_color, dash_color=dash_color,
                cell_spacing=cell_spacing, line_spacing=line_spacing, char_font_ratio=char_font_ratio
            )
            generator = CalligraphyGenerator(config)
            generator.generate_article_pdf(content, out_pdf)

        else:  # stories
            config = CalligraphyConfig(
                char_list=["占"], gray_factor=gray_factor, cols_per_row=cols_per_row,
                page_size=page_size, dpi=dpi, margin_mm=margin_mm, title=title if title else None,
                font_path=font_path, border_color=border_color, dash_color=dash_color,
                cell_spacing=cell_spacing, line_spacing=line_spacing, char_font_ratio=char_font_ratio
            )
            generator = CalligraphyGenerator(config)
            generator.generate_stories_pdf(content, output_pdf_path=out_pdf)

        if not os.path.exists(out_pdf):
            return f"PDF 文件未生成", 500

        return send_file(out_pdf, as_attachment=True, download_name=f"练字字帖_{action}.pdf")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"服务器内部错误: {str(e)}", 500

if __name__ == '__main__':
    print("=" * 50)
    print("✨ 字帖生成器 Web 版已启动（含页数预校验，超过30页会提示）")
    print("👉 正在自动打开浏览器...")
    print("📁 临时目录:", TEMP_DIR)
    print("👤 作者：hongge  shenjitask@163.com")
    print("=" * 50)
    threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
    app.run(debug=False, host='127.0.0.1', port=5000)