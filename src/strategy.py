"""Strategy definitions. The live signal logic is intentionally deferred."""


STRATEGY_NAME = "HTF Trend Pullback Trail"


def signal(frame, config):
    """Build non-lookahead signals in the backtest implementation phase."""
    raise NotImplementedError("Backtest implementation is scheduled for the next phase")
