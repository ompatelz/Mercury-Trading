from app.evolution.specification import StrategySpecification


def population_diversity(specifications: list[StrategySpecification]) -> dict[str, float | int]:
    if len(specifications) < 2:
        return {
            "population_size": len(specifications),
            "parameter_distance": 0.0,
            "family_count": len(specifications),
        }
    distances = []
    for left_index, left in enumerate(specifications):
        for right in specifications[left_index + 1 :]:
            distances.append(
                (
                    abs(left.short_window - right.short_window)
                    + abs(left.long_window - right.long_window)
                )
                / 252.0
            )
    families = {specification.strategy_family for specification in specifications}
    return {
        "population_size": len(specifications),
        "parameter_distance": round(sum(distances) / len(distances), 6),
        "family_count": len(families),
    }
