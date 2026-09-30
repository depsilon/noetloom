from __future__ import annotations

import copy
import unittest

from helpers import ROOT, policy
from noetloom.allocation_contracts import validate_allocation_protocol
from noetloom.contracts import ContractError, read_json


def protocol() -> dict:
    return read_json(ROOT / "experiments/EXP-0003/protocol.json")


class AllocationContractTests(unittest.TestCase):
    def test_registered_protocol_is_accepted(self):
        validate_allocation_protocol(protocol(), policy())

    def test_unknown_and_missing_fields_are_rejected_at_every_level(self):
        changes = [((), "extra", 1), (("data",), "extra", 1), (("gate",), "extra", 1),
                   (("training",), "extra", 1), (("preflight",), "extra", 1),
                   (("budget",), "extra", 1), (("acceptance",), "extra", 1),
                   (("data",), "train_episodes", None), (("gate",), "features", None),
                   (("training",), "backend", None), (("preflight",), "warmup_steps", None),
                   (("budget",), "max_training_attempts", None), (("acceptance",), "interval", None)]
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
                    validate_allocation_protocol(changed, policy())

    def test_rejects_nonfinite_and_bool_numbers_and_invalid_lists(self):
        mutations = [lambda p: p["gate"].__setitem__("payload_penalty", True),
                     lambda p: p["training"].__setitem__("learning_rate", float("nan")),
                     lambda p: p["acceptance"].__setitem__("all_family_accuracy", float("inf")),
                     lambda p: p.__setitem__("arms", []),
                     lambda p: p.__setitem__("arms", ["adaptive", "adaptive", "dense"]),
                     lambda p: p.__setitem__("seeds", []),
                     lambda p: p.__setitem__("seeds", [1103, 1103, 3301, 4409, 5519])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(protocol())
                mutate(changed)
                with self.assertRaises(ContractError):
                    validate_allocation_protocol(changed, policy())

    def test_frozen_science_and_training_settings_cannot_change(self):
        mutations = [lambda p: p["data"].__setitem__("generator_seed", 4),
                     lambda p: p["data"].__setitem__("test_families", ["base"]),
                     lambda p: p["gate"].__setitem__("trainable_scalars", 8),
                     lambda p: p["training"].__setitem__("candidate_steps", [64, 128]),
                     lambda p: p["acceptance"].__setitem__("minimum_continue_rate", 0.0),
                     lambda p: p.__setitem__("teacher_assistance", "changed"),
                     lambda p: p.__setitem__("network_during_run", True),
                     lambda p: p.__setitem__("external_pretrained_components", ["teacher"])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(protocol())
                mutate(changed)
                with self.assertRaises(ContractError):
                    validate_allocation_protocol(changed, policy())

    def test_attempt_memory_and_derived_presentation_budgets_are_enforced(self):
        for key, value in (("max_training_attempts", 4), ("max_peak_rss_bytes", 2 * 1024**3 + 1),
                           ("max_query_presentations_per_run", 9487)):
            changed = copy.deepcopy(protocol())
            changed["budget"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_allocation_protocol(changed, policy())
        for key, value in (("max_wall_seconds", 119),
                           ("max_run_output_bytes", 16 * 1024**2 - 1),
                           ("max_memory_slots", 32), ("max_cases", 9487)):
            changed_policy = policy()
            changed_policy[key] = value
            with self.subTest(policy_key=key), self.assertRaises(ContractError):
                validate_allocation_protocol(protocol(), changed_policy)


if __name__ == "__main__":
    unittest.main()
