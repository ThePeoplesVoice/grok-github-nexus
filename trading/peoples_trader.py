from decimal import Decimal
from nexustrader.strategy import Strategy
from nexustrader.constants import ExchangeType, OrderSide, OrderType
from nexustrader.config import Config
from nexustrader.engine import Engine
from nexustrader.schema import BookL1


class PeoplesVoiceTrader(Strategy):
    def init(self):
        super().init()
        self.exchange = ExchangeType.BINANCE
        self.symbol = "BTCUSDT"

    def on_bookl1(self, book: BookL1):
        if book.bid > 0 and book.ask > 0:
            spread = (book.ask - book.bid) / book.bid
            if spread > Decimal('0.001'):  # 10 basis points
                self.create_order(
                    symbol=self.symbol,
                    side=OrderSide.BUY,
                    quantity=Decimal('0.001'),
                    order_type=OrderType.MARKET,
                )
