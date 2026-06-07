import os, re
import math
from PIL import Image, ImageDraw, ImageFont

# ========================== 虚线绘制工具 ==========================
def draw_dashed_line(draw, start, end, fill, dash_length=6, gap_length=4):
    """
    在PIL图像上绘制任意角度的虚线。
    
    参数:
        draw: PIL.ImageDraw对象
        start: 起点坐标 (x1, y1)
        end:   终点坐标 (x2, y2)
        fill:  虚线颜色 (R,G,B)
        dash_length: 实线段的长度（像素）
        gap_length:  空白段的长度（像素）
    """
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux = dx / length
    uy = dy / length
    cur_x, cur_y = x1, y1
    t = 0
    while t + dash_length <= length:
        end_x = cur_x + ux * dash_length
        end_y = cur_y + uy * dash_length
        draw.line((cur_x, cur_y, end_x, end_y), fill=fill, width=1)
        cur_x = end_x + ux * gap_length
        cur_y = end_y + uy * gap_length
        t += dash_length + gap_length
    if t < length:
        draw.line((cur_x, cur_y, x2, y2), fill=fill, width=1)


# ========================== 配置类（所有参数集中管理，均有注释） ==========================
class CalligraphyConfig:
    """
    练字字帖的全部配置参数。
    使用时创建该类的实例，传入自定义参数，然后交给 CalligraphyGenerator 生成 PDF。
    """
    def __init__(self,
                 # ----- 1. 字帖内容 -----
                 char_list=None,
                 # 必填：需要练习的汉字列表，例如 ['你','我','他'] 或字符串 "你好" 转换成的列表。

                 # ----- 2. 灰度控制（两种方式任选其一）-----
                 gray_level=None,
                 # 灰度值 0~255，值越大颜色越淡（255为白色，几乎看不见）。若同时提供了 gray_factor，则优先使用 gray_level。
                 gray_factor=0.5,
                 # 灰度系数 0.0~1.0，0=纯黑，1=极淡灰（接近白色）。当 gray_level 为 None 时生效。推荐 0.3~0.5。

                 # ----- 3. 布局参数 -----
                 cols_per_row=11,
                 # 每行格子数量，即每个汉字在一行内重复的次数。例如 11 表示一行有11个相同的汉字格子。
                 # 格子宽度会根据此数值和页面宽度自动等比例缩放，确保填满整行。

                 # ----- 4. 页面参数 -----
                 page_size='A4',
                 # 纸张大小，支持 'A4'（210x297mm）或自定义元组 (宽度_mm, 高度_mm)
                 dpi=300,
                 # 输出分辨率，推荐 300（适合打印），数值越高图片越精细。
                 margin_mm=12,
                 # 页边距，单位毫米。上下左右均为此值。通常 10~15mm 比较美观。

                 # ----- 5. 样式参数 -----
                 title="幼小衔接练字",
                 # 页面顶部的标题文字。设置为 None 或空字符串则不显示标题。
                 font_path=None,
                 # 中文字体文件路径。若为 None，程序会自动搜索系统常见字体（楷体、黑体等）。
                 border_color=(70, 175, 70),
                 # 格子外框颜色，默认绿色 (R,G,B)。可改为 (0,0,0) 黑色等。
                 dash_color=(190, 190, 190),
                 # 田字格内辅助线（十字线、对角线）的颜色，默认浅灰色。

                 # ----- 6. 间距参数（一般保持默认0，即格子紧贴）-----
                 cell_spacing=0,
                 # 同一行内两个格子之间的水平间距（像素）。0表示无间距，格子紧挨着。
                 line_spacing=0,
                 # 行与行之间的垂直间距（像素）。0表示无间距，行紧挨着。
                 
                 # ----- 7. 字体比例（科学调整字的大小）-----
                 char_font_ratio=0.7
                 # 汉字在格子中的相对大小。推荐值 0.65~0.75。
                 # 0.68 表示字高约占格子高度的 68%，打印后约 1.5~2cm，适合儿童。
                 # 太小则字不清晰，太大容易写出格。
                 ):
        
        self.char_list = char_list or []
        self.gray_level = gray_level
        self.gray_factor = gray_factor
        self.cols_per_row = cols_per_row
        self.page_size = page_size
        self.dpi = dpi
        self.margin_mm = margin_mm
        self.title = title
        self.font_path = font_path
        self.border_color = border_color
        self.dash_color = dash_color
        self.cell_spacing = cell_spacing
        self.line_spacing = line_spacing
        self.char_font_ratio = char_font_ratio

        # 根据页面尺寸和DPI预计算宽高（像素）
        if page_size == 'A4':
            self.width_px = int(8.27 * dpi)    # 8.27英寸 ≈ 210mm
            self.height_px = int(11.69 * dpi)  # 11.69英寸 ≈ 297mm
        else:
            # 自定义尺寸：(width_mm, height_mm)
            w_mm, h_mm = page_size
            self.width_px = int(w_mm / 25.4 * dpi)
            self.height_px = int(h_mm / 25.4 * dpi)
        
        # 将边距从毫米转换为像素
        self.margin_px = int(self.margin_mm / 25.4 * dpi)


