import re
import secrets
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from . import model_handler
from .email_service import send_email
from .model_handler import ModelNotAvailableError
from .models import Feedback, Recommendation, Scan, User, db
from .preprocessor import preprocess, validate_tomato_leaf_image
from .rate_limiter import InMemoryRateLimiter

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_IMAGE_SUFFIXES = {f".{ext}" for ext in ALLOWED_IMAGE_EXTENSIONS}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def register_routes(app):
    from flask_login import LoginManager

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login_page"

    @login_manager.user_loader
    def load_user_by_id(user_id):
        return db.session.get(User, int(user_id))

    UPLOAD_FOLDER = Path(app.config["UPLOAD_FOLDER"])
    MODEL_PATH = app.config["MODEL_PATH"]
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

    def utc_now():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    limiter = InMemoryRateLimiter()

    def request_data():
        return request.get_json(silent=True) or request.form

    def request_identity():
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        remote = (request.remote_addr or "").strip()
        return forwarded or remote or "unknown"

    def rate_limit_response(scope, limit, window_seconds, bucket=""):
        key = f"{scope}:{request_identity()}:{bucket}".lower()
        result = limiter.check(key, limit, window_seconds)
        if result.allowed:
            return None
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Too many requests. Please try again shortly.",
                    "retry_after_seconds": result.retry_after_seconds,
                }
            ),
            429,
        )

    def normalize_label(label):
        raw = (label or "").strip()
        if not raw:
            return ""
        key = re.sub(r"\s+", " ", raw.replace("_", " ")).strip().lower()
        return {
            "early blight": "Early Blight",
            "late blight": "Late Blight",
            "leaf mold": "Leaf Mold",
            "healthy": "Healthy",
        }.get(key, raw)

    def get_recent_feedbacks(limit=4):
        rows = (
            db.session.query(Feedback, User.name)
            .join(User, Feedback.user_id == User.user_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
            .all()
        )
        return [feedback.to_dict(user_name=user_name) for feedback, user_name in rows]

    def existing_upload_url(filename):
        if not filename:
            return None
        file_path = UPLOAD_FOLDER / filename
        if not file_path.exists():
            return None
        return url_for("uploaded_file", filename=filename)

    def delete_uploaded_file(filename):
        if not filename:
            return
        try:
            file_path = UPLOAD_FOLDER / filename
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass

    def build_upload_filename(original_name, prefix):
        safe_name = secure_filename(original_name or "")
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_IMAGE_SUFFIXES:
            ext = ".jpg"
        return f"{prefix}_{uuid.uuid4().hex}{ext}"

    def save_uploaded_image(file_storage, prefix):
        filename = build_upload_filename(file_storage.filename, prefix)
        save_path = UPLOAD_FOLDER / filename
        file_storage.save(str(save_path))
        return filename, save_path

    def is_email_valid(email):
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))

    def generate_otp():
        return f"{secrets.randbelow(1000000):06d}"

    def send_verification_otp(user, email):
        otp = generate_otp()
        user.otp_code = otp
        user.otp_expires_at = utc_now() + timedelta(minutes=10)
        user.is_verified = False
        db.session.commit()
        body = (
            "Welcome to AI Tomato Care!\n\n"
            f"Your email verification code is: {otp}\n\n"
            "This code expires in 10 minutes.\n"
            "If you did not request this, you can ignore this email."
        )
        send_email(app, email, "Verify your AI Tomato Care email", body)

    @app.route("/")
    def index():
        last_prediction = None
        if current_user.is_authenticated:
            last_label = current_user.last_prediction_label
            if last_label:
                normalized_label = normalize_label(last_label)
                recommendation = current_user.last_prediction_recommendation or ""
                if not recommendation:
                    rec = Recommendation.get_for_label(normalized_label)
                    recommendation = rec.text if rec else ""
                image_url = existing_upload_url(current_user.last_prediction_image_url)
                last_prediction = {
                    "label": normalized_label,
                    "confidence": current_user.last_prediction_confidence,
                    "recommendation": recommendation,
                    "image_url": image_url,
                }
        return render_template("index.html", last_prediction=last_prediction)

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        if request.method == "POST":
            data = request_data()
            email = (data.get("email") or "").strip()
            password = data.get("password") or ""
            limited = rate_limit_response("login", 8, 900, bucket=email)
            if limited:
                return limited
            user = User.query.filter_by(email=email).first()
            if not user:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "User is not registered. Please sign up.",
                        }
                    ),
                    404,
                )
            if user.check_password(password):
                if not user.is_verified:
                    verification_redirect = url_for(
                        "register_page",
                        email=user.email,
                        stage="otp",
                        reason="verify_required",
                    )
                    payload = {
                        "success": False,
                        "requires_verification": True,
                        "message": "Please verify your email with OTP before logging in.",
                        "email": user.email,
                        "redirect": verification_redirect,
                    }
                    if request.is_json:
                        return jsonify(payload), 403
                    return redirect(verification_redirect)
                login_user(user)
                next_param = request.args.get("next")
                redirect_url = (
                    next_param
                    if (
                        next_param
                        and next_param.startswith("/")
                        and "//" not in next_param
                    )
                    else url_for("index")
                )
                return (
                    jsonify({"success": True, "redirect": redirect_url})
                    if request.is_json
                    else redirect(redirect_url)
                )
            return jsonify(
                {"success": False, "message": "Email or password is incorrect."}
            ), 401
        return render_template("login.html")

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password_page():
        if request.method == "POST":
            data = request_data()
            email = (data.get("email") or "").strip()
            limited = rate_limit_response("forgot_password", 5, 900, bucket=email)
            if limited:
                return limited
            if not email:
                return jsonify(
                    {
                        "success": False,
                        "message": "Please enter your email address.",
                    }
                ), 400
            user = User.query.filter_by(email=email).first()
            if not user:
                message = "Use your login email or sign up email."
                if request.is_json:
                    return jsonify({"success": False, "message": message}), 404
                return render_template("forgot_password.html", error=message)
            token = serializer.dumps(email, salt="password-reset")
            reset_link = url_for("reset_password_query", token=token, _external=True)
            body = (
                "You requested a password reset for AI Tomato Care.\n\n"
                f"Reset your password using this link:\n{reset_link}\n\n"
                "If you did not request this, you can ignore this email."
            )
            try:
                send_email(
                    app,
                    email,
                    "Reset your AI Tomato Care password",
                    body,
                )
            except Exception:
                app.logger.exception(
                    "Failed to send password reset email for %s", email
                )
                fallback_enabled = app.config.get("PASSWORD_RESET_LINK_FALLBACK", False)
                if fallback_enabled:
                    app.logger.warning(
                        "PASSWORD_RESET_LINK_FALLBACK is enabled. Disable it in production."
                    )
                    message = "Email could not be sent. Contact support."
                    if request.is_json:
                        return jsonify({"success": False, "message": message}), 503
                    return render_template("forgot_password.html", error=message), 503
                return (
                    render_template(
                        "forgot_password.html",
                        error="Email service is not configured. Contact support.",
                    ),
                    500,
                )
            message = "If this email exists, a password reset link has been sent."
            if request.is_json:
                return jsonify({"success": True, "message": message})
            return render_template("forgot_password.html", success=message)
        return render_template("forgot_password.html")

    @app.route("/reset-password/<path:token>", methods=["GET", "POST"])
    def reset_password_page(token):
        email = None
        error = None
        try:
            email = serializer.loads(
                token,
                salt="password-reset",
                max_age=app.config.get("RESET_TOKEN_MAX_AGE", 3600),
            )
        except SignatureExpired:
            error = "This reset link has expired. Please request a new one."
        except BadSignature:
            error = "Invalid reset link. Please request a new one."

        if error:
            return render_template("reset_password.html", error=error)

        if request.method == "POST":
            data = request_data()
            password = (data.get("password") or "").strip()
            confirm = (data.get("confirm_password") or "").strip()
            limited = rate_limit_response("reset_password", 6, 900, bucket=email or "")
            if limited:
                return limited
            if not password or not confirm:
                return render_template(
                    "reset_password.html",
                    error="Please fill in all fields.",
                )
            if len(password) < 8:
                message = "Password must be at least 8 characters."
                if request.is_json:
                    return jsonify({"success": False, "message": message}), 400
                return render_template("reset_password.html", error=message)
            if password != confirm:
                return render_template(
                    "reset_password.html",
                    error="Passwords do not match.",
                )
            user = User.query.filter_by(email=email).first()
            if not user:
                return render_template(
                    "reset_password.html",
                    error="Account not found.",
                )
            user.set_password(password)
            db.session.commit()
            if request.is_json:
                return jsonify(
                    {
                        "success": True,
                        "message": "Password updated. Please log in.",
                        "redirect": url_for("login_page"),
                    }
                )
            return redirect(url_for("login_page"))

        return render_template("reset_password.html")

    @app.route(
        "/reset-password", methods=["GET", "POST"], endpoint="reset_password_query"
    )
    def reset_password_query():
        token = (request.args.get("token") or "").strip()
        if not token:
            return render_template(
                "reset_password.html",
                error="Missing reset token. Please request a new reset link.",
            )
        return reset_password_page(token)

    @app.route("/verify-email", methods=["GET", "POST"])
    def verify_email_page():
        if request.method == "GET":
            return redirect(url_for("register_page"))
        data = request_data()
        email = (data.get("email") or "").strip()
        otp = (data.get("otp") or "").strip()
        limited = rate_limit_response("verify_email", 8, 600, bucket=email)
        if limited:
            return limited
        if not otp:
            return jsonify(
                {"success": False, "message": "Please enter the OTP code."}
            ), 400
        user = User.query.filter_by(email=email).first()
        if not user:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Use your login email or sign up email.",
                    }
                ),
                404,
            )
        if user.is_verified:
            return jsonify(
                {
                    "success": True,
                    "message": "Email already verified.",
                    "redirect": url_for("login_page"),
                }
            )
        if not user.otp_code or not user.otp_expires_at:
            return jsonify(
                {"success": False, "message": "OTP expired. Please resend OTP."}
            ), 400
        if utc_now() > user.otp_expires_at:
            return jsonify(
                {"success": False, "message": "OTP expired. Please resend OTP."}
            ), 400
        if otp != user.otp_code:
            return jsonify(
                {"success": False, "message": "Invalid OTP. Please try again."}
            ), 400
        user.is_verified = True
        user.otp_code = None
        user.otp_expires_at = None
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": "Email verified successfully.",
                "redirect": url_for("login_page"),
            }
        )

    @app.route("/resend-otp", methods=["POST"])
    def resend_otp():
        data = request_data()
        email = (data.get("email") or "").strip()
        limited = rate_limit_response("resend_otp", 5, 600, bucket=email)
        if limited:
            return limited
        if not email:
            return jsonify(
                {"success": False, "message": "Please enter your email."}
            ), 400
        user = User.query.filter_by(email=email).first()
        if not user:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Use your login email or sign up email.",
                    }
                ),
                404,
            )
        if user.is_verified:
            return jsonify({"success": True, "message": "Email already verified."})
        try:
            send_verification_otp(user, user.email)
        except Exception:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Email service is not configured. Please contact support.",
                    }
                ),
                500,
            )
        return jsonify(
            {"success": True, "message": "A new OTP has been sent to your email."}
        )

    @app.route("/register", methods=["GET", "POST"])
    def register_page():
        if request.method == "POST":
            wants_json = (
                request.is_json
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            )
            data = request_data()
            name = (data.get("name") or "").strip()
            email = (data.get("email") or "").strip()
            password = data.get("password") or ""
            limited = rate_limit_response("register", 5, 900, bucket=email)
            if limited:
                return limited
            if not name or not email or not password:
                payload = {"success": False, "message": "Please fill all fields."}
                if wants_json:
                    return jsonify(payload), 400
                return render_template("register.html", error=payload["message"])
            if len(password) < 8:
                payload = {
                    "success": False,
                    "message": "Password must be at least 8 characters.",
                }
                if wants_json:
                    return jsonify(payload), 400
                return render_template("register.html", error=payload["message"])
            if not is_email_valid(email):
                payload = {
                    "success": False,
                    "message": "Please enter a valid email address.",
                }
                if wants_json:
                    return jsonify(payload), 400
                return render_template("register.html", error=payload["message"])
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                if existing_user.is_verified:
                    payload = {
                        "success": False,
                        "message": "Email already registered.",
                    }
                    if wants_json:
                        return jsonify(payload), 400
                    return render_template(
                        "register.html",
                        error=payload["message"],
                    )
                try:
                    send_verification_otp(existing_user, existing_user.email)
                except Exception:
                    payload = {
                        "success": False,
                        "message": "Email service is not configured. Please contact support.",
                    }
                    if wants_json:
                        return jsonify(payload), 500
                    return render_template("register.html", error=payload["message"])
                payload = {
                    "success": True,
                    "stage": "otp",
                    "email": existing_user.email,
                    "message": "Account exists but email is not verified. A new OTP has been sent.",
                }
                if wants_json:
                    return jsonify(payload)
                return render_template(
                    "register.html",
                    otp_stage=True,
                    otp_email=existing_user.email,
                    success=payload["message"],
                )
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            try:
                send_verification_otp(user, user.email)
            except Exception:
                payload = {
                    "success": False,
                    "message": "Email service is not configured. Please contact support.",
                }
                if wants_json:
                    return jsonify(payload), 500
                return render_template("register.html", error=payload["message"])
            payload = {
                "success": True,
                "stage": "otp",
                "email": user.email,
                "message": "OTP sent. Please verify your email to complete sign up.",
            }
            if wants_json:
                return jsonify(payload)
            return render_template(
                "register.html", otp_stage=True, otp_email=user.email
            )
        otp_stage = (request.args.get("stage") or "").strip().lower() == "otp"
        otp_email = (request.args.get("email") or "").strip()
        reason = (request.args.get("reason") or "").strip().lower()
        success = None
        if not otp_email:
            otp_stage = False
        elif otp_stage and reason == "verify_required":
            success = "Your account is not verified yet. Enter OTP below or resend OTP."
        return render_template(
            "register.html",
            otp_stage=otp_stage,
            otp_email=otp_email,
            success=success,
        )

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/history")
    @login_required
    def history_page():
        return render_template("history.html")

    @app.route("/account")
    @login_required
    def account_page():
        return render_template("account.html")

    @app.route("/change-password")
    @login_required
    def change_password():
        return render_template("change_password.html")

    @app.route("/delete-account")
    @login_required
    def delete_account():
        return render_template("delete_account.html")

    @app.route("/api/account/change-password", methods=["POST"])
    @login_required
    def api_change_password():
        data = request_data()
        current_password = (data.get("current_password") or "").strip()
        new_password = (data.get("new_password") or "").strip()
        confirm_password = (data.get("confirm_password") or "").strip()

        if not current_password or not new_password or not confirm_password:
            return jsonify(
                {"success": False, "message": "Please fill in all password fields."}
            ), 400

        if new_password != confirm_password:
            return jsonify(
                {"success": False, "message": "New passwords do not match."}
            ), 400
        if len(new_password) < 8:
            return jsonify(
                {
                    "success": False,
                    "message": "Password must be at least 8 characters.",
                }
            ), 400

        if not current_user.check_password(current_password):
            return jsonify(
                {"success": False, "message": "Current password is incorrect."}
            ), 400

        current_user.set_password(new_password)
        db.session.commit()
        return jsonify({"success": True, "message": "Password updated successfully."})

    @app.route("/api/account/delete", methods=["POST"])
    @login_required
    def api_delete_account():
        data = request_data()
        confirm_text = (data.get("confirm_text") or "").strip().upper()
        password = (data.get("password") or "").strip()

        if confirm_text != "DELETE":
            return jsonify(
                {
                    "success": False,
                    "message": 'Please type "DELETE" in the confirmation box to proceed.',
                }
            ), 400

        if not password:
            return jsonify(
                {
                    "success": False,
                    "message": "Password is required to delete your account.",
                }
            ), 400

        if not current_user.check_password(password):
            return jsonify({"success": False, "message": "Password is incorrect."}), 400

        user_id = int(current_user.get_id())

        user_scans = Scan.query.filter_by(user_id=user_id).all()
        for scan in user_scans:
            delete_uploaded_file(scan.image_url)

        Feedback.query.filter_by(user_id=user_id).delete()
        Scan.query.filter_by(user_id=user_id).delete()

        user = db.session.get(User, user_id)
        if user:
            db.session.delete(user)

        db.session.commit()
        logout_user()
        return jsonify(
            {
                "success": True,
                "message": "Your account and history have been deleted.",
                "redirect": url_for("index"),
            }
        )

    @app.route("/recommendations")
    def recommendations_page():
        return redirect(url_for("care_tips_page"))

    @app.route("/about")
    def about_page():
        return render_template("about.html")

    @app.route("/dashboard")
    @login_required
    def dashboard_page():
        user_id = int(current_user.get_id())
        all_scans = Scan.query.filter_by(user_id=user_id).all()
        total_scans = len(all_scans)
        healthy_count = sum(
            1 for scan in all_scans if normalize_label(scan.label) == "Healthy"
        )
        label_counts = Counter(
            normalize_label(scan.label) or "Unknown" for scan in all_scans
        )
        top_labels = label_counts.most_common(3)

        recent_scans = (
            Scan.query.filter_by(user_id=user_id)
            .order_by(Scan.created_at.desc())
            .limit(5)
            .all()
        )
        last_scan = recent_scans[0] if recent_scans else None
        healthy_rate = (
            round((healthy_count / total_scans) * 100, 1) if total_scans else 0
        )
        last_scan_label = normalize_label(last_scan.label) if last_scan else None
        recent_scan_data = [
            {
                "label": normalize_label(scan.label),
                "confidence": round(scan.confidence * 100, 1),
                "created_at_iso": scan.created_at.isoformat()
                if scan.created_at
                else None,
                "image_url": existing_upload_url(scan.image_url),
            }
            for scan in recent_scans
        ]
        return render_template(
            "dashboard.html",
            total_scans=total_scans,
            last_scan=last_scan,
            last_scan_label=last_scan_label,
            last_scan_iso=last_scan.created_at.isoformat()
            if last_scan and last_scan.created_at
            else None,
            healthy_rate=healthy_rate,
            top_labels=top_labels,
            recent_scans=recent_scan_data,
        )

    @app.route("/care-tips")
    def care_tips_page():
        return render_template("care_tips.html")

    @app.route("/faq")
    def faq_page():
        return render_template("faq.html")

    @app.route("/feedback")
    def feedback_page():
        user_feedback = None
        if current_user.is_authenticated:
            row = Feedback.query.filter_by(user_id=int(current_user.get_id())).first()
            if row:
                user_feedback = row.to_dict(user_name=current_user.name)
        return render_template(
            "feedback.html",
            recent_feedbacks=get_recent_feedbacks(limit=4),
            user_feedback=user_feedback,
        )

    @app.route("/contact", methods=["GET", "POST"])
    @login_required
    def contact_page():
        if request.method == "POST":
            data = request_data()
            name = (data.get("name") or "").strip()
            email = current_user.email
            subject = (data.get("subject") or "New contact message").strip()
            message = (data.get("message") or "").strip()
            if not name or not email or not message:
                error = "Please fill in name, email, and message."
                if request.is_json:
                    return jsonify({"success": False, "message": error}), 400
                return render_template("contact.html", error=error)
            if not is_email_valid(email):
                error = "Please enter a valid email address."
                if request.is_json:
                    return jsonify({"success": False, "message": error}), 400
                return render_template("contact.html", error=error)

            receiver = app.config.get("CONTACT_RECEIVER")
            body = f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\n{message}"
            try:
                send_email(
                    app,
                    receiver,
                    f"[AI Tomato Care] {subject}",
                    body,
                    reply_to=email,
                )
            except Exception:
                error = "Email service is not configured. Please try again later."
                if request.is_json:
                    return jsonify({"success": False, "message": error}), 500
                return render_template("contact.html", error=error)

            success = "Message sent successfully. We will reply soon."
            if request.is_json:
                return jsonify({"success": True, "message": success})
            return render_template("contact.html", success=success)

        return render_template("contact.html")

    @app.route("/api/feedback", methods=["POST"])
    @login_required
    def api_feedback_create():
        data = request_data()
        comment = (data.get("comment") or "").strip()
        rating_raw = data.get("rating")
        user_id = int(current_user.get_id())

        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Rating must be 1 to 5."}), 400

        if rating < 1 or rating > 5:
            return jsonify({"success": False, "message": "Rating must be 1 to 5."}), 400
        if len(comment) > 1000:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Comment is too long. Keep it under 1000 characters.",
                    }
                ),
                400,
            )

        feedback = Feedback.query.filter_by(user_id=user_id).first()
        is_update = feedback is not None
        if is_update:
            feedback.rating = rating
            feedback.comment = comment or ""
            feedback.created_at = utc_now()
        else:
            feedback = Feedback(
                user_id=user_id,
                rating=rating,
                comment=comment or "",
            )
        try:
            if not is_update:
                db.session.add(feedback)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            fallback = Feedback.query.filter_by(user_id=user_id).first()
            if not fallback:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Failed to save feedback. Please try again.",
                        }
                    ),
                    500,
                )
            fallback.rating = rating
            fallback.comment = comment or ""
            fallback.created_at = utc_now()
            db.session.commit()
            feedback = fallback
            is_update = True

        return jsonify(
            {
                "success": True,
                "message": "Feedback updated successfully."
                if is_update
                else "Thanks for your feedback!",
                "feedback": feedback.to_dict(user_name=current_user.name),
            }
        )

    @app.route("/api/feedback/delete", methods=["POST"])
    @login_required
    def api_feedback_delete():
        user_id = int(current_user.get_id())
        feedback = Feedback.query.filter_by(user_id=user_id).first()
        if not feedback:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No existing feedback found to delete.",
                    }
                ),
                404,
            )

        db.session.delete(feedback)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": "Your feedback was deleted. You can submit a new one now.",
            }
        )

    @app.route("/api/predict", methods=["POST"])
    def api_predict():
        if "file" not in request.files and "image" not in request.files:
            return jsonify({"error": "No image file provided."}), 400
        file = request.files.get("file") or request.files.get("image")
        if not file or file.filename == "":
            return jsonify({"error": "No image selected."}), 400
        if not allowed_file(file.filename):
            return jsonify({"error": "Allowed formats: JPG, JPEG, PNG."}), 400
        try:
            filename, save_path = save_uploaded_image(file, "scan")
        except Exception:
            return jsonify({"error": "Failed to save image."}), 500

        leaf_gate_config = {
            "min_foliage_ratio": float(
                app.config.get("LEAF_GATE_MIN_FOLIAGE_RATIO", 0.25)
            ),
            "min_largest_component_ratio": float(
                app.config.get("LEAF_GATE_MIN_LARGEST_COMPONENT_RATIO", 0.25)
            ),
            "max_component_complexity": float(
                app.config.get("LEAF_GATE_MAX_COMPONENT_COMPLEXITY", 9.0)
            ),
            "min_edge_ratio": float(app.config.get("LEAF_GATE_MIN_EDGE_RATIO", 0.015)),
        }
        is_leaf_like, leaf_metrics = validate_tomato_leaf_image(
            save_path,
            **leaf_gate_config,
        )
        if not is_leaf_like:
            delete_uploaded_file(filename)
            app.logger.info(
                "Rejected non-leaf image: %s metrics=%s thresholds=%s",
                filename,
                leaf_metrics,
                leaf_gate_config,
            )
            return (
                jsonify(
                    {
                        "error": (
                            "This image does not look like a tomato leaf. "
                            "Please upload a clear close-up of one tomato leaf."
                        )
                    }
                ),
                400,
            )

        try:
            input_size = model_handler.get_input_shape(MODEL_PATH)
            tensor = preprocess(save_path, target_size=input_size or (224, 224))
        except Exception:
            delete_uploaded_file(filename)
            return jsonify({"error": "Invalid or unreadable image."}), 400

        try:
            label, confidence = model_handler.predict(tensor, MODEL_PATH)
        except ModelNotAvailableError:
            delete_uploaded_file(filename)
            return jsonify({"error": "Prediction service is unavailable."}), 503
        except Exception:
            delete_uploaded_file(filename)
            return jsonify(
                {"error": "Prediction failed. Please try another image."}
            ), 500

        label = normalize_label(label)
        if confidence < 0.5:
            delete_uploaded_file(filename)
            return (
                jsonify(
                    {
                        "error": (
                            "Could not confidently detect a tomato leaf disease. "
                            "Upload a clearer, well-lit photo of a single tomato leaf."
                        )
                    }
                ),
                400,
            )

        rec = Recommendation.get_for_label(label)
        recommendation = rec.text if rec else "No specific recommendation available."

        if current_user.is_authenticated:
            scan = Scan(
                user_id=int(current_user.get_id()),
                image_url=filename,
                label=label,
                confidence=confidence,
            )
            db.session.add(scan)
            current_user.last_prediction_label = label
            current_user.last_prediction_confidence = confidence
            current_user.last_prediction_recommendation = recommendation
            current_user.last_prediction_image_url = filename
            current_user.last_prediction_created_at = utc_now()
            db.session.commit()
        else:
            delete_uploaded_file(filename)

        return jsonify(
            {
                "label": label,
                "confidence": round(confidence, 2),
                "recommendation": recommendation,
            }
        )

    @app.route("/api/history")
    @login_required
    def api_history():
        scans = (
            Scan.query.filter_by(user_id=int(current_user.get_id()))
            .order_by(Scan.created_at.desc())
            .all()
        )
        rows = []
        for scan in scans:
            row = scan.to_dict()
            row["label"] = normalize_label(row.get("label"))
            rows.append(row)
        return jsonify(rows)

    @app.route("/api/history/<int:scan_id>/delete", methods=["POST"])
    @login_required
    def api_history_delete(scan_id):
        user_id = int(current_user.get_id())
        scan = Scan.query.filter_by(scan_id=scan_id, user_id=user_id).first()
        if not scan:
            return jsonify({"success": False, "message": "Scan not found."}), 404
        delete_uploaded_file(scan.image_url)
        db.session.delete(scan)
        db.session.commit()
        return jsonify({"success": True, "message": "Scan deleted."})

    @app.route("/api/history/clear", methods=["POST"])
    @login_required
    def api_history_clear():
        user_id = int(current_user.get_id())

        scans = Scan.query.filter_by(user_id=user_id).all()
        for scan in scans:
            delete_uploaded_file(scan.image_url)

        Scan.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({"success": True, "message": "Scan history cleared."})

    @app.route("/api/last-prediction/clear", methods=["POST"])
    @login_required
    def api_last_prediction_clear():
        current_user.last_prediction_label = None
        current_user.last_prediction_confidence = None
        current_user.last_prediction_recommendation = None
        current_user.last_prediction_image_url = None
        current_user.last_prediction_created_at = None
        db.session.commit()
        return jsonify({"success": True, "message": "Last prediction cleared."})

    @app.route("/api/recommendations")
    def api_recommendations():
        recs = Recommendation.query.all()
        return jsonify(
            [{"label": r.label, "text": r.text, "image_url": r.image_url} for r in recs]
        )

    @app.route("/uploads/<path:filename>")
    @login_required
    def uploaded_file(filename):
        safe_name = secure_filename(Path(filename).name)
        if not safe_name or safe_name != filename:
            return "", 404
        user_id = int(current_user.get_id())
        owns_scan_file = (
            Scan.query.filter_by(user_id=user_id, image_url=safe_name).first()
            is not None
        )
        owns_last_snapshot = current_user.last_prediction_image_url == safe_name
        if not owns_scan_file and not owns_last_snapshot:
            return "", 404
        return send_from_directory(UPLOAD_FOLDER, safe_name)
