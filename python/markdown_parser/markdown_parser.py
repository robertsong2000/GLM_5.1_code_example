"""
Markdown 解析器 — 测试字符串处理、递归、AST 构建

采用经典的 Lexer → Parser → AST → Renderer 三阶段架构：
  Markdown 文本 → Block 解析 → 行内递归解析 → AST → HTML

支持的语法：
  块级：标题(#~######)、代码块(```)、有序/无序列表、引用(>)、分割线(---)、段落
  行内：加粗(**/***)、斜体(*)、行内代码(`)、链接、图片、换行

使用方式：
  python3 markdown_parser.py
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Optional, Union


# ============================================================
# 1. AST 节点定义
# ============================================================

@dataclass
class Text:
    """纯文本节点"""
    content: str


@dataclass
class Bold:
    """加粗文本节点"""
    children: list[InlineNode]


@dataclass
class Italic:
    """斜体文本节点"""
    children: list[InlineNode]


@dataclass
class Code:
    """行内代码节点"""
    content: str


@dataclass
class Link:
    """链接节点"""
    text: list[InlineNode]
    url: str


@dataclass
class Image:
    """图片节点"""
    alt: str
    url: str


@dataclass
class LineBreak:
    """换行节点"""
    pass


# 行内节点联合类型
InlineNode = Union[Text, Bold, Italic, Code, Link, Image, LineBreak]


@dataclass
class Heading:
    """标题节点"""
    level: int          # 1 ~ 6
    children: list[InlineNode]


@dataclass
class Paragraph:
    """段落节点"""
    children: list[InlineNode]


@dataclass
class CodeBlock:
    """代码块节点"""
    language: str       # 语言标识（可为空）
    content: str        # 原始代码内容


@dataclass
class BlockQuote:
    """引用块节点"""
    children: list[BlockNode]    # 可嵌套块级元素


@dataclass
class ListItem:
    """列表项节点"""
    children: list[InlineNode]


@dataclass
class OrderedList:
    """有序列表节点"""
    items: list[ListItem]


@dataclass
class UnorderedList:
    """无序列表节点"""
    items: list[ListItem]


@dataclass
class HorizontalRule:
    """分割线节点"""
    pass


@dataclass
class TableCell:
    """表格单元格节点"""
    children: list[InlineNode]
    align: str = ''        # 'left' / 'center' / 'right' / ''


@dataclass
class TableRow:
    """表格行节点"""
    cells: list[TableCell]


@dataclass
class Table:
    """表格节点"""
    header: TableRow       # 表头行
    rows: list[TableRow]   # 数据行


@dataclass
class Document:
    """文档根节点"""
    children: list[BlockNode]


# 块级节点联合类型
BlockNode = Union[Heading, Paragraph, CodeBlock, BlockQuote,
                  OrderedList, UnorderedList, HorizontalRule, Table, Document]


# ============================================================
# 2. 块级解析器 — 将 Markdown 文本拆分为块级元素
# ============================================================

class BlockParser:
    """块级解析器：按行扫描识别块级结构"""

    def __init__(self, text: str) -> None:
        self.lines = text.split('\n')
        self.pos = 0    # 当前行位置

    # ---------- 工具方法 ----------

    def _current_line(self) -> Optional[str]:
        if self.pos < len(self.lines):
            return self.lines[self.pos]
        return None

    def _advance(self, n: int = 1) -> None:
        self.pos += n

    # ---------- 主入口 ----------

    def parse(self) -> Document:
        """解析完整文档，返回 AST 根节点"""
        children: list[BlockNode] = []
        while self.pos < len(self.lines):
            node = self._parse_block()
            if node is not None:
                children.append(node)
        return Document(children=children)

    # ---------- 块级元素分派 ----------

    def _parse_block(self) -> Optional[BlockNode]:
        line = self._current_line()
        if line is None:
            return None

        stripped = line.strip()

        # 空行跳过
        if stripped == '':
            self._advance()
            return None

        # 代码块 — 最高优先级
        if stripped.startswith('```'):
            return self._parse_code_block()

        # 标题
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if heading_match:
            self._advance()
            level = len(heading_match.group(1))
            inline_text = heading_match.group(2)
            return Heading(level=level,
                           children=InlineParser(inline_text).parse())

        # 分割线（--- / *** / ___，至少3个字符）
        if re.match(r'^(\*{3,}|-{3,}|_{3,})$', stripped):
            self._advance()
            return HorizontalRule()

        # 引用块
        if stripped.startswith('>'):
            return self._parse_blockquote()

        # 无序列表（- / * / + 后跟空格）
        if re.match(r'^[-*+]\s', stripped):
            return self._parse_unordered_list()

        # 有序列表（1. 后跟空格）
        if re.match(r'^\d+\.\s', stripped):
            return self._parse_ordered_list()

        # 表格（以 | 开头，下一行为分隔行 |---|---|）
        if stripped.startswith('|') and self._is_table_start():
            return self._parse_table()

        # 默认：段落
        return self._parse_paragraph()

    # ---------- 各块级元素解析 ----------

    def _parse_code_block(self) -> CodeBlock:
        """解析围栏代码块 ```lang ... ```"""
        current = self._current_line()
        assert current is not None
        opening = current.strip()
        # 提取语言标识
        language = opening[3:].strip()
        self._advance()

        content_lines: list[str] = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is not None and line.strip() == '```':
                self._advance()
                break
            if line is not None:
                content_lines.append(line)
            else:
                content_lines.append('')
            self._advance()

        return CodeBlock(language=language, content='\n'.join(content_lines))

    def _parse_blockquote(self) -> BlockQuote:
        """解析引用块，收集连续 > 开头的行"""
        quote_lines: list[str] = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is None:
                break
            stripped = line.strip()
            if not stripped.startswith('>'):
                break
            # 去掉前缀 >
            content = stripped[1:]
            if content.startswith(' '):
                content = content[1:]
            quote_lines.append(content)
            self._advance()

        # 递归解析引用内容为块级元素
        inner_text = '\n'.join(quote_lines)
        inner_doc = BlockParser(inner_text).parse()
        return BlockQuote(children=inner_doc.children)

    def _parse_unordered_list(self) -> UnorderedList:
        """解析无序列表"""
        items: list[ListItem] = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is None:
                break
            stripped = line.strip()
            if not re.match(r'^[-*+]\s', stripped):
                break
            # 去掉列表标记
            item_text = re.sub(r'^[-*+]\s+', '', stripped)
            items.append(ListItem(
                children=InlineParser(item_text).parse()
            ))
            self._advance()
        return UnorderedList(items=items)

    def _parse_ordered_list(self) -> OrderedList:
        """解析有序列表"""
        items: list[ListItem] = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is None:
                break
            stripped = line.strip()
            if not re.match(r'^\d+\.\s', stripped):
                break
            # 去掉序号标记
            item_text = re.sub(r'^\d+\.\s+', '', stripped)
            items.append(ListItem(
                children=InlineParser(item_text).parse()
            ))
            self._advance()
        return OrderedList(items=items)

    def _parse_paragraph(self) -> Paragraph:
        """解析段落 — 连续非空行合并"""
        text_lines: list[str] = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is None:
                break
            stripped = line.strip()
            if stripped == '':
                break
            # 如果遇到其他块级元素的开头，停止
            if (stripped.startswith('```')
                    or re.match(r'^#{1,6}\s', stripped)
                    or re.match(r'^(\*{3,}|-{3,}|_{3,})$', stripped)
                    or re.match(r'^[-*+]\s', stripped)
                    or re.match(r'^\d+\.\s', stripped)
                    or stripped.startswith('>')):
                break
            text_lines.append(stripped)
            self._advance()

        full_text = ' '.join(text_lines)
        return Paragraph(children=InlineParser(full_text).parse())

    # ---------- 表格解析 ----------

    @staticmethod
    def _split_table_row(line: str) -> list[str]:
        """将 | cell1 | cell2 | 拆分为 ['cell1', 'cell2']"""
        cells = line.strip().strip('|').split('|')
        return [c.strip() for c in cells]

    def _is_table_start(self) -> bool:
        """判断当前行是否为表格起始行（下一行需为分隔行 |---|---|）"""
        next_idx = self.pos + 1
        if next_idx >= len(self.lines):
            return False
        next_line = self.lines[next_idx].strip()
        # 分隔行：由 |、-、:、空格组成，至少含一段连续的 ---
        return bool(re.match(r'^[\s|:\-]+$', next_line)
                    and '---' in next_line)

    @staticmethod
    def _parse_align(separator: str) -> list[str]:
        """从分隔行解析每列对齐方式，如 | :--- | :---: | ---: | → ['left','center','right']"""
        parts = separator.strip().strip('|').split('|')
        aligns: list[str] = []
        for part in parts:
            p = part.strip()
            if p.startswith(':') and p.endswith(':'):
                aligns.append('center')
            elif p.endswith(':'):
                aligns.append('right')
            elif p.startswith(':'):
                aligns.append('left')
            else:
                aligns.append('')
        return aligns

    def _parse_table(self) -> Table:
        """解析 Markdown 表格"""
        # 第一行：表头
        header_line = self._current_line()
        assert header_line is not None
        header_cells = self._split_table_row(header_line)
        self._advance()

        # 第二行：分隔符（确定对齐方式）
        separator = self._current_line()
        assert separator is not None
        aligns = self._parse_align(separator)
        self._advance()

        # 补齐对齐信息
        while len(aligns) < len(header_cells):
            aligns.append('')

        # 构建表头行
        header = TableRow(cells=[
            TableCell(children=InlineParser(text).parse(), align=aligns[i])
            for i, text in enumerate(header_cells)
        ])

        # 解析数据行
        rows: list[TableRow] = []
        while self.pos < len(self.lines):
            line = self._current_line()
            if line is None:
                break
            stripped = line.strip()
            if not stripped.startswith('|'):
                break
            cells = self._split_table_row(stripped)
            row = TableRow(cells=[
                TableCell(children=InlineParser(text).parse(), align=aligns[i] if i < len(aligns) else '')
                for i, text in enumerate(cells)
            ])
            rows.append(row)
            self._advance()

        return Table(header=header, rows=rows)


# ============================================================
# 3. 行内解析器 — 递归下降解析行内 Markdown 元素
# ============================================================

class InlineParser:
    """
    递归下降行内解析器

    通过光标位置逐字符扫描，遇到特殊标记时递归解析对应的行内结构。
    解析优先级（从高到低）：行内代码 > 图片 > 链接 > 加粗+斜体 > 加粗 > 斜体 > 换行
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.length = len(text)

    def parse(self) -> list[InlineNode]:
        """解析整段行内文本，返回节点列表"""
        nodes: list[InlineNode] = []
        while self.pos < self.length:
            node = self._parse_next()
            if node is not None:
                nodes.append(node)
        return nodes

    # ---------- 辅助方法 ----------

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx < self.length:
            return self.text[idx]
        return ''

    def _starts_with(self, s: str) -> bool:
        return self.text[self.pos:self.pos + len(s)] == s

    def _find_closing(self, marker: str, start: int) -> int:
        """从 start 位置查找闭合标记，返回其起始位置"""
        idx = start
        while idx <= self.length - len(marker):
            if self.text[idx:idx + len(marker)] == marker:
                return idx
            idx += 1
        return -1

    # ---------- 解析分派 ----------

    def _parse_next(self) -> Optional[InlineNode]:
        ch = self._peek()

        # 行内代码 `code`
        if ch == '`':
            return self._parse_inline_code()

        # 图片 ![alt](url)
        if ch == '!' and self._starts_with('!['):
            return self._parse_image()

        # 链接 [text](url)
        if ch == '[':
            return self._parse_link()

        # 加粗+斜体 ***text***
        if self._starts_with('***'):
            return self._parse_bold_italic()

        # 加粗 **text** 或 __text__
        if self._starts_with('**') or self._starts_with('__'):
            return self._parse_bold()

        # 斜体 *text* 或 _text_（需避免与列表标记混淆）
        if ch in ('*', '_'):
            return self._parse_italic()

        # 换行（行尾双空格或反斜杠）
        if ch == '\\' and self._peek(1) == '\n':
            self.pos += 2
            return LineBreak()
        if ch == ' ' and self._peek(1) == ' ' and (
                self.pos + 2 >= self.length or self._peek(2) == '\n'):
            self.pos += 2
            if self.pos < self.length and self._peek() == '\n':
                self.pos += 1
            return LineBreak()

        # 普通文本
        return self._parse_text()

    # ---------- 各行内元素解析 ----------

    def _parse_inline_code(self) -> InlineNode:
        """解析行内代码 `code`"""
        self.pos += 1  # 跳过开头 `
        start = self.pos
        while self.pos < self.length and self.text[self.pos] != '`':
            self.pos += 1
        content = self.text[start:self.pos]
        if self.pos < self.length:
            self.pos += 1  # 跳过结尾 `
        return Code(content=content)

    def _parse_image(self) -> InlineNode:
        """解析图片 ![alt](url)"""
        self.pos += 2  # 跳过 ![
        alt_start = self.pos
        while self.pos < self.length and self.text[self.pos] != ']':
            self.pos += 1
        alt = self.text[alt_start:self.pos]
        self.pos += 1  # 跳过 ]

        # 查找 (url)
        url = ''
        if self.pos < self.length and self.text[self.pos] == '(':
            self.pos += 1
            url_start = self.pos
            while self.pos < self.length and self.text[self.pos] != ')':
                url += self.text[self.pos]
                self.pos += 1
            if self.pos < self.length:
                self.pos += 1  # 跳过 )

        return Image(alt=alt, url=url)

    def _parse_link(self) -> InlineNode:
        """解析链接 [text](url)"""
        self.pos += 1  # 跳过 [
        text_start = self.pos
        while self.pos < self.length and self.text[self.pos] != ']':
            self.pos += 1
        link_text = self.text[text_start:self.pos]
        self.pos += 1  # 跳过 ]

        # 查找 (url)
        url = ''
        if self.pos < self.length and self.text[self.pos] == '(':
            self.pos += 1
            url_start = self.pos
            while self.pos < self.length and self.text[self.pos] != ')':
                url += self.text[self.pos]
                self.pos += 1
            if self.pos < self.length:
                self.pos += 1  # 跳过 )

        # 递归解析链接文本中的行内格式
        text_nodes = InlineParser(link_text).parse()
        return Link(text=text_nodes, url=url)

    def _parse_bold_italic(self) -> InlineNode:
        """解析加粗+斜体 ***text***"""
        self.pos += 3  # 跳过 ***
        end = self._find_closing('***', self.pos)
        if end == -1:
            # 未找到闭合，回退为普通文本
            self.pos -= 2
            return self._parse_text()

        inner = self.text[self.pos:end]
        self.pos = end + 3
        inner_nodes = InlineParser(inner).parse()
        return Bold(children=[Italic(children=inner_nodes)])

    def _parse_bold(self) -> InlineNode:
        """解析加粗 **text** 或 __text__"""
        marker = self.text[self.pos:self.pos + 2]
        self.pos += 2
        end = self._find_closing(marker, self.pos)
        if end == -1:
            # 未找到闭合，回退为普通文本
            self.pos -= 1
            return self._parse_text()

        inner = self.text[self.pos:end]
        self.pos = end + 2
        inner_nodes = InlineParser(inner).parse()
        return Bold(children=inner_nodes)

    def _parse_italic(self) -> InlineNode:
        """解析斜体 *text* 或 _text_

        遵循 CommonMark 规则：当标记符为 _ 时，只有前后都是单词边界
        （空格、行首/尾、标点）才触发斜体，避免 merge_k_sorted 中的 _ 被误解析。
        """
        marker = self.text[self.pos]

        # _ 在单词中间（前后都是字母/数字）时不触发斜体
        if marker == '_':
            before = self.text[self.pos - 1] if self.pos > 0 else ' '
            after = self.text[self.pos + 1] if self.pos + 1 < self.length else ' '
            if before.isalnum() and after.isalnum():
                return self._parse_text()

        self.pos += 1

        # 查找闭合标记
        end = -1
        idx = self.pos
        while idx < self.length:
            if self.text[idx] == marker:
                # 确保不是 ** 或 __ 的一部分
                if idx + 1 < self.length and self.text[idx + 1] == marker:
                    idx += 2
                    continue
                end = idx
                break
            idx += 1

        if end == -1:
            # 未找到闭合，回退为普通文本
            self.pos -= 1
            return self._parse_text()

        inner = self.text[self.pos:end]
        self.pos = end + 1
        inner_nodes = InlineParser(inner).parse()
        return Italic(children=inner_nodes)

    def _parse_text(self) -> InlineNode:
        """解析纯文本，直到遇到特殊字符或末尾

        保证至少消费一个字符，防止调用方回退光标后造成死循环。
        """
        special = set('`*[!_\\')
        start = self.pos
        # 至少消费一个字符（可能是未匹配的特殊字符，如孤立的 _ 或 *）
        if self.pos < self.length:
            self.pos += 1
        while self.pos < self.length:
            if self.text[self.pos] in special:
                break
            # 检查双空格换行
            if (self.text[self.pos] == ' '
                    and self.pos + 1 < self.length
                    and self.text[self.pos + 1] == ' '
                    and (self.pos + 2 >= self.length
                         or self.text[self.pos + 2] == '\n')):
                break
            self.pos += 1
        return Text(content=self.text[start:self.pos])


