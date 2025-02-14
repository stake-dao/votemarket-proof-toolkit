import asyncio
import httpx
import os

from typing import Any, Dict, List

from rich import print as rprint
from rich.console import Console
from web3 import Web3

from votemarket_toolkit.shared.constants import GaugeControllerConstants
from votemarket_toolkit.shared.services.etherscan_service import (
    get_logs_by_address_and_topics,
)
from votemarket_toolkit.votes.models.data_types import GaugeVotes, VoteLog
from votemarket_toolkit.votes.services.parquet_service import ParquetService

console = Console()


class VotesService:
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self.parquet_service = ParquetService(cache_dir)
        self.votes_cache_file = "{protocol}_votes_cache.parquet"
        self.api_base_url = "https://raw.githubusercontent.com/stake-dao/api/main/api/votemarket/votes_cache"

    def _get_start_block(self, protocol: str, cache_file: str) -> int:
        """Get the starting block for vote fetching"""
        try:
            start_block_list = self.parquet_service.get_columns(
                cache_file, ["latest_block"]
            ).get("latest_block", [])

            return (
                start_block_list[0]
                if start_block_list
                else GaugeControllerConstants.CREATION_BLOCKS[protocol]
            )
        except Exception:
            return GaugeControllerConstants.CREATION_BLOCKS[protocol]

    async def _get_remote_parquet(self, protocol: str) -> None:
        """Fetch parquet file from stake-dao/api repository"""

        remote_file = f"{self.api_base_url}/{protocol}_votes_cache.parquet"
        cache_file = os.path.join(self.cache_dir, self.votes_cache_file.format(protocol=protocol))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(remote_file)
                response.raise_for_status()

                # Ensure cache directory exists
                os.makedirs(self.cache_dir, exist_ok=True)

                # Write the downloaded file
                with open(cache_file, "wb") as f:
                    f.write(response.content)
                rprint(f"[green]Successfully downloaded votes cache from stake-dao/api[/green]")
        except Exception as e:
            rprint(f"[red]Failed to fetch remote parquet file: {str(e)}[/red]")
            # If file doesn't exist locally, create empty cache
            if not os.path.exists(cache_file):
                self.parquet_service.save_votes(self.votes_cache_file.format(protocol=protocol), 0, [])

    async def get_gauge_votes(
        self, protocol: str, gauge_address: str, block_number: int
    ) -> GaugeVotes:
        """Query and return votes for a specific gauge"""
        cache_file = self.votes_cache_file.format(protocol=protocol)

        # Try to fetch latest data from stake-dao/api
        await self._get_remote_parquet(protocol)

        if cache_file:
            rprint(f"[cyan]Using cached votes file: {cache_file}[/cyan]")

        start_block = self._get_start_block(protocol, cache_file)
        end_block = block_number


        rprint(f"[cyan]Fetching votes from block {start_block} to {end_block}[/cyan]")


        all_votes = await self._get_all_votes(
            protocol, start_block, end_block, cache_file
        )

        filtered_votes = [
            VoteLog.from_dict(vote)
            for vote in all_votes
            if vote["gauge_addr"].lower() == gauge_address.lower()
        ]

        rprint(
            f"[green]Filtered votes for gauge {gauge_address}:"
            f" {len(filtered_votes)}[/green]"
        )

        return GaugeVotes(
            gauge_address=gauge_address,
            votes=filtered_votes,
            latest_block=end_block,
        )

    async def _get_all_votes(
        self, protocol: str, start_block: int, end_block: int, cache_file: str
    ) -> List[Dict[str, Any]]:
        """Get all votes combining cache and new fetches"""
        if start_block < end_block:
            rprint(
                f"[cyan]Fetching new votes from block {start_block} to"
                f" {end_block}[/cyan]"
            )
            new_votes = await self._fetch_new_votes(
                protocol, start_block, end_block
            )
            cached_votes = self._get_cached_votes(cache_file)
            all_votes = cached_votes + new_votes

            rprint(f"[green]Total votes: {len(all_votes)}[/green]")
            self.parquet_service.save_votes(cache_file, end_block, all_votes)
            return all_votes

        rprint("[yellow]No new votes to fetch. Using cached data.[/yellow]")
        return self._get_cached_votes(cache_file)

    def _get_cached_votes(self, cache_file: str) -> List[Dict[str, Any]]:
        """Get votes from cache"""
        cached_data = self.parquet_service.get_columns(
            cache_file, ["time", "user", "gauge_addr", "weight"]
        )
        return [
            {"time": t, "user": u, "gauge_addr": g, "weight": w}
            for t, u, g, w in zip(
                cached_data["time"],
                cached_data["user"],
                cached_data["gauge_addr"],
                cached_data["weight"],
            )
        ]

    async def _fetch_votes_chunk(
        self,
        protocol: str,
        start_block: int,
        end_block: int,
    ) -> List[Dict[str, Any]]:
        """Fetch a chunk of votes"""
        try:
            votes_logs = get_logs_by_address_and_topics(
                GaugeControllerConstants.GAUGE_CONTROLLER[protocol],
                start_block,
                end_block,
                {"0": GaugeControllerConstants.VOTE_EVENT_HASH},
            )
            rprint(f"{len(votes_logs)} votes logs found")
            return [self._decode_vote_log(log) for log in votes_logs]
        except Exception as e:
            if "No records found" in str(e):
                return []
            raise

    async def _fetch_new_votes(
        self,
        protocol: str,
        start_block: int,
        end_block: int,
    ) -> List[Dict[str, Any]]:
        """Fetch new votes in chunks"""
        INCREMENT = 100_000
        tasks = []

        for block in range(start_block, end_block + 1, INCREMENT):
            current_end_block = min(block + INCREMENT - 1, end_block)
            task = asyncio.create_task(
                self._fetch_votes_chunk(protocol, block, current_end_block)
            )
            tasks.append(task)

        chunks = await asyncio.gather(*tasks)
        return [vote for chunk in chunks for vote in chunk]

    def _decode_vote_log(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """Decode a vote log"""
        data = bytes.fromhex(log["data"][2:])
        try:
            return {
                "time": int.from_bytes(data[0:32], byteorder="big"),
                "user": Web3.to_checksum_address("0x" + data[44:64].hex()),
                "gauge_addr": Web3.to_checksum_address(
                    "0x" + data[76:96].hex()
                ),
                "weight": int.from_bytes(data[96:128], byteorder="big"),
            }
        except ValueError as e:
            raise ValueError(
                f"Error decoding vote log: {str(e)}. Raw data: {log['data']}"
            )


# Global instance
votes_service = VotesService()
