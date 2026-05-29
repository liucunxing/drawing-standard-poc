# -*- coding: utf-8 -*-
"""
标准编号比对模块 (最终版)

功能:
1. 从 Markdown/HTML 表格文本中提取标准编号
2. 解析标准编号结构 (前缀/编号/年份)
3. 与标准库比对，输出比对结果
4. 支持: 完全符合、年份不一致、较为相似、不存在

使用方式:
    直接传入 Markdown 文本，模块自动提取标准编号并与标准库比对

日期: 2026-05-27
"""

import re
import json
from html.parser import HTMLParser
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

from backend.config.config import SQLManager


class MatchStatus(Enum):
    """比对结果状态"""
    EXACT_MATCH = "完全符合"
    YEAR_MISMATCH = "年份不一致"
    SIMILAR = "较为相似"
    NOT_FOUND = "不存在"
    PARSE_ERROR = "解析错误"


@dataclass
class StandardCode:
    """标准编号数据结构"""
    original: str          # 原始文本
    prefix: str            # 前缀 (GB, NB, HG, SY, JB 等)
    standard_type: str       # 标准类型 (GB/T, GB, NB/T 等)
    number: str            # 标准号数字部分
    year: str              # 年份
    has_T: bool            # 是否带 /T

    def to_dict(self):
        return asdict(self)


@dataclass
class MatchResult:
    """比对结果数据结构"""
    status: MatchStatus
    score: int
    extracted: StandardCode
    matched_library_entry: Optional[StandardCode]
    message: str

    def to_dict(self):
        return {
            'status': self.status.value,
            'score': self.score,
            'extracted': self.extracted.to_dict(),
            'matched_library_entry': self.matched_library_entry.to_dict() if self.matched_library_entry else None,
            'message': self.message
        }


class TableParser(HTMLParser):
    """HTML 表格解析器"""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ""
        self.in_table = False
        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr':
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self.in_cell = False
            cell_text = self.current_cell.strip()
            self.current_row.append(cell_text)
        elif tag == 'tr':
            self.in_row = False
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag == 'table':
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


