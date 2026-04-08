from __future__ import annotations

from sqlalchemy import func, select

from packages.neuroslice_common.models import Prediction


def latest_prediction_subquery():
    return (
        select(
            Prediction.session_id.label("session_id"),
            func.max(Prediction.predicted_at).label("latest_predicted_at"),
        )
        .group_by(Prediction.session_id)
        .subquery()
    )
