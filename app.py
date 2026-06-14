from pathlib import Path

from flask import Flask
from sqlalchemy import text

from backend.models import Recommendation, db
from backend.routes import register_routes
from config import Config

DEFAULT_RECOMMENDATIONS = [
    (
        "Early Blight",
        "Remove affected leaves. Apply copper-based fungicide. Improve air circulation and avoid overhead watering.",
    ),
    (
        "Late Blight",
        "Apply fungicide containing chlorothalonil or copper. Destroy infected plants. Avoid watering foliage.",
    ),
    (
        "Leaf Mold",
        "Use fungicide (e.g. chlorothalonil). Reduce humidity; water at base. Ensure good ventilation.",
    ),
    (
        "Healthy",
        "No treatment needed. Continue good practices: proper spacing, watering at base, and monitoring.",
    ),
]


def _ensure_runtime_directories(app: Flask) -> None:
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)


def _is_postgresql() -> bool:
    return db.engine.dialect.name == "postgresql"


def _drop_removed_profile_columns() -> None:
    if not _is_postgresql():
        return

    removed_columns = ("avatar_url", "phone", "location", "farm_name", "bio")
    with db.engine.begin() as conn:
        for column_name in removed_columns:
            conn.execute(text(f"ALTER TABLE users DROP COLUMN IF EXISTS {column_name}"))


def _enforce_single_feedback_per_user() -> None:
    if not _is_postgresql():
        return

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM feedbacks older
                USING feedbacks newer
                WHERE older.user_id = newer.user_id
                  AND (
                    older.created_at < newer.created_at
                    OR (
                      older.created_at = newer.created_at
                      AND older.feedback_id < newer.feedback_id
                    )
                  )
                """
            )
        )
        has_unique_user_index = conn.execute(
            text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = ANY (current_schemas(false))
                  AND tablename = 'feedbacks'
                  AND indexdef ILIKE 'CREATE UNIQUE INDEX%(%user_id%)'
                LIMIT 1
                """
            )
        ).first()
        if not has_unique_user_index:
            conn.execute(
                text("CREATE UNIQUE INDEX uq_feedbacks_user_id ON feedbacks (user_id)")
            )


def _seed_recommendations() -> None:
    if Recommendation.query.count() > 0:
        return

    for label, text_value in DEFAULT_RECOMMENDATIONS:
        db.session.add(Recommendation(label=label, text=text_value))
    db.session.commit()


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    _ensure_runtime_directories(app)
    db.init_app(app)
    register_routes(app)

    with app.app_context():
        db.create_all()
        _drop_removed_profile_columns()
        _enforce_single_feedback_per_user()
        _seed_recommendations()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
