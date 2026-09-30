"""Own-initialized learned mappings and dynamics; observed runtime inputs only."""
from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from .state_rep_model import shapes, validate_snapshot


class Model(nn.Module):
    def __init__(self, arm: str, seed: int):
        super().__init__()
        self.arm, self.seed = arm, seed
        torch.manual_seed(seed)
        for name, shape in shapes(arm).items():
            value = torch.zeros(shape, dtype=torch.float32)
            if name == "transition_weight":
                value.uniform_(-0.05, 0.05).add_(torch.eye(10).unsqueeze(0))
            elif "first_weight" in name:
                value.uniform_(-1 / math.sqrt(10), 1 / math.sqrt(10))
            self.register_parameter(name, nn.Parameter(value))

    def mapping(self, values, prefix: str):
        hidden = torch.tanh(F.linear(values, getattr(self, prefix + "_first_weight"), getattr(self, prefix + "_first_bias")))
        return values + F.linear(hidden, getattr(self, prefix + "_last_weight"), getattr(self, prefix + "_last_bias"))

    def encode(self, observation):
        return observation if self.arm == "direct" else self.mapping(observation, "encoder")

    def decode(self, state):
        return state if self.arm == "direct" else self.mapping(state, "decoder")

    def advance(self, state, action):
        if self.arm == "direct":
            hidden = torch.tanh(torch.bmm(self.first_weight[action], state.unsqueeze(-1)).squeeze(-1) + self.first_bias[action])
            state = state + torch.bmm(self.last_weight[action], hidden.unsqueeze(-1)).squeeze(-1) + self.last_bias[action]
            return state, state
        state = torch.bmm(self.transition_weight[action], state.unsqueeze(-1)).squeeze(-1) + self.transition_bias[action]
        return self.decode(state), state

    def forward(self, initial, actions, *, return_states=False, zero_initial=False):
        state = self.encode(initial)
        if zero_initial:
            state = torch.zeros_like(state)
        outputs, states = [], []
        for action in actions.unbind(1):
            value, state = self.advance(state, action)
            outputs.append(value)
            states.append(state)
        values = torch.stack(outputs, 1)
        return (values, torch.stack(states, 1)) if return_states else values

    def snapshot(self, step: int) -> dict:
        return {"schema_version": "noetloom.state_rep_parameters.v1", "arm": self.arm,
                "seed": self.seed, "step": step,
                "tensors": {key: value.detach().tolist() for key, value in self.state_dict().items()}}

    @classmethod
    def restore(cls, snapshot: dict):
        validate_snapshot(snapshot)
        model = cls(snapshot["arm"], snapshot["seed"])
        model.load_state_dict({key: torch.tensor(value, dtype=torch.float32) for key, value in snapshot["tensors"].items()})
        return model
