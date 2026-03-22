def calculate_order_total(items: list[dict]) -> float:
    """
    Sum price * quantity for all items.
    """
    total = 0.0
    for item in items:
        total += item["price"] * item["quantity"]
    return round(total, 2)


def apply_discount(total: float, discount_rate: float) -> float:
    """
    Apply a percentage discount to the total.
    """
    discount = total * discount_rate
    return round(total - discount, 2)
