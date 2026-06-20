from difflib import SequenceMatcher


KEYWORD_ALIASES = {
    "亲子": ("亲子", "家庭", "儿童"),
    "老人": ("老人", "长者", "老年", "康养"),
    "疗休养": ("疗休养", "康养", "休养"),
    "团建": ("团建", "团队", "员工"),
    "自由行": ("自由行", "自由"),
    "品质": ("品质", "精品", "高端"),
    "低价": ("低价", "实惠", "经济", "优惠"),
    "暑假": ("暑假", "夏令营"),
    "寒假": ("寒假", "冬令营"),
    "海岛": ("海岛", "海湾", "沙滩", "巽寮湾"),
    "研学": ("研学", "学习", "文化"),
}


def normalize_text(value):
    if value is None:
        return ""
    return "".join(str(value).lower().split())


def score_destination(requested_destination, product_destination):
    requested = normalize_text(requested_destination)
    product = normalize_text(product_destination)

    if not requested:
        return 20, "未指定目的地，按通用匹配计分"

    if requested == product:
        return 40, f"目的地与{product_destination}完全匹配"

    if requested in product or product in requested:
        return 30, f"目的地与{product_destination}模糊匹配"

    similarity = SequenceMatcher(None, requested, product).ratio()
    if similarity >= 0.5:
        return 15, f"目的地与{product_destination}存在一定相似度"

    return 0, f"目的地与{product_destination}不匹配"


def score_budget(product_price, budget):
    if budget is None or budget <= 0:
        return 15, "未提供有效预算，按中性分计算"

    if product_price <= budget:
        price_ratio = product_price / budget
        if price_ratio >= 0.9:
            score = 30
        elif price_ratio >= 0.75:
            score = 27
        elif price_ratio >= 0.5:
            score = 23
        else:
            score = 20
        return score, f"价格{product_price}元在预算{budget}元以内"

    over_budget_ratio = (product_price - budget) / budget
    if over_budget_ratio <= 0.1:
        return 18, f"价格超预算{product_price - budget}元，差距较小"
    if over_budget_ratio <= 0.25:
        return 8, f"价格超预算{product_price - budget}元"
    return 0, f"价格超预算{product_price - budget}元，差距较大"


def score_people(people_count, product):
    if people_count is None:
        return 5, "未提供出行人数，按中性分计算"

    min_people = product.get("min_people")
    max_people = product.get("max_people")
    if min_people is None and max_people is None:
        return 5, "产品未设置人数限制，按中性分计算"

    if min_people is not None and people_count < min_people:
        return 2, f"出行人数低于产品最低人数{min_people}"
    if max_people is not None and people_count > max_people:
        return 0, f"出行人数超过产品上限{max_people}"
    return 10, "出行人数符合产品限制"


def score_departure_date(departure_date, product):
    if departure_date is None:
        return 3, "未提供出发日期，按中性分计算"

    available_from = product.get("available_from")
    available_to = product.get("available_to")
    if available_from is None and available_to is None:
        return 3, "产品未设置可售日期，按中性分计算"

    departure = str(departure_date)
    if available_from is not None and departure < str(available_from):
        return 0, "出发日期早于产品可售日期"
    if available_to is not None and departure > str(available_to):
        return 0, "出发日期晚于产品可售日期"
    return 5, "出发日期在产品可售范围内"


def score_keywords(message, product):
    message_text = normalize_text(message)
    if not message_text:
        return 0, []

    product_text = normalize_text(
        " ".join([
            product.get("title") or "",
            product.get("destination") or "",
            product.get("category") or "",
            product.get("description") or "",
        ])
    )

    matched_keywords = []
    for keyword, aliases in KEYWORD_ALIASES.items():
        if keyword not in message_text:
            continue
        if any(normalize_text(alias) in product_text for alias in aliases):
            matched_keywords.append(keyword)

    return min(len(matched_keywords) * 3, 15), matched_keywords


def score_product(
    product,
    destination=None,
    budget=None,
    people_count=None,
    departure_date=None,
    message=None,
):
    destination_score, destination_reason = score_destination(
        destination,
        product["destination"],
    )
    budget_score, budget_reason = score_budget(product["price"], budget)
    people_score, people_reason = score_people(people_count, product)
    departure_date_score, departure_date_reason = score_departure_date(
        departure_date,
        product,
    )
    keyword_score, matched_keywords = score_keywords(message, product)

    score_detail = {
        "destination_score": destination_score,
        "budget_score": budget_score,
        "people_score": people_score,
        "departure_date_score": departure_date_score,
        "keyword_score": keyword_score,
    }
    total_score = sum(score_detail.values())

    reason_parts = [destination_reason, budget_reason]
    if people_score != 5:
        reason_parts.append(people_reason)
    if departure_date_score != 3:
        reason_parts.append(departure_date_reason)
    if matched_keywords:
        keyword_text = "、".join(matched_keywords)
        reason_parts.append(f"匹配需求关键词：{keyword_text}")

    needs_manual_confirmation = (
        (bool(normalize_text(destination)) and destination_score < 40)
        or (budget is not None and budget > 0 and product["price"] > budget)
    )
    if needs_manual_confirmation:
        reason_parts.append("预算或条件存在差异，建议销售人工确认")

    product_info = {
        "id": product["id"],
        "title": product["title"],
        "destination": product["destination"],
        "days": product["days"],
        "price": product["price"],
        "category": product["category"],
        "description": product["description"],
    }
    recommendation_reason = "；".join(reason_parts)

    return {
        **product_info,
        "product": product_info,
        "total_score": total_score,
        "score_detail": score_detail,
        "recommendation_reason": recommendation_reason,
        "reason": recommendation_reason,
        "_eligible": (
            (budget is None or budget <= 0 or budget_score > 0)
            and (destination is None or destination_score > 0 or keyword_score > 0)
        ),
    }


def rank_recommendations(
    products,
    destination=None,
    budget=None,
    people_count=None,
    departure_date=None,
    message=None,
):
    scored_products = [
        score_product(
            product,
            destination=destination,
            budget=budget,
            people_count=people_count,
            departure_date=departure_date,
            message=message,
        )
        for product in products
    ]
    scored_products.sort(
        key=lambda item: (-item["total_score"], item["price"], item["id"])
    )

    eligible_products = [item for item in scored_products if item["_eligible"]]
    recommendations = eligible_products if eligible_products else scored_products[:3]

    if not eligible_products:
        fallback_notice = "预算或条件存在差异，建议销售人工确认"
        for item in recommendations:
            if fallback_notice not in item["recommendation_reason"]:
                item["recommendation_reason"] += f"；{fallback_notice}"
                item["reason"] = item["recommendation_reason"]

    for item in recommendations:
        item.pop("_eligible", None)

    return recommendations
