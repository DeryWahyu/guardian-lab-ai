# Guardian Lab AI — Agent Guidelines

Read README.md, ai-agent-docs/machine-learning-plan.md, and ai-agent-docs/url-qr-dataset-research.md before changing the ML pipeline.

Current user choice: use **frozen Logistic Regression v6 as the single primary model for now**. Read [ai-agent-docs/selected-model-v6.md](ai-agent-docs/selected-model-v6.md). The primary notebook is `guardian_lab_url_qr_data_v6.ipynb`; the shadow API already loads the original v6 artifact and original thresholds. Focus current work on v6. Keep v3/v7-v10 as research archives and preserve their provenance; v10 CNN remains untrained. This choice does not satisfy production/Indonesia gates or select a winner from final-test accuracy.

For the authorized five-step recall/CNN v10 work, read [ai-agent-docs/recall-cnn-v10-plan.md](ai-agent-docs/recall-cnn-v10-plan.md) and results. Development audit and public intake are completed; CNN is untrained and must remain gated until a sufficiently supported new two-class temporal holdout is frozen. IOB researcher-accepted FQDNs are historical domain-only negatives, not current page labels; 32 unaccepted cases are excluded. PhishTank is positive-only. Do not combine historical negatives and recent positives into a purported valid temporal accuracy. Register completed intake exposure before fitting; v10 provenance does not imply completed training. User preference remains public sources only, no access-form submission or invented reviewers.

For error/label audits, research serving, abstention and aggregate monitoring, read [ai-agent-docs/model-hardening-plan.md](ai-agent-docs/model-hardening-plan.md) and [ai-agent-docs/shadow-api-contract.md](ai-agent-docs/shadow-api-contract.md). Use published human evidence first as requested by the user; do not invent local reviewers or Indonesian labels. Preserve frozen notebooks/weights. Runtime changes require source-manifest updates and real-artifact parity tests. The shadow API never promotes LOW to SAFE or unsupported/unavailable input to LOW.

For structural retraining v7 and Phish360 evaluation, read [ai-agent-docs/structural-retraining-v7-plan.md](ai-agent-docs/structural-retraining-v7-plan.md). Quarantine fit ambiguities without relabeling; preserve other partitions. Select and freeze exclusively from development. Distinguish publisher manual-curation claims from two independently released per-case human audits, historical data from current Indonesian evidence, and original v6 thresholds from the predeclared confidence-policy control. Register completed v7 data exposure only after model, code, dataset, and evaluation hashes validate.

For v8 data expansion and worst-source selection, read [ai-agent-docs/data-expansion-v8-plan.md](ai-agent-docs/data-expansion-v8-plan.md). TR-OP labels are author-reported manual validation, not Indonesian gold. Its new holdout is domain-disjoint from added development from the same source. Verify bounded ZIP text reads and CRC; do not use incomplete source intake. Preserve Phish360 as an observed benchmark. Respect the source regression guard and retain v6 when no new candidate passes; diagnostic challengers are not selected replacements. Index all valid sanitized intake exposure after completed v8 provenance validates.

For the authorized CatBoost versus Logistic Regression comparison v9, read [ai-agent-docs/model-family-comparison-v9-plan.md](ai-agent-docs/model-family-comparison-v9-plan.md) and its results. Compare matched-feature models separately from full-TF-IDF controls; SVD compression limits family-wide conclusions. All seven benchmarks are observed. Keep classifier fitting, sigmoid calibration and threshold roles separate. Report v6 comparison thresholds separately from unchanged original shadow thresholds. No new URLs or gold labels are introduced; never promote from benchmark accuracy.

For the v4 development retraining experiment, also read [ai-agent-docs/retraining-v4-plan.md](ai-agent-docs/retraining-v4-plan.md). Preserve the frozen v3 baseline and identify all previously observed benchmarks explicitly.

For v5 recall improvement and evaluation on new sources, read [ai-agent-docs/recall-improvement-v5-plan.md](ai-agent-docs/recall-improvement-v5-plan.md). Keep the new evaluation datasets out of all fitting/selection/calibration/threshold decisions; record vendor consensus and published human labels as separate evidence tiers.

For v6 data expansion, current community phishing, and low-FPR reference controls, read [ai-agent-docs/data-improvement-v6-plan.md](ai-agent-docs/data-improvement-v6-plan.md). Distinguish original baseline policy from the late-declared development-threshold control, report recall regressions, and never invent FPR from a positive-only feed.

For Indonesian candidate collection, annotation, exposure audits, gold sets, and local validation, also read [ai-agent-docs/indonesia-gold-set-plan.md](ai-agent-docs/indonesia-gold-set-plan.md). Preparation tools must not invent human reviews or present previously observed data as a new independent holdout.

- Scope: URL-only binary phishing classification; decoded QR URLs use the same model. APK classifiers and deployment integration remain separate work.
- Never visit dataset target URLs, execute HTML, request real credentials, or send dataset rows to an LLM.
- Never persist raw URLs containing personal information. Apply the same versioned parser, sanitizer, and feature extractor during ingestion and prediction.
- Keep raw data, local environments, and model binaries out of Git. Track aggregate audit reports, manifests, source versions, and checksums.
- Audit canonical duplicates, label conflicts, time boundaries, registered domains/private hosting tenants, and source overlap before training. Record unverified campaign overlap honestly.
- Separate fitting, tuning, calibration, threshold selection, and final testing. Never fit transformations on holdouts or choose a winner from final-test metrics.
- Report precision, recall, FPR with uncertainty, calibration, sample counts, runtime, and limitations. Do not invent accuracy or claim production readiness from a research benchmark.
- Pin dependencies and use the PSL offline. Do not fetch live reputation or DNS during URL-only inference.
- Add meaningful tests for privacy, data leakage, and saved-model prediction parity. Keep modules focused and portable.
- Work on a feature branch. Do not commit, push, or publish datasets without explicit instructions.
