"""Fail-closed training gate; historical/positive-only challenges cannot unlock fitting."""


def require_training_readiness(evidence):
    failures = []
    for key in [
        "development_error_audit_complete",
        "intake_integrity_verified",
        "new_holdout_frozen_before_training",
        "holdout_domains_disjoint",
        "holdout_labels_traceable",
        "holdout_period_verified",
    ]:
        if evidence.get(key) is not True:
            failures.append(key)
    if evidence.get("new_holdout_benign", 0) < 400:
        failures.append("new_holdout_benign_at_least_400")
    if evidence.get("new_holdout_phishing", 0) < 200:
        failures.append("new_holdout_phishing_at_least_200")
    if failures:
        raise ValueError("cnn_training_gate_failed:" + ",".join(failures))
    return True
