"""Research-only decisions with explicit abstention and no target echo."""

import re
from urllib.parse import urlsplit

from .preprocessing import EXTRACT, InvalidUrl, prepare_url
from .rich_artifact import RichArtifact
from .rich_features import SCHEMA_VERSION
from .shadow_contracts import GeekView, HumanView, ShadowResult


def unavailable_reply(input_type="URL"):
    return ShadowResult(
        status="unavailable",
        input_type=input_type,
        reason_codes=["model_unavailable"],
        human=HumanView(
            title="Analisis belum tersedia",
            explanation="Model belum dapat memberikan indikator. Tautan memerlukan verifikasi.",
        ),
        geek=GeekView(),
    )


class ShadowPredictor:
    def __init__(self, artifact=None):
        self.artifact = artifact if artifact is not None else RichArtifact()

    def predict(self, url, input_type="URL"):
        if input_type not in {"URL", "QR"}:
            raise ValueError("unsupported_input_type")
        try:
            prepared = prepare_url(url)
            probability = float(self.artifact.predict_cores([prepared.core])[0])
        except InvalidUrl as error:
            reason = str(error)
            if not re.fullmatch(r"[a-z_]{1,64}", reason):
                reason = "unsupported_input"
            return ShadowResult(
                status="unsupported_input",
                input_type=input_type,
                reason_codes=[reason],
                human=HumanView(
                    title="Input memerlukan pemeriksaan lain",
                    explanation="Format ini belum dapat dinilai oleh classifier URL.",
                ),
                geek=GeekView(),
            )
        metadata = self.artifact.metadata
        thresholds = self.artifact.decision_thresholds
        band = (
            "HIGH"
            if metadata["high_enabled"] and probability >= thresholds["high"]
            else "MEDIUM"
            if probability >= thresholds["warning"]
            else "LOW"
        )
        raw = urlsplit(url if "://" in url else "https://" + url)
        flags = ["research_model_not_production_validated"]
        if raw.query:
            flags.append("query_context_excluded")
        if raw.fragment:
            flags.append("fragment_context_excluded")
        if "REDACTED" in prepared.path:
            flags.append("redacted_placeholder_in_model_view")
        if EXTRACT(prepared.host).is_private:
            flags.append("private_hosting_tenant_requires_context")
        if "xn--" in prepared.host:
            flags.append("punycode_host_requires_context")
        if len(prepared.core.split("://", 1)[1]) > 120:
            flags.append("long_url_requires_context")
        explanations = {
            "LOW": (
                "Indikator pola URL rendah",
                "Skor rendah belum menjamin tautan aman. Isi dan tujuan akhirnya masih memerlukan verifikasi.",
            ),
            "MEDIUM": (
                "Pola URL perlu diperiksa",
                "Model menemukan pola yang patut ditinjau. Tunda memasukkan data pribadi sampai ada bukti tambahan.",
            ),
            "HIGH": (
                "Indikasi kuat dari pola URL",
                "Pola URL mendapat indikator tinggi. Tunda interaksi dan periksa bukti tambahan.",
            ),
        }
        title, explanation = explanations[band]
        return ShadowResult(
            status="complete",
            input_type=input_type,
            risk_band=band,
            model_score=probability,
            reason_codes=flags,
            human=HumanView(title=title, explanation=explanation),
            geek=GeekView(
                model_version=metadata["version"],
                artifact_sha256=self.artifact.manifest["bundle_sha256"],
                feature_schema=SCHEMA_VERSION,
                thresholds=thresholds,
                frozen_thresholds=metadata["thresholds"],
                decision_policy_version=self.artifact.decision_policy_version,
                context_flags=flags,
            ),
        )
