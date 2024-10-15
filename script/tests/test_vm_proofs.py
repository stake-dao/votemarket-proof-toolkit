import pytest
from ape import accounts
from eth_utils import to_checksum_address


# Using test values to match with previous prod proofs and votes on Votemarket v1 : https://github.com/stake-dao/votemarket-data/blob/main/bounties/x-chain/1723680000/

EPOCH = 1723680000
BLOCK_NUMBER = 20530737
BLOCK_TIMESTAMP = 1723685159

VOTER = to_checksum_address("0x52f541764e6e90eebc5c21ff570de0e2d63766b6".lower())


@pytest.mark.asyncio
async def test_block_header(vm_proofs, setup_environment, oracle, whale):
    votemarket = setup_environment["votemarket"]
    campaign = votemarket.getCampaign(setup_environment["campaign1_id"])
    gauge_address = campaign[1]

    print("Gauge address:", gauge_address)

    # First, block data and header to oracle
    block_info = vm_proofs.get_block_info(BLOCK_NUMBER)

    # Data : https://github.com/stake-dao/votemarket-data/blob/main/bounties/x-chain/1723680000/block_header.json
    assert block_info["block_number"] == BLOCK_NUMBER, "Block number should match"
    assert (
        block_info["block_timestamp"] == BLOCK_TIMESTAMP
    ), "Block timestamp should match"
    assert (
        block_info["BlockHash"]
        == "0xc8eada67a2c66e11ff9596628240fb4bccbd6aa039bc07256dc12a40d8430bcf"
    ), "Block hash should match"
    assert (
        block_info["rlp_block_header"]
        == "0xf90257a00f93f4a04ba5e0721a824c63b27648771871cccd7bce742a641f0c068ced6630a01dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d493479495222290dd7278aa3ddd389cc1e1d165cc4bafe5a0c40a51066f8d36749763611a9fc87de19e778d60b4555be33cb0d0c051663587a0102a043268a245ef4c7b50b1d4d81d8961d617d3c6eb7fc1517a1768eef96f51a07bfdcaf0668b54725447422d5cfe0777269e20ded93b11995426319412965a8eb9010015ad81697a1bd9c74e201994e6003101b39820108c8f6cb0433f420036228958044304680ada01122221324297cb69c943f9da309940e235f3df65228d6801905611bd8b50c8ef9bec7c5888904990a090824515426c482430f71585ac34c3043842522d6260043c1a0ac1bc2228edd726c007ac898f6e36c8244d7506090c4429e430502969c4d6c2c92b6623a40b418681b03145a082ea89a44142509b32718784288c1d973457066954c208828fc8260746209764320006280e3080282074d793450a905a1f6001094c5c5afb3c16324816aba74e853011025703d5bae19795fcb9f0468c262929072e865698ee26596cd700f39cb0c1a905b15ff0f534258084013946318401c9c38083fa4d0b8466bd59278f6265617665726275696c642e6f7267a0a640a7528ddbf0c4d321162d1fb321808bf4b62f15b10781e1fecf6ee4aa549a880000000000000000844142e2a2a08843e21b3de9054031a339d51ab4afef373bb2d1f559bb7981c0f251297416c48302000080a007b6926cb57c9857fbbeb48fff177d9432172c12247db1bdbf953aa47d483875"
    )

    # Insert in the oracle block info
    with accounts.use_sender(whale):
        oracle.insertBlockNumber(
            EPOCH,
            (
                block_info["block_hash"],
                "0x0000000000000000000000000000000000000000000000000000000000000000",
                block_info["block_number"],
                block_info["block_timestamp"],
            ),
        )

    # Assert the block in the oracle
    epoch_block_number = oracle.epochBlockNumber(EPOCH)

    # Assert the block hash
    assert (
        epoch_block_number[0].hex()
        == "0xc8eada67a2c66e11ff9596628240fb4bccbd6aa039bc07256dc12a40d8430bcf"
    ), "Block hash in oracle should match"

    # Assert the state root hash
    assert (
        epoch_block_number[1].hex()
        == "0x0000000000000000000000000000000000000000000000000000000000000000"
    ), "State root hash in oracle should match"

    # Assert the block number
    assert epoch_block_number[2] == BLOCK_NUMBER, "Block number in oracle should match"

    # Assert the timestamp
    assert (
        epoch_block_number[3] == BLOCK_TIMESTAMP
    ), "Block timestamp in oracle should match"