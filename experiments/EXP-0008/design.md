# Learning useful coordinates while preserving information

N-012 follows [EXP-0007](../EXP-0007/design.md) and its
[decision](../../docs/decisions/0012-state-representation-pilot.md). The old experiment
and results remain immutable. This pilot is an acquisition comparison in the same finite
nonlinear world, not an extension of its unsuccessful fitting runs.

The expert comparator is a reproducible representation-learning ablation: separate capacity,
optimization, state coverage, information preservation and rollout competence. A successful
oracle parameter setting is not learned competence; exact reconstruction is not useful dynamics.
This is a limited component probe under the [charter](../../docs/charter.md), with equal state
and observation widths, no compression, selective memory or variable-work claim.

## Capacity and prior evidence

For bipolar u,v, let a = 2/(tanh(3)-3 tanh(1)) and b = -1-2a tanh(1).
Then u*v = a[tanh(u+v+1)-tanh(u+v-1)]+b. Two tanh units therefore express one
registered product on this finite domain. Six units in each existing residual map can
subtract/add the three shears; signed permutation matrices implement the known actions.
The isolated oracle uses these facts to construct an old-family 1,804-parameter snapshot.
Its 512 one-step and 64 six-step training-only paths are a numerical capacity witness.
No oracle weights, inverse, canonical targets or action rules enter learned initialization,
objectives, runtime inputs or candidate evaluation. The review's downloadable archive was
not accessible; this is an independent derivation and implementation.

Both independent residual maps start as identity. Reconstruction-only pretraining would
therefore have zero initial loss and supplies no coordinate-learning signal. EXP-0007 lost
reconstruction during joint fitting; it did not establish a causal gradient-conflict diagnosis.
Its aligned baseline continuation score was already 1.0, leaving no room for the registered
+0.10 consistency improvement. The supported conclusion is no benefit demonstrated at that
ceiling. Consistency is omitted from this primary objective comparison.

## Controlled mapping comparison

The independent encoder and decoder retain the original 10->32 tanh->10 residual maps.
The reversible alternative has four generic additive coupling layers with 5->30 tanh->5
functions, alternating even and odd coordinate subsets. It decodes by reversing the layers
and subtracting each coupling output. This layout is independent of the generator's products.
Output layers start at zero. Both latent arms use the same four affine action maps, including
identical seeded initial transition parameters. Counts are 1,804 versus 1,780 (1.33% fewer).
Parameter similarity does not imply compute equivalence: each reversible encoding or decoding
uses 1,200 multiplications versus 640 for an independent map; all conversions are charged.

[NICE](https://arxiv.org/abs/1410.8516) sections 3.1–3.3 supply the additive-coupling and
explicit inverse mechanism. We use that established mechanism with tanh functions for prediction,
without its density objective, learned scaling or published model sizes. It is not a new invention
or a universal Noetloom constraint: partial observations, noise and useful abstraction can require
discarding information. Numerical reconstruction error is measured even for the reversible arm.

The unchanged 5,416-parameter direct observation predictor receives its own nonlinear acquisition
pilot, without aligned-task admission. It is a relevant larger baseline, not a parameter-matched
reversibility ablation. All arms receive identical observed training pairs; none receives simulator
state. Adam, prediction MSE, batch size eight, clipping, rates and numeric precision are common.
Independent mappings retain the original 0.5 reconstruction term; reversibility makes that term
approximately zero by construction. This imposed constraint is the intended intervention.

## Independent coverage tests and bounded selection

The [numeric protocol](protocol.json) freezes all choices before fitting. For each of three
arms, two rates and three seeds, run tiny fitting (32 pairs, 2,048 updates) and one-step fitting
(512 pairs, 4,096 updates) from independent copies of the same initial parameters. Tiny failure
does not prevent coverage fitting. Compare their curves separately; more data and more updates
are disclosed differences between cohorts, not an isolated causal coverage effect.

After both rates' one-step fits terminate, select the first common rate where every seed passes all registered prediction,
reconstruction and action-slice floors. Each of those three snapshots may initialize one
2,048-update mixed fit over familiar lengths 1–3, with a fresh optimizer. Gates use observed
coordinate error <=0.25 at every prefix, not only endpoints. Retain every measurement snapshot,
failure and discarded update. A learnable configuration requires all seeds to pass one-step
and mixed gates; tiny is a separately reported optimization diagnostic. No development-composition
or final trajectory is rendered by this pilot, and it makes no transfer or significance claim.

At steps 0, 256 and the final tiny/one step, copy the checkpoint and apply one prediction-only
SGD perturbation on the 32 tiny training pairs. For independent mappings, perturb encoder,
decoder, both mappings and all parameters separately; for reversible, shared mappings and all;
for direct, all. Clip the selected group's gradient norm to one and use the declared fit rate.
Restore the original checkpoint before each perturbation. Record before/after prediction and
reconstruction metrics. This is a controlled local sensitivity measurement, not the actual Adam
update or proof of what caused the historical reconstruction failures. Its work and replay count.

All fits have bounded per-run work, output, time and RSS. Up to 45 fits, two synthetic preflights,
one injected failure, one oracle and 54 replays fit within 103 attempts, 132,000 total gradient
updates (including perturbations), 256 MiB of new run artifacts and one hour of process time.
The existing shared lease serializes writers. Prior evidence already has the owner-authorized
private duplicate and restored-source replay; archive this pilot the same way before closing.
That same-disk copy has the previously recorded failure-domain limitation. No unique data is deleted.

## Separate next decision

[Learning Koopman Invariant Subspaces](https://proceedings.neurips.cc/paper_files/paper/2017/file/3a835d3215755c435ef4fe9965a3f2a0-Paper.pdf)
sections 3.1–3.4 motivate learning observables via the residual of an inner least-squares solve,
with reconstruction preventing trivial constants. That is a separate possible optimization
comparison. It is not run here; any later registration needs sufficient current-encoder training
support, explicit rank or regularization rules, and decoded multistep acceptance. The paper's
autonomous dynamical examples do not establish Noetloom's controlled-action performance.

After this pilot, choose a learnable configuration or localize the remaining failure. Do not
automatically add width or objectives. Learning a bridge after the observation regime changes,
while retaining already learned operations, is a future falsifiable question. Provider changes
and broader capability claims require their own evidence and queue decision.
