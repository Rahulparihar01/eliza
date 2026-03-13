# PRD: Tiny Model Studio (Regression / Classification / Clustering) for Eliza Platform

## Overview
Tiny Model Studio is a generalized platform capability that lets any Eliza solution/app/agent pipeline:
1) capture labeled/unlabeled training data,
2) optionally use an LLM-driven augmentation + labeling workflow,
3) train multiple “tiny” model candidates in parallel (AutoML-lite),
4) evaluate using k-fold cross-validation and standardized metrics,
5) allow the user to **explicitly choose** between **Best** vs **Lightest (Fast + Interpretable)** winners,
6) deploy the selected model version as a callable inference endpoint/tool.

This capability is designed to be reused across products while adhering to Eliza’s standard architecture patterns: API routes + schemas, async tasks, CrewAI flows, SSE updates, and multi-tenant data access.


## Problem Statement / User Need
Teams building solutions on Eliza need a repeatable way to create and deploy small task-specific ML models (starting with classifiers, expanding to regression and clustering) without bespoke ML pipelines per product. They also want:
- Fast inference for real-time decisions (routing, scoring, gating)
- Interpretability for trust, debugging, and stakeholder adoption
- Guardrails against overfitting via cross-validation and stable evaluation
- Data augmentation that is measurable and can be gated via review/approval


## Goals
- Provide a **general** “model factory” capability usable across any Eliza workflow.
- Enable users to create datasets, define schemas/targets, and manage labeling/augmentation.
- Train multiple candidate algorithms **in parallel**; evaluate with **k-fold CV**.
- Support explicit user selection: **Best** vs **Lightest (Fast + Interpretable)**.
- Provide versioned model artifacts + metrics and a stable inference interface.
- Stream job progress and results to UI (augmentation + training + evaluation).

## Non-Goals (V1)
- Full AutoML with large hyperparameter sweeps.
- Deep neural networks / large embedding models (unless later explicitly added).
- Automated production drift correction (monitoring can be added later; not required for V1).
- Unbounded synthetic data generation without evaluation gating.


## Key Capabilities

### 1) Projects & Datasets
A **Model Project** is created for a task type (classification / regression / clustering) and owns one or more datasets.

**Dataset Features**
- Ingest examples with optional labels/targets.
- Store input as a flexible “field bundle” (e.g., `{text, metadata}`) with a canonicalized representation for V1.
- Maintain dataset versions (immutable snapshots) for training/evaluation reproducibility.
- Maintain label taxonomy (classification) and target definition (regression).

### 2) LLM-assisted Labeling & Augmentation
A reusable **augmentation flow** can:
- Propose labels for unlabeled items.
- Generate candidate synthetic examples (e.g., paraphrases, boundary cases, rare-class coverage).
- Flag uncertain or conflicting items for human review.
- Produce an “approval queue.”

**Guardrails**
- Tag synthetic and LLM-labeled data with provenance (source, recipe, prompt version).
- Default policy: require human approval before synthetic or LLM-labeled examples can enter a training snapshot.
- Dedup / near-dup checks to prevent repeated paraphrase inflation.

### 3) Build Runs (AutoML-lite)
A **Build Run** trains **multiple candidate algorithms in parallel**, evaluates them, and presents results.

**Candidate Definition**
- Algorithm + configuration
- Feature handling profile (V1: canonicalized text; later: structured / categorical)
- CV plan (k-fold) + metrics
- Latency proxy + interpretability score

**Parallelization**
- Each candidate training/eval is a separate async task execution unit.
- The Build Run coordinates candidates and aggregates results.

### 4) Evaluation & Overfitting Prevention
**Default evaluation** for regression/classification:
- k-fold cross-validation (default k=5; reduce when dataset is very small)
- Store mean + standard deviation per metric (stddev is a stability/overfit risk indicator)

**Classification metrics**
- Precision, recall, F1 (overall + per class)
- Confusion matrix
- Optional decision threshold tuning step (independent from training)

**Regression metrics**
- MAE, RMSE (optionally MAPE when appropriate)
- Residual summary (error distribution; largest-error samples)

**Clustering**
- Internal metrics (silhouette, Davies–Bouldin)
- Stability proxy (bootstrap resampling optional)
- Human validation step (cluster naming/approval; optional V1)

### 5) Winner Selection: Best vs Lightest (Fast + Interpretable)
Users must explicitly choose a winner policy for each Build Run:

- **Best**
  - Select highest primary quality metric (task-dependent).
- **Lightest (Fast + Interpretable)**
  - Filter candidates that meet a minimum quality threshold (configurable default).
  - Select minimal latency proxy while maximizing interpretability score.
  - If ties remain, select simpler feature profile and smaller artifact size proxy.

### 6) Model Registry & Inference
Each successful Build Run can publish a **Model Version** containing:
- Artifact pointer(s)
- Metrics summary + CV details
- Winner policy selection record
- Dataset version reference used for training/evaluation

Expose inference as:
- Predict endpoint (single + batch)
- Optional CrewAI custom tool wrapper for use inside flows


## User Stories / Flows

### Flow A: Create project and dataset
1. User creates Model Project (task type).
2. User defines target schema:
   - classification: label taxonomy + definitions
   - regression: target field definition + units/range guidance
3. User uploads examples (labeled/unlabeled) and metadata.
4. System creates Dataset Version v1 (draft).

### Flow B: LLM-assisted labeling/augmentation + approval
1. User triggers “Augment & Label” run.
2. Augmentation flow proposes labels and/or synthetic examples.
3. User reviews queue: approve/reject/edit.
4. User publishes Dataset Version v2 (approved snapshot).

### Flow C: Build Run (parallel candidates) with explicit winner choice
1. User triggers Build Run on an approved dataset version.
2. System runs candidate trainings/evals in parallel, performing k-fold CV.
3. UI displays candidate leaderboard with quality metrics + stability + latency + interpretability.
4. User selects:
   - Best
   - Lightest (Fast + Interpretable)
5. System publishes Model Version and enables inference.

### Flow D: Use model in any Eliza pipeline
1. Product/agent pipeline calls the predict endpoint (or tool wrapper).
2. Result is used for routing/scoring/clustering decisions.
3. Optionally, user feedback (correct/incorrect) is captured as new labeled data.

## UX / UI Requirements
- Project dashboard: list projects, task type, latest model version, status.
- Dataset view: examples table, label schema, approval queue, version history.
- Augmentation run view: progress, sample previews, bulk approve/reject, provenance tags.
- Build run leaderboard:
  - sort/filter candidates by quality metric, latency proxy, interpretability
  - show mean ± std CV metrics
  - “overfit risk” indicator derived from CV variance
  - explicit winner choice buttons: **Best** vs **Lightest (Fast + Interpretable)**
- Model version view: metrics, dataset version reference, inference usage snippet, audit trail.
- Job progress views use SSE for real-time updates.


## Dependencies / Edge Cases
- Small datasets: auto-reduce k in k-fold; warn on instability.
- Leakage: dedup and split hygiene checks before training.
- Label drift: allow updating label schema with versioning and migration path (V2).
- Synthetic dominance: cap % synthetic in training snapshots; require approval by default.
- Permissions: ensure only authorized users can view data, trigger runs, and deploy models.
- Clustering ambiguity: provide human validation step for cluster naming/interpretation.


## Acceptance Criteria
- Users can create a project for classification/regression/clustering and ingest data.
- Users can trigger an augmentation run and review/approve proposed examples.
- Users can trigger a Build Run that trains multiple candidates in parallel.
- System performs k-fold CV and stores mean + std metrics per candidate.
- UI shows a ranked leaderboard including quality, stability, latency proxy, interpretability.
- User must explicitly choose winner policy: **Best** or **Lightest (Fast + Interpretable)**.
- Published model version supports inference via API for single and batch predictions.
- All endpoints are multi-tenant and RBAC-protected.
- Jobs expose progress via SSE and handle failures gracefully.


## Outstanding Product Decisions
- Candidate algorithm set per task type (initial 2–3 per task vs broader set).
- Default quality thresholds for “Lightest” selection (per task type).
- Whether clustering requires human naming/approval in V1 or V2.
- Level of inference logging retained by default (privacy + storage considerations).
- Whether to support multi-label classification in V1 or later.

## Open Engineering Questions
- Artifact storage mechanism for model files and large metrics (DB vs object store abstraction).
- Latency proxy measurement approach (static proxy vs runtime micro-benchmark).
- Standardized feature canonicalization for “field bundle” inputs (deterministic stringification vs learned featurization).
- How to schedule/limit parallel candidate runs to protect shared worker capacity.