class StandardCodeExtractor:

    def get_standard_list(self) -> List:
        select_sql = (
            f'SELECT distinct standard_no from standard_data'
        )

        with SQLManager() as db:
            total = db.get_list(select_sql)

            list = []
            if total:
                for standard in total:
                    list.append(
                        standard['standard_no']
                    )

        return list

    """标准编号提取器"""

    # ============================================================
    # 用户提供的标准前缀列表 (精确匹配)
    # ============================================================
    VALID_PREFIXES = {
        'AQ', 'C/TE', 'GB', 'GB/T', 'GBZ/T', 'HG', 'HG/T',
        'JB', 'JB/T', 'NB/T', 'Q/SH', 'SH/T', 'SY/T',
        'T/ES', 'TSG', 'YB/T'
    }

    # 构建正则表达式 - 按长度降序排列，避免短前缀匹配到长前缀的一部分
    _sorted_prefixes = sorted(VALID_PREFIXES, key=len, reverse=True)
    _prefix_pattern = '|'.join(re.escape(p) for p in _sorted_prefixes)

    # 标准编号正则表达式
    # 匹配模式: 前缀 + 可选空格 + 数字(可带小数点) + - + 年份
    STANDARD_PATTERN = re.compile(
        r'\b(' + _prefix_pattern + r')'
        r'\s*'
        r'(\d+(?:\.\d+)?)'
        r'[-–—]'
        r'(\d{4})'
        r'\b',
        re.IGNORECASE
    )

    def extract_from_markdown(self, markdown_text: str) -> List[Dict]:
        """
        从 Markdown 文本中提取标准编号（核心入口方法）
        
        整体流程:
        1. 尝试解析 HTML <table> 标签格式的表格
        2. 如果解析成功，从表格单元格中提取标准编号
        3. 如果解析失败，直接从纯文本中提取标准编号
        
        支持格式:
        - HTML <table> 标签格式
        - Markdown | 列1 | 列2 | 格式
        - 纯文本中的标准编号

        Args:
            markdown_text: Markdown 格式的表格文本，可能包含标准编号

        Returns:
            提取的标准编号列表，每个元素为字典:
            {
                'row': int,           # 行号
                'col': int,           # 列号
                'cell_text': str,     # 单元格原文
                'full_match': str,    # 完整匹配文本（如 "GB/T 150.1-2011"）
                'prefix': str,        # 前缀（如 GB/T）
                'has_T': bool,        # 是否带 /T
                'number': str,        # 标准号数字部分（如 "150.1"）
                'year': str,          # 年份（如 "2011"）
                'standard_type': str  # 标准类型（同 prefix）
            }
        """
        # 先尝试解析 HTML 表格
        parser = TableParser()
        parser.feed(markdown_text)

        if parser.tables:
            # 从 HTML 表格中提取
            return self._extract_from_table(parser.tables[0])
        else:
            # 直接从文本中提取
            return self._extract_from_text(markdown_text)

    def _extract_from_table(self, table_data: List[List[str]]) -> List[Dict]:
        """
        从表格数据中提取标准编号
        
        处理逻辑:
        遍历表格的每一行每一列，对每个单元格的内容使用正则表达式匹配标准编号格式
        如果匹配成功，解析匹配结果并记录位置信息（行号、列号）
        
        Args:
            table_data: 表格数据，二维列表结构 [[row1_col1, row1_col2], [row2_col1, row2_col2], ...]
            
        Returns:
            提取的标准编号列表，每个元素包含匹配信息和位置信息
        """
        results = []

        for row_idx, row in enumerate(table_data):
            for col_idx, cell in enumerate(row):
                matches = self.STANDARD_PATTERN.finditer(cell)
                for match in matches:
                    code_info = self._parse_match(match, row_idx, col_idx, cell)
                    if code_info:
                        results.append(code_info)

        return results

    def _extract_from_text(self, text: str) -> List[Dict]:
        """
        从纯文本中提取标准编号
        
        处理逻辑:
        当输入文本不是 HTML 表格格式时，直接在整个文本中搜索标准编号
        不使用行号列号定位，统一标记为 row=0, col=0
        
        Args:
            text: 纯文本内容，可能包含标准编号
            
        Returns:
            提取的标准编号列表
        """
        results = []

        matches = self.STANDARD_PATTERN.finditer(text)
        for match in matches:
            code_info = self._parse_match(match, 0, 0, text)
            if code_info:
                results.append(code_info)

        return results

    def _parse_match(self, match, row_idx: int, col_idx: int, cell_text: str) -> Optional[Dict]:
        """
        解析正则表达式匹配结果，提取标准编号的各部分信息
        
        处理逻辑:
        1. 从正则匹配对象中提取完整文本、前缀、数字部分、年份
        2. 将前缀转为大写，与合法前缀列表进行精确匹配
        3. 如果前缀不合法，返回 None（过滤无效匹配）
        4. 判断前缀是否包含 /T（推荐性标准）
        5. 组装成标准编号信息字典并返回
        
        Args:
            match: 正则表达式匹配对象
            row_idx: 行号（HTML表格中的位置）
            col_idx: 列号（HTML表格中的位置）
            cell_text: 单元格原始文本内容
            
        Returns:
            标准编号信息字典，如果前缀不合法则返回 None
        """
        full_match = match.group(0)
        prefix = match.group(1).upper()  # 转为大写统一处理

        # 找到标准格式的前缀
        found_prefix = None
        for valid_prefix in self.VALID_PREFIXES:
            if prefix == valid_prefix.upper():
                found_prefix = valid_prefix
                break

        if not found_prefix:
            return None

        # 判断是否有 /T (根据前缀本身判断)
        has_T = '/T' in found_prefix

        return {
            'row': row_idx,
            'col': col_idx,
            'cell_text': cell_text,
            'full_match': full_match,
            'prefix': found_prefix,  # 使用标准格式的前缀
            'has_T': has_T,
            'number': match.group(2),
            'year': match.group(3),
            'standard_type': found_prefix
        }

    def extract_unique_codes(self, markdown_text: str) -> List[str]:
        """
        提取唯一的标准编号列表（去重）
        
        处理逻辑:
        1. 调用 extract_from_markdown 提取所有标准编号
        2. 提取完整匹配文本（full_match）
        3. 使用 set 去重
        4. 排序后返回
        
        Args:
            markdown_text: Markdown 表格文本
            
        Returns:
            去重后的标准编号字符串列表，按字母顺序排序
        """
        extracted = self.extract_from_markdown(markdown_text)
        unique_codes = list(set([e['full_match'] for e in extracted]))
        return sorted(unique_codes)



