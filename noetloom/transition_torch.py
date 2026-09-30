"""Own-initialized learned models. No simulator, data generator or scoring import."""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F

from .contracts import ContractError
from .transition_model import validate_snapshot


class Model(nn.Module):
    def __init__(self, arm: str, seed: int):
        super().__init__()
        self.arm, self.seed = arm, seed
        torch.manual_seed(seed)
        if arm == "shared_transition":
            self.weight = nn.Parameter(torch.empty(4, 8, 8).uniform_(-0.125, 0.125))
            self.bias = nn.Parameter(torch.zeros(4, 8))
        elif arm == "direct":
            self.encoder = nn.Linear(8, 64)
            self.cell = nn.GRUCell(4, 64)
            self.decoder = nn.Linear(64, 8)
        else:
            raise ContractError("unregistered transition model")

    def initial_state(self, initial):
        return initial if self.arm == "shared_transition" else torch.tanh(self.encoder(2 * initial - 1))

    def advance(self, state, action):
        if self.arm == "shared_transition":
            logits = torch.bmm(self.weight[action], (2 * state - 1).unsqueeze(-1)).squeeze(-1) + self.bias[action]
            return logits, torch.sigmoid(logits)
        state = self.cell(F.one_hot(action, 4).float(), state)
        return self.decoder(state), state

    def forward(self, initial, actions, *, return_states=False):
        state = self.initial_state(initial)
        logits, states = [], []
        for action in actions.unbind(1):
            values, state = self.advance(state, action)
            logits.append(values)
            states.append(state)
        outputs = torch.stack(logits, 1)
        return (outputs, torch.stack(states, 1)) if return_states else outputs

    def snapshot(self, step: int) -> dict:
        return {"schema_version": "noetloom.transitions_parameters.v1", "arm": self.arm,
                "seed": self.seed, "step": step,
                "tensors": {key: value.detach().tolist() for key, value in self.state_dict().items()}}

    @classmethod
    def restore(cls, snapshot: dict):
        validate_snapshot(snapshot)
        model = cls(snapshot["arm"], snapshot["seed"])
        model.load_state_dict({key: torch.tensor(value, dtype=torch.float32) for key, value in snapshot["tensors"].items()})
        return model
