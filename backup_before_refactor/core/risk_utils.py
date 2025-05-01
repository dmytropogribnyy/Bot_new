# Функции для автоматизации (будут использоваться после теста)
def get_adaptive_risk_percent(balance):
    if balance < 100:
        return 0.01
    elif balance < 300:
        return 0.02
    elif balance < 1000:
        return 0.03
    else:
        return 0.05


def get_max_positions(balance):
    if balance < 100:
        return 1
    elif balance < 300:
        return 2
    elif balance < 1000:
        return 3
    else:
        return 5