# ============================================================
# 4. HTML 渲染器 — 遍历 AST 生成 HTML
# ============================================================

class HTMLRenderer:
    """将 AST 渲染为 HTML 字符串"""

    def render(self, doc: Document) -> str:
        """渲染整个文档"""
        parts = [self._render_block(child) for child in doc.children]
        return '\n'.join(parts)

    # ---------- 块级节点渲染 ----------

    def _render_block(self, node: BlockNode) -> str:
        if isinstance(node, Heading):
            tag = f'h{node.level}'
            inner = self._render_inline_list(node.children)
            return f'<{tag}>{inner}</{tag}>'

        if isinstance(node, Paragraph):
            inner = self._render_inline_list(node.children)
            return f'<p>{inner}</p>'

        if isinstance(node, CodeBlock):
            lang_attr = f' class="language-{node.language}"' if node.language else ''
            escaped = (node.content
                       .replace('&', '&amp;')
                       .replace('<', '&lt;')
                       .replace('>', '&gt;')
                       .replace('"', '&quot;'))
            return f'<pre><code{lang_attr}>{escaped}</code></pre>'

        if isinstance(node, BlockQuote):
            inner = '\n'.join(self._render_block(c) for c in node.children)
            return f'<blockquote>\n{inner}\n</blockquote>'

        if isinstance(node, UnorderedList):
            items = '\n'.join(
                f'<li>{self._render_inline_list(item.children)}</li>'
                for item in node.items
            )
            return f'<ul>\n{items}\n</ul>'

        if isinstance(node, OrderedList):
            items = '\n'.join(
                f'<li>{self._render_inline_list(item.children)}</li>'
                for item in node.items
            )
            return f'<ol>\n{items}\n</ol>'

        if isinstance(node, HorizontalRule):
            return '<hr>'

        if isinstance(node, Table):
            return self._render_table(node)

        return ''

    # ---------- 表格渲染 ----------

    def _render_table(self, table: Table) -> str:
        """渲染表格为 HTML"""
        lines: list[str] = ['<table>']

        # 表头
        lines.append('<thead>')
        lines.append('<tr>')
        for cell in table.header.cells:
            align_attr = f' style="text-align:{cell.align}"' if cell.align else ''
            inner = self._render_inline_list(cell.children)
            lines.append(f'<th{align_attr}>{inner}</th>')
        lines.append('</tr>')
        lines.append('</thead>')

        # 数据行
        if table.rows:
            lines.append('<tbody>')
            for row in table.rows:
                lines.append('<tr>')
                for cell in row.cells:
                    align_attr = f' style="text-align:{cell.align}"' if cell.align else ''
                    inner = self._render_inline_list(cell.children)
                    lines.append(f'<td{align_attr}>{inner}</td>')
                lines.append('</tr>')
            lines.append('</tbody>')

        lines.append('</table>')
        return '\n'.join(lines)

    # ---------- 行内节点渲染 ----------

    def _render_inline(self, node: InlineNode) -> str:
        if isinstance(node, Text):
            return node.content

        if isinstance(node, Bold):
            inner = self._render_inline_list(node.children)
            return f'<strong>{inner}</strong>'

        if isinstance(node, Italic):
            inner = self._render_inline_list(node.children)
            return f'<em>{inner}</em>'

        if isinstance(node, Code):
            escaped = (node.content
                       .replace('&', '&amp;')
                       .replace('<', '&lt;')
                       .replace('>', '&gt;'))
            return f'<code>{escaped}</code>'

        if isinstance(node, Link):
            inner = self._render_inline_list(node.text)
            return f'<a href="{node.url}">{inner}</a>'

        if isinstance(node, Image):
            return f'<img src="{node.url}" alt="{node.alt}">'

        if isinstance(node, LineBreak):
            return '<br>'

        return ''

    def _render_inline_list(self, nodes: list[InlineNode]) -> str:
        return ''.join(self._render_inline(n) for n in nodes)


