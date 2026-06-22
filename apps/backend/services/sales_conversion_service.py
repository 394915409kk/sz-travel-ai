import json
from datetime import date, datetime

from fastapi import HTTPException

from apps.backend.db import get_connection


JSON_FIELDS = (
    "customer_objections_json",
    "recommended_actions_json",
    "risk_flags_json",
)


def _json_list(value):
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def serialize_record(row):
    record = dict(row)
    for field in JSON_FIELDS:
        record[field.removesuffix("_json")] = _json_list(record.pop(field))
    return record


class SalesConversionService:
    """基于本地 CRM、跟进任务和报价数据生成可解释成交建议。"""

    @classmethod
    def analyze(cls, quote_id, customer_objections=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT q.*, i.priority, i.follow_status, i.assigned_sales,
                   i.next_follow_up_at
            FROM quotes AS q
            LEFT JOIN inquiries AS i ON i.id = q.inquiry_id
            WHERE q.id = ?
            """,
            (quote_id,),
        )
        quote = cursor.fetchone()
        if quote is None:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该报价")

        has_follow_up = False
        if quote["inquiry_id"] is not None:
            cursor.execute(
                """
                SELECT 1 FROM follow_up_tasks
                WHERE inquiry_id = ? AND task_status IN ('pending', 'done')
                LIMIT 1
                """,
                (quote["inquiry_id"],),
            )
            has_follow_up = cursor.fetchone() is not None

        analysis = cls._score(quote, has_follow_up)
        objections = customer_objections or []
        actions = cls._actions(analysis["risk_flags"], has_follow_up)
        next_best_action = actions[0]
        script = cls._script(quote, objections, next_best_action)

        cursor.execute(
            """
            INSERT INTO sales_conversion_records (
                inquiry_id, quote_id, customer_name, phone, destination,
                budget, final_price, conversion_probability, conversion_stage,
                customer_objections_json, recommended_actions_json,
                follow_up_script, risk_flags_json, next_best_action,
                assigned_sales
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote["inquiry_id"],
                quote["id"],
                quote["customer_name"],
                quote["phone"],
                quote["destination"],
                quote["customer_budget"],
                quote["final_price"],
                analysis["probability"],
                analysis["stage"],
                json.dumps(objections, ensure_ascii=False),
                json.dumps(actions, ensure_ascii=False),
                script,
                json.dumps(analysis["risk_flags"], ensure_ascii=False),
                next_best_action,
                quote["assigned_sales"] or "未分配",
            ),
        )
        record_id = cursor.lastrowid
        conn.commit()
        record = cls._get(cursor, record_id)
        conn.close()
        return serialize_record(record)

    @staticmethod
    def _score(quote, has_follow_up):
        probability = 0.35
        risks = []
        budget = quote["customer_budget"]
        final_price = float(quote["final_price"])

        if quote["quote_status"] in ("proposed", "accepted"):
            probability += 0.15
        if quote["quote_status"] == "accepted":
            probability += 0.20
        if budget is not None:
            budget = float(budget)
            if final_price <= budget:
                probability += 0.15
            else:
                probability -= min(0.25, (final_price - budget) / max(final_price, 1))
                risks.extend(["PRICE_TOO_HIGH", "BUDGET_TOO_LOW", "OVER_BUDGET_RISK"])
        if quote["priority"] == "high":
            probability += 0.10
        elif quote["priority"] == "low":
            probability -= 0.08
        if quote["follow_status"] in ("interested", "quoted", "confirmed"):
            probability += 0.10
        if has_follow_up:
            probability += 0.08
        else:
            risks.append("NO_FOLLOW_UP")
        if quote["phone"] in (None, ""):
            risks.append("MISSING_CONTACT_INFO")
            probability -= 0.10
        if float(quote["estimated_margin"]) < 0.10:
            risks.append("LOW_MARGIN_RISK")

        departure = quote["departure_date"]
        if departure:
            days = (date.fromisoformat(departure) - date.today()).days
            if 0 <= days <= 14:
                probability += 0.08
            if 0 <= days <= 7:
                risks.append("URGENT_DEPARTURE")
            if days < 0:
                probability -= 0.20
                risks.append("SALES_CONVERSION_RISK")

        probability = round(max(0.0, min(1.0, probability)), 4)
        if quote["quote_status"] == "converted_to_order":
            stage = "converted"
            probability = 1.0
        elif quote["quote_status"] == "accepted":
            stage = "accepted"
        elif probability >= 0.65:
            stage = "high_intent"
        elif probability < 0.40:
            stage = "low_intent"
            risks.append("LOW_INTENT")
        else:
            stage = "quoted"
        return {"probability": probability, "stage": stage, "risk_flags": list(dict.fromkeys(risks))}

    @staticmethod
    def _actions(risks, has_follow_up):
        actions = []
        if "MISSING_CONTACT_INFO" in risks:
            actions.append("先补齐客户有效联系方式")
        if "BUDGET_TOO_LOW" in risks:
            actions.append("解释报价价值并提供不低于毛利保护线的替代资源方案")
        if "URGENT_DEPARTURE" in risks:
            actions.append("今日确认行程与证件准备时间")
        if not has_follow_up:
            actions.append("立即创建销售跟进任务并约定下次联系时间")
        if not actions:
            actions.append("确认客户接受报价并推动报价转订单")
        actions.append("记录客户异议与本次沟通结果")
        return actions

    @staticmethod
    def _script(quote, objections, next_best_action):
        objection_text = "、".join(objections) if objections else "暂未记录明确异议"
        return (
            f"{quote['customer_name']}您好，您咨询的{quote['destination']}方案当前报价为"
            f"{float(quote['final_price']):.2f}元。已记录您关注：{objection_text}。"
            f"建议下一步：{next_best_action}。资源与价格以转订单时再次核验为准。"
        )

    @classmethod
    def list_records(cls, stage=None, risky=False, high_intent=False):
        conn = get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM sales_conversion_records"
        conditions = []
        params = []
        if stage:
            conditions.append("conversion_stage = ?")
            params.append(stage)
        if risky:
            conditions.append("risk_flags_json <> '[]'")
        if high_intent:
            conditions.append("(conversion_probability >= 0.65 OR conversion_stage IN ('high_intent', 'accepted', 'converted'))")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY conversion_probability DESC, id DESC"
        cursor.execute(sql, params)
        records = [serialize_record(row) for row in cursor.fetchall()]
        conn.close()
        return records

    @classmethod
    def get(cls, record_id):
        conn = get_connection()
        cursor = conn.cursor()
        row = cls._get(cursor, record_id)
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="未找到该成交分析记录")
        return serialize_record(row)

    @staticmethod
    def _get(cursor, record_id):
        cursor.execute("SELECT * FROM sales_conversion_records WHERE id = ?", (record_id,))
        return cursor.fetchone()

    @classmethod
    def update_stage(cls, record_id, stage):
        conn = get_connection()
        cursor = conn.cursor()
        if cls._get(cursor, record_id) is None:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该成交分析记录")
        cursor.execute(
            """
            UPDATE sales_conversion_records
            SET conversion_stage = ?, updated_at = ?
            WHERE id = ?
            """,
            (stage, datetime.now().isoformat(timespec="seconds"), record_id),
        )
        conn.commit()
        row = cls._get(cursor, record_id)
        conn.close()
        return serialize_record(row)
