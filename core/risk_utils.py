# Функции для автоматизации (будут использоваться после теста)
def get_adaptive_risk_percent(balance):
    if balance < 100:
        return 0.02  # 2% for ultra-small accounts (more aggressive for quick results)
    elif balance < 150:
        return 0.025  # 2.5% for small accounts
    elif balance < 300:
        return 0.03  # 3% for medium accounts
    else:
        return 0.04  # 4% for larger accounts


def get_max_positions(balance):
    if balance < 100:
        return 2  # Allow 2 positions for ultra-small accounts for faster testing
    elif balance < 150:
        return 3  # More positions for small accounts
    elif balance < 300:
        return 4  # Even more for medium accounts
    else:
        return 5  # Max for large accounts
