# JEPA Paper Summary

## Current Project Status - 2026-07

The papers summarized below are research background. The active live trading system is the JEPA event-option static-union package, not a literal LeWorldModel, V-JEPA, GBT+RL, or 180m JEPA production deployment.

Current live package:

```text
neural/models/jepa/jepa_production_event_options_frozen2025_static_union_202607/
policy: event_option_frozen2025_static_union_balanced_202607
```

VISReg/SIGReg/XInputJEPA work should be treated as auxiliary representation research until it improves the static-union event-option baseline under the same causal/live-ready checks.

This note summarizes the PDFs currently stored in `research_papers/JEPA`.

## 1. A Path Towards Autonomous Machine Intelligence

File: `10356_a_path_towards_autonomous_mach.pdf`

Yann LeCun's position paper lays out the high-level motivation for JEPA: intelligent systems should learn internal world models mostly from observation, then use those models for prediction, reasoning, and planning. The proposed agent contains perception, a configurable world model, actor, critic/cost modules, short-term memory, and a configurator. Planning is framed as energy minimization over imagined action sequences, close to model predictive control.

The most relevant idea is the move away from pixel-perfect generation. The world model should predict useful representations of future state, not every unimportant detail of the raw observation. The paper also motivates hierarchical JEPA: learn representations and predictions at multiple time scales, because long-horizon reasoning is too hard with one flat model.

Relevance for this project: this is the conceptual blueprint. For trading, the market is an external dynamical system, so the valuable part is representation prediction and hierarchical time scales. The direct actor/world interaction premise is weaker because our trades do not causally move SPX/QQQ/SPY.

## 2. Contrastive and Non-Contrastive Self-Supervised Learning Recover Global and Local Spectral Embedding Methods

File: `Contrastive and Non-Contrastive Self-Supervised.pdf`

This paper gives a theory view of SSL methods such as VICReg, SimCLR, NNCLR, and Barlow Twins. It shows that many SSL objectives recover classical spectral embedding methods. The key object is the pairwise relation matrix `G`: it defines which samples are treated as semantically close. If `G` aligns with the downstream task, SSL can recover representations useful for that task. If `G` is misaligned, the learned representation can be harmful.

The paper's practical lesson is that the positive-pair definition matters as much as the model. Contrastive methods are linked to global spectral embeddings, while non-contrastive methods are linked to local spectral methods. VICReg can preserve fuller rank under some settings, while SimCLR and Barlow Twins tend to match the rank of the relation graph.

Relevance for this project: any market JEPA lives or dies by how we define positive pairs and prediction horizons. "Adjacent minutes are positives" is not automatically right. We need pairs that preserve tradable state: same regime, nearby time, same support/resistance context, or future states under horizons that match our labels.

## 3. V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning

File: `V-JEPA 2_ Self-Supervised Video Models Enable Understanding, Prediction and Planning - 2506.09985v1.pdf`

V-JEPA 2 scales video JEPA pretraining to more than 1 million hours of video and 1 million images. It predicts masked video representations rather than pixels. The method still uses stop-gradient and an EMA target encoder to avoid collapse. Scaling ingredients include larger datasets, larger ViT encoders, longer training, and progressive increases in resolution and clip length.

For planning, the authors freeze the pretrained V-JEPA 2 encoder and train an action-conditioned predictor, V-JEPA 2-AC, on about 62 hours of unlabeled robot videos. The predictor takes frame embeddings, robot state, and actions, then predicts future embeddings. At test time, it plans by minimizing latent distance to goal images with CEM/MPC. It performs zero-shot reaching, grasping, and pick-and-place on real Franka robots, with better success and far faster planning than a video-generation baseline.

The main limitations are long-horizon planning and sensitivity to camera setup. The model can plan short tasks, but longer non-greedy tasks need subgoals or hierarchy.

Relevance for this project: useful as an example of staged pretraining plus action-conditioned latent prediction. Less directly applicable than LeWorldModel because it relies on huge video scale and a causal action setting. Our actions do not change future market states.

## 4. LeJEPA: Provable and Scalable Self-Supervised Learning Without the Heuristics

