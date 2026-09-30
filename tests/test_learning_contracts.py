from __future__ import annotations

import copy
import unittest

from helpers import ROOT, policy
from noetloom.contracts import ContractError, read_json
from noetloom.learning_contracts import validate_learning_protocol


def protocol() -> dict:
    return read_json(ROOT / "experiments/EXP-0002/protocol.json")


class LearningContractTests(unittest.TestCase):
    def test_registered_protocol_is_accepted(self):
        validate_learning_protocol(protocol(), policy())

    def test_unknown_and_missing_fields_are_rejected_at_each_nested_level(self):
        changes = [
            ((), "extra", 1),
            (("dimensions",), "extra", 1),
            (("data",), "extra", 1),
            (("training",), "extra", 1),
            (("preflight",), "extra", 1),
            (("budget",), "extra", 1),
            (("acceptance",), "extra", 1),
            (("dimensions",), "key", None),
            (("data",), "train_episodes", None),
            (("training",), "backend", None),
            (("preflight",), "warmup_steps", None),
            (("budget",), "max_training_attempts", None),
            (("acceptance",), "interval", None),
        ]
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
                    validate_learning_protocol(changed, policy())

    def test_rejects_bool_nonfinite_and_zero_or_duplicate_arms_and_seeds(self):
        mutations = [
            lambda p: p["training"].__setitem__("threads", True),
            lambda p: p["training"].__setitem__("learning_rate", float("nan")),
            lambda p: p["acceptance"].__setitem__("base_accuracy", True),
            lambda p: p.__setitem__("arms", []),
            lambda p: p.__setitem__("arms", ["selective", "selective", "frozen_routing", "no_history"]),
            lambda p: p.__setitem__("seeds", []),
            lambda p: p.__setitem__("seeds", [1103, 1103, 3301, 4409, 5519]),
            lambda p: p.__setitem__("seeds", [0, 2207, 3301, 4409, 5519]),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(protocol())
                mutate(changed)
                with self.assertRaises(ContractError):
                    validate_learning_protocol(changed, policy())

    def test_rejects_protocol_or_derived_query_budgets_below_workload(self):
        changed = copy.deepcopy(protocol())
        changed["budget"]["max_query_presentations_per_run"] = 9743
        with self.assertRaisesRegex(ContractError, "derived query presentations"):
            validate_learning_protocol(changed, policy())

        changed_policy = policy()
        changed_policy["max_cases"] = 9743
        with self.assertRaisesRegex(ContractError, "max_cases"):
            validate_learning_protocol(protocol(), changed_policy)

    def test_host_wall_output_and_capacity_ceilings_apply(self):
        for key, value in (
            ("max_wall_seconds", 119),
            ("max_run_output_bytes", 16 * 1024**2 - 1),
            ("max_memory_slots", 31),
        ):
            with self.subTest(policy_key=key):
                changed_policy = policy()
                changed_policy[key] = value
                with self.assertRaises(ContractError):
                    validate_learning_protocol(protocol(), changed_policy)

    def test_registered_dimensions_family_and_supervision_cannot_change(self):
        mutations = [
            lambda p: p["dimensions"].__setitem__("latent", 9),
            lambda p: p.__setitem__("family", "other_family"),
            lambda p: p.__setitem__("network_during_run", True),
            lambda p: p.__setitem__("pretrained_components", ["teacher"]),
            lambda p: p["source_refs"].__setitem__(0, "R-OTHER"),
            lambda p: p["budget"].__setitem__("max_training_attempts", 19),
            lambda p: p["budget"].__setitem__("max_peak_rss_bytes", 2 * 1024**3 + 1),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(protocol())
                mutate(changed)
                with self.assertRaises(ContractError):
                    validate_learning_protocol(changed, policy())


if __name__ == "__main__":
    unittest.main()
