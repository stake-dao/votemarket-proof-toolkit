import asyncio
import os
import time
import logging
from typing import Dict, List, Any
import requests
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_KEY = os.getenv("ETHERSCAN_API_KEY", "")


class RateLimiter:
    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self.queue = []
        self.running = 0

    async def add(self, fn):
        while self.running >= self.max_concurrent:
            await asyncio.sleep(0.1)
        self.running += 1
        try:
            return await fn()
        finally:
            self.running -= 1
            if self.queue:
                self.queue.pop(0)()


rate_limiter = RateLimiter(5)


def delay(ms: int):
    time.sleep(ms / 1000)


def get_logs_by_address_and_topics(
    address: str, from_block: int, to_block: int, topics: Dict[str, str]
) -> Dict[str, Any]:
    url = f"https://api.etherscan.io/api?module=logs&action=getLogs&fromBlock={from_block}&toBlock={to_block}&address={address}&apikey={ETHERSCAN_KEY}"

    for key, value in topics.items():
        url += f"&topic{key}_{int(key)+1}_opr=and&topic{key}={value}"

    max_retries = 5
    retries = 0

    while retries < max_retries:
        try:
            response = requests.get(url)
            data = response.json()

            if data["status"] == "1":
                return data["result"]
            elif data["status"] == "0" and data["message"] == "No records found":
                logging.info(
                    f"No records found for address {address} from block {from_block} to {to_block}"
                )
                return {}
            elif (
                data["message"] == "NOTOK"
                and data["result"] == "Max rate limit reached"
                or data["message"] == "NOTOK"
                and data["result"] == "Max calls per sec rate limit reached (5/sec)"
            ):
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
                retries += 1
            else:
                logging.error(f"Unexpected response: {data}")
                raise Exception(data["message"] or "Unknown error")
        except requests.RequestException as e:
            if response.status_code == 429:
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
                retries += 1
            else:
                logging.error(f"Error fetching logs: {str(e)}")
                raise e

    raise Exception("Max retries reached")


@staticmethod
def get_token_transfers(
    address: str,
    contract_address: str = None,
    from_block: int = 0,
    to_block: int = 99999999,
    sort: str = "asc",
) -> Dict[str, Any]:
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&startblock={from_block}&endblock={to_block}&sort={sort}&apikey={ETHERSCAN_KEY}"

    if contract_address:
        url += f"&contractaddress={contract_address}"

    max_retries = 5
    retries = 0

    while retries < max_retries:
        try:
            response = requests.get(url)
            data = response.json()

            if data["status"] == "1":
                return data["result"]
            elif data["status"] == "0" and data["message"] == "No transactions found":
                logging.info(f"No token transfers found for address {address}")
                return []
            elif (
                data["message"] == "NOTOK"
                and data["result"] == "Max rate limit reached"
                or data["message"] == "NOTOK"
                and data["result"] == "Max calls per sec rate limit reached (5/sec)"
            ):
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
                retries += 1
            else:
                logging.error(f"Unexpected response: {data}")
                raise Exception(data["message"] or "Unknown error")
        except requests.RequestException as e:
            if response.status_code == 429:
                logging.info("Rate limit reached, retrying after delay...")
                delay(1000)
                retries += 1
            else:
                logging.error(f"Error fetching token transfers: {str(e)}")
                raise e

    raise Exception("Max retries reached")
