from app.db.session import SessionLocal
from app.market_data.live import LiveMarketDataProvider, YahooFinanceLiveMarketDataProvider
from app.market_data.provider import MarketDataProvider
from app.market_data.yahoo import YahooFinanceProvider
from app.paper_trading.live_service import LivePaperTradingService

_live_paper_trading_service: LivePaperTradingService | None = None


def get_market_data_provider() -> MarketDataProvider:
    return YahooFinanceProvider()


def get_live_market_data_provider() -> LiveMarketDataProvider:
    return YahooFinanceLiveMarketDataProvider()


def get_live_paper_trading_service() -> LivePaperTradingService:
    global _live_paper_trading_service
    if _live_paper_trading_service is None:
        _live_paper_trading_service = LivePaperTradingService(
            SessionLocal,
            get_live_market_data_provider(),
        )
    return _live_paper_trading_service
