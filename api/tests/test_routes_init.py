from ragtrader_api.routes import create_strategy_app, create_strategy_router


def test_routes_init_exports_strategy_helpers() -> None:
    assert callable(create_strategy_app)
    assert callable(create_strategy_router)