File: `LeJEPA_ Provable and Scalable Self-Supervised Learning Without the Heuristics - 2511.08544v3.pdf`

This is one of the two most important papers for this repository. LeJEPA argues that JEPA embeddings should follow an isotropic Gaussian distribution. The paper claims this distribution minimizes downstream prediction risk under broad linear and nonlinear probing settings. To enforce it, the authors introduce SIGReg, Sketched Isotropic Gaussian Regularization.

SIGReg projects embeddings onto many random one-dimensional directions and runs a Gaussian normality test, specifically an Epps-Pulley characteristic-function statistic, on each projection. By Cramer-Wold style reasoning, matching all one-dimensional projections matches the joint distribution. In practice, random projections are resampled during training, giving broad coverage with linear memory and compute.

The final LeJEPA loss combines a predictive/alignment loss with SIGReg. The practical appeal is that it removes common JEPA anti-collapse heuristics: no stop-gradient, no EMA teacher-student target, no carefully tuned schedules, no prototypes, and no whitening layer dependency. It exposes mostly one meaningful tradeoff hyperparameter, the prediction/SIGReg balance `lambda`.

Experiments claim stable training across many datasets and architectures, including ResNets, ConvNeXts, ViTs, Swins, and large ViTs. A useful result for this project is that LeJEPA training loss is informative about downstream performance, which is rare in SSL. The paper also argues that in-domain self-supervised pretraining can beat generic foundation-model transfer in specialized domains.

Relevance for this project: highly relevant, but mostly as a tabular/time-series representation learner. The most useful ingredient is SIGReg as a principled anti-collapse regularizer for predictive embeddings. It is a better fit than copying a pixel/video architecture.

## 5. LeWorldModel: Stable End-to-End Joint-Embedding Predictive Architecture from Pixels

File: `LeWorldModel_ Stable End-to-End Joint-Embedding Predictive Architecture from Pixels - 2603.19312v2.pdf`

This is the other vital paper. LeWorldModel applies the LeJEPA/SIGReg idea to action-conditioned world models trained end-to-end from pixels. It learns an encoder `z_t = enc(o_t)` and a predictor `z_hat_{t+1} = pred(z_t, a_t)`. The loss has only two terms: next-embedding prediction MSE and SIGReg on latent embeddings.

The paper's important engineering point is simplicity. Earlier end-to-end latent world models needed many losses or pretrained frozen encoders to avoid collapse. LeWM trains directly from raw pixels without stop-gradient, EMA, reward signals, reconstruction loss, or task supervision. The default model is compact: roughly 15M parameters, with a small ViT encoder and transformer predictor, trainable on one GPU in a few hours.

At inference, LeWM plans in latent space. Given a current observation and goal observation, it rolls out candidate action sequences through the predictor and optimizes actions with CEM/MPC to minimize latent distance to the goal. The paper reports competitive performance on 2D and 3D control tasks, much faster planning than foundation-model world models, and latent spaces that encode physical quantities. It also uses "surprise" from prediction error to detect physically implausible events.

The stated limitations matter: current latent world models still struggle with long horizons, and SIGReg can be awkward when the environment has very low intrinsic dimensionality but the embedding dimension is high.

Relevance for this project: the direct LeWM architecture does not map cleanly to trading because it assumes actions causally change future observations. Our trade action changes portfolio payoff, not the market. The transferable part is the two-term objective and the use of prediction error/surprise as a learned state-quality signal.

## 6. VL-JEPA: Joint Embedding Predictive Architecture for Vision-Language

File: `VL-JEPA_ Joint Embedding Predictive Architecture for Vision-language - 2512.10942v2.pdf`

VL-JEPA extends JEPA to vision-language tasks. Instead of autoregressively generating tokens, it predicts continuous target-text embeddings from visual inputs and text queries. A lightweight decoder is used only when text must be emitted. The claim is that semantic embedding prediction avoids wasting capacity on surface-level wording variation.

