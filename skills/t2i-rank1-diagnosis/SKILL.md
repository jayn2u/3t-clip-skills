---
name: t2i-rank1-diagnosis
description: Diagnose why a CLIP-based text-to-image (t2i) pedestrian retrieval run under- or over-performs on Rank-1 in this repo — stalled/plateaued training, a drop between val and test, unstable/high-variance folds on icfg-pedes or rstpreid, an Optuna study that isn't improving, or a fold that scored surprisingly low or high. Use this whenever the user shares or points at a W&B run, `train_retrieval.log`, `run_config.json`, `results/MM-DD/*.json`, or an Optuna study and asks what happened, why a number looks off, or what to try next — even if they just paste a metric and ask "why". Also use when asked to review whether a new training idea (a new loss, hard-negative scheme, adapter) is worth trying against this codebase's current in-batch-InfoNCE-only design.
---

# t2i Rank-1 Diagnosis

This repo trains CLIP-family models for text-to-image pedestrian retrieval (CUHK-PEDES / ICFG-PEDES / RSTPReid) and treats **t2i R@1** as the north-star metric (current published SOTA context: ~75–80%, see `AGENTS.md`). This skill is for *diagnosing a run that already happened* — reading its evidence and explaining the number, not guessing from vibes.

The core discipline: **gather evidence before forming a hypothesis, then rank hypotheses by what the evidence actually supports.** A diagnosis that isn't traceable to a specific log line, config value, or W&B chart is not a diagnosis — it's a guess. Cite the file and value you're reasoning from.

## 0. Read-only compatibility preflight

Before reading a run, identify the current checkout with read-only commands such as
`pwd`, `git rev-parse --show-toplevel`, `test -f`, and repository text search.
Continue only when the root is a compatible lab_clip checkout containing
`AGENTS.md`, `CONTEXT.md`, the required `docs/` domain and decision records,
the relevant `configs/` YAML, `src/` modules, and the requested `artifacts/`
directory with `wandb_meta.json` when W&B linkage is part of the question.
If any required compatibility marker is missing, refuse the diagnosis clearly
and explain which marker failed. Outside a compatible checkout this skill is
read-only: it must not modify, create, delete, or synchronize project files.

## 1. Know what "current" means here

The active training surface is **in-batch InfoNCE with person-ID positive sets, full-model finetuning, no modality adapter** — three optimizer variants (`train_itc_sgd.py`, `train_itc_adam.py`, `train_itc_adamw.py`), optionally with trainable-parameter EMA. This is the *only* supported objective; SDM, ID loss, EFA, distillation, and adapter-based conditions are retired (see `docs/adr/0005`–`0008`, all `superseded_by` → `docs/superpowers/specs/2026-08-09-train-itc-only-design.md`). `src/wandb_tracking.py` still has logging code paths for those retired losses (`sdm_loss`, `id_loss`, `efa_loss`, `distill_loss`, …) — if you see those keys mentioned in code, they're dead metric names from before the simplification, not something currently being trained. Don't diagnose a run as "missing SDM regularization" or propose reviving an adapter; that would contradict the accepted design decision. If a genuinely new idea seems worth trying anyway, say so explicitly and flag that it's a fresh proposal, not a return to a retired ADR.

Use `CONTEXT.md`'s vocabulary exactly when naming concepts: **in-batch InfoNCE**, **person-ID positive set**, **t2i R@1**, **trainable-parameter EMA**. Don't drift into loose synonyms ("hard negative loss", "the classifier") the glossary doesn't use.

## 2. Collect the evidence before reasoning

For the run(s) in question, gather what's actually available — don't assume a file exists, check:

| Artifact | Path pattern | What it tells you |
|---|---|---|
| Run config | `artifacts/{dataset}_itc_{optimizer}/run_config.json` | The exact resolved hyperparameters for that run (not the YAML default — the actual injected values) |
| Training log | `artifacts/{dataset}_itc_{optimizer}/train_retrieval.log` | Per-epoch loss and val retrieval metrics over time — this is where you see plateaus, divergence, instability |
| W&B linkage | `artifacts/{dataset}_itc_{optimizer}/wandb_meta.json` | `run_id`/`group`/`job_type` — use this to pull the actual W&B run instead of guessing from local files alone |
| Checkpoints | `best.pt` (best avg@1), `best_t2i.pt` (best t2i@1) in the same dir | Whether checkpoint selection (`t2i_r1`, see `src/wandb_tracking.py:finish_train_run`) picked a different epoch than you'd expect |
| Final test eval | `results/MM-DD/*.json` | The mandatory post-train Argo evaluation of `best_t2i.pt` on the native test split — compare this against the training-time val number to see val→test generalization gap |
| Optuna study | trial artifact dirs under the Optuna output root + each trial's own `run_config.json`/log | Per-trial hyperparameters vs. reported `t2i_r1`, and whether the pruner killed promising trials early |

If the user only pasted a number or a screenshot, ask them for (or go find) the underlying `run_config.json` / log / W&B link before diagnosing — a bare metric has no causal information by itself.

### Reading the W&B metric namespace

`src/wandb_tracking.py` fixes the metric names; use this map instead of guessing:

- **During training**, validation metrics log under `{split}/t2i@1`, `{split}/avg@1`, `{split}/i2t@1`, etc., where `{split}` is `val` for `cuhk-pedes` and for every `icfg-pedes`/`rstpreid` fold (fold labels like `fold_2_of_5` normalize to `val` — see `_train_metric_split`), and `test` only for a plain non-fold eval split. Don't confuse a training-time `val/t2i@1` with the final test-set number.
- Per-epoch training diagnostics live under `train/*` (`train/loss`, `train/examples_per_second`, `train/cumulative_gpu_hours`, VRAM metrics) and `early_stop/*` (`early_stop/plateau_best_t2i`, `early_stop/bad_epochs`) — these tell you whether early stopping fired and why.
- The run summary carries `{split}/best_t2i@1`, `best_t2i_epoch`, `best_avg_epoch`, and `checkpoint_selection_metric` (always `t2i_r1`) — compare `best_t2i_epoch` against total epochs to see if the run stopped improving early or was still climbing when it ended.
- Final test evaluation logs under `test/{dataset_slug}/{direction}/top{k}` and `.../mAP` (see `_eval_metric_prefix`) — a *different* namespace from training-time val metrics. Don't compare `val/t2i@1` directly to `test/cuhk_pedes/text_to_image/top1` as if they were the same measurement; one is training-time model selection, the other is the final Argo post-train evaluation.

## 3. Map the knobs that actually exist

Every tunable lives in `configs/train/train_itc_{sgd,adam,adamw}.yaml` (or the matching Optuna config). When a symptom points at a hyperparameter, name the *actual* YAML key, not a generic ML term:

| Knob | What it controls | Symptom it tends to explain |
|---|---|---|
| `lr`, `warmup_ratio`, `weight_decay`, `grad_clip_norm` | Optimization dynamics (also the four Optuna search dimensions in `optuna_itc.yaml`) | Training loss spikes/NaNs early → `lr` too high or `warmup_ratio` too short; val R@1 rises then decays → `lr` too high for the tail of training or no decay schedule pressure; loss barely moves → `lr` too low |
| `batch_size`, `pk_sampler`, `num_instances` | In-batch negative pool size and identity composition (`src/pk_sampler.py`'s `RandomIdentitySampler` when `pk_sampler: true`) | Noisy epoch-to-epoch R@1 → too few unique identities per batch when `pk_sampler` is on with a large `num_instances`; weak negatives → small `batch_size` shrinking the in-batch negative pool |
| `multipositive` | Whether same-person-ID batch members are all treated as positives (`src/losses.py:multi_positive_contrastive_loss`) vs. diagonal-only positives | If `false`, expect the model to fight itself when multiple captions/images of the same person land in one batch — a real, checkable cause of a stuck R@1 |
| `ema_enabled`, `ema_decay` | Trainable-parameter EMA used for validation/checkpoint selection (`src/trainable_parameter_ema.py`) | A checkpoint that looks worse than the training curve suggested → EMA decay too slow/fast to track a short run; compare `raw` vs EMA-evaluated metrics if both are logged |
| `precision` | `fp32`/`fp16`/`bf16`/`amp_fp16`/`amp_bf16` | Loss NaNs or sudden metric collapse mid-run → check for fp16 overflow before blaming the optimizer |
| `early_stop_plateau_min_delta`, `early_stop_plateau_patience`, `early_stop_plateau_start_epoch` | When training stops if `t2i_r1` plateaus | A run that "should have kept improving" but stopped → check `early_stop/*` in the log against these thresholds before assuming underfitting |
| `img_aug`, `preprocess_mode`, `caption_mode` | Data augmentation and text-sampling strategy | Train/val gap that looks like overfitting → check whether `img_aug` is actually on for that run |

Cross-reference the run's `run_config.json` against this table — don't reason from the YAML defaults in the repo if the run injected different values (Optuna trials and manual overrides both do this).

## 4. Fold- and dataset-specific checks

`icfg-pedes` and `rstpreid` expand into 5 identity-disjoint validation folds (`src/training_folds.py`, seed `42`, protocol `identity-shuffle-v1`); `cuhk-pedes` does not fold. When diagnosing variance across folds:

- Confirm the folds really are identity-disjoint for the comparison being made — `split_training_fold` holds out `person_ids[fold_index::5]`, so a legitimate per-fold difference in identity difficulty (not just noise) is expected and should be named as such rather than written off as instability.
- A fold with an unusually low validation identity count relative to the others is a real confound worth checking (`len(holdout_ids)`), not just "bad luck".
- Every fold gets its own `best_t2i.pt` and its own mandatory post-train test evaluation — when comparing "did fold 3 do worse", make sure you're comparing the same metric (val during training vs. the shared native test evaluation) across folds, not mixing the two.

## 5. Optuna-specific diagnosis

If the question is about a study rather than a single run: check whether trials that scored well got pruned early (Optuna direction is fixed to `maximize` on `t2i_r1`), whether the search space bounds in `configs/optuna/optuna_itc.yaml` actually bracket the good region implied by manual runs, and whether trials are being compared fairly (same dataset/fold, same epoch budget). A study that "isn't improving" is often a search-space or pruner-timing problem, not evidence that the objective is maxed out.

## 6. Write the diagnosis

Structure the answer as:

1. **What the evidence shows** — the specific numbers/log lines/config values you looked at, with file paths.
2. **Ranked hypotheses** — most-supported first, each tied to a specific piece of evidence, not a generic ML platitude.
3. **What would confirm or rule out the top hypothesis** — a concrete thing to look at or a specific, small experiment.
4. **If a next experiment is warranted**, propose it as a YAML change to the existing stem-paired config (never a CLI flag — this repo rejects CLI args) and note whether it needs `env/.env` changes, respecting that dataset/model selection is env-injected and folds are code-owned, not researcher-configurable.

If your diagnosis would contradict an accepted ADR or the `train-itc-only` design (e.g. it implies bringing back a retired objective), say so explicitly rather than quietly recommending it.
