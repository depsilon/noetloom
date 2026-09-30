"""Own-initialized coordinate maps; generic reversible coupling has no world access."""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from . import coordinates_model as scalar
from .state_rep_torch import Model as IndependentModel


class Model(IndependentModel):
    def __init__(self, arm: str, seed: int):
        if arm != "reversible":
            super().__init__(arm, seed)
            return
        nn.Module.__init__(self)
        self.arm, self.seed = arm, seed
        torch.manual_seed(seed)
        for name, shape in scalar.shapes(arm).items():
            value = torch.zeros(shape, dtype=torch.float32)
            if name == "coupling_first_weight":
                value.uniform_(-1 / math.sqrt(5), 1 / math.sqrt(5))
            elif name == "transition_weight":
                # Match the independent model's transition initialization exactly.
                # Its two first-layer matrices consume 640 draws before the maps.
                generator = torch.Generator().manual_seed(seed)
                torch.empty(640).uniform_(-1 / math.sqrt(10), 1 / math.sqrt(10), generator=generator)
                value.uniform_(-0.05, 0.05, generator=generator).add_(torch.eye(10).unsqueeze(0))
            self.register_parameter(name, nn.Parameter(value))

    def coupling(self, values, inverse=False):
        order = range(3, -1, -1) if inverse else range(4)
        for layer in order:
            fixed = [0, 2, 4, 6, 8] if layer % 2 == 0 else [1, 3, 5, 7, 9]
            changed = [1, 3, 5, 7, 9] if layer % 2 == 0 else [0, 2, 4, 6, 8]
            hidden = torch.tanh(F.linear(values[..., fixed], self.coupling_first_weight[layer],
                                         self.coupling_first_bias[layer]))
            delta = F.linear(hidden, self.coupling_last_weight[layer], self.coupling_last_bias[layer])
            updated = values.clone()
            updated[..., changed] = values[..., changed] + (-delta if inverse else delta)
            values = updated
        return values

    def encode(self, observation):
        return self.coupling(observation) if self.arm == "reversible" else super().encode(observation)

    def decode(self, state):
        return self.coupling(state, inverse=True) if self.arm == "reversible" else super().decode(state)

    def snapshot(self, step: int) -> dict:
        result = super().snapshot(step)
        result["schema_version"] = "noetloom.coordinates_parameters.v1"
        return result

    @classmethod
    def restore(cls, snapshot: dict):
        scalar.validate_snapshot(snapshot)
        model = cls(snapshot["arm"], snapshot["seed"])
        model.load_state_dict({key: torch.tensor(value, dtype=torch.float32) for key, value in snapshot["tensors"].items()})
        return model
