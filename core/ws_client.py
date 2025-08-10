#!/usr/bin/env python3
"""
Stage E: WebSocket/User Data client for Binance USDC Futures
Provides functions for managing listen keys and streaming user data.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp


async def get_listen_key(http: aiohttp.ClientSession, api_base: str, headers: dict[str, str]) -> str:
    """
    Get a listen key for User Data Stream.

    Args:
        http: aiohttp ClientSession instance
        api_base: API base URL (e.g., "https://fapi.binance.com")
        headers: HTTP headers including API key

    Returns:
        listenKey string

    Raises:
        Exception: If request fails
    """
    url = f"{api_base}/fapi/v1/listenKey"

    async with http.post(url, headers=headers) as response:
        if response.status != 200:
            text = await response.text()
            raise Exception(f"Failed to get listen key: {response.status} - {text}")

        data = await response.json()
        listen_key = data.get("listenKey")

        if not listen_key:
            raise Exception(f"No listenKey in response: {data}")

        logging.info(f"Got listen key: {listen_key[:8]}...")
        return listen_key


async def keepalive(http: aiohttp.ClientSession, api_base: str, headers: dict[str, str], listen_key: str) -> None:
    """
    Keepalive a listen key to prevent it from expiring.

    Args:
        http: aiohttp ClientSession instance
        api_base: API base URL
        headers: HTTP headers including API key
        listen_key: The listen key to keep alive

    Raises:
        Exception: If request fails
    """
    url = f"{api_base}/fapi/v1/listenKey"
    params = {"listenKey": listen_key}

    async with http.put(url, headers=headers, params=params) as response:
        if response.status != 200:
            text = await response.text()
            raise Exception(f"Failed to keepalive listen key: {response.status} - {text}")

        logging.debug(f"Listen key keepalive successful: {listen_key[:8]}...")


async def stream_user_data(
    ws_url: str,
    listen_key: str,
    on_event: Callable[[dict[str, Any]], None],
    ws_reconnect_interval: int = 5,
    ws_heartbeat_interval: int = 30,
) -> None:
    """
    Stream user data from WebSocket.

    Args:
        ws_url: WebSocket base URL (e.g., "wss://stream.binance.com:9443")
        listen_key: Listen key for user data stream
        on_event: Callback function to handle incoming events
        ws_reconnect_interval: Reconnect interval in seconds (default: 5)
        ws_heartbeat_interval: Heartbeat interval in seconds (default: 30)

    This function handles:
    - WebSocket connection and reconnection
    - JSON parsing of incoming messages
    - Heartbeat/ping management
    - Calling on_event callback for each received event
    """
    full_url = f"{ws_url}/ws/{listen_key}"

    while True:
        try:
            logging.info(f"Connecting to WebSocket: {ws_url}/ws/{listen_key[:8]}...")

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(full_url, heartbeat=ws_heartbeat_interval, autoping=True) as ws:
                    logging.info("WebSocket connected successfully")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                event_dict = json.loads(msg.data)
                                logging.debug(f"Received event: {event_dict.get('e', 'unknown')}")

                                # Call the event handler
                                on_event(event_dict)

                            except json.JSONDecodeError as e:
                                logging.error(f"Failed to parse WebSocket message: {e}")
                                logging.error(f"Raw message: {msg.data}")

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logging.error(f"WebSocket error: {ws.exception()}")
                            break

                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logging.warning("WebSocket connection closed")
                            break

        except aiohttp.ClientError as e:
            logging.error(f"WebSocket connection error: {e}")

        except Exception as e:
            logging.error(f"Unexpected error in WebSocket stream: {e}")

        # Wait before reconnecting
        logging.info(f"Reconnecting in {ws_reconnect_interval} seconds...")
        await asyncio.sleep(ws_reconnect_interval)


class UserDataStreamManager:
    """
    Manager class for User Data Stream with automatic keepalive.
    """

    def __init__(
        self,
        api_base: str,
        ws_url: str,
        api_key: str,
        on_event: Callable[[dict[str, Any]], None],
        ws_reconnect_interval: int = 5,
        ws_heartbeat_interval: int = 30,
    ):
        """
        Initialize UserDataStreamManager.

        Args:
            api_base: API base URL
            ws_url: WebSocket base URL
            api_key: Binance API key
            on_event: Event handler callback
            ws_reconnect_interval: Reconnect interval
            ws_heartbeat_interval: Heartbeat interval
        """
        self.api_base = api_base
        self.ws_url = ws_url
        self.api_key = api_key
        self.on_event = on_event
        self.ws_reconnect_interval = ws_reconnect_interval
        self.ws_heartbeat_interval = ws_heartbeat_interval

        self.listen_key = None
        self.http_session = None
        self.keepalive_task = None
        self.stream_task = None

    async def start(self) -> None:
        """Start the user data stream with automatic keepalive."""
        headers = {"X-MBX-APIKEY": self.api_key}

        # Create HTTP session
        self.http_session = aiohttp.ClientSession()

        try:
            # Get listen key
            self.listen_key = await get_listen_key(self.http_session, self.api_base, headers)

            # Start keepalive task (every 30 minutes)
            self.keepalive_task = asyncio.create_task(self._keepalive_loop(headers))

            # Start streaming
            self.stream_task = asyncio.create_task(
                stream_user_data(
                    self.ws_url, self.listen_key, self.on_event, self.ws_reconnect_interval, self.ws_heartbeat_interval
                )
            )

            logging.info("User Data Stream started successfully")

        except Exception as e:
            logging.error(f"Failed to start User Data Stream: {e}")
            await self.stop()
            raise

    async def _keepalive_loop(self, headers: dict[str, str]) -> None:
        """Keep the listen key alive every 30 minutes."""
        while True:
            try:
                await asyncio.sleep(30 * 60)  # 30 minutes

                if self.listen_key and self.http_session:
                    await keepalive(self.http_session, self.api_base, headers, self.listen_key)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Keepalive error: {e}")

    async def stop(self) -> None:
        """Stop the user data stream and cleanup resources."""
        # Cancel tasks
        if self.keepalive_task:
            self.keepalive_task.cancel()

        if self.stream_task:
            self.stream_task.cancel()

        # Close HTTP session
        if self.http_session:
            await self.http_session.close()

        logging.info("User Data Stream stopped")


# Example event handlers
def log_event_handler(event: dict[str, Any]) -> None:
    """Simple event handler that logs events."""
    event_type = event.get("e", "unknown")
    logging.info(f"Event received: {event_type}")

    if event_type == "ACCOUNT_UPDATE":
        # Account update (margin, balance changes)
        logging.info(f"Account update: {event}")

    elif event_type == "ORDER_TRADE_UPDATE":
        # Order update (fills, cancellations, etc.)
        order = event.get("o", {})
        symbol = order.get("s", "")
        status = order.get("X", "")
        logging.info(f"Order update for {symbol}: {status}")

    elif event_type == "listenKeyExpired":
        # Listen key expired
        logging.error("Listen key expired!")

    else:
        logging.debug(f"Unhandled event type: {event_type}")
