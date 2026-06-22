from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


MONEY = Decimal("0.01")
MARGIN = Decimal("0.0001")


def as_decimal(value):
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def money(value, rounding=ROUND_HALF_UP):
    return as_decimal(value).quantize(MONEY, rounding=rounding)


def margin(value):
    return as_decimal(value).quantize(MARGIN, rounding=ROUND_HALF_UP)


def parse_date(value):
    if value is None:
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


class PricingService:
    """使用本地规则计算报价，不调用外部 AI 或外部价格接口。"""

    HIGH_BUDGET_THRESHOLD = Decimal("1.20")
    HIGH_BUDGET_UPLIFT = Decimal("0.05")

    @classmethod
    def calculate(
        cls,
        resource_items,
        target_margin,
        customer_budget=None,
        departure_date=None,
        today=None,
    ):
        target = as_decimal(target_margin)
        budget = (
            money(customer_budget) if customer_budget is not None else None
        )
        today = today or date.today()
        departure = parse_date(departure_date)

        base_cost = money(
            sum(
                as_decimal(item.get("unit_cost")) * item["quantity"]
                for item in resource_items
            )
        )
        listed_price = money(
            sum(
                as_decimal(item.get("listed_unit_price")) * item["quantity"]
                for item in resource_items
            )
        )

        risk_flags = []
        if any(item.get("cost_missing") for item in resource_items):
            risk_flags.append("missing_resource_cost")

        denominator = Decimal("1") - target
        margin_floor = (
            money(base_cost / denominator, ROUND_CEILING)
            if denominator > 0
            else listed_price
        )
        base_price = max(listed_price, margin_floor)
        if margin_floor > listed_price:
            risk_flags.append("margin_protection")

        min_available = min(
            (int(item["available_quantity"]) for item in resource_items),
            default=None,
        )
        inventory_rate = Decimal("0")
        if min_available is not None and min_available <= 2:
            inventory_rate = Decimal("0.10")
        elif min_available is not None and min_available <= 5:
            inventory_rate = Decimal("0.05")
        if inventory_rate:
            risk_flags.append("low_stock_price_increase")

        departure_rate = Decimal("0")
        if departure is not None:
            days_until_departure = (departure - today).days
            if 0 <= days_until_departure <= 7:
                departure_rate = Decimal("0.08")
            elif days_until_departure <= 14 and days_until_departure >= 0:
                departure_rate = Decimal("0.04")
        if departure_rate:
            risk_flags.append("near_departure_price_increase")

        dynamic_adjustment = money(
            base_price * (inventory_rate + departure_rate)
        )
        provisional_price = money(base_price + dynamic_adjustment)

        if (
            budget is not None
            and base_price > 0
            and budget >= money(base_price * cls.HIGH_BUDGET_THRESHOLD)
            and budget > provisional_price
        ):
            opportunity_uplift = min(
                money(base_price * cls.HIGH_BUDGET_UPLIFT),
                money(budget - provisional_price),
            )
            if opportunity_uplift > 0:
                dynamic_adjustment = money(
                    dynamic_adjustment + opportunity_uplift
                )
                risk_flags.append("high_margin_opportunity")

        final_price = money(base_price + dynamic_adjustment)
        final_margin_floor = (
            money(base_cost / denominator, ROUND_CEILING)
            if denominator > 0
            else final_price
        )
        if final_price < final_margin_floor:
            protection = money(final_margin_floor - final_price)
            dynamic_adjustment = money(dynamic_adjustment + protection)
            final_price = final_margin_floor
            if "margin_protection" not in risk_flags:
                risk_flags.append("margin_protection")

        estimated_profit = money(final_price - base_cost)
        estimated_margin = (
            margin(estimated_profit / final_price)
            if final_price > 0
            else Decimal("0.0000")
        )

        if budget is not None and final_price > budget:
            risk_flags.append("over_customer_budget")
        if final_price == 0 or estimated_margin < target:
            risk_flags.append("below_target_margin")

        priced_items = cls._allocate_item_prices(resource_items, final_price)
        recommendation = cls._build_recommendation(risk_flags)
        return {
            "base_cost": float(base_cost),
            "base_price": float(base_price),
            "dynamic_adjustment": float(dynamic_adjustment),
            "final_price": float(final_price),
            "estimated_profit": float(estimated_profit),
            "estimated_margin": float(estimated_margin),
            "risk_flags": risk_flags,
            "recommendation": recommendation,
            "items": priced_items,
        }

    @classmethod
    def _allocate_item_prices(cls, resource_items, final_price):
        if not resource_items:
            return []

        listed_weights = [
            money(as_decimal(item.get("listed_unit_price")) * item["quantity"])
            for item in resource_items
        ]
        weight_total = sum(listed_weights, Decimal("0"))
        if weight_total <= 0:
            listed_weights = [
                money(as_decimal(item.get("unit_cost")) * item["quantity"])
                for item in resource_items
            ]
            weight_total = sum(listed_weights, Decimal("0"))
        if weight_total <= 0:
            listed_weights = [Decimal("1") for _ in resource_items]
            weight_total = Decimal(len(resource_items))

        allocated = []
        assigned_total = Decimal("0")
        final_price = money(final_price)
        for index, (item, weight) in enumerate(
            zip(resource_items, listed_weights, strict=True)
        ):
            if index == len(resource_items) - 1:
                total_price = money(final_price - assigned_total)
            else:
                total_price = money(final_price * weight / weight_total)
                assigned_total = money(assigned_total + total_price)

            quantity = int(item["quantity"])
            total_cost = money(as_decimal(item.get("unit_cost")) * quantity)
            unit_price = money(total_price / quantity)
            item_margin = (
                margin((total_price - total_cost) / total_price)
                if total_price > 0
                else Decimal("0.0000")
            )
            allocated.append(
                {
                    **item,
                    "unit_cost": float(money(item.get("unit_cost"))),
                    "unit_price": float(unit_price),
                    "total_cost": float(total_cost),
                    "total_price": float(total_price),
                    "margin": float(item_margin),
                }
            )
        return allocated

    @staticmethod
    def _build_recommendation(risk_flags):
        recommendations = []
        if "missing_resource_cost" in risk_flags:
            recommendations.append("存在缺失或为零的资源成本，请补齐并人工复核报价。")
        if "margin_protection" in risk_flags:
            recommendations.append("已按目标毛利率执行最低售价保护。")
        if "low_stock_price_increase" in risk_flags:
            recommendations.append("库存紧张已触发加价，成交前请再次确认实时库存。")
        if "near_departure_price_increase" in risk_flags:
            recommendations.append("出发日期临近已触发加价，请尽快确认资源。")
        if "high_margin_opportunity" in risk_flags:
            recommendations.append("客户预算空间较高，已识别高利润机会并温和调价。")
        if "over_customer_budget" in risk_flags:
            recommendations.append("报价超过客户预算，不建议降至亏损，请销售沟通或调整资源方案。")
        if "below_target_margin" in risk_flags:
            recommendations.append("当前毛利仍低于目标，请暂停提交并人工调整。")
        if not recommendations:
            recommendations.append("报价毛利和预算匹配正常，可由销售复核后提交客户。")
        return " ".join(recommendations)
