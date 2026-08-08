import polars as pl


def moving_average_crossover_signals(
    bars: pl.DataFrame, short_window: int, long_window: int
) -> pl.DataFrame:
    if short_window >= long_window:
        raise ValueError("short_window must be less than long_window")
    if bars.height < long_window + 1:
        raise ValueError("not enough bars for the requested moving-average windows")

    return bars.with_columns(
        pl.col("close").rolling_mean(short_window).alias("short_ma"),
        pl.col("close").rolling_mean(long_window).alias("long_ma"),
    ).with_columns(
        pl.when(pl.col("short_ma") > pl.col("long_ma"))
        .then(1.0)
        .otherwise(0.0)
        .shift(1)
        .fill_null(0.0)
        .alias("position")
    )
