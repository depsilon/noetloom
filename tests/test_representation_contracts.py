from __future__ import annotations

import copy
import unittest

from helpers import ROOT, policy
from noetloom.contracts import ContractError, read_json
from noetloom.representation_contracts import validate_representation_protocol


def protocol() -> dict:
    return read_json(ROOT / "experiments/EXP-0004/protocol.json")


class RepresentationContractTests(unittest.TestCase):
    def test_registered_protocol_is_accepted(self):
        validate_representation_protocol(protocol(), policy())

    def test_unknown_and_missing_fields_are_rejected(self):
        changes = [((), "extra", 1), (("data",), "extra", 1), (("data", "seen_rotations"), "extra", [1]),
                   (("model",), "extra", 1), (("training",), "extra", 1),
                   (("preflight",), "extra", 1), (("budget",), "extra", 1),
                   (("acceptance",), "extra", 1), (("data",), "training_cases", None),
                   (("model",), "latent_scalars", None), (("training",), "batch_size", None),
                   (("preflight",), "warmup_steps", None), (("budget",), "max_case_presentations_per_run", None),
                   (("acceptance",), "interval", None)]
        for path, key, value in changes:
            with self.subTest(path=path, key=key):
                changed = copy.deepcopy(protocol())
                target = changed
                for part in path:
                    target = target[part]
                if value is None:
                    target.pop(key)
                else:
                    target[key] = value
                with self.assertRaises(ContractError):
                    validate_representation_protocol(changed, policy())

    def test_booleans_nonfinite_and_duplicate_seed_are_rejected(self):
        mutations = [lambda p: p["seeds"].__setitem__(0, True),
                     lambda p: p["training"].__setitem__("batch_size", True),
                     lambda p: p["data"].__setitem__("training_cases", True),
                     lambda p: p["acceptance"].__setitem__("base_accuracy", True),
                     lambda p: p["acceptance"].__setitem__("base_accuracy", float("nan")),
                     lambda p: p["seeds"].__setitem__(1, 6101)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(protocol())
                mutate(changed)
                with self.assertRaises(ContractError):
                    validate_representation_protocol(changed, policy())

    def test_registered_science_order_and_supervision_cannot_change(self):
        mutations = [lambda p: p["arms"].__setitem__(0, "conditional"),
                     lambda p: p["source_refs"].__setitem__(0, "R-OTHER"),
                     lambda p: p["data"].__setitem__("generator_seed", 731992),
                     lambda p: p["data"]["seen_rotations"]["ranks"].__setitem__(2, 1),
                     lambda p: p["model"].__setitem__("transport", "sparse"),
                     lambda p: p["training"].__setitem__("learning_rate", 0.004),
                     lambda p: p.__setitem__("network_during_run", True),
                     lambda p: p.__setitem__("external_pretrained_components", ["teacher"])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(protocol())
                mutate(changed)
                with self.assertRaises(ContractError):
                    validate_representation_protocol(changed, policy())

    def test_derived_case_and_memory_admission(self):
        changed = copy.deepcopy(protocol())
        changed["budget"]["max_case_presentations_per_run"] = 8559
        with self.assertRaisesRegex(ContractError, "derived case presentations"):
            validate_representation_protocol(changed, policy())

        changed_policy = policy()
        changed_policy["max_cases"] = 8559
        with self.assertRaisesRegex(ContractError, "max_cases"):
            validate_representation_protocol(protocol(), changed_policy)

        changed_policy = policy()
        changed_policy["max_memory_slots"] = 0
        with self.assertRaises(ContractError):
            validate_representation_protocol(protocol(), changed_policy)

    def test_wall_and_output_caps_obey_policy_ceilings(self):
        changed_policy = policy()
        changed_policy["max_wall_seconds"] = 119
        with self.assertRaises(ContractError):
            validate_representation_protocol(protocol(), changed_policy)

        changed_policy = policy()
        changed_policy["max_run_output_bytes"] = 32 * 1024**2 - 1
        with self.assertRaises(ContractError):
            validate_representation_protocol(protocol(), changed_policy)

        # Explicitly tightened resource caps remain valid when the host allows them.
        tightened = copy.deepcopy(protocol())
        tightened["preflight"]["max_wall_seconds"] = 100
        tightened["preflight"]["max_output_bytes"] = 16 * 1024**2
        tightened["budget"]["max_wall_seconds_per_run"] = 100
        tightened["budget"]["max_output_bytes_per_run"] = 16 * 1024**2
        tightened["budget"]["max_training_attempts"] = 10
        tightened["budget"]["max_peak_rss_bytes"] = 1024**3
        tightened["budget"]["max_training_proxy_ops"] = 1_000_000_000
        tightened["budget"]["max_forward_scalar_ops"] = 50_000
        validate_representation_protocol(tightened, policy())

    def test_computation_caps_are_positive_and_within_registered_limits(self):
        for key, value in (("max_training_proxy_ops", 2_000_000_001),
                           ("max_forward_scalar_ops", 100_001), ("max_training_attempts", 21)):
            changed = copy.deepcopy(protocol())
            changed["budget"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_representation_protocol(changed, policy())
        changed = copy.deepcopy(protocol())
        changed["budget"]["max_training_proxy_ops"] = 0
        with self.assertRaises(ContractError):
            validate_representation_protocol(changed, policy())


if __name__ == "__main__":
    unittest.main()
