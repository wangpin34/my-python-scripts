# 按照日期合并发票文件
import logging
import os
import re
from datetime import datetime

import dateparser
import pandas as pd
from pdfplumber import open as open_pdf  # 更先进的PDF解析库
from PyPDF2 import PdfReader, PdfWriter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("invoice_parser.log"), logging.StreamHandler()]
)

def extract_text_with_pdfplumber(pdf_path):
    """使用pdfplumber提取文本，保留更好的布局信息"""
    try:
        with open_pdf(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                # 尝试保留布局的方式提取文本
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            return text
    except Exception as e:
        logging.error(f"pdfplumber提取文本失败 {pdf_path}: {str(e)}")
        return extract_text_with_pypdf2(pdf_path)  #  fallback to PyPDF2

def extract_text_with_pypdf2(pdf_path):
    """使用PyPDF2提取文本作为备选方案"""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        return text
    except Exception as e:
        logging.error(f"PyPDF2提取文本失败 {pdf_path}: {str(e)}")
        return ""

def find_related_text(text, target, window_size=50):
    """在文本中查找目标关键词附近的内容，解决顺序混乱问题"""
    # 将文本转换为小写便于匹配
    lower_text = text.lower()
    target_lower = target.lower()
    
    # 查找所有目标关键词出现的位置
    positions = [i for i in range(len(lower_text)) if lower_text.startswith(target_lower, i)]
    
    # 收集每个位置附近的文本片段
    context = []
    for pos in positions:
        start = max(0, pos - window_size)
        end = min(len(text), pos + len(target) + window_size)
        context.append(text[start:end])
    
    return "\n".join(context) if context else text

def extract_invoice_code(text):
    """优化的发票代码提取，结合上下文分析"""
    # 先找到"发票代码"附近的文本
    code_context = find_related_text(text, "发票代码")
    
    # 如果找不到，尝试其他关键词
    if not re.search(r'\d{10,12}', code_context):
        code_context += "\n" + find_related_text(text, "发票号码")
        code_context += "\n" + find_related_text(text, "单据编号")
    
    # 从上下文提取10-12位数字作为发票代码
    patterns = [
        r'(\d{10,12})',  # 直接匹配10-12位数字
        r'[:：\s]*(\d{10,12})'  # 匹配冒号或空格后的数字
    ]
    
    for pattern in patterns:
        match = re.search(pattern, code_context)
        if match:
            return match.group(1)
    return None

def extract_invoice_date(text):
    """优化的日期提取，结合上下文分析"""
    # 先找到"日期"相关关键词附近的文本
    date_context = find_related_text(text, "日期")
    date_context += "\n" + find_related_text(text, "开票日")
    
    # 尝试从上下文中提取日期
    date_patterns = [
        r'(\d{4}[年/-]\d{1,2}[月/-]\d{1,2}[日]?)',  # 2023年12月31日 或 2023-12-31
        r'(\d{1,2}[月/-]\d{1,2}[日/-]\d{4})',       # 12月31日2023 或 12/31/2023
        r'(\d{4}\d{2}\d{2})'                        # 20231231
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, date_context)
        if match:
            date_str = match.group(1)
            date_obj = dateparser.parse(date_str)
            if date_obj:
                return date_obj.strftime('%Y-%m-%d')
    
    # 如果上述方法失败，尝试全文搜索
    date_obj = dateparser.parse(text, settings={'STRICT_PARSING': False})
    if date_obj:
        return date_obj.strftime('%Y-%m-%d')
    
    logging.warning(f"无法提取日期，上下文: {date_context[:100]}...")
    return None

def extract_payer_info(text):
    """提取交款人/付款人信息"""
    # 交款人可能的关键词
    payer_keywords = [
        "交款人",
    ]
    
    # 收集所有相关上下文
    payer_context = ""
    for keyword in payer_keywords:
        payer_context += find_related_text(text, keyword, window_size=150) + "\n\n"
    
    if not payer_context:
        logging.warning("未找到交款人相关关键词")
        return None
    
    # 匹配交款人信息的模式
    # 中文姓名通常是2-4个汉字，公司名称可能更长
    patterns = [
        # 匹配关键词后的名称（带冒号或空格）
        r'交款人：[\s]*([^\n:：,，；;\s]+)',
        # 匹配可能的个人姓名（2-4个汉字）
        r'([\u4e00-\u9fa5]{2,4})'
    ]
    
    # 尝试各种模式提取交款人信息
    for pattern in patterns:
        matches = re.findall(pattern, payer_context)
        for match in matches:
            # 过滤掉太短或无意义的匹配
            if match and len(match.strip()) >= 2:
                # 去除可能的标点符号
                cleaned = re.sub(r'^[:：\s]+|[:：\s]+$', '', match)
                if cleaned:
                    return cleaned
    
    logging.warning(f"无法提取交款人信息，上下文: {payer_context[:150]}...")
    return None


def extract_amount(text):
    """提取金额信息"""
    # 先找到"金额"相关关键词附近的文本
    amount_context = find_related_text(text, "(小写）",  window_size=100)

    # 尝试从上下文中提取金额
    amount_patterns = [
        r'\(小写\）[\s]*(\d+(?:\.\d{1,2})?)',
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, amount_context)
        if match:
            return match.group(1)
    return None

    

def process_invoice(pdf_path):
    """处理单个发票文件，提取关键信息"""
    try:
        # 提取文本（优先使用pdfplumber）
        text = extract_text_with_pdfplumber(pdf_path)
        if not text:
            logging.warning(f"无法从 {pdf_path} 提取文本")
            return None
        
        # 提取信息
        invoice_code = extract_invoice_code(text)
        invoice_date = extract_invoice_date(text)
        invoice_payer = extract_payer_info(text)
        invoice_amount = extract_amount(text)
        
        if not invoice_code:
            logging.warning(f"无法从 {pdf_path} 提取发票代码")
        if not invoice_date:
            logging.warning(f"无法从 {pdf_path} 提取日期")
        if not invoice_payer:
            logging.warning(f"无法从 {pdf_path} 提取交款人")
        if not invoice_amount:
            logging.warning(f"无法从 {pdf_path} 提取金额")
            
        return {
            'path': pdf_path,
            'filename': os.path.basename(pdf_path),
            'invoice_code': invoice_code,
            'date': invoice_date,
            'payer': invoice_payer,
            'modified_time': os.path.getmtime(pdf_path),
            'amount': invoice_amount
        }
    except Exception as e:
        logging.error(f"处理发票 {pdf_path} 失败: {str(e)}")
        return None


def process_invoice_files(input_dir, output_dir):
    """处理所有发票文件：提取信息、去重、合并"""
    # 存储发票信息
    invoice_data = []
    
    # 遍历输入目录中的所有PDF文件
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(input_dir, filename)
            logging.info(f"处理文件: {filename}")
            data = process_invoice(pdf_path)
            if not data:
                logging.warning(f"处理 {filename} 失败，跳过该文件")
                continue
            
            # 添加到数据列表
            invoice_data.append({
                'filename': filename,
                'path': pdf_path,
                'invoice_code': data.get('invoice_code'),
                'date': data.get('date'),
                'year': data.get('date', '')[:4] if data.get('date') else None,
                'modified_time': os.path.getmtime(pdf_path)  # 获取文件修改时间，用于去重
            })
            logging.info(f"提取信息 - 发票代码: {data.get('invoice_code')}, 日期: {data.get('date')}")

    if not invoice_data:
        logging.info("没有找到可处理的发票文件")
        return
    
    # 创建DataFrame进行数据处理
    df = pd.DataFrame(invoice_data)
    
    # 按发票代码去重，保留最新的文件（根据修改时间）
    df['modified_time'] = pd.to_datetime(df['modified_time'], unit='s')
    df = df.sort_values('modified_time', ascending=False)
    df_unique = df.drop_duplicates(subset='invoice_code', keep='first')
    logging.info(f"去重后保留 {len(df_unique)} 个发票文件（原始 {len(df)} 个）")
    
    # 按日期分组并合并PDF
    date_groups = df_unique.groupby('date')
    
    for date, group in date_groups:
        logging.info(f"合并 {date} 的 {len(group)} 个发票文件")
        
        # 创建PDF写入器
        writer = PdfWriter()

        # 按日期排序（可以根据需要修改排序方式）
        for _, row in group.sort_values('date').iterrows():
            try:
                reader = PdfReader(row['path'])
                # 将所有页面添加到写入器
                for page in reader.pages:
                    writer.add_page(page)
                logging.info(f"添加文件: {row['filename']}")
            except Exception as e:
                logging.error(f"添加文件 {row['filename']} 失败: {str(e)}")
        
        # 保存合并后的PDF
        output_filename = f"{date}.pdf"
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            with open(output_path, 'wb') as f:
                writer.write(f)
            logging.info(f"已保存合并文件: {output_filename}")
        except Exception as e:
            logging.error(f"保存合并文件 {output_filename} 失败: {str(e)}")

# 示例使用
if __name__ == "__main__":
    downloads_path = os.path.expanduser("~/Downloads")
    dir_name = 'my_health_invoices'
    # 配置目录路径
    input_dir = os.path.join(downloads_path, '发票', dir_name)
    output_dir = os.path.join(downloads_path, 'merged_invoices', dir_name)

    # 确保目录存在
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    process_invoice_files(input_dir, output_dir)