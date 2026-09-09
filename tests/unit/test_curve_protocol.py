from unittest.mock import patch

import pytest

from tests.curve_fixture import (
    BLOCK,
    CONTROLLER,
    EPOCH,
    GAUGE,
    POINT_SLOT,
    SPELLINGS,
    USER,
    USER_SLOTS,
    RecordedCurveProvider,
)
from votemarket_toolkit.proofs.generators.bulk_proof import (
    get_gauge_proof_slots,
    get_user_proof_slots,
)
from votemarket_toolkit.proofs.generators.gauge_proof import (
    generate_gauge_proof,
)
from votemarket_toolkit.proofs.generators.node_bag import (
    supports_batch_verifier,
)
from votemarket_toolkit.proofs.generators.user_proof import generate_user_proof
from votemarket_toolkit.proofs.protocol import normalize_proof_protocol


@pytest.mark.parametrize("protocol", SPELLINGS)
def test_curve_spelling_selects_recorded_storage_slots(protocol):
    assert get_user_proof_slots(protocol, GAUGE, USER) == list(USER_SLOTS)
    assert get_gauge_proof_slots(protocol, GAUGE, EPOCH) == [POINT_SLOT]
    assert supports_batch_verifier(protocol)


@pytest.mark.parametrize("protocol", SPELLINGS)
def test_scalar_and_bulk_accept_curve_spellings_with_recorded_proofs(protocol):
    provider = RecordedCurveProvider()
    manager = provider.manager()
    with patch(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        return_value=CONTROLLER,
    ) as controller:
        gauge = manager.get_gauge_proof(protocol, GAUGE, EPOCH, BLOCK)
        user = manager.get_user_proof(protocol, GAUGE, USER, BLOCK)
        bulk = manager.get_proofs_bulk(
            protocol,
            BLOCK,
            gauge_epochs=[(GAUGE, EPOCH)],
            users=[(GAUGE, USER)],
        )
        assert gauge.success and user.success and bulk.success
        assert all(
            call.args == ("curve",) for call in controller.call_args_list
        )
    assert (
        gauge.data["point_data_proof"].hex()
        == provider.fixture["point_data_proof"][2:]
    )
    assert (
        user.data["storage_proof"].hex()
        == provider.fixture["users"][USER]["storage_proof"][2:]
    )
    assert bulk.data.gauge_proofs[(GAUGE, EPOCH)] == gauge.data
    assert bulk.data.user_proofs[(GAUGE, USER)] == user.data


@pytest.mark.parametrize("protocol", SPELLINGS)
def test_scalar_generators_normalize_without_the_manager(protocol):
    provider = RecordedCurveProvider()
    w3 = provider.manager().web3_service.w3
    with patch(
        "votemarket_toolkit.shared.registry.get_gauge_controller",
        return_value=CONTROLLER,
    ):
        _, gauge = generate_gauge_proof(w3, protocol, GAUGE, EPOCH, BLOCK)
        _, user = generate_user_proof(w3, protocol, GAUGE, USER, BLOCK)
    assert gauge.hex() == provider.fixture["point_data_proof"][2:]
    assert user.hex() == provider.fixture["users"][USER]["storage_proof"][2:]


@pytest.mark.parametrize("protocol", ["", "unknown", None, 123, True])
def test_invalid_protocol_is_rejected_before_rpc(protocol):
    with pytest.raises(ValueError):
        normalize_proof_protocol(protocol)
    provider = RecordedCurveProvider()
    manager = provider.manager()
    assert not manager.get_user_proof(protocol, GAUGE, USER, BLOCK).success
    assert not manager.get_gauge_proof(protocol, GAUGE, EPOCH, BLOCK).success
    assert not manager.get_proofs_bulk(
        protocol, BLOCK, users=[(GAUGE, USER)]
    ).success
    assert provider.calls == []
