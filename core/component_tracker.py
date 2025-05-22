# component_tracker.py
import json
import os
from datetime import datetime

from constants import COMPONENT_TRACKER_LOG_FILE
from utils_logging import log


def log_component_data(symbol, breakdown, is_successful=True):
    """
    Track components that contributed to a signal for analysis.

    Args:
        symbol (str): Trading pair symbol
        breakdown (dict): Signal components breakdown
        is_successful (bool): Whether the trade was successful
    """
    filepath = COMPONENT_TRACKER_LOG_FILE

    try:
        # Create directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        # Load existing data or create new
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {"symbols": {}, "components": {}, "candlestick_rejections": 0}
        else:
            data = {"symbols": {}, "components": {}, "candlestick_rejections": 0}

        # Initialize symbol data if not exists
        if symbol not in data["symbols"]:
            data["symbols"][symbol] = {"count": 0, "successful": 0, "components": {}}

        # Update symbol statistics
        data["symbols"][symbol]["count"] += 1
        if is_successful:
            data["symbols"][symbol]["successful"] += 1

        # Update counts for each active component
        for component, value in breakdown.items():
            if value > 0:
                # Update global component stats
                if component not in data["components"]:
                    data["components"][component] = {"count": 0, "successful": 0, "last_used": ""}

                data["components"][component]["count"] += 1
                if is_successful:
                    data["components"][component]["successful"] += 1
                data["components"][component]["last_used"] = datetime.utcnow().isoformat()

                # Update symbol-specific component stats
                if component not in data["symbols"][symbol]["components"]:
                    data["symbols"][symbol]["components"][component] = {"count": 0, "successful": 0}

                data["symbols"][symbol]["components"][component]["count"] += 1
                if is_successful:
                    data["symbols"][symbol]["components"][component]["successful"] += 1

        # Save back to file
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        log(f"Error logging component data: {e}", level="ERROR")