class StandardCodeComparator:
    """标准编号比对器"""

    def __init__(self):
        """
        初始化比对器
        
        处理逻辑:
        1. 初始化标准库列表为空
        2. 创建标准编号提取器实例
        3. 自动从数据库加载标准库
        """
        self.library: List[StandardCode] = []
        self.extractor = StandardCodeExtractor()
        
        # 自动从数据库加载标准库
        count = self.load_library_from_db()
        print(f"从数据库加载了 {count} 条标准库数据")

    def load_library_from_db(self):
        """
        从数据库加载标准库
        
        处理逻辑:
        1. 调用 StandardCodeExtractor.get_standard_list() 从数据库获取标准编号列表
        2. 遍历列表，解析每个标准编号
        3. 将解析成功的 StandardCode 对象添加到 self.library 中
        
        Returns:
            加载的标准编号数量
        """
        extractor = StandardCodeExtractor()
        library_list = extractor.get_standard_list()
        
        self.library = []
        for item in library_list:
            parsed = self._parse_code_string(item)
            if parsed:
                self.library.append(parsed)
        
        return len(self.library)


    def _parse_code_string(self, code_str: str) -> Optional[StandardCode]:
        """
        解析标准编号字符串为 StandardCode 对象
        
        处理逻辑:
        1. 使用正则表达式匹配标准编号格式
        2. 提取前缀、数字部分、年份
        3. 验证前缀是否在合法列表中
        4. 判断是否包含 /T
        5. 构建并返回 StandardCode 对象
        
        Args:
            code_str: 标准编号字符串，如 "GB/T 150.1-2011"
            
        Returns:
            StandardCode 对象，如果格式不合法则返回 None
        """
        match = self.extractor.STANDARD_PATTERN.match(code_str.strip())
        if match:
            prefix = match.group(1).upper()

            # 找到标准格式的前缀
            found_prefix = None
            for valid_prefix in self.extractor.VALID_PREFIXES:
                if prefix == valid_prefix.upper():
                    found_prefix = valid_prefix
                    break

            if not found_prefix:
                return None

            has_T = '/T' in found_prefix

            return StandardCode(
                original=code_str.strip(),
                prefix=found_prefix,
                standard_type=found_prefix,
                number=match.group(2),
                year=match.group(3),
                has_T=has_T
            )
        return None

    def compare(self, extracted_code: Dict) -> MatchResult:
        """
        比对提取的标准编号与标准库（核心比对方法）
        
        处理逻辑:
        1. 将提取的字典信息转换为 StandardCode 对象
        2. 如果标准库为空，直接返回 NOT_FOUND
        3. 遍历标准库，计算每个库中标准与提取标准的相似度分数
        4. 找出相似度最高的标准库条目
        5. 根据分数和匹配细节，判定比对结果状态：
           - 100分: 完全符合（前缀+编号+年份都相同）
           - 前缀不匹配: 不存在
           - 编号相似度<30%: 不存在
           - 主编号相同+年份不同: 年份不一致
           - 编号相似度>=50%+年份相同: 较为相似
           - 编号相似度>=30%: 较为相似（兜底）
           - 其他: 不存在

        Args:
            extracted_code: 提取的标准编号信息字典（来自 extract_from_markdown）

        Returns:
            MatchResult 比对结果对象，包含状态、分数、匹配信息等
        """
        # 构建 StandardCode 对象
        extracted = StandardCode(
            original=extracted_code['full_match'],
            prefix=extracted_code['prefix'],
            standard_type=extracted_code['standard_type'],
            number=extracted_code['number'],
            year=extracted_code['year'],
            has_T=extracted_code['has_T']
        )

        if not self.library:
            return MatchResult(
                status=MatchStatus.NOT_FOUND,
                score=0,
                extracted=extracted,
                matched_library_entry=None,
                message="标准库为空，无法比对"
            )

        # 寻找最佳匹配
        best_match = None
        best_score = 0
        best_details = {}

        for lib_entry in self.library:
            score, details = self._calculate_similarity(extracted, lib_entry)
            if score > best_score:
                best_score = score
                best_match = lib_entry
                best_details = details

        # ============================================================
        # 判定逻辑
        # ============================================================

        # 1. 完全匹配: 前缀相同 + 编号相同 + 年份相同
        if best_score >= 100:
            return MatchResult(
                status=MatchStatus.EXACT_MATCH,
                score=best_score,
                extracted=extracted,
                matched_library_entry=best_match,
                message=f"标准编号完全匹配: {extracted.original}"
            )

        # 2. 前缀不匹配 -> 不存在
        if not best_details.get('prefix_match', False):
            return MatchResult(
                status=MatchStatus.NOT_FOUND,
                score=best_score,
                extracted=extracted,
                matched_library_entry=None,
                message=f"标准库中不存在: {extracted.original}"
            )

        # 3. 编号差异过大 -> 不存在
        number_similarity = best_details.get('number_similarity', 0)
        if number_similarity < 0.3:  # 编号相似度低于30%
            return MatchResult(
                status=MatchStatus.NOT_FOUND,
                score=best_score,
                extracted=extracted,
                matched_library_entry=None,
                message=f"标准库中不存在: {extracted.original} (编号差异过大)"
            )

        # 4. 编号主部分相同 + 年份不同 -> 年份不一致
        if best_details.get('main_number_match', False) and not best_details.get('year_match', False):
            return MatchResult(
                status=MatchStatus.YEAR_MISMATCH,
                score=best_score,
                extracted=extracted,
                matched_library_entry=best_match,
                message=f"年份不一致: 提取 {extracted.original} vs 库中 {best_match.original}"
            )

        # 5. 编号相似 + 年份相同 -> 较为相似
        if number_similarity >= 0.5 and best_details.get('year_match', False):
            return MatchResult(
                status=MatchStatus.SIMILAR,
                score=best_score,
                extracted=extracted,
                matched_library_entry=best_match,
                message=f"较为相似: 提取 {extracted.original} vs 库中 {best_match.original}"
            )

        # 6. 其他情况 -> 较为相似 (兜底)
        if number_similarity >= 0.3:
            return MatchResult(
                status=MatchStatus.SIMILAR,
                score=best_score,
                extracted=extracted,
                matched_library_entry=best_match,
                message=f"较为相似: 提取 {extracted.original} vs 库中 {best_match.original if best_match else 'None'}"
            )

        # 7. 默认 -> 不存在
        return MatchResult(
            status=MatchStatus.NOT_FOUND,
            score=best_score,
            extracted=extracted,
            matched_library_entry=None,
            message=f"标准库中不存在: {extracted.original}"
        )

    def _calculate_similarity(self, code1: StandardCode, code2: StandardCode) -> Tuple[int, Dict]:
        """
        计算两个标准编号的相似度分数
        
        评分规则（总分110分）:
        - 前缀相同: +40分（前缀是核心标识，必须相同才继续计算）
        - 标准号完全相同: +50分（包括小数点部分）
        - 标准号主编号相同（忽略小数点）: +30分（如 150.1 和 150）
        - 标准号编辑距离较小（相似度>=50%）: +20分
        - 标准号编辑距离中等（相似度>=30%）: +10分
        - 年份相同: +20分
        
        处理逻辑:
        1. 前缀不同直接返回0分（前缀是硬性要求）
        2. 计算编号的编辑距离和相似度
        3. 判断主编号是否相同（忽略小数点）
        4. 判断年份是否相同
        5. 累加分数并返回详细匹配信息

        Args:
            code1: 第一个标准编号（从 Markdown 提取的）
            code2: 第二个标准编号（从标准库加载的）

        Returns:
            (分数, 详细匹配信息字典)
            详细匹配信息包含:
            - prefix_match: 前缀是否匹配
            - main_number_match: 主编号是否匹配
            - exact_number_match: 完整编号是否匹配
            - year_match: 年份是否匹配
            - number_similarity: 编号相似度（0-1）
            - levenshtein_ratio: 编辑距离相似度（0-1）
        """
        score = 0
        details = {
            'prefix_match': False,
            'main_number_match': False,
            'exact_number_match': False,
            'year_match': False,
            'number_similarity': 0.0,
            'levenshtein_ratio': 0.0
        }

        # 1. 前缀比对 (核心权重)
        if code1.prefix == code2.prefix:
            score += 40
            details['prefix_match'] = True
        else:
            return score, details  # 前缀不同，直接返回

        # 2. 标准号比对
        num1 = code1.number  # 例如: "150.1"
        num2 = code2.number  # 例如: "150"

        # ============================================================
        # 计算编号相似度（基于 Levenshtein 编辑距离）
        # ============================================================
        # 
        # 【核心公式】
        #   相似度 = 1.0 - (编辑距离 / 最长字符串长度)
        #
        # 【编辑距离定义】
        #   将字符串A转换为字符串B所需的最少单字符编辑操作次数
        #   允许的操作：插入、删除、替换
        #
        # 【计算示例】
        #   示例1: "150.1" vs "150.1"
        #     编辑距离 = 0 (完全相同)
        #     相似度 = 1.0 - (0/5) = 1.0 = 100%
        #
        #   示例2: "150" vs "150.1"
        #     编辑距离 = 2 (需要插入 '.' 和 '1')
        #     相似度 = 1.0 - (2/5) = 0.6 = 60%
        #
        #   示例3: "150.2" vs "150.1"
        #     编辑距离 = 1 (只需替换 '2' → '1')
        #     相似度 = 1.0 - (1/5) = 0.8 = 80%
        #
        #   示例4: "999" vs "150.1"
        #     编辑距离 = 5 (完全不同的字符串)
        #     相似度 = 1.0 - (5/5) = 0.0 = 0%
        #
        # 【判定阈值】
        #   - 相似度 >= 50%: 编号较相似（可能是OCR误差或版本差异）
        #   - 相似度 >= 30%: 编号有一定相似（需要进一步判断）
        #   - 相似度 <  30%: 编号差异过大（判定为不存在的标准）
        #
        # ============================================================
        max_len = max(len(num1), len(num2))  # 取较长字符串的长度作为分母
        if max_len > 0:
            # 调用编辑距离算法计算两个编号的差异程度
            distance = self._levenshtein_distance(num1, num2)
            
            # 将编辑距离转换为相似度（0.0-1.0）
            # distance越小 → 相似度越接近1.0（越相似）
            # distance越大 → 相似度越接近0.0（越不同）
            details['levenshtein_ratio'] = 1.0 - (distance / max_len)
            details['number_similarity'] = details['levenshtein_ratio']

        # 主编号比对 (忽略小数点)
        main_num1 = num1.split('.')[0]
        main_num2 = num2.split('.')[0]

        if num1 == num2:
            score += 50
            details['exact_number_match'] = True
            details['main_number_match'] = True
            details['number_similarity'] = 1.0
        elif main_num1 == main_num2:
            score += 30
            details['main_number_match'] = True
            # 主编号相同，编号相似度至少0.5
            details['number_similarity'] = max(details['number_similarity'], 0.5)
        elif details['levenshtein_ratio'] >= 0.5:
            # 编辑距离较小 (相似度>=50%)
            score += 20
        elif details['levenshtein_ratio'] >= 0.3:
            # 编辑距离中等 (相似度>=30%)
            score += 10

        # 3. 年份比对
        if code1.year == code2.year:
            score += 20
            details['year_match'] = True

        return score, details

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        计算两个字符串的编辑距离（Levenshtein Distance）
        
        【算法原理：动态规划】
        构建一个 (len(s1)+1) × (len(s2)+1) 的矩阵，matrix[i][j] 表示
        将 s1[0:i] 转换为 s2[0:j] 所需的最少编辑操作次数。
        
        【状态转移方程】
        如果 s1[i-1] == s2[j-1]:
            matrix[i][j] = matrix[i-1][j-1]  # 字符相同，不需要操作
        否则:
            matrix[i][j] = min(
                matrix[i-1][j] + 1,      # 删除操作
                matrix[i][j-1] + 1,      # 插入操作
                matrix[i-1][j-1] + 1     # 替换操作
            )
        
        【计算示例："150" → "150.1"】
        
        构建矩阵（行="150"，列="150.1"）：
        
             ""   1    5    0    .    1
          +----+----+----+----+----+----+
        ""|  0 |  1 |  2 |  3 |  4 |  5 |
          +----+----+----+----+----+----+
         1|  1 |  0 |  1 |  2 |  3 |  4 |  ← "1" vs "1" 相同，继承对角线0
          +----+----+----+----+----+----+
         5|  2 |  1 |  0 |  1 |  2 |  3 |  ← "5" vs "5" 相同，继承对角线0
          +----+----+----+----+----+----+
         0|  3 |  2 |  1 |  0 |  1 |  2 |  ← "0" vs "0" 相同，继承对角线0
          +----+----+----+----+----+----+
        
        右下角 matrix[3][5] = 2，即编辑距离为2
        （需要插入 '.' 和 '1' 两个字符）
        
        【另一个示例："150.2" → "150.1"】
        
             ""   1    5    0    .    1
          +----+----+----+----+----+----+
        ""|  0 |  1 |  2 |  3 |  4 |  5 |
          +----+----+----+----+----+----+
         1|  1 |  0 |  1 |  2 |  3 |  4 |
          +----+----+----+----+----+----+
         5|  2 |  1 |  0 |  1 |  2 |  3 |
          +----+----+----+----+----+----+
         0|  3 |  2 |  1 |  0 |  1 |  2 |
          +----+----+----+----+----+----+
         .|  4 |  3 |  2 |  1 |  0 |  1 |
          +----+----+----+----+----+----+
         2|  5 |  4 |  3 |  2 |  1 |  1 |  ← "2" vs "1" 不同，取min(1+1, 1+1, 0+1)=1
          +----+----+----+----+----+----+
        
        右下角 matrix[5][5] = 1，即编辑距离为1
        （只需将 '2' 替换为 '1'）
        
        【空间优化】
        原始算法需要 O(m×n) 空间，这里优化为只保存两行数据，空间复杂度降为 O(min(m,n))
        - previous_row: 上一行（i-1）
        - current_row:  当前行（i）
        
        Args:
            s1: 第一个字符串（较长）
            s2: 第二个字符串（较短）
            
        Returns:
            编辑距离（整数），0表示完全相同
            
        【性能说明】
        - 时间复杂度: O(m×n)，m和n分别为两个字符串的长度
        - 空间复杂度: O(min(m,n))，优化后只需保存一行数据
        - 对于标准号（通常长度<10），计算非常快（<0.01ms）
        """
        # 确保 s1 是较长的字符串，优化空间使用
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        # 边界情况：如果 s2 为空，编辑距离就是 s1 的长度（全部删除）
        if len(s2) == 0:
            return len(s1)

        # 初始化第一行：从空字符串转换为 s2[0:j] 需要 j 次插入操作
        # 例如: "" → "150.1" 需要5次插入，所以 previous_row = [0,1,2,3,4,5]
        previous_row = list(range(len(s2) + 1))
        
        # 逐行计算矩阵
        for i, c1 in enumerate(s1):
            # 初始化当前行的第一个元素
            # 从 s1[0:i+1] → "" 需要 i+1 次删除操作
            current_row = [i + 1]
            
            for j, c2 in enumerate(s2):
                # 计算三种操作的成本：
                # 1. 插入：在 s1 中插入字符以匹配 s2[j]
                #    成本 = previous_row[j+1] + 1
                insertions = previous_row[j + 1] + 1
                
                # 2. 删除：从 s1 中删除字符
                #    成本 = current_row[j] + 1
                deletions = current_row[j] + 1
                
                # 3. 替换：将 s1[i] 替换为 s2[j]
                #    如果字符相同，成本 = previous_row[j] + 0
                #    如果字符不同，成本 = previous_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                
                # 取三种操作的最小值作为当前位置的编辑距离
                current_row.append(min(insertions, deletions, substitutions))
            
            # 保存当前行，作为下一次迭代的上一行
            previous_row = current_row

        # 返回最后一行的最后一个元素，即完整的编辑距离
        return previous_row[-1]

    def batch_compare(self, markdown_text: str) -> List[MatchResult]:
        """
        批量比对 Markdown 文本中的所有标准编号
        
        处理逻辑:
        1. 调用 extractor 从 Markdown 中提取所有标准编号
        2. 对每个提取的标准编号调用 compare 方法进行比对
        3. 收集所有比对结果并返回

        Args:
            markdown_text: Markdown 表格文本，包含多个标准编号

        Returns:
            比对结果列表，每个元素是一个 MatchResult 对象
        """
        extracted_codes = self.extractor.extract_from_markdown(markdown_text)

        results = []
        for code in extracted_codes:
            result = self.compare(code)
            results.append(result)

        return results

    def generate_report(self, markdown_text: str) -> Dict:
        """
        生成完整比对报告（结构化数据）
        
        处理逻辑:
        1. 调用 batch_compare 获取所有比对结果
        2. 统计各状态的数量（完全符合、年份不一致、较为相似、不存在）
        3. 将比对结果转换为字典格式
        4. 计算摘要信息（有效编号数、无效编号数）
        5. 返回包含统计信息、详细结果、摘要的报告字典

        Args:
            markdown_text: Markdown 表格文本

        Returns:
            比对报告字典，结构如下:
            {
                'statistics': {  # 统计信息
                    'total': 总数,
                    'exact_match': 完全符合数,
                    'year_mismatch': 年份不一致数,
                    'similar': 较为相似数,
                    'not_found': 不存在数
                },
                'results': [  # 详细比对结果列表
                    {MatchResult.to_dict()},
                    ...
                ],
                'summary': {  # 摘要信息
                    'total_extracted': 提取总数,
                    'valid_codes': 有效编号数（完全符合+年份不一致+较为相似）,
                    'invalid_codes': 无效编号数（不存在+解析错误）
                }
            }
        """
        results = self.batch_compare(markdown_text)

        # 统计
        stats = {
            'total': len(results),
            'exact_match': 0,
            'year_mismatch': 0,
            'similar': 0,
            'not_found': 0,
            'parse_error': 0
        }

        detailed_results = []
        for result in results:
            stats[result.status.name.lower().replace('match_status.', '')] += 1
            detailed_results.append(result.to_dict())

        return {
            'statistics': stats,
            'results': detailed_results,
            'summary': {
                'total_extracted': stats['total'],
                'valid_codes': stats['exact_match'] + stats['year_mismatch'] + stats['similar'],
                'invalid_codes': stats['not_found'] + stats['parse_error']
            }
        }

    def generate_markdown_report(self, markdown_text: str) -> str:
        """
        生成 Markdown 格式的比对报告（可读文本）
        
        处理逻辑:
        1. 调用 generate_report 获取结构化报告数据
        2. 构建 Markdown 文本，包含：
           - 标题：标准编号比对报告
           - 统计摘要：各状态的计数
           - 详细比对结果表格：提取标准、库中标准、比对结果、说明
        3. 返回 Markdown 格式字符串

        Args:
            markdown_text: Markdown 表格文本

        Returns:
            Markdown 格式的比对报告字符串，可直接展示或保存到文件
        """
        report = self.generate_report(markdown_text)

        md_lines = [
            "## 标准编号比对报告",
            "",
            "### 统计摘要",
            "",
            f"- **总计提取**: {report['statistics']['total']} 个标准编号",
            f"- **完全符合**: {report['statistics']['exact_match']} 个",
            f"- **年份不一致**: {report['statistics']['year_mismatch']} 个",
            f"- **较为相似**: {report['statistics']['similar']} 个",
            f"- **不存在**: {report['statistics']['not_found']} 个",
            "",
            "### 详细比对结果",
            "",
            "| 提取标准信息 | 标准库信息 | 比对结果 | 说明 |",
            "|-------------|-----------|---------|------|",
        ]

        for result in report['results']:
            extracted = result['extracted']['original']
            lib_match = result['matched_library_entry']['original'] if result['matched_library_entry'] else "-"
            status = result['status']
            message = result['message']

            md_lines.append(f"| {extracted} | {lib_match} | {status} | {message} |")

        return "\n".join(md_lines)




# ========== 使用示例 ==========
if __name__ == '__main__':
    import sys
    import os

    # 步骤 1: 读取实际的 MD 文件
    md_file_path = r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\task001\patched_task001_管口表.md"
    
    if not os.path.exists(md_file_path):
        print(f"错误: 文件不存在 - {md_file_path}")
        sys.exit(1)
    
    with open(md_file_path, 'r', encoding='utf-8') as f:
        markdown_text = f.read()
    
    print(f"成功读取 MD 文件: {md_file_path}")
    print(f"文件大小: {len(markdown_text)} 字符")
    print("="*80)

    # 步骤 2: 创建比对器（自动从数据库加载标准库）
    comparator = StandardCodeComparator()

    # 步骤 3: 提取标准编号
    codes = comparator.extractor.extract_from_markdown(markdown_text)
    print(f"\n【提取结果】共提取到 {len(codes)} 个标准编号:")
    for i, code in enumerate(codes, 1):
        print(f"  {i}. {code['full_match']} (前缀={code['prefix']}, 编号={code['number']}, 年份={code['year']})")

    # 步骤 5: 批量比对所有提取的标准编号
    print(f"\n【比对结果】")
    print("="*80)
    results = comparator.batch_compare(markdown_text)
    
    for i, result in enumerate(results, 1):
        extracted_code = result.extracted.original
        matched_code = result.matched_library_entry.original if result.matched_library_entry else "无匹配"
        status = result.status.value
        score = result.score
        message = result.message
        
        print(f"  {i}. {extracted_code}")
        print(f"     状态: {status} (分数={score})")
        print(f"     匹配: {matched_code}")
        print(f"     说明: {message}")
        print()

    # 步骤 6: 生成完整报告
    print("="*80)
    print("\n【完整报告】")
    report = comparator.generate_report(markdown_text)
    
    stats = report['statistics']
    print(f"总计提取: {stats['total']} 个")
    print(f"完全符合: {stats['exact_match']} 个")
    print(f"年份不一致: {stats['year_mismatch']} 个")
    print(f"较为相似: {stats['similar']} 个")
    print(f"不存在: {stats['not_found']} 个")
    
    # 步骤 7: 生成 Markdown 格式报告
    print("\n" + "="*80)
    print("【Markdown 报告】")
    print("="*80)
    md_report = comparator.generate_markdown_report(markdown_text)
    print(md_report)
    
    # 可选: 保存报告到文件
    output_file = r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\task001\标准比对报告.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_report)
    print(f"\n报告已保存到: {output_file}")