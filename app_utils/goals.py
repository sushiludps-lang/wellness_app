def daily_weight_change(target_kg, current_kg, days_left):
    if days_left <= 0:
        return 0.0
    return (target_kg - current_kg) / days_left

def protein_target(weight, goal_type):
    if goal_type == "gain":
        return round(weight * 1.8, 1)
    if goal_type == "loss":
        return round(weight * 1.6, 1)
    return round(weight * 1.5, 1)
