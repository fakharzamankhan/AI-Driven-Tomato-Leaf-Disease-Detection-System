from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(10), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)
    last_prediction_label = db.Column(db.String(100), nullable=True)
    last_prediction_confidence = db.Column(db.Float, nullable=True)
    last_prediction_recommendation = db.Column(db.Text, nullable=True)
    last_prediction_image_url = db.Column(db.String(255), nullable=True)
    last_prediction_created_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    def get_id(self) -> str:
        return str(self.user_id)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Scan(db.Model):
    __tablename__ = "scans"

    scan_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    image_url = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "image_url": self.image_url,
            "label": self.label,
            "confidence": round(self.confidence, 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    feedback_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, unique=True
    )
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    def to_dict(self, user_name: str | None = None) -> dict:
        return {
            "feedback_id": self.feedback_id,
            "user_id": self.user_id,
            "user_name": user_name or "User",
            "rating": int(self.rating),
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Recommendation(db.Model):
    __tablename__ = "recommendations"

    rec_id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)

    @staticmethod
    def get_for_label(label: str):
        return Recommendation.query.filter_by(label=label).first()
