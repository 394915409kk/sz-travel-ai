import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from apps.backend.db import get_connection
from apps.backend.services.profit_service import ProfitService


def _loads(value):
    try:
        result = json.loads(value or "[]")
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def serialize_profile(row):
    profile = dict(row)
    profile["preferred_destinations"] = _loads(profile.pop("preferred_destinations_json"))
    profile["risk_flags"] = _loads(profile.pop("risk_flags_json"))
    return profile


class CustomerLifecycleService:
    """按本地历史订单生成可重算的客户画像和复购任务。"""

    @classmethod
    def generate_profiles(cls):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY created_at ASC, id ASC")
        groups = defaultdict(list)
        for order in cursor.fetchall():
            groups[(order["customer_name"], order["phone"] or "")].append(order)
        profit_service = ProfitService(conn)
        generated = []
        for (customer_name, phone_key), orders in groups.items():
            phone = phone_key or None
            profits = [profit_service.get_order_profit(order["id"]) for order in orders]
            total_spent = round(sum(float(order["total_amount"]) for order in orders), 2)
            total_profit = round(sum(item["gross_profit"] for item in profits), 2)
            destinations = [name for name, _ in Counter(order["destination"] for order in orders).most_common(3)]
            amounts = [float(order["total_amount"]) for order in orders]
            last_order_at = max(order["created_at"] for order in orders)
            last_date = date.fromisoformat(last_order_at[:10])
            days_since = (date.today() - last_date).days
            level = "high_value" if len(orders) >= 3 or total_spent >= 10000 or total_profit >= 3000 else "regular"
            risks = []
            if days_since > 180:
                stage = "dormant"
                risks.append("CUSTOMER_DORMANT_RISK")
            elif level == "high_value":
                stage = "high_value"
            elif len(orders) > 1:
                stage = "active"
            else:
                stage = "new"
            paid_ratio = sum(order["payment_status"] == "mock_paid" for order in orders) / len(orders)
            recency_score = 0.35 if days_since <= 180 else (0.15 if days_since <= 365 else 0.05)
            probability = min(1.0, 0.20 + min(len(orders), 3) * 0.10 + paid_ratio * 0.20 + recency_score + (0.10 if level == "high_value" else 0))
            probability = round(probability, 4)
            next_date = last_date + timedelta(days=180)
            recommendation = (
                f"优先推荐{destinations[0]}关联或同类产品，并由销售人工确认新的日期、预算和同行人需求。"
                if destinations else "先由销售补充客户目的地偏好后再推荐。"
            )
            cursor.execute(
                "SELECT id FROM customer_profiles WHERE customer_name = ? AND COALESCE(phone, '') = ?",
                (customer_name, phone_key),
            )
            existing = cursor.fetchone()
            values = (
                level, len(orders), total_spent, total_profit,
                json.dumps(destinations, ensure_ascii=False),
                f"{min(amounts):.2f}-{max(amounts):.2f}", last_order_at,
                next_date.isoformat(), probability, stage,
                json.dumps(risks, ensure_ascii=False), recommendation,
                datetime.now().isoformat(timespec="seconds"),
            )
            if existing:
                cursor.execute(
                    """
                    UPDATE customer_profiles SET customer_level = ?, total_orders = ?, total_spent = ?,
                    total_profit = ?, preferred_destinations_json = ?, preferred_budget_range = ?,
                    last_order_at = ?, next_repurchase_date = ?, repurchase_probability = ?,
                    lifecycle_stage = ?, risk_flags_json = ?, recommendation_text = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (*values, existing["id"]),
                )
                profile_id = existing["id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO customer_profiles (
                        customer_name, phone, customer_level, total_orders, total_spent, total_profit,
                        preferred_destinations_json, preferred_budget_range, last_order_at,
                        next_repurchase_date, repurchase_probability, lifecycle_stage,
                        risk_flags_json, recommendation_text, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (customer_name, phone, *values),
                )
                profile_id = cursor.lastrowid
            generated.append(profile_id)
        conn.commit()
        profiles = cls._profiles_by_ids(cursor, generated)
        conn.close()
        return profiles

    @staticmethod
    def _profiles_by_ids(cursor, ids):
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(f"SELECT * FROM customer_profiles WHERE id IN ({placeholders}) ORDER BY id", ids)
        return [serialize_profile(row) for row in cursor.fetchall()]

    @classmethod
    def list_profiles(cls, customer_level=None, lifecycle_stage=None):
        conn = get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM customer_profiles"
        conditions = []
        params = []
        if customer_level:
            conditions.append("customer_level = ?")
            params.append(customer_level)
        if lifecycle_stage:
            conditions.append("lifecycle_stage = ?")
            params.append(lifecycle_stage)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY repurchase_probability DESC, total_profit DESC, id DESC"
        cursor.execute(sql, params)
        profiles = [serialize_profile(row) for row in cursor.fetchall()]
        conn.close()
        return profiles

    @classmethod
    def get_profile(cls, profile_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customer_profiles WHERE id = ?", (profile_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="未找到该客户画像")
        return serialize_profile(row)

    @classmethod
    def generate_repurchase_tasks(cls):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM customer_profiles AS p
            WHERE (repurchase_probability >= 0.5 OR customer_level = 'high_value' OR lifecycle_stage = 'dormant')
              AND NOT EXISTS (SELECT 1 FROM repurchase_tasks AS t WHERE t.customer_profile_id = p.id AND t.status = 'pending')
            ORDER BY repurchase_probability DESC, total_profit DESC
            """
        )
        profile_rows = cursor.fetchall()
        task_ids = []
        for row in profile_rows:
            profile = serialize_profile(row)
            destination = profile["preferred_destinations"][0] if profile["preferred_destinations"] else None
            cursor.execute(
                "SELECT id FROM travel_products WHERE status = 'active' AND (? IS NULL OR destination = ?) ORDER BY id LIMIT 1",
                (destination, destination),
            )
            product = cursor.fetchone()
            priority = "high" if profile["customer_level"] == "high_value" or profile["lifecycle_stage"] == "dormant" else "medium"
            due_date = profile["next_repurchase_date"] or date.today().isoformat()
            reason = (
                "沉睡客户唤醒，需先确认客户是否仍有出行需求"
                if profile["lifecycle_stage"] == "dormant"
                else "历史订单与复购概率达到规则阈值"
            )
            cursor.execute(
                """
                INSERT INTO repurchase_tasks (
                    customer_profile_id, customer_name, phone, recommended_destination,
                    recommended_product_id, reason, priority, due_date, assigned_sales
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (profile["id"], profile["customer_name"], profile["phone"], destination,
                 product["id"] if product else None, reason, priority, due_date, "未分配"),
            )
            task_ids.append(cursor.lastrowid)
        conn.commit()
        tasks = cls._tasks_by_ids(cursor, task_ids)
        conn.close()
        return tasks

    @staticmethod
    def _tasks_by_ids(cursor, ids):
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        cursor.execute(f"SELECT * FROM repurchase_tasks WHERE id IN ({placeholders}) ORDER BY id", ids)
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def list_tasks(cls, status=None):
        conn = get_connection()
        cursor = conn.cursor()
        sql = "SELECT * FROM repurchase_tasks"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date, id"
        cursor.execute(sql, params)
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks

    @classmethod
    def update_task_status(cls, task_id, status):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM repurchase_tasks WHERE id = ?", (task_id,))
        existing = cursor.fetchone()
        if existing is None:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该复购任务")
        completed_at = existing["completed_at"]
        if status == "completed" and not completed_at:
            completed_at = datetime.now().isoformat(timespec="seconds")
        elif status != "completed":
            completed_at = None
        cursor.execute("UPDATE repurchase_tasks SET status = ?, completed_at = ? WHERE id = ?", (status, completed_at, task_id))
        conn.commit()
        cursor.execute("SELECT * FROM repurchase_tasks WHERE id = ?", (task_id,))
        task = dict(cursor.fetchone())
        conn.close()
        return task
