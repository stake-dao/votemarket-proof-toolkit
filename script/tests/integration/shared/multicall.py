from tests.integration.shared.send_tx_with_balance import impersonate_and_send_tx
from eth_utils import to_checksum_address, function_signature_to_4byte_selector
from eth_abi import encode

def multicall(from_address, to_address, calls, value=0):
    
    from_address = to_checksum_address(from_address)
    to_address = to_checksum_address(to_address)

    calldata_list = []
    for call in calls:
        calldata_temp= function_signature_to_4byte_selector(call[0]).hex()
        calldata_temp+= encode(call[1], call[2]).hex()
        calldata_list+= [bytes.fromhex(calldata_temp)]

    calldata = f"0x{function_signature_to_4byte_selector('multicall(bytes[])').hex()}"
    calldata += encode([
            'bytes[]'
        ], [
            calldata_list
        ]).hex()

    impersonate_and_send_tx(from_address, to_address, calldata, value)
