from .web3 import W3, check_error, force_mine_block

time_fast_forwarded = 0


def to_seconds(seconds=0, minutes=0, hours=0, days=0, weeks=0):
    return seconds + minutes * 60 + hours * 3600 + days * 86400 + weeks * 7 * 86400


def fast_forward(seconds=0, minutes=0, hours=0, days=0, weeks=0):
    global time_fast_forwarded
    total_time = to_seconds(seconds, minutes, hours, days, weeks)
    time_fast_forwarded += total_time
    W3.provider.make_request("evm_increaseTime", [total_time])
    force_mine_block()


def take_snapshot():
    snapshot = W3.provider.make_request("evm_snapshot", [])
    check_error(snapshot)
    force_mine_block()
    return snapshot


def restore_snapshot(snapshot):
    check_error(W3.provider.make_request("evm_revert", [snapshot["result"]]))
    force_mine_block()