# ============================================================
# 5. 公共 API
# ============================================================

def parse_markdown(text: str) -> Document:
    """解析 Markdown 文本，返回 AST"""
    return BlockParser(text).parse()


def markdown_to_html(text: str) -> str:
    """将 Markdown 文本转换为 HTML 片段"""
    doc = parse_markdown(text)
    return HTMLRenderer().render(doc)


def markdown_to_html_file(md_text: str, output_path: str, title: str = 'Markdown') -> None:
    """将 Markdown 文本转换为完整的 HTML 文件并写入磁盘

    Args:
        md_text:    Markdown 原始文本
        output_path: 输出 HTML 文件路径
        title:      页面 <title> 内容
    """
    body = markdown_to_html(md_text)
    html = textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    max-width: 800px;
                    margin: 2rem auto;
                    padding: 0 1rem;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                code {{
                    background: #f4f4f4;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.9em;
                }}
                pre {{
                    background: #f4f4f4;
                    padding: 1rem;
                    border-radius: 6px;
                    overflow-x: auto;
                }}
                pre code {{
                    background: none;
                    padding: 0;
                }}
                blockquote {{
                    border-left: 4px solid #ddd;
                    margin: 0;
                    padding-left: 1rem;
                    color: #666;
                }}
                hr {{
                    border: none;
                    border-top: 1px solid #ddd;
                    margin: 2rem 0;
                }}
                img {{
                    max-width: 100%;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1rem 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px 12px;
                    text-align: left;
                }}
                th {{
                    background: #f6f6f6;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{
                    background: #fafafa;
                }}
            </style>
        </head>
        <body>
        {body}
        </body>
        </html>""")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'已生成: {output_path}')


# ============================================================
# 6. 测试用例
# ============================================================

def _assert_eq(test_name: str, actual: str, expected: str) -> None:
    """辅助断言函数"""
    # 标准化空白字符后比较
    actual_normalized = actual.strip()
    expected_normalized = expected.strip()
    if actual_normalized == expected_normalized:
        print(f'  ✓ {test_name}')
    else:
        print(f'  ✗ {test_name}')
        print(f'    期望: {expected_normalized!r}')
        print(f'    实际: {actual_normalized!r}')


def run_tests() -> None:
    """运行所有测试用例"""
    print('=' * 60)
    print('Markdown 解析器测试')
    print('=' * 60)

    # ---- 1. 标题测试 ----
    print('\n[标题测试]')
    _assert_eq(
        'H1 标题',
        markdown_to_html('# Hello World'),
        '<h1>Hello World</h1>',
    )
    _assert_eq(
        'H3 标题',
        markdown_to_html('### Section'),
        '<h3>Section</h3>',
    )
    _assert_eq(
        'H6 标题',
        markdown_to_html('###### Deep Heading'),
        '<h6>Deep Heading</h6>',
    )

    # ---- 2. 行内格式测试 ----
    print('\n[行内格式测试]')
    _assert_eq(
        '加粗',
        markdown_to_html('This is **bold** text'),
        '<p>This is <strong>bold</strong> text</p>',
    )
    _assert_eq(
        '斜体',
        markdown_to_html('This is *italic* text'),
        '<p>This is <em>italic</em> text</p>',
    )
    _assert_eq(
        '加粗+斜体',
        markdown_to_html('This is ***bold italic*** text'),
        '<p>This is <strong><em>bold italic</em></strong> text</p>',
    )
    _assert_eq(
        '行内代码',
        markdown_to_html('Use the `print()` function'),
        '<p>Use the <code>print()</code> function</p>',
    )

    # ---- 3. 链接和图片测试 ----
    print('\n[链接和图片测试]')
    _assert_eq(
        '链接',
        markdown_to_html('[Click here](https://example.com)'),
        '<p><a href="https://example.com">Click here</a></p>',
    )
    _assert_eq(
        '图片',
        markdown_to_html('![Logo](/images/logo.png)'),
        '<p><img src="/images/logo.png" alt="Logo"></p>',
    )
    _assert_eq(
        '链接中含格式',
        markdown_to_html('[**Bold Link**](https://example.com)'),
        '<p><a href="https://example.com"><strong>Bold Link</strong></a></p>',
    )

    # ---- 4. 列表测试 ----
    print('\n[列表测试]')
    _assert_eq(
        '无序列表',
        markdown_to_html('- Apple\n- Banana\n- Cherry'),
        '<ul>\n<li>Apple</li>\n<li>Banana</li>\n<li>Cherry</li>\n</ul>',
    )
    _assert_eq(
        '有序列表',
        markdown_to_html('1. First\n2. Second\n3. Third'),
        '<ol>\n<li>First</li>\n<li>Second</li>\n<li>Third</li>\n</ol>',
    )
    _assert_eq(
        '列表含行内格式',
        markdown_to_html('- **Bold item**\n- *Italic item*'),
        '<ul>\n<li><strong>Bold item</strong></li>\n<li><em>Italic item</em></li>\n</ul>',
    )

    # ---- 5. 代码块测试 ----
    print('\n[代码块测试]')
    _assert_eq(
        '代码块（无语言）',
        markdown_to_html('```\nhello world\n```'),
        '<pre><code>hello world</code></pre>',
    )
    _assert_eq(
        '代码块（带语言）',
        markdown_to_html('```python\nprint("Hello")\n```'),
        '<pre><code class="language-python">print(&quot;Hello&quot;)</code></pre>',
    )
    _assert_eq(
        '代码块保留 HTML 特殊字符',
        markdown_to_html('```\n<div>foo</div>\n```'),
        '<pre><code>&lt;div&gt;foo&lt;/div&gt;</code></pre>',
    )

    # ---- 6. 引用块测试 ----
    print('\n[引用块测试]')
    _assert_eq(
        '简单引用',
        markdown_to_html('> This is a quote'),
        '<blockquote>\n<p>This is a quote</p>\n</blockquote>',
    )
    _assert_eq(
        '多行引用',
        markdown_to_html('> Line 1\n> Line 2'),
        '<blockquote>\n<p>Line 1 Line 2</p>\n</blockquote>',
    )

    # ---- 7. 分割线测试 ----
    print('\n[分割线测试]')
    _assert_eq(
        '分割线 ---',
        markdown_to_html('---'),
        '<hr>',
    )
    _assert_eq(
        '分割线 ***',
        markdown_to_html('***'),
        '<hr>',
    )

    # ---- 8. 段落测试 ----
    print('\n[段落测试]')
    _assert_eq(
        '简单段落',
        markdown_to_html('Hello world'),
        '<p>Hello world</p>',
    )
    _assert_eq(
        '多行合并为段落',
        markdown_to_html('Line 1\nLine 2'),
        '<p>Line 1 Line 2</p>',
    )
    _assert_eq(
        '多段落',
        markdown_to_html('Paragraph 1\n\nParagraph 2'),
        '<p>Paragraph 1</p>\n<p>Paragraph 2</p>',
    )

    # ---- 9. 空输入测试 ----
    print('\n[边界测试]')
    _assert_eq(
        '空输入',
        markdown_to_html(''),
        '',
    )
    _assert_eq(
        '仅空行',
        markdown_to_html('\n\n\n'),
        '',
    )
    _assert_eq(
        '混合空白',
        markdown_to_html('  # Title  '),
        '<h1>Title</h1>',
    )

    # ---- 10. 综合文档测试 ----
    print('\n[综合文档测试]')
    complex_md = textwrap.dedent("""\
        # My Document

        This is a **bold** paragraph with *italic* and `code`.

        ## Features

        - Item one with **bold**
        - Item two with [a link](https://example.com)

        > A wise man once said something.

        ---

        1. First step
        2. Second step
    """)
    result = markdown_to_html(complex_md)
    assert '<h1>My Document</h1>' in result, '综合文档应包含 H1'
    assert '<h2>Features</h2>' in result, '综合文档应包含 H2'
    assert '<strong>bold</strong>' in result, '综合文档应包含加粗'
    assert '<em>italic</em>' in result, '综合文档应包含斜体'
    assert '<code>code</code>' in result, '综合文档应包含行内代码'
    assert '<ul>' in result, '综合文档应包含无序列表'
    assert '<a href="https://example.com">' in result, '综合文档应包含链接'
    assert '<blockquote>' in result, '综合文档应包含引用'
    assert '<hr>' in result, '综合文档应包含分割线'
    assert '<ol>' in result, '综合文档应包含有序列表'
    print('  ✓ 综合文档解析正确')

    # ---- 11. AST 结构验证 ----
    print('\n[AST 结构验证]')
    doc = parse_markdown('# Title\n\nHello **world**\n\n- Item 1')
    assert isinstance(doc, Document), '根节点应为 Document'
    assert len(doc.children) == 3, f'应有 3 个子节点，实际 {len(doc.children)}'
    assert isinstance(doc.children[0], Heading), '第一个应为 Heading'
    assert doc.children[0].level == 1, '标题级别应为 1'
    assert isinstance(doc.children[1], Paragraph), '第二个应为 Paragraph'
    assert isinstance(doc.children[2], UnorderedList), '第三个应为 UnorderedList'
    print('  ✓ AST 结构正确')

    # ---- 12. 递归嵌套测试 ----
    print('\n[递归嵌套测试]')
    nested_md = '**bold with *italic inside* text**'
    result = markdown_to_html(nested_md)
    _assert_eq(
        '加粗内嵌斜体',
        result,
        '<p><strong>bold with <em>italic inside</em> text</strong></p>',
    )

    # ---- 13. 表格测试 ----
    print('\n[表格测试]')
    _assert_eq(
        '简单表格',
        markdown_to_html('| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob | 25 |'),
        '<table>\n<thead>\n<tr>\n<th>Name</th>\n<th>Age</th>\n</tr>\n</thead>\n'
        '<tbody>\n<tr>\n<td>Alice</td>\n<td>30</td>\n</tr>\n<tr>\n<td>Bob</td>\n<td>25</td>\n</tr>\n</tbody>\n</table>',
    )
    _assert_eq(
        '表格含行内格式',
        markdown_to_html('| Col |\n|-----|\n| **bold** |'),
        '<table>\n<thead>\n<tr>\n<th>Col</th>\n</tr>\n</thead>\n'
        '<tbody>\n<tr>\n<td><strong>bold</strong></td>\n</tr>\n</tbody>\n</table>',
    )
    table_align_result = markdown_to_html('| Left | Center | Right |\n|:-----|:------:|------:|\n| L | C | R |')
    assert 'style="text-align:left"' in table_align_result, '表格应支持左对齐'
    assert 'style="text-align:center"' in table_align_result, '表格应支持居中对齐'
    assert 'style="text-align:right"' in table_align_result, '表格应支持右对齐'
    print('  ✓ 表格对齐方式')

    print('\n' + '=' * 60)
    print('所有测试完成!')
    print('=' * 60)


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 2:
        # 命令行模式：python3 markdown_parser.py input.md [output.html]
        input_path = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) >= 3 else input_path.rsplit('.', 1)[0] + '.html'
        with open(input_path, encoding='utf-8') as f:
            md_text = f.read()
        markdown_to_html_file(md_text, output_path, title=input_path)
    else:
        # 无参数时运行测试
        run_tests()
