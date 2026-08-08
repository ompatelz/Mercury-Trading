from app.market_data.provider import MarketDataProvider
from app.market_data.yahoo import YahooFinanceProvider


def get_market_data_provider() -> MarketDataProvider:
    return YahooFinanceProvider()
