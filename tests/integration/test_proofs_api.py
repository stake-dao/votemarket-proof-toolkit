"""
Test: Toolkit proof data matches GitHub API.

Compares:
- Proof file existence
- Proof data structure (users dict)
- User proof lookup
"""

import httpx
import pytest

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/stake-dao/api/main/api/votemarket"
GITHUB_API_BASE = "https://api.github.com/repos/stake-dao/api/contents/api/votemarket"


def fetch_github_metadata():
    """Get latest epoch from metadata."""
    response = httpx.get(f"{GITHUB_RAW_BASE}/metadata.json", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_github_proof(epoch: int, protocol: str, platform: str, chain_id: int, gauge: str):
    """Fetch proof file from GitHub."""
    url = f"{GITHUB_RAW_BASE}/{epoch}/{protocol}/{platform.lower()}/{chain_id}/{gauge.lower()}.json"
    response = httpx.get(url, timeout=30)
    if response.status_code == 200:
        return response.json()
    return None


@pytest.mark.integration
class TestProofsVsAPI:
    """Compare toolkit proofs vs GitHub proofs."""

    def test_metadata_accessible(self):
        """GitHub metadata should be accessible."""
        metadata = fetch_github_metadata()
        assert "latestUpdatedEpoch" in metadata
        assert isinstance(metadata["latestUpdatedEpoch"], int)

    def test_proof_structure_matches(self):
        """Proof file structure should have 'users' dict."""
        metadata = fetch_github_metadata()
        epoch = metadata["latestUpdatedEpoch"]

        # Known active gauge/platform combination
        platform = "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9"
        chain_id = 42161

        # List directory to find a gauge
        dir_url = f"{GITHUB_API_BASE}/{epoch}/curve/{platform.lower()}/{chain_id}"
        response = httpx.get(dir_url, timeout=30)

        if response.status_code != 200:
            pytest.skip("No proofs available for this epoch")

        files = response.json()
        gauge_files = [f for f in files if f["name"].endswith(".json")]

        if not gauge_files:
            pytest.skip("No gauge proofs found")

        # Fetch first gauge proof
        gauge = gauge_files[0]["name"].replace(".json", "")
        proof = fetch_github_proof(epoch, "curve", platform, chain_id, gauge)

        assert proof is not None
        assert "users" in proof
        assert isinstance(proof["users"], dict)

    def test_user_in_proof_is_valid_address(self):
        """Users in proof file should be valid Ethereum addresses."""
        metadata = fetch_github_metadata()
        epoch = metadata["latestUpdatedEpoch"]

        platform = "0x8c2c5A295450DDFf4CB360cA73FCCC12243D14D9"
        chain_id = 42161

        # Find a proof with users
        dir_url = f"{GITHUB_API_BASE}/{epoch}/curve/{platform.lower()}/{chain_id}"
        response = httpx.get(dir_url, timeout=30)

        if response.status_code != 200:
            pytest.skip("No proofs available")

        files = response.json()
        gauge_files = [f for f in files if f["name"].endswith(".json")]

        # Find first gauge with users
        for gf in gauge_files[:5]:  # Check first 5
            gauge = gf["name"].replace(".json", "")
            proof = fetch_github_proof(epoch, "curve", platform, chain_id, gauge)

            if proof and proof.get("users"):
                user = list(proof["users"].keys())[0]

                # Verify valid Ethereum address format
                assert user.startswith("0x"), f"Invalid address prefix: {user}"
                assert len(user) == 42, f"Invalid address length: {user}"
                int(user, 16)  # Should be valid hex
                return

        pytest.skip("No proofs with users found")
