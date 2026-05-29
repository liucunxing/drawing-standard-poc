from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from backend.app.services.table_layout_service import TableLayoutService4Batch
from backend.app.services.mineru_img2md import image_to_markdown
from backend.app.services.identify_standard import StandardCodeComparator
from backend.config.config import SQLManager


class PocService:
    """POC 服务层,协调PDF上传、解析等业务流程"""

    def __init__(self):
        self.table_layout_service = TableLayoutService4Batch()

    def upload_pdf(self, pdf_bytes: bytes, filename: str, task_name: str = None) -> Dict[str, Any]:
        """
        接收前端上传的PDF文件,保存到tmp/uploads目录,并记录到数据库
        
        Args:
            pdf_bytes: PDF文件字节流
            filename: 原始文件名
            task_name: 任务名称(可选)
            
        Returns:
            包含上传结果的字典:
            {
                "task_id": "任务ID",
                "filename": "保存的文件名",
                "file_path": "文件存储路径",
                "file_size": "文件大小(字节)",
                "uploaded_at": "上传时间"
            }
        """
        if not pdf_bytes:
            raise ValueError("上传文件内容为空")
        
        # 验证文件类型
        if not filename.lower().endswith(".pdf"):
            raise ValueError("仅支持PDF文件")
        
        # 生成任务ID: 优先使用任务名,其次使用文件名前缀 + 时间戳
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        if task_name and task_name.strip():
            # 使用任务名 + 时间戳
            task_id = f"{task_name.strip()}_{timestamp}"
            print(f"[POC] 使用任务名生成task_id: {task_id}")
        else:
            # 使用文件名前缀 + 时间戳
            file_stem = Path(filename).stem.strip() or "upload"
            task_id = f"{file_stem}_{timestamp}"
            print(f"[POC] 使用文件名生成task_id: {task_id}")
        
        # 确保uploads目录存在
        upload_dir = self.table_layout_service.base_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存PDF文件
        save_filename = f"{task_id}.pdf"
        save_path = upload_dir / save_filename
        save_path.write_bytes(pdf_bytes)
        
        file_size = len(pdf_bytes)
        uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 记录到数据库(pdf_task表)
        db_record_id = self._save_to_database(
            task_id=task_id,
            original_filename=filename,
            file_path=str(save_path),
            file_size=file_size,
            uploaded_at=uploaded_at
        )
        
        print(f"[POC] PDF上传成功: {save_path} ({file_size} bytes), DB记录ID: {db_record_id}")
        
        return {
            "task_id": task_id,
            "filename": save_filename,
            "original_filename": filename,
            "file_path": str(save_path),
            "file_size": file_size,
            "uploaded_at": uploaded_at,
        }

    def _save_to_database(
        self,
        task_id: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        uploaded_at: str,
    ) -> int:
        """
        将上传记录保存到数据库
        
        Args:
            task_id: 任务ID
            original_filename: 原始文件名
            file_path: 文件存储路径
            file_size: 文件大小
            uploaded_at: 上传时间
            
        Returns:
            插入的记录ID,失败返回0
        """
        insert_sql = """
            INSERT INTO pdf_task (
                task_id, 
                original_filename, 
                file_path, 
                file_size, 
                page_count,
                status, 
                progress,
                current_step,
                table_count,
                standard_count,
                exact_match_count,
                year_mismatch_count,
                similar_count,
                not_found_count,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        args = (
            task_id,              # task_id
            original_filename,    # original_filename
            file_path,            # file_path
            file_size,            # file_size
            0,                    # page_count (待解析)
            0,                    # status (0-待处理)
            0.00,                 # progress (0%)
            "文件已上传,等待解析",  # current_step
            0,                    # table_count
            0,                    # standard_count
            0,                    # exact_match_count
            0,                    # year_mismatch_count
            0,                    # similar_count
            0,                    # not_found_count
            uploaded_at,          # created_at
            uploaded_at           # updated_at
        )
        
        try:
            with SQLManager() as db:
                last_id = db.create(insert_sql, args)
                if last_id:
                    print(f"[POC] 数据库记录成功: task_id={task_id}, db_id={last_id}")
                    return last_id
                else:
                    print(f"[POC] 数据库记录失败: task_id={task_id}")
                    return 0
        except Exception as exc:
            print(f"[POC] 数据库操作异常: {exc}")
            return 0

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态和进度
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典,未找到返回空字典
        """
        select_sql = """
            SELECT 
                id, task_id, original_filename, file_path, file_size,
                page_count, status, progress, current_step,
                table_count, standard_count, error_message,
                created_at, updated_at, started_at, completed_at
            FROM pdf_task
            WHERE task_id = %s
        """
        
        try:
            with SQLManager() as db:
                result = db.get_one(select_sql, (task_id,))
                if result:
                    print(f"[POC] 查询任务成功: task_id={task_id}")
                    return dict(result)
                else:
                    print(f"[POC] 任务不存在: task_id={task_id}")
                    return {}
        except Exception as exc:
            print(f"[POC] 查询任务异常: {exc}")
            return {}

    def process_pdf_tables(self, task_id: str) -> Dict[str, Any]:
        """
        解析PDF并提取表格图片
        
        Args:
            task_id: 任务ID
            
        Returns:
            包含表格图片信息的字典
        """
        # 1. 从数据库查询任务信息
        task_info = self.get_task_status(task_id)
        if not task_info:
            raise ValueError(f"任务不存在: {task_id}")
        
        file_path = task_info.get('file_path')
        if not file_path:
            raise ValueError(f"任务文件路径为空: {task_id}")
        
        # 2. 更新任务状态为"解析中"
        self._update_task_status(
            task_id=task_id,
            status=1,  # 1-解析中
            progress=10.00,
            current_step="正在解析PDF并提取表格"
        )
        
        try:
            # 3. 调用table_layout_service解析PDF
            print(f"[POC] 开始解析PDF: {file_path}")
            result = self.table_layout_service.export_annotated_from_pdf_path(
                pdf_path=file_path,
                task_id=task_id,
                render_zoom=None,  # 使用默认值
                max_pages=None,    # 使用默认值
            )
            
            # 4. 提取表格图片信息并转换为URL
            tables = []
            total_tables = 0
                    
            for page in result.get('pages', []):
                page_idx = page.get('page', 0)
                table_crop_paths = page.get('table_crop_paths', [])
                total_tables += len(table_crop_paths)
                        
                for table_path in table_crop_paths:
                    # 将本地路径转换为URL路径
                    url_path = self._local_path_to_url(table_path)
                    print(f"[POC] 表格图片路径转换: {table_path} -> {url_path}")
                    tables.append({
                        "page": page_idx,
                        "image_path": table_path,  # 本地路径
                        "image_url": url_path,     # 可访问的URL
                        "label": "table",
                        "score": 0.0,
                    })
            
            # 5. 更新数据库统计信息
            self._update_task_status(
                task_id=task_id,
                status=2,  # 2-已完成
                progress=100.00,
                current_step="解析完成",
                page_count=result.get('total_pages', 0),
                table_count=total_tables,
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            print(f"[POC] PDF解析成功: {total_tables} 个表格")
            
            return {
                "task_id": task_id,
                "total_pages": result.get('total_pages', 0),
                "total_tables": total_tables,
                "tables": tables,
                "page_images_dir": result.get('page_images_dir', ''),
                "debug_dir": result.get('debug_dir', ''),
            }
            
        except Exception as exc:
            # 解析失败,更新状态
            self._update_task_status(
                task_id=task_id,
                status=3,  # 3-失败
                current_step=f"解析失败: {str(exc)}"
            )
            print(f"[POC] PDF解析失败: {exc}")
            raise

    def convert_tables_to_markdown(self, task_id: str, tables: list) -> Dict[str, Any]:
        """
        将表格图片转换为Markdown
        
        Args:
            task_id: 任务ID
            tables: 表格图片信息列表
            
        Returns:
            包含Markdown文件信息的字典
        """
        if not tables:
            raise ValueError("没有表格图片需要转换")
        
        # 创建输出目录
        markdown_dir = self.table_layout_service.base_dir / "markdown" / task_id
        markdown_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[POC] 开始转换表格为Markdown,共 {len(tables)} 个表格")
        
        results = []
        for idx, table in enumerate(tables):
            image_path = table.get('image_path', '')
            if not image_path:
                print(f"[POC] 跳过表格 {idx}: 没有图片路径")
                continue
            
            try:
                # 调用mineru_img2md转换
                print(f"[POC] 转换表格 {idx+1}/{len(tables)}: {Path(image_path).name}")
                
                # 生成该表格的task_id
                table_task_id = f"{task_id}_table_{idx+1}"
                
                result = image_to_markdown(
                    image_path=Path(image_path),
                    task_id=table_task_id,
                    output_dir=str(markdown_dir),
                    dpi=300,
                    scale=1.5,
                )
                
                # 优先使用patched版本(优化后的结果),如果没有则使用raw版本
                md_file = result.get('patched_md_file')
                if not md_file or not Path(md_file).exists():
                    md_file = result.get('md_file')
                
                # 读取Markdown内容
                md_content = ""
                if md_file and Path(md_file).exists():
                    md_content = Path(md_file).read_text(encoding='utf-8')
                
                # 将本地路径转换为URL
                md_url = self._local_path_to_url(md_file) if md_file else ""
                
                # 判断是否应用了补丁
                patched = result.get('md_patched', False)
                
                results.append({
                    "table_index": idx + 1,
                    "source_image": image_path,
                    "md_file": md_file,
                    "md_url": md_url,
                    "md_content": md_content,
                    "patched": patched,
                    "success": True,
                })
                
                print(f"[POC] 表格 {idx+1} 转换成功: {md_file} {'(已优化)' if patched else '(原始)'}")
                
            except Exception as exc:
                print(f"[POC] 表格 {idx+1} 转换失败: {exc}")
                results.append({
                    "table_index": idx + 1,
                    "source_image": image_path,
                    "error": str(exc),
                    "success": False,
                })
        
        success_count = sum(1 for r in results if r.get('success'))
        print(f"[POC] Markdown转换完成: 成功 {success_count}/{len(tables)}")
        
        return {
            "task_id": task_id,
            "total_tables": len(tables),
            "success_count": success_count,
            "fail_count": len(tables) - success_count,
            "markdown_dir": str(markdown_dir),
            "results": results,
        }

    def _local_path_to_url(self, local_path: str) -> str:
        """
        将本地文件路径转换为可访问的URL
        
        Args:
            local_path: 本地文件路径
            
        Returns:
            URL路径
        """
        # 获取base_dir (tmp目录)
        base_dir = self.table_layout_service.base_dir
        local_path_obj = Path(local_path)
        
        try:
            # 计算相对路径 (相对于tmp目录)
            relative_path = local_path_obj.relative_to(base_dir)
            # 返回URL路径 (不需要再加tmp,因为路由已经指向tmp目录)
            url_path = f"/api/files/{relative_path.as_posix()}"
            print(f"[POC] 路径转换: {local_path} -> {url_path}")
            return url_path
        except ValueError:
            # 如果不在base_dir下,返回空
            print(f"[POC] 路径转换失败: {local_path} 不在 {base_dir} 下")
            return ""

    def _update_task_status(
        self,
        task_id: str,
        status: int = None,
        progress: float = None,
        current_step: str = None,
        page_count: int = None,
        table_count: int = None,
        standard_count: int = None,
        completed_at: str = None,
    ) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度
            current_step: 当前步骤
            page_count: 页数
            table_count: 表格数
            standard_count: 标准号数
            completed_at: 完成时间
        """
        # 构建UPDATE语句
        updates = []
        args = []
        
        if status is not None:
            updates.append("status = %s")
            args.append(status)
        if progress is not None:
            updates.append("progress = %s")
            args.append(progress)
        if current_step is not None:
            updates.append("current_step = %s")
            args.append(current_step)
        if page_count is not None:
            updates.append("page_count = %s")
            args.append(page_count)
        if table_count is not None:
            updates.append("table_count = %s")
            args.append(table_count)
        if standard_count is not None:
            updates.append("standard_count = %s")
            args.append(standard_count)
        if completed_at is not None:
            updates.append("completed_at = %s")
            args.append(completed_at)
        
        # 总是更新updated_at
        updates.append("updated_at = NOW()")
        args.append(task_id)
        
        if not updates:
            return
        
        update_sql = f"UPDATE pdf_task SET {', '.join(updates)} WHERE task_id = %s"
        
        try:
            with SQLManager() as db:
                db.modify(update_sql, tuple(args))
                print(f"[POC] 任务状态更新: task_id={task_id}")
        except Exception as exc:
            print(f"[POC] 更新任务状态异常: {exc}")

    def detect_standards(self, task_id: str, markdown_files: list) -> Dict[str, Any]:
        """
        检测Markdown文件中的标准号并与标准库比对
        
        Args:
            task_id: 任务ID
            markdown_files: Markdown文件路径列表
            
        Returns:
            包含标准检测结果的字典
        """
        if not markdown_files:
            raise ValueError("Markdown文件列表为空")
        
        print(f"[POC] 开始标准检测: task_id={task_id}, {len(markdown_files)} 个文件")
        
        # 更新任务状态为"标准检测中"
        self._update_task_status(
            task_id=task_id,
            status=1,  # 1-解析中
            progress=50.00,
            current_step="正在检测标准号"
        )
        
        try:
            # 创建标准比对器
            comparator = StandardCodeComparator()
            
            all_results = []
            total_standards = 0
            exact_match_count = 0
            year_mismatch_count = 0
            similar_count = 0
            not_found_count = 0
            
            # 遍历每个Markdown文件
            for idx, md_file_path in enumerate(markdown_files):
                md_path = Path(md_file_path)
                if not md_path.exists():
                    print(f"[POC] Markdown文件不存在: {md_file_path}")
                    continue
                
                # 读取Markdown内容
                md_content = md_path.read_text(encoding='utf-8')
                
                # 提取标准号
                extracted_codes = comparator.extractor.extract_from_markdown(md_content)
                
                if not extracted_codes:
                    print(f"[POC] 文件 {md_file_path} 未提取到标准号")
                    continue
                
                print(f"[POC] 文件 {md_file_path} 提取到 {len(extracted_codes)} 个标准号")
                
                # 比对每个标准号
                table_results = []
                for code in extracted_codes:
                    match_result = comparator.compare(code)
                    result_dict = match_result.to_dict()
                    
                    # 添加文件信息
                    result_dict['markdown_file'] = str(md_file_path)
                    result_dict['table_index'] = idx + 1
                    
                    table_results.append(result_dict)
                    
                    # 统计
                    total_standards += 1
                    status = match_result.status.value
                    if status == "完全符合":
                        exact_match_count += 1
                    elif status == "年份不一致":
                        year_mismatch_count += 1
                    elif status == "较为相似":
                        similar_count += 1
                    elif status == "不存在":
                        not_found_count += 1
                
                all_results.extend(table_results)
            
            # 更新数据库统计信息
            self._update_task_status(
                task_id=task_id,
                status=2,  # 2-已完成
                progress=100.00,
                current_step="标准检测完成",
                standard_count=total_standards,
                completed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            print(f"[POC] 标准检测完成: 总计 {total_standards} 个标准号")
            
            return {
                "task_id": task_id,
                "total_standards": total_standards,
                "exact_match_count": exact_match_count,
                "year_mismatch_count": year_mismatch_count,
                "similar_count": similar_count,
                "not_found_count": not_found_count,
                "results": all_results,
            }
            
        except Exception as exc:
            # 检测失败,更新状态
            self._update_task_status(
                task_id=task_id,
                status=3,  # 3-失败
                current_step=f"标准检测失败: {str(exc)}"
            )
            print(f"[POC] 标准检测失败: {exc}")
            raise


# 单例实例
poc_service = PocService()