The model uses an X-encoder for visual input, a Y-encoder for text targets, a predictor that maps visual/query context to target embeddings, and an optional Y-decoder. This paper uses InfoNCE as the main anti-collapse mechanism, while noting that VICReg or SIGReg could be used in future work. It reports better or comparable performance than token-space VLM baselines under matched data and parameter budgets, plus selective decoding that reduces decoding cost in streaming video.

Relevance for this project: the lesson is that predicting embeddings can reduce target ambiguity. For trading, this suggests predicting future market-state embeddings or distributions may be more stable than directly predicting noisy up/down labels at every minute.

## 7. Hierarchical Planning with Latent World Models

File: `Hierarchical Planning with Latent World Models - 2604.03208v1.pdf`

This paper addresses a core weakness of learned world models: long-horizon planning. It proposes HWM, a hierarchical MPC framework using multiple latent world models at different temporal scales. A high-level model predicts long-horizon latent subgoals using compressed latent macro-actions. A low-level model then plans short primitive-action sequences to reach the first subgoal, replanning in MPC style.

The method is modular and can sit on top of different latent world models, including V-JEPA2-AC, DINO-WM, and PLDM. It improves non-greedy and long-horizon tasks: real-robot pick-and-place without manual subgoals improves from 0% to about 70%, Push-T long-horizon success improves materially, and maze navigation improves on larger unseen mazes. It also reduces planning-time compute by roughly 3x to 4x in some settings.

The paper still acknowledges that long-horizon manipulation remains hard. It recommends more abstract high-level representations, uncertainty-aware planning, and better feedback between hierarchy levels.

Relevance for this project: the time-scale idea is relevant because our labels and backtests use up to 180 minutes, while features update every 5 minutes. A trading adaptation should predict multiple horizons. The action-planning part is less direct because market transitions are exogenous.

## 8. When Does LeJEPA Learn a World Model?

File: `When Does LeJEPA Learn a World Model_ - 2605.26379v1.pdf`

This paper gives theory for when LeJEPA learns a faithful world model. Under stationary additive-noise transitions and Gaussian latent variables, LeJEPA's alignment plus Gaussian regularization linearly recovers the world's latent variables up to rotation. This property is called linear identifiability.

The strongest result is both positive and restrictive: the Gaussian latent distribution is not just convenient, it is unique for this guarantee under the paper's assumptions. If the latents are non-Gaussian, linear identifiability can fail. The paper also gives an approximate identifiability result: if alignment and whitening are only approximately satisfied, recovery degrades continuously rather than catastrophically.

For planning, the paper argues that if the learned representation is a rotation of the true latent state, then latent-space planning with orthogonally invariant costs is equivalent to planning in the true latent space. Empirically, SIGReg and VICReg maintain high linear recovery in controlled Gaussian settings, but real RL trajectories show weaker identifiability because they are non-Gaussian and anisotropic.

Relevance for this project: this is a warning. Market trajectories are nonstationary, heavy-tailed, regime-dependent, and not guaranteed Gaussian. SIGReg can still be useful, but we should not assume the formal world-model guarantee holds globally. Regime conditioning, robust normalization, and walk-forward validation are mandatory.

## Cross-Paper Takeaways for Trading

1. JEPA is not mainly about pixels. The durable idea is predictive representation learning: learn a compact latent state whose future is easier to predict than raw observations.

2. SIGReg is the most practical new ingredient. It gives an explicit anti-collapse objective that may be easier to integrate into a tabular market sequence model than EMA/teacher-student tricks.

3. Positive-pair and horizon design are critical. Adjacent timestamps, same-day windows, same-regime windows, cross-ticker context, and support/resistance event windows will produce different representations.

4. Action-conditioned world modeling only applies when actions affect the environment. In this trading system, actions affect PnL, not market evolution. A LeWorldModel-style market model should be actionless or conditioned on exogenous state, not trade action.

5. The most realistic use is additive: pretrain a small temporal LeJEPA on market/options sequences, export latent features and prediction-surprise features, and test them against the current event-option static-union package under the same causal walk-forward, leakage, live-equivalence, and systemd checks. The old GBT/RL path is only a historical comparison point.
