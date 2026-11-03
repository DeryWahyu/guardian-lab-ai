# Guardian Lab AI — Agent Guidelines

Current user choice, 3 November 2026: keep **frozen Logistic Regression v6 only**.
Other model implementations, notebooks, tests and local model binaries have been removed from the active workspace at the user's request. Do not restore alternative models without a new instruction.

Read README.md, ai-agent-docs/selected-model-v6.md, ai-agent-docs/machine-learning-plan.md and ai-agent-docs/url-qr-dataset-research.md before changing the ML pipeline.

- Primary notebook: `guardian_lab_url_qr_v6.ipynb`. It loads and checks frozen v6; it does not train. Its execution must not depend on another model or notebook.
- Primary service: `guardian_ml.shadow_service:create_app`. Preserve the original v6 binary, frozen metadata and thresholds: warning `0.904713285827399`, high `0.9884744926236343`.
- The original v6 training notebook is preserved in the ignored local source snapshot documented by `ml/provenance/v6-origin.json`. Do not rewrite its training provenance. Hashes of old baselines inside frozen metadata are historical references, not runtime requirements.
- Read ai-agent-docs/data-improvement-v6-plan.md, ai-agent-docs/model-hardening-plan.md and ai-agent-docs/shadow-api-contract.md for evidence and scope. Original aggregate reports retain historical comparisons; removal of other models does not erase regressions or turn observed benchmarks into new tests.
- Scope: URL-only binary phishing classification. Decoded QR URLs use the same model. QR decoding, QRIS, APK and page/redirect inspection are separate work.
- Never visit dataset target URLs, execute HTML, request real credentials, or send dataset rows to an LLM.
- Never persist raw URLs containing personal information. The frozen sanitizer is heuristic; short secrets in path assignments are a known limitation. Do not silently change frozen representation or claim full anonymization.
- No live reputation, DNS or PSL refresh during inference. Use the bundled offline PSL with private hosting tenants.
- Keep datasets, exposure registries, local environments, source snapshots and model binaries out of Git.
- Runtime changes require source-manifest updates and real-artifact prediction parity. The declared inference dependency set must match its versions in the original training metadata; empty or partial sets must be rejected.
- LOW never means SAFE. Unsupported input or an unavailable model must have no model score or risk band. Serving remains shadow, with `production_ready=false`.
- Keep fitting, tuning, calibration, threshold selection and final testing separate. No fitting transformations on holdouts, winner selection from test accuracy, automatic relabeling, fabricated reviewers or Indonesian labels.
- Previously observed benchmark/exposure history remains relevant after cleanup. Preserve the local exposure registry; historical negatives and recent positive-only feeds do not form a valid two-class temporal holdout.
- Report sample counts, precision, recall, FPR, uncertainty, calibration and limitations. Positive-only feeds cannot supply FPR or traffic precision. No Indonesian gold set or production readiness is established.
- Use public sources only. Do not submit access forms or contact others without explicit instructions.
- Add meaningful privacy, leakage and saved-model parity tests for relevant changes. Work on a feature branch. Do not commit, push or publish datasets without explicit instructions.