# ========================== 字帖生成器 ==========================
class CalligraphyGenerator:
    """根据配置生成练字字帖，自动分页并输出 PDF"""
    def __init__(self, config):
        self.config = config
        self._validate_input()
        self._load_fonts()
        self._determine_gray_color()
        self._compute_cell_size()

    def _validate_input(self):
        """过滤并验证输入的汉字列表"""
        chars = []
        for item in self.config.char_list:
            s = str(item).strip()
            if s:
                chars.append(s[0])   # 只取第一个字符
        if not chars:
            raise ValueError("char_list 为空或无有效汉字")
        self.chars = chars
        self.total_chars = len(chars)

    def _load_fonts(self):
        """加载中文字体（优先使用用户指定的路径，否则自动搜索）"""
        font_path = self.config.font_path
        if font_path is None:
            possible_fonts = [
                "C:/Windows/Fonts/simkai.ttf",   # 楷体（最适合练字）
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/msyh.ttc",
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
            ]
            for f in possible_fonts:
                if os.path.exists(f):
                    font_path = f
                    break
            else:
                font_path = None
        self.font_path = font_path

    def _determine_gray_color(self):
        """确定描红字的灰度颜色（R,G,B）"""
        if self.config.gray_level is not None:
            g = max(0, min(255, self.config.gray_level))
        else:
            g = int(255 * (1 - self.config.gray_factor))
            g = max(0, min(255, g))
        self.gray_color = (g, g, g)

    def _compute_cell_size(self):
        """
        根据每行格子数、页面宽度和边距，计算正方形格子的边长（像素）。
        格子会自动填满可用宽度，并确保为整数。
        """
        usable_width = self.config.width_px - 2 * self.config.margin_px
        cols = self.config.cols_per_row
        spacing = self.config.cell_spacing
        if spacing == 0:
            cell_size = usable_width // cols
        else:
            total_spacing = (cols - 1) * spacing
            cell_size = (usable_width - total_spacing) // cols
        # 防止格子过小（至少40像素，否则无法书写）
        if cell_size < 40:
            cell_size = 40
        self.cell_size = cell_size
        self.half_cell = cell_size // 2

    def _compute_rows_per_page(self):
        """
        计算一页A4纸最多能容纳多少行格子（每个汉字占用2行：描红行+空白行）。
        考虑标题、上下边距、行间距等因素。
        """
        margin = self.config.margin_px
        title_height = self._get_title_height() if self.config.title else 0
        usable_height = self.config.height_px - 2 * margin - title_height
        
        if self.config.line_spacing == 0:
            rows_per_page = usable_height // self.cell_size
        else:
            # 考虑行间距：总高度 = rows * cell_size + (rows-1) * line_spacing
            max_rows = 0
            while True:
                h = (max_rows + 1) * self.cell_size + max_rows * self.config.line_spacing
                if h <= usable_height:
                    max_rows += 1
                else:
                    break
            rows_per_page = max_rows
        return max(1, rows_per_page)

    def _get_title_height(self):
        """计算标题占用的像素高度（包含上下留白）"""
        if not self.config.title:
            return 0
        # 临时画布用于测量文字高度
        temp_img = Image.new('RGB', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        try:
            font_title = ImageFont.truetype(self.font_path, 48) if self.font_path else ImageFont.load_default()
        except:
            font_title = ImageFont.load_default()
        bbox = temp_draw.textbbox((0, 0), self.config.title, font=font_title)
        text_height = bbox[3] - bbox[1]
        # 标题上下各留20像素空白
        return text_height + 40

    def _draw_grid(self, draw, x1, y1, x2, y2):
        """
        在指定矩形区域内绘制完整的田字格：
        - 绿色实线外框
        - 水平、垂直虚线中线
        - 两条虚线对角线
        """
        # 外框
        draw.rectangle([x1, y1, x2, y2], outline=self.config.border_color, width=1)
        # 水平中线
        mid_y = (y1 + y2) / 2
        draw_dashed_line(draw, (x1, mid_y), (x2, mid_y), fill=self.config.dash_color, dash_length=6, gap_length=4)
        # 垂直中线
        mid_x = (x1 + x2) / 2
        draw_dashed_line(draw, (mid_x, y1), (mid_x, y2), fill=self.config.dash_color, dash_length=6, gap_length=4)
        # 对角线
        draw_dashed_line(draw, (x1, y1), (x2, y2), fill=self.config.dash_color, dash_length=6, gap_length=4)
        draw_dashed_line(draw, (x2, y1), (x1, y2), fill=self.config.dash_color, dash_length=6, gap_length=4)

    def _draw_text_centered(self, draw, x1, y1, x2, y2, text, font, fill_color):
        """在矩形区域内居中绘制文字"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        draw.text((cx, cy), text, font=font, fill=fill_color, anchor="mm")

    def _create_page_image(self, page_chars):
        """
        生成一页字帖的图片（PIL.Image 对象）
        :param page_chars: 当前页需要绘制的汉字列表
        """
        img = Image.new("RGB", (self.config.width_px, self.config.height_px), "white")
        draw = ImageDraw.Draw(img)

        # 根据格子大小动态确定字体大小
        char_font_size = int(self.cell_size * self.config.char_font_ratio)
        title_font_size = int(char_font_size * 0.8)

        try:
            font_char = ImageFont.truetype(self.font_path, char_font_size) if self.font_path else ImageFont.load_default()
            font_title = ImageFont.truetype(self.font_path, title_font_size) if self.font_path else ImageFont.load_default()
        except:
            font_char = ImageFont.load_default()
            font_title = ImageFont.load_default()

        margin = self.config.margin_px
        # 绘制标题
        if self.config.title:
            title_bbox = draw.textbbox((0, 0), self.config.title, font=font_title)
            title_w = title_bbox[2] - title_bbox[0]
            title_x = (self.config.width_px - title_w) / 2
            title_y = margin // 2
            draw.text((title_x, title_y), self.config.title, font=font_title, fill=(0, 0, 0))
            title_height = title_y + (title_bbox[3] - title_bbox[1]) + 20
        else:
            title_height = 0

        start_y = margin + title_height
        black = (0, 0, 0)

        # 逐字绘制两行（描红行 + 空白行）
        for idx, ch in enumerate(page_chars):
            row_top = start_y + idx * (self.cell_size + self.config.line_spacing) * 2
            line1_y = row_top          # 第一行（描红行）的Y坐标
            line2_y = row_top + self.cell_size  # 第二行（空白行）的Y坐标

            # ---------- 第一行：描红行（首格黑色，其余灰度） ----------
            for col in range(self.config.cols_per_row):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = line1_y
                y2 = line1_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)
                # 写字
                if col == 0:
                    self._draw_text_centered(draw, x_left, y1, x_right, y2, ch, font_char, black)
                else:
                    self._draw_text_centered(draw, x_left, y1, x_right, y2, ch, font_char, self.gray_color)

            # ---------- 第二行：空白练习格（无文字） ----------
            for col in range(self.config.cols_per_row):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = line2_y
                y2 = line2_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)
                # 不写字

        return img

    def generate_pdf(self, output_pdf_path=None):
        """
        生成字帖 PDF，自动分页，保存到指定路径。
        :param output_pdf_path: PDF文件的完整路径，若为None则自动保存到桌面。
        :return: PDF文件的路径
        """
        if output_pdf_path is None:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_pdf_path = os.path.join(desktop, "练字字帖.pdf")

        # 计算每页能容纳的汉字数量（每个字占2行）
        rows_per_page = self._compute_rows_per_page()
        chars_per_page = rows_per_page // 2
        if chars_per_page == 0:
            raise RuntimeError("页面高度不足以放下一个完整的字（两行），请减小边距或增大页面尺寸")

        # 分页
        pages = []
        for i in range(0, self.total_chars, chars_per_page):
            page_chars = self.chars[i:i+chars_per_page]
            pages.append(page_chars)

        if not pages:
            raise RuntimeError("没有生成任何页面")

        # 生成每一页的图片
        images = []
        for idx, page_chars in enumerate(pages, start=1):
            img = self._create_page_image(page_chars)
            images.append(img)
            print(f"生成第 {idx} 页，包含 {len(page_chars)} 个汉字")

        # 保存为多页 PDF
        if len(images) == 1:
            images[0].save(output_pdf_path, save_all=True, dpi=(self.config.dpi, self.config.dpi))
        else:
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:], dpi=(self.config.dpi, self.config.dpi))

        print(f"字帖 PDF 已保存至: {output_pdf_path}")
        return output_pdf_path

    # ========================== 文章字帖功能 ==========================
    def _split_article_into_lines(self, article_text):
        """
        将文章拆分为字符行列表，考虑每行最大格子数和原文换行符。
        返回: list of list of str, 例如 [['你','好','吗'], ['我','是','A','B','C']]
        注意：忽略空行（连续换行符不会产生空列表）
        """
        max_cols = self.config.cols_per_row
        lines = []
        current_line_chars = []
        for ch in article_text:
            if ch == '\n':
                if current_line_chars:
                    lines.append(current_line_chars)
                    current_line_chars = []
                # 遇到换行符且当前行无内容 → 空行，直接跳过（不添加空列表）
                # 这能消除连续空行带来的多余空白格子
            elif ch == '\r':
                continue
            else:
                current_line_chars.append(ch)
                if len(current_line_chars) >= max_cols:
                    lines.append(current_line_chars)
                    current_line_chars = []
        # 处理最后剩余字符（如果文章末尾没有换行符）
        if current_line_chars:
            lines.append(current_line_chars)
        # 如果整个文本全是换行符，则 lines 可能为空，此时至少保留一行空行？但古诗场景不会发生
        return lines


    def _compute_text_rows_per_page(self):
        """
        计算一页最多能容纳多少行**文本行**（每行文本对应两行格子：描红行+空白行）。
        考虑标题、上下边距、行间距（line_spacing 作为文本行之间的间距，同一文本行内的两行格子之间无间距）。
        """
        margin = self.config.margin_px
        title_height = self._get_title_height() if self.config.title else 0
        usable_height = self.config.height_px - 2 * margin - title_height
        # 每组（描红行+空白行）高度 = 2 * cell_size + line_spacing（最后一行无间距，但计算时暂时包含）
        group_height = 2 * self.cell_size + self.config.line_spacing
        if group_height <= 0:
            return 1
        max_groups = usable_height // group_height
        return max(1, max_groups)

    def _draw_article_page(self, text_lines):
        """
        绘制一页文章字帖（描红行 + 空白行交替），每行格子数固定为 config.cols_per_row，
        不足的格子留空（不写字）。
        :param text_lines: 当前页的文本行列表，每个元素是一个字符列表（长度可能小于 cols_per_row）
        :return: PIL.Image 对象
        """
        img = Image.new("RGB", (self.config.width_px, self.config.height_px), "white")
        draw = ImageDraw.Draw(img)

        # 字体大小
        char_font_size = int(self.cell_size * self.config.char_font_ratio)
        title_font_size = int(char_font_size * 0.8)

        try:
            font_char = ImageFont.truetype(self.font_path, char_font_size) if self.font_path else ImageFont.load_default()
            font_title = ImageFont.truetype(self.font_path, title_font_size) if self.font_path else ImageFont.load_default()
        except:
            font_char = ImageFont.load_default()
            font_title = ImageFont.load_default()

        margin = self.config.margin_px
        # 绘制标题
        if self.config.title:
            title_bbox = draw.textbbox((0, 0), self.config.title, font=font_title)
            title_w = title_bbox[2] - title_bbox[0]
            title_x = (self.config.width_px - title_w) / 2
            title_y = margin // 2
            draw.text((title_x, title_y), self.config.title, font=font_title, fill=(0, 0, 0))
            title_height = title_y + (title_bbox[3] - title_bbox[1]) + 20
        else:
            title_height = 0

        start_y = margin + title_height
        cols = self.config.cols_per_row          # 每行固定格子数
        # 逐行处理文本
        for line_idx, line_chars in enumerate(text_lines):
            # 当前文本行对应的描红行和空白行的 Y 坐标
            line_top_y = start_y + line_idx * (2 * self.cell_size + self.config.line_spacing)
            trace_y = line_top_y            # 描红行 Y
            blank_y = line_top_y + self.cell_size  # 空白行 Y

            # 绘制描红行：固定绘制 cols 个格子
            for col in range(cols):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = trace_y
                y2 = trace_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)
                # 如果当前列有对应的字符（col < len(line_chars)），则写入灰色字
                if col < len(line_chars):
                    ch = line_chars[col]
                    self._draw_text_centered(draw, x_left, y1, x_right, y2, ch, font_char, self.gray_color)
                # 否则不写字（留空）

            # 绘制空白行：固定绘制 cols 个格子，均不写字
            for col in range(cols):
                x_left = margin + col * (self.cell_size + self.config.cell_spacing)
                x_right = x_left + self.cell_size
                y1 = blank_y
                y2 = blank_y + self.cell_size
                self._draw_grid(draw, x_left, y1, x_right, y2)
                # 此处不写字

        return img

    def generate_article_pdf(self, article_text, output_pdf_path=None):
        """
        将一篇文章生成练字字帖（描红一行 + 空白一行），自动分页，每页固定填满最大行数（不足补空白行）。
        :param article_text: 字符串，可包含汉字、标点、英文字母、数字、换行符等。
        :param output_pdf_path: PDF 保存路径，为 None 时自动保存到桌面。
        :return: PDF 文件路径
        """
        if output_pdf_path is None:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_pdf_path = os.path.join(desktop, "诗歌文章练字字帖.pdf")

        # 1. 将文章拆分为行（按每行格子数和换行符）
        all_text_lines = self._split_article_into_lines(article_text)
        if not all_text_lines:
            raise ValueError("文章内容为空")

        # 2. 计算每页能容纳多少行文本（一行文本对应两行格子）
        max_text_lines_per_page = self._compute_text_rows_per_page()
        if max_text_lines_per_page == 0:
            raise RuntimeError("页面高度不足以放下任何一行文本，请减小边距或增大页面尺寸")

        # 3. 分页，并补足最后一页的空行
        pages_lines = []
        for i in range(0, len(all_text_lines), max_text_lines_per_page):
            page_lines = all_text_lines[i:i+max_text_lines_per_page]
            # 如果最后一页不足，用空行补足（空行用空列表 [] 表示）
            if len(page_lines) < max_text_lines_per_page:
                page_lines += [[] for _ in range(max_text_lines_per_page - len(page_lines))]
            pages_lines.append(page_lines)

        # 4. 生成每页图片
        images = []
        for idx, page_lines in enumerate(pages_lines, start=1):
            img = self._draw_article_page(page_lines)
            images.append(img)
            # 统计实际有内容的行数（非空列表）
            actual_lines = sum(1 for line in page_lines if line)
            print(f"生成第 {idx} 页，共 {max_text_lines_per_page} 行（其中实际内容 {actual_lines} 行，空白 {max_text_lines_per_page - actual_lines} 行）")

        # 5. 保存为 PDF
        if len(images) == 1:
            images[0].save(output_pdf_path, save_all=True, dpi=(self.config.dpi, self.config.dpi))
        else:
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:], dpi=(self.config.dpi, self.config.dpi))

        print(f"文章字帖 PDF 已保存至: {output_pdf_path}")
        return output_pdf_path

    # ========================== 多故事自动分页功能 ==========================
    def generate_stories_pdf(self, stories_text, split_pattern=None, strip_star=True, output_pdf_path=None):
        """
        将多个小故事生成练字字帖，每个故事自动分页（从新页开始），每页固定填满最大行数（不足补空白行）。
        
        :param stories_text: 包含多个故事的原始文本
        :param split_pattern: 故事分割的正则表达式（默认 r'\\n\\s*\\n'，即至少一个空行）
        :param strip_star: 是否去除标题中的 ** 标记（如 '**小兔子种花**' -> '小兔子种花'）
        :param output_pdf_path: PDF 保存路径（None 则自动保存到桌面）
        :return: PDF 文件路径
        """
        if output_pdf_path is None:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            output_pdf_path = os.path.join(desktop, "多故事练字字帖.pdf")

        # ----- 1. 分割故事 -----
        if split_pattern is None:
            split_pattern = r'\n\s*\n'          # 两个以上的换行符（允许中间有空白）
        raw_stories = re.split(split_pattern, stories_text.strip())
        # 过滤掉可能出现的空字符串
        raw_stories = [s.strip() for s in raw_stories if s.strip()]

        if not raw_stories:
            raise ValueError("没有检测到任何故事内容")

        # ----- 2. 处理标题中的 ** 标记（可选）-----
        processed_stories = []
        for story in raw_stories:
            if strip_star:
                # 去除行首行尾的 ** 标记（例如 **标题** 变成 标题）
                lines = story.split('\n')
                new_lines = []
                for line in lines:
                    line = re.sub(r'^\*\*(.*?)\*\*$', r'\1', line.strip())
                    new_lines.append(line)
                story = '\n'.join(new_lines)
            processed_stories.append(story)

        # ----- 3. 确保格子尺寸已计算 -----
        self._compute_cell_size()
        max_text_lines_per_page = self._compute_text_rows_per_page()
        if max_text_lines_per_page == 0:
            raise RuntimeError("页面高度不足以放下任何一行文本，请减小边距或增大页面尺寸")

        # ----- 4. 将所有故事拆分为行，并按故事强制分页，每页固定填满 -----
        all_page_lines = []          # 存放每一页的行列表（每个元素是一页的 text_lines）
        cur_page_lines = []          # 当前正在累积的文本行（字符列表的列表）

        for story_idx, story_text in enumerate(processed_stories):
            # 将单个故事拆分为行（按每行格子数和原始换行符）
            story_lines = self._split_article_into_lines(story_text)
            if not story_lines:
                continue

            # 如果是第一个故事之后的故事，且当前页不为空 → 强制分页（新故事从新页开始）
            if story_idx > 0 and cur_page_lines:
                # 将当前页补足后加入 all_page_lines
                if len(cur_page_lines) < max_text_lines_per_page:
                    cur_page_lines += [[] for _ in range(max_text_lines_per_page - len(cur_page_lines))]
                all_page_lines.append(cur_page_lines)
                cur_page_lines = []

            # 将当前故事的行逐行加入 cur_page_lines，超出页容量时切分
            for line_chars in story_lines:
                cur_page_lines.append(line_chars)
                if len(cur_page_lines) >= max_text_lines_per_page:
                    all_page_lines.append(cur_page_lines)
                    cur_page_lines = []

        # 处理最后一页：补足空行后加入
        if cur_page_lines:
            if len(cur_page_lines) < max_text_lines_per_page:
                cur_page_lines += [[] for _ in range(max_text_lines_per_page - len(cur_page_lines))]
            all_page_lines.append(cur_page_lines)

        if not all_page_lines:
            raise RuntimeError("没有生成任何页面")

        # ----- 5. 绘制每一页并保存为 PDF -----
        images = []
        for idx, page_lines in enumerate(all_page_lines, start=1):
            img = self._draw_article_page(page_lines)
            images.append(img)
            actual_lines = sum(1 for line in page_lines if line)
            print(f"生成第 {idx} 页，共 {max_text_lines_per_page} 行（其中实际内容 {actual_lines} 行，空白 {max_text_lines_per_page - actual_lines} 行）")

        if len(images) == 1:
            images[0].save(output_pdf_path, save_all=True, dpi=(self.config.dpi, self.config.dpi))
        else:
            images[0].save(output_pdf_path, save_all=True, append_images=images[1:], dpi=(self.config.dpi, self.config.dpi))

        print(f"多故事字帖 PDF 已保存至: {output_pdf_path}")
        return output_pdf_path


# ========================== 示例数据（供独立运行和 Web 导入） ==========================
# 以下三个变量将被 Web 端导入使用，同时也用于下面的独立运行示例

DEMO_HANZI_STR = "一二三十人人口手七九八上下中个大个小刀天天云石日月水火木山土田方尺王毛牛车牙心东西北南左右前后白皮石目耳头鸟虫鱼贝风雨电闪雷爸妈爷奶哥姐弟妹叔伯阿姨们身手足牙舌血目耳口鼻舌心走立坐卧站行止飞花草树叶苗竹瓜果米面饭菜肉蛋鱼虾鸡鸭鹅兔猫狗牛羊马鸟虫草红黄蓝绿白黑灰亮美丽对错是非正反长短高低粗细厚薄软硬深浅远近快慢热冷暖凉温干湿饱饿渴睡醒笑哭骂听说读写看问答想记忘记加减多少钱币买卖店铺医院药病痛安全危险快乐悲伤忙闲勤劳懒惰诚实勇敢善良团结互助分享合作年级班校课本书笔尺刀剪针线布衣裤袜鞋帽爷奶爷奶河江湖海浪沙冰霜春夏秋冬早晚晨夕午夜晚饭汤粥饼糕糖甜酸苦辣哥姐弟妹叔伯阿姨朋友邻居城市乡村公园学校教室操场操场球场足球乒乓篮球跳绳踢毽子画画唱歌跳舞弹琴读书写字算术测量时间钟表单双加减乘除等于结果正确错误修改作业考试复习预习听讲思考回答提问举手发言排队集合升旗敬礼谢谢对不起没关系你好再见欢迎光临帮助爱护尊敬感谢表扬批评奖励惩罚规则纪律安全卫生值日劳动工具扫帚拖把抹布水桶毛巾肥皂洗手刷牙洗脸洗澡穿衣吃饭睡觉起床叠被整理书包文具盒铅笔橡皮尺子圆规三角板量角器计算器字典词典百科全书故事童话寓言谜语儿歌诗歌古诗作文日记书信便条通知请假条借条收据发票车船飞机火车地铁公交出租导航地图方向距离速度重量体积容量温度湿度气压风力级别颜色深浅明暗形状圆方三角长方正方体球体圆柱圆锥梯形菱形平行垂直水平角度度数分数小数百分比例因数倍数奇数偶数质数合数"

DEMO_ARTICLE = """咏鹅（唐·骆宾王）
鹅，鹅，鹅，曲项向天歌。
白毛浮绿水，红掌拨清波。

夜宿山寺（唐·李白）
危楼高百尺，手可摘星辰。
不敢高声语，恐惊天上人。

江雪（唐·柳宗元）
千山鸟飞绝，万径人踪灭。
孤舟蓑笠翁，独钓寒江雪。

画（唐·王维）
远看山有色，近听水无声。
春去花还在，人来鸟不惊。

静夜思（唐·李白）
床前明月光，疑是地上霜。
举头望明月，低头思故乡。

悯农·其二（唐·李绅）
锄禾日当午，汗滴禾下土。
谁知盘中餐，粒粒皆辛苦。

春晓（唐·孟浩然）
春眠不觉晓，处处闻啼鸟。
夜来风雨声，花落知多少。

寻隐者不遇（唐·贾岛）
松下问童子，言师采药去。
只在此山中，云深不知处。

登鹳雀楼（唐·王之涣）
白日依山尽，黄河入海流。
欲穷千里目，更上一层楼。

风（唐·李峤）
解落三秋叶，能开二月花。
过江千尺浪，入竹万竿斜。

山村咏怀（宋·邵雍）
一去二三里，烟村四五家。
亭台六七座，八九十枝花。

古朗月行（节选）（唐·李白）
小时不识月，呼作白玉盘。
又疑瑶台镜，飞在青云端。

小池（宋·杨万里）
泉眼无声惜细流，树阴照水爱晴柔。
小荷才露尖尖角，早有蜻蜓立上头。

村居（清·高鼎）
草长莺飞二月天，拂堤杨柳醉春烟。
儿童散学归来早，忙趁东风放纸鸢。

咏柳（唐·贺知章）
碧玉妆成一树高，万条垂下绿丝绦。
不知细叶谁裁出，二月春风似剪刀。

山行（唐·杜牧）
远上寒山石径斜，白云生处有人家。
停车坐爱枫林晚，霜叶红于二月花。

回乡偶书（唐·贺知章）
少小离家老大回，乡音无改鬓毛衰。
儿童相见不相识，笑问客从何处来。

赠汪伦（唐·李白）
李白乘舟将欲行，忽闻岸上踏歌声。
桃花潭水深千尺，不及汪伦送我情。

望庐山瀑布（唐·李白）
日照香炉生紫烟，遥看瀑布挂前川。
飞流直下三千尺，疑是银河落九天。

绝句（唐·杜甫）
两个黄鹂鸣翠柳，一行白鹭上青天。
窗含西岭千秋雪，门泊东吴万里船。

九月九日忆山东兄弟（唐·王维）
独在异乡为异客，每逢佳节倍思亲。
遥知兄弟登高处，遍插茱萸少一人。

出塞（唐·王昌龄）
秦时明月汉时关，万里长征人未还。
但使龙城飞将在，不教胡马度阴山。"""

DEMO_STORIES = """小兔去菜园种萝卜了。它竖起耳朵听鸟鸣，用足蹬地，拿起锄头挖了三个坑。用尺子量了坑深，放进种子，盖上土，浇了水。每天清晨都来看，拔草捉虫。几天后绿芽钻出来了，小兔开心得跳起来。夏天到了，萝卜长得又大又红。小兔拿刀切了一根，送给山羊爷爷。山羊咬一口说：“真甜啊！这是你劳动的结果呢。”小兔笑了，还用粘米粉和水搅拌成糊，蒸成萝卜糕，香味飘满了园子。

小猫跟老师学写字啦。老师教它握毛笔，画横竖撇捺，还教它认简单的字。小猫写“山”字，写得歪歪扭扭的。它不放弃，练了又练，手都酸了。太阳下山时，终于写出了工整的“水”字。老师点头说：“进步很快呢，继续努力吧。”小猫摇着尾巴说：“明天我要写‘火’字了。还要用尺子画直线，用橡皮擦改错字。”妈妈端来了米粥，小猫边吃边背字。它说：“语文课真有趣啊。”

小松鼠去森林找松果了。它跳过石头，爬过大树，闻到了一阵香味。拨开厚厚的落叶，发现了一堆金黄的松果，像小金子一样。小松鼠高兴得叫起来：“够吃一冬天啦！”它用大尾巴扫出一条路，把松果滚回了家。伙伴们闻着香味都来了，它分给大家吃，大家都说：“真大方啊。”小松鼠还折了一艘纸舟，放在溪水里漂着，舟上载着一颗松果送给河对岸的朋友。它站在岸边，望见远方有一面红旗。

下雨了，小鸡躲进了蘑菇伞下。小鸭没伞，急得嘎嘎叫。小鸡招招手：“快来呀，这把伞很大！”两个挤在一起，身子暖暖的。雨停了，天空挂起了彩虹桥。小鸭说：“谢谢你救了我。”小鸡回答：“朋友就应该互相帮助嘛。”它们手拉着手去踩水坑。小鸡还看见了禾苗在田里喝饱了水，绿油油的。小鸭说：“禾苗长大了就是米，我们吃的米饭就是从这里来的呀。”小鸡点点头，回家画了一幅画。

小牛帮山羊奶奶背草。草捆好重啊，像一座小山，小牛咬着牙坚持，一步一步往前走。山羊奶奶说：“你真是个好孩子呀。”小牛脸红了：“我力气大，就应该多干点活。”回家后妈妈表扬了它，奖励了一大碗热牛奶。小牛喝了一口，心里比牛奶还要甜。它还学会了用刀切草喂小羊，又用尺子量了量自己长高了多少。它立志长大要开拖拉机，帮大家耕田，种出更多的粮食来。

小鹅学游泳了。它跳进清凉的河里，翅膀扑腾着，身子往下沉。妈妈急忙托住它：“别害怕，腿往后蹬呀。”小鹅试了几次，终于浮起来了。它兴奋地游到了对岸，啄了一朵野花送给妈妈。妈妈亲亲它的头：“真是个勇敢的宝贝。”小鹅还看见了一条小船，船上坐着小鸭。小鹅问：“船会沉下去吗？”小鸭回答：“木船浮在水面上，就像你浮在水上一样呢。”小鹅学会后，每天清早都去练习。

小刺猬滚下山坡，撞到了一棵大树，身上扎满了红果子。它抖了抖身子，果子落了一地，滚得到处都是。小兔和小松鼠都来帮忙捡。小刺猬说：“大家一起吃吧，这么多我吃不完呢。”它们围成了一圈，咬一口果子，甜滋滋的。小刺猬还拿出了小刀，把果子切成片，晒成了干。它说：“冬天就有零食啦。”大家竖起耳朵听它讲怎么做果干，学了一门新手艺。小刺猬还把多余的果子分给路过的蚂蚁。

小熊过生日，收到一盒彩色画笔，有红黄蓝绿紫。它画了蓝天、绿草、红花、黄鸟，还画了学校的教室和国旗。画完挂在了墙上。妈妈看了说：“这是最珍贵的礼物呢。”小熊抱住妈妈：“我要画更多的画，送给没有画笔的朋友们。”第二天它带着画去森林小学。路上它看见了一辆车，车轮圆圆的。小熊想：“车有轮子才能跑，我有脚才能走呀。”它蹦蹦跳跳去了学校，把画分给了同桌。

小蜗牛想爬上葡萄架。别的动物都笑它爬得太慢了。它不理会，一步一步往上爬，风吹雨打都不肯停。一个月后，它终于爬到了架顶，尝到了甜甜的葡萄。它说：“慢不要紧，坚持就会赢的。”小蚂蚁们鼓起了掌。小蜗牛还用身体量了量葡萄架的高度，它说：“我的足虽然小，却能走到最高处呢。”蚂蚁们用米粒给它做了一顿庆功饭。小蜗牛把葡萄籽种在了土里，希望明年能长出更多的葡萄来。

小猴爱玩水。它打翻了水桶，地板湿了一大片。妈妈没有骂它，递过一块抹布：“自己擦干净吧。”小猴擦完了，满头大汗。妈妈说：“犯错了要自己负责，这才是好孩子。”小猴记住了。以后它拿杯子都很小心，还主动帮妈妈浇花。它学着用刀切西瓜，分给全家吃。小猴说：“刀很锋利，要小心用呢。米和面能做饭，水能解渴，每样东西都有用。”它还学会了写数字，会用元角分买东西。

青蛙蹲在荷叶上唱着歌。小鱼游过来听，小虾也来凑热闹。青蛙唱完了问：“好听吗？”小鱼吐着泡泡：“再唱一首吧，我们还没听够呢。”青蛙又唱：“夏天夏天真美丽，荷花荷花笑嘻嘻，晚风吹来凉丝丝。”蜻蜓停在它头上当听众。晚风吹来了，大家都很快乐。青蛙还教小鱼认字，在水面上写“禾”“米”“面”。小鱼说：“原来禾苗种在水田里，我们吃的米饭就是从这里来的呀。”

小羊迷路了，站在岔路口哭。黄牛伯伯路过问：“别哭，你家在哪个方向？”小羊指东方：“那边有条小河。”黄牛说：“我带你回去。”路上小羊采了一束野花送给黄牛。到家后羊妈妈感谢黄牛，留它吃晚饭。小羊学会了用尺子量脚印，记住回家的路。它说：“眼睛能看路，脚能走路，耳朵能听声音，都要好好保护。”第二天上学，小羊把这件事写在了日记本上，老师给了个优。

小猪爱睡懒觉，太阳晒屁股了也不起来。公鸡喔喔叫着它起床，它翻个身继续睡。妈妈掀开被子说：“早起才能看到晨露呢，很美很美。”小猪揉揉眼睛，走出了门。露珠在花瓣上闪闪发光，像珍珠一样。小猪第一次觉得早晨这么美。它还用鼻子拱了拱土，种下了几粒玉米种子。小猪说：“秋天就能吃到自己种的粮食啦。粮食就是米和面，可不能浪费。”它还学会了认钟表，早上六点半就起床了。

小鸭和天鹅交上了朋友。天鹅会飞，飞得很高，小鸭不会飞，很难过。天鹅说：“你会游泳呀，游得比我快，还能潜水抓鱼呢。各有各的长处嘛。”小鸭下了水，给天鹅表演潜水和抓鱼，抓了一条大鱼。天鹅鼓着掌说：“你真厉害！”它们成了最好的朋友，谁也不羡慕谁了。小鸭还做了一艘小舟，请天鹅站在舟上，用嘴推着舟在水面上滑行。天鹅说：“你真是个发明家。”

小鹿帮花猫找毛线球。花猫急得团团转，把屋子都翻遍了。小鹿低下头用鼻子闻了闻，在沙发下面找到了。花猫谢了它，送给它一条小鱼干。小鹿说：“不用谢呀，看到你开心我就开心，朋友就应该互相帮忙呢。”它们一起玩起了毛线球，你追我赶的。小鹿还拿出了一把尺子，量了量毛线有多长。花猫说：“你做事真认真呀。”小鹿说：“尺子可以量长短，眼睛可以看远近，都要用起来呢。”

小狮子怕打针，一看到针筒就哭。它生病了，妈妈带它去医院，它不肯进去。医生叔叔轻轻一扎，小狮子咬着牙没哭，眼泪在眼眶里转。医生夸它勇敢，奖励了一颗甜甜的糖果。小狮子回家告诉爸爸：“打针只有一点点疼，就像蚊子咬一样，以后我再也不怕啦。”爸爸竖起了大拇指。小狮子还学会了用刀削苹果，削给妈妈吃。妈妈说：“你真懂事。刀用好了能帮忙，用不好会伤手，要小心。”

小羊和好朋友吵了一架，谁也不理谁了。它难过地坐在河边，看着流水发呆。小鱼跃出水面说：“去道歉吧，朋友比面子重要呢，失去了朋友才后悔呀。”小羊鼓起勇气，找到朋友说了一声“对不起”。朋友也认了错，两个抱在一起哭了又笑。它们一起堆起了沙堡，比从前更好了。小羊还摘了一把稻穗，说：“禾苗结出了稻谷，碾成米就能做饭了。朋友就像米一样，天天都需要。”

小马想学踢足球，可是总踢不准。它追着球跑，球却滚到了别处，急得直跺脚。小狗旺旺教它：“用脚尖踢，看准方向，身体要稳当。”小马练了一下午，满头大汗，终于把球踢进了门。它高兴得扬起了前蹄。小狗说：“你进步真快呀，再练几天就能比赛啦。”小马说：“多亏了你教我，下次我教你跑步吧，我们互相帮助。”它们还比赛了跑步，小马用足飞奔。小狗说：“你的足真有力。”

小鸡捡到了一颗蛋，圆圆的，白白的，不知道是谁的。它问鸭妈妈，鸭妈妈摇了摇头；问鹅妈妈，鹅妈妈也摇了摇头；问鸟妈妈，鸟妈妈也说不是。小鸡把蛋放在暖草里，日夜守着它，连觉都不睡了。几天后蛋裂开了，钻出了一只毛茸茸的小鸟。鸟妈妈飞来接走了孩子，连声道谢。小鸡虽然有点不舍，但心里觉得暖暖的，它知道自己做了一件好事。它还种了一行禾苗，每天浇水。

小兔和妈妈去赶集了。集市上热闹极了，有人卖糖葫芦，红红的亮亮的，小兔很想吃。妈妈给了钱，小兔买了两串，一串递给了妈妈。妈妈咬了一口说：“又酸又甜的，真好吃。”小兔说：“分享更快乐嘛，两个人吃比一个人吃开心。”回家路上小兔看到了一只流浪猫，瘦瘦的，就分了半串给它。妈妈夸她心肠好，是个善良的好孩子。小兔还看见了一个木匠用尺子量木头，用锯子锯，用刨子刨。"""


# ========================== 使用示例（独立运行） ==========================
if __name__ == "__main__":
    # ---------- 示例1：原有单个汉字重复练习 ----------
    config1 = CalligraphyConfig(
        char_list=list(DEMO_HANZI_STR),  # 使用导出的汉字字符串
        gray_factor=0.2,
        cols_per_row=16,
        title="幼小衔接练字帖",
        margin_mm=12,
        dpi=300,
        char_font_ratio=0.75
    )   
    gen1 = CalligraphyGenerator(config1)
    gen1.generate_pdf()   # 桌面生成 "练字字帖.pdf"

    # ---------- 示例2：文章字帖（自动填满每页）----------
    config2 = CalligraphyConfig(
        char_list=["占"],  # 占位
        gray_factor=0.25,
        cols_per_row=16,
        title="经典古诗练习",
        margin_mm=10,
        dpi=300,
        char_font_ratio=0.7
    )
    gen2 = CalligraphyGenerator(config2)
    gen2.generate_article_pdf(DEMO_ARTICLE)   # 桌面生成 "诗歌文章练字字帖.pdf"

    # ---------- 示例3：多故事字帖（自动填满每页，每个故事强制分页）----------
    config3 = CalligraphyConfig(
        char_list=["占"],
        gray_factor=0.25,
        cols_per_row=16,
        title="小故事练字合集",
        margin_mm=10,
        dpi=300,
        char_font_ratio=0.7
    )
    gen3 = CalligraphyGenerator(config3)
    gen3.generate_stories_pdf(DEMO_STORIES, strip_star=True)