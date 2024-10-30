import os
import pandas as pd
from typing import Dict, Any, List


class ParquetCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_file_path(self, filename: str) -> str:
        return os.path.join(self.cache_dir, filename)

    def load(self, filename: str) -> Dict[str, Any]:
        cache_file = self._get_cache_file_path(filename)
        if os.path.exists(cache_file):
            try:
                df = pd.read_parquet(cache_file)
                return df.to_dict(orient="list")
            except Exception as e:
                print(f"Error reading Parquet file: {e}")
                return {}
        return {}

    def save(self, filename: str, data: Dict[str, Any]):
        if not self._validate_data(data):
            raise ValueError("All arrays must be of the same length")
        cache_file = self._get_cache_file_path(filename)
        df = pd.DataFrame(data)
        df.to_parquet(cache_file)

    def get_columns(
        self, filename: str, column_names: List[str]
    ) -> Dict[str, List[Any]]:
        cache_file = self._get_cache_file_path(filename)
        if os.path.exists(cache_file):
            try:
                df = pd.read_parquet(cache_file, columns=column_names)
                return df.to_dict(orient="list")
            except Exception as e:
                print(
                    f"Error reading columns {column_names} from Parquet file: {e}"
                )
                return {col: [] for col in column_names}
        return {col: [] for col in column_names}

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        lengths = [len(v) for v in data.values()]
        if len(set(lengths)) != 1:
            print(f"Data validation error: {data}")
            return False
        return True

    def save_votes(
        self, filename: str, latest_block: int, votes: List[Dict[str, Any]]
    ):
        cache_file = self._get_cache_file_path(filename)
        df_votes = pd.DataFrame(votes)
        df_votes["latest_block"] = latest_block
        df_votes.to_parquet(cache_file)
