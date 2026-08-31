from datetime import date
from types import SimpleNamespace

import pandas as pd

from app.market_data.yahoo import YahooFinanceProvider


def test_single_symbol_download_flattens_columns_without_pyarrow(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            [100.0, 101.0, 99.0, 100.5, 1_000],
            [101.0, 102.0, 100.0, 101.5, 1_100],
        ],
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        columns=pd.MultiIndex.from_tuples(
            [
                ("Open", "MSFT"),
                ("High", "MSFT"),
                ("Low", "MSFT"),
                ("Close", "MSFT"),
                ("Volume", "MSFT"),
            ]
        ),
    )
    monkeypatch.setattr("app.market_data.yahoo.yf.download", lambda **_: frame)
    monkeypatch.setattr(
        "app.market_data.yahoo.get_settings", lambda: SimpleNamespace(yahoo_auto_adjust=False)
    )

    result = YahooFinanceProvider().fetch_bars(
        symbol="MSFT", start=date(2024, 1, 1), end=date(2024, 1, 4), interval="1d"
    )

    assert result.columns == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert result.height == 2
