from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from backend.config.config import SQLManager


OPERATOR_ADMIN = "ADMIN"


class StandardDataService:
    """标准信息库 CRUD 服务"""

    @staticmethod
    def _format_datetime_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value).replace("T", " ")[:19]

    def _serialize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row)
        for field in ("create_time", "update_time"):
            data[field] = self._format_datetime_value(data.get(field))
        return data

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        return (value or "").strip()

    def _normalize_operator(self, operator: str | None) -> str:
        return OPERATOR_ADMIN

    def list_standards(self, keyword: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        keyword = self._normalize_text(keyword)
        page = max(1, int(page or 1))
        page_size = max(1, min(200, int(page_size or 20)))
        offset = (page - 1) * page_size

        where_sql = ""
        params: list[Any] = []
        if keyword:
            where_sql = (
                "WHERE standard_no LIKE %s OR standard_type LIKE %s OR standard_prefix LIKE %s"
            )
            fuzzy = f"%{keyword}%"
            params.extend([fuzzy, fuzzy, fuzzy])

        count_sql = f"SELECT COUNT(1) AS total FROM standard_data {where_sql}"
        list_sql = f"""
            SELECT
                id,
                standard_no,
                standard_type,
                standard_prefix,
                create_time,
                update_time,
                create_user,
                update_user
            FROM standard_data
            {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """

        try:
            with SQLManager() as db:
                total_row = db.get_one(count_sql, tuple(params)) or {"total": 0}
                rows = db.get_list(list_sql, tuple(params + [page_size, offset])) or []

            return {
                "total": int(total_row.get("total") or 0),
                "page": page,
                "page_size": page_size,
                "items": [self._serialize_row(row) for row in rows],
            }
        except Exception as exc:
            raise RuntimeError(f"查询标准信息库失败: {exc}") from exc

    def create_standard(
        self,
        standard_no: str,
        standard_type: str,
        standard_prefix: str,
        operator: str = "system",
    ) -> Dict[str, Any]:
        standard_no = self._normalize_text(standard_no)
        standard_type = self._normalize_text(standard_type)
        standard_prefix = self._normalize_text(standard_prefix)
        operator = self._normalize_operator(operator)

        if not standard_no or not standard_type or not standard_prefix:
            raise ValueError("standard_no、standard_type、standard_prefix 不能为空")

        check_sql = "SELECT id FROM standard_data WHERE standard_no = %s LIMIT 1"
        insert_sql = """
            INSERT INTO standard_data (
                standard_no,
                standard_type,
                standard_prefix,
                create_time,
                update_time,
                create_user,
                update_user
            ) VALUES (%s, %s, %s, NOW(), NOW(), %s, %s)
        """
        query_sql = """
            SELECT
                id,
                standard_no,
                standard_type,
                standard_prefix,
                create_time,
                update_time,
                create_user,
                update_user
            FROM standard_data
            WHERE id = %s
        """

        try:
            with SQLManager() as db:
                existed = db.get_one(check_sql, (standard_no,))
                if existed:
                    raise ValueError(f"标准号已存在: {standard_no}")

                new_id = db.create(
                    insert_sql,
                    (standard_no, standard_type, standard_prefix, OPERATOR_ADMIN, OPERATOR_ADMIN),
                )
                if not new_id:
                    raise RuntimeError("新增标准信息失败")

                row = db.get_one(query_sql, (new_id,))
            return self._serialize_row(row or {})
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"新增标准信息失败: {exc}") from exc

    def update_standard(
        self,
        standard_id: int,
        standard_no: str,
        standard_type: str,
        standard_prefix: str,
        operator: str = "system",
    ) -> Dict[str, Any]:
        standard_id = int(standard_id)
        standard_no = self._normalize_text(standard_no)
        standard_type = self._normalize_text(standard_type)
        standard_prefix = self._normalize_text(standard_prefix)
        operator = self._normalize_operator(operator)

        if not standard_no or not standard_type or not standard_prefix:
            raise ValueError("standard_no、standard_type、standard_prefix 不能为空")

        check_current_sql = "SELECT id FROM standard_data WHERE id = %s LIMIT 1"
        check_duplicate_sql = "SELECT id FROM standard_data WHERE standard_no = %s AND id <> %s LIMIT 1"
        update_sql = """
            UPDATE standard_data
            SET
                standard_no = %s,
                standard_type = %s,
                standard_prefix = %s,
                update_time = NOW(),
                update_user = %s
            WHERE id = %s
        """
        query_sql = """
            SELECT
                id,
                standard_no,
                standard_type,
                standard_prefix,
                create_time,
                update_time,
                create_user,
                update_user
            FROM standard_data
            WHERE id = %s
        """

        try:
            with SQLManager() as db:
                current = db.get_one(check_current_sql, (standard_id,))
                if not current:
                    raise ValueError(f"标准信息不存在: id={standard_id}")

                duplicated = db.get_one(check_duplicate_sql, (standard_no, standard_id))
                if duplicated:
                    raise ValueError(f"标准号已存在: {standard_no}")

                db.modify(
                    update_sql,
                    (standard_no, standard_type, standard_prefix, OPERATOR_ADMIN, standard_id),
                )
                row = db.get_one(query_sql, (standard_id,))
            return self._serialize_row(row or {})
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"更新标准信息失败: {exc}") from exc

    def delete_standard(self, standard_id: int) -> None:
        standard_id = int(standard_id)
        check_sql = "SELECT id FROM standard_data WHERE id = %s LIMIT 1"
        delete_sql = "DELETE FROM standard_data WHERE id = %s"

        try:
            with SQLManager() as db:
                row = db.get_one(check_sql, (standard_id,))
                if not row:
                    raise ValueError(f"标准信息不存在: id={standard_id}")
                db.modify(delete_sql, (standard_id,))
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"删除标准信息失败: {exc}") from exc


standard_data_service = StandardDataService()
