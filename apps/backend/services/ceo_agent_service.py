from collections import Counter, defaultdict
from datetime import date

from apps.backend.services.profit_service import ProfitService


ALERT_CONFIG = {
    "negative_profit": ("negative_profit", "critical", "订单出现负毛利"),
    "low_margin": ("low_margin", "high", "订单毛利率低于 10%"),
    "unpaid_order": ("unpaid_order", "medium", "订单仍未支付"),
    "cancelled_order": ("cancelled_order", "medium", "订单已取消"),
    "missing_resource_cost": ("missing_cost", "high", "订单资源成本缺失"),
}


class CeoAgentService:
    """不调用外部模型的规则化 CEO 经营分析服务。"""

    def __init__(self, conn):
        self.profit_service = ProfitService(conn)

    def daily_report(self, report_date=None):
        report_date = report_date or date.today()
        orders = self._daily_orders(report_date)
        summary = self.profit_service.summarize_orders(orders)
        destination_summary = self._destination_summary(orders)
        risk_counts = Counter(
            flag for order in orders for flag in order["risk_flags"]
        )
        recommendations = self._build_recommendations(orders)

        paid_orders = [
            order for order in orders if order["payment_status"] == "mock_paid"
        ]
        paid_revenue = round(
            sum(order["order_revenue"] for order in paid_orders),
            2,
        )
        top_profit_orders = sorted(
            orders,
            key=lambda order: order["gross_profit"],
            reverse=True,
        )[:5]

        return {
            "report_date": report_date.isoformat(),
            "revenue_summary": {
                "booked_revenue": summary["total_revenue"],
                "paid_revenue": paid_revenue,
                "insurance_revenue": summary["total_insurance_revenue"],
            },
            "profit_summary": {
                "resource_cost": summary["total_resource_cost"],
                "gross_profit": summary["total_gross_profit"],
                "average_margin": summary["average_margin"],
                "high_profit_orders": summary["high_profit_orders"],
                "low_profit_orders": summary["low_profit_orders"],
                "loss_orders": summary["loss_orders"],
            },
            "order_summary": {
                "total_orders": summary["total_orders"],
                "paid_orders": summary["paid_orders"],
                "unpaid_orders": risk_counts["unpaid_order"],
                "cancelled_orders": summary["cancelled_orders"],
            },
            "destination_summary": destination_summary,
            "risk_summary": {
                "risk_orders": sum(bool(order["risk_flags"]) for order in orders),
                "risk_type_counts": dict(sorted(risk_counts.items())),
            },
            "top_profit_orders": [
                self._compact_order(order) for order in top_profit_orders
            ],
            "key_findings": self._key_findings(
                summary,
                destination_summary,
                risk_counts,
            ),
            "action_suggestions": [
                recommendation["action"] for recommendation in recommendations
            ],
        }

    def risk_alerts(self, report_date=None):
        report_date = report_date or date.today()
        orders = self._daily_orders(report_date)
        alerts = []
        for order in orders:
            for flag in order["risk_flags"]:
                alert_type, severity, message = ALERT_CONFIG[flag]
                alerts.append(
                    {
                        "risk_type": alert_type,
                        "severity": severity,
                        "order_id": order["order_id"],
                        "order_no": order["order_no"],
                        "destination": order["destination"],
                        "message": message,
                        "recommended_action": order["recommendation"],
                    }
                )

        concentration = self._concentration_risk(orders)
        if concentration is not None:
            alerts.append(concentration)

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(
            key=lambda alert: (
                severity_order[alert["severity"]],
                alert.get("order_id") or 0,
            )
        )
        return {
            "report_date": report_date.isoformat(),
            "count": len(alerts),
            "alerts": alerts,
        }

    def recommendations(self, report_date=None):
        report_date = report_date or date.today()
        orders = self._daily_orders(report_date)
        recommendations = self._build_recommendations(orders)
        return {
            "report_date": report_date.isoformat(),
            "count": len(recommendations),
            "recommendations": recommendations,
        }

    def _daily_orders(self, report_date):
        return self.profit_service.list_order_profits(
            date_from=report_date,
            date_to=report_date,
        )

    @staticmethod
    def _compact_order(order):
        return {
            "order_id": order["order_id"],
            "order_no": order["order_no"],
            "customer_name": order["customer_name"],
            "destination": order["destination"],
            "gross_profit": order["gross_profit"],
            "gross_margin": order["gross_margin"],
            "profit_level": order["profit_level"],
            "risk_flags": order["risk_flags"],
        }

    @staticmethod
    def _destination_summary(orders):
        grouped = defaultdict(list)
        for order in orders:
            grouped[order["destination"]].append(order)

        summaries = []
        for destination, destination_orders in grouped.items():
            revenue = round(
                sum(order["order_revenue"] for order in destination_orders),
                2,
            )
            gross_profit = round(
                sum(order["gross_profit"] for order in destination_orders),
                2,
            )
            summaries.append(
                {
                    "destination": destination,
                    "total_orders": len(destination_orders),
                    "revenue": revenue,
                    "gross_profit": gross_profit,
                    "gross_margin": (
                        round(gross_profit / revenue, 4) if revenue > 0 else 0.0
                    ),
                }
            )
        return sorted(
            summaries,
            key=lambda item: (item["gross_profit"], item["revenue"]),
            reverse=True,
        )

    @staticmethod
    def _key_findings(summary, destination_summary, risk_counts):
        findings = [
            f"今日新增订单 {summary['total_orders']} 单，订单总额 "
            f"{summary['total_revenue']:.2f} 元。",
            f"今日毛利 {summary['total_gross_profit']:.2f} 元，综合毛利率 "
            f"{summary['average_margin']:.2%}。",
        ]
        if destination_summary:
            top = destination_summary[0]
            findings.append(
                f"当前毛利贡献最高目的地为{top['destination']}，毛利 "
                f"{top['gross_profit']:.2f} 元。"
            )
        if risk_counts["negative_profit"] or risk_counts["low_margin"]:
            findings.append(
                f"低毛利或亏损订单共 "
                f"{risk_counts['low_margin'] + risk_counts['negative_profit']} 项风险。"
            )
        if risk_counts["unpaid_order"]:
            findings.append(
                f"有 {risk_counts['unpaid_order']} 单未支付，需要销售跟进。"
            )
        if risk_counts["missing_resource_cost"]:
            findings.append(
                f"有 {risk_counts['missing_resource_cost']} 单成本信息不完整。"
            )
        return findings

    def _build_recommendations(self, orders):
        risk_counts = Counter(
            flag for order in orders for flag in order["risk_flags"]
        )
        recommendations = []

        if risk_counts["negative_profit"] or risk_counts["low_margin"]:
            recommendations.append(
                self._recommendation(
                    "pricing",
                    "critical" if risk_counts["negative_profit"] else "high",
                    "修复低利润订单报价",
                    "提高低利润目的地报价，或重新组合交通、酒店和地接资源。",
                )
            )
        high_profit_orders = [
            order for order in orders if order["profit_level"] == "high_profit"
        ]
        if high_profit_orders:
            top = max(high_profit_orders, key=lambda order: order["gross_profit"])
            recommendations.append(
                self._recommendation(
                    "growth",
                    "high",
                    "优先推广高利润产品",
                    f"优先推广{top['destination']}相关产品，并复用高利润资源组合。",
                )
            )
        if risk_counts["missing_resource_cost"]:
            recommendations.append(
                self._recommendation(
                    "cost_control",
                    "high",
                    "补齐资源成本",
                    "检查成本缺失资源，成本核实前不要把对应订单作为高利润样本。",
                )
            )
        if risk_counts["unpaid_order"]:
            recommendations.append(
                self._recommendation(
                    "collection",
                    "high",
                    "跟进未支付订单",
                    "按订单金额和创建时间排序催付，及时关闭无效预留。",
                )
            )

        low_profit_count = sum(
            order["profit_level"] in ("low_profit", "loss") for order in orders
        )
        if orders and low_profit_count / len(orders) >= 0.20:
            recommendations.append(
                self._recommendation(
                    "margin_control",
                    "high",
                    "控制低毛利订单比例",
                    "设置 10% 毛利率审核线，低于审核线的订单需人工确认。",
                )
            )

        insurance_orders = sum(order["insurance_revenue"] > 0 for order in orders)
        if orders and insurance_orders / len(orders) < 0.30:
            recommendations.append(
                self._recommendation(
                    "insurance_attach",
                    "medium",
                    "优化保险附加销售",
                    "在报价和付款前增加保险说明，提升保险附加率。",
                )
            )

        concentration = self._concentration_risk(orders)
        if concentration is not None:
            recommendations.append(
                self._recommendation(
                    "concentration_control",
                    "medium",
                    "降低目的地集中风险",
                    concentration["recommended_action"],
                )
            )

        if not recommendations:
            recommendations.append(
                self._recommendation(
                    "monitoring",
                    "low",
                    "保持利润监控",
                    "当前未发现显著经营风险，继续核对订单收入、成本和支付状态。",
                )
            )
        return recommendations

    @staticmethod
    def _recommendation(category, priority, title, action):
        return {
            "category": category,
            "priority": priority,
            "title": title,
            "action": action,
        }

    @staticmethod
    def _concentration_risk(orders):
        if len(orders) < 3:
            return None
        total_revenue = sum(order["order_revenue"] for order in orders)
        if total_revenue <= 0:
            return None
        destination_revenue = Counter()
        for order in orders:
            destination_revenue[order["destination"]] += order["order_revenue"]
        destination, revenue = destination_revenue.most_common(1)[0]
        share = revenue / total_revenue
        if share < 0.60:
            return None
        return {
            "risk_type": "concentration_risk",
            "severity": "medium",
            "order_id": None,
            "order_no": None,
            "destination": destination,
            "message": f"{destination}收入占比达到 {share:.2%}",
            "recommended_action": "增加其他目的地有效订单，降低单一目的地依赖。",
        }
