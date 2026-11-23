# poker_bankroll_analyzer/editorial_routes.py
import re
from flask import Blueprint, jsonify, request
from .decorators import require_auth, require_role
from .errors import error_response
from .extensions import db
from .models import (
    Article,
    SponsorBanner,
    User,
    VALID_ARTICLE_CATEGORIES,
    VALID_BANNER_PLACEMENTS,
)

editorial_blueprint = Blueprint("editorial", __name__)


def _slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "article"


@editorial_blueprint.route("/articles", methods=["GET"])
def list_articles():
    """Public DFW editorial feed (Player Spotlights, News, Strategy + Affiliate links)."""
    category = request.args.get("category", "").strip().lower()
    query = Article.query.filter_by(is_published=True)

    if category:
        if category not in VALID_ARTICLE_CATEGORIES:
            return error_response(
                "VALIDATION_ERROR",
                f"category must be one of: {', '.join(sorted(VALID_ARTICLE_CATEGORIES))}.",
                400,
            )
        query = query.filter_by(category=category)

    articles = query.order_by(Article.created_at.desc(), Article.id.desc()).all()
    items = [a.to_dict() for a in articles]
    return jsonify({"items": items, "total": len(items)}), 200


@editorial_blueprint.route("/articles/<string:slug>", methods=["GET"])
def get_article_by_slug(slug):
    """Fetch a single published article or player spotlight by its URL slug."""
    article = Article.query.filter_by(slug=slug, is_published=True).first()
    if not article:
        return error_response("NOT_FOUND", "Article not found.", 404)
    return jsonify(article.to_dict()), 200


@editorial_blueprint.route("/articles", methods=["POST"])
@require_auth
@require_role("admin")
def create_article():
    """Admin-only endpoint to publish a North Dallas Player Spotlight, news, or strategy post."""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    category = (data.get("category") or "spotlight").strip().lower()

    if not title or not body:
        return error_response("VALIDATION_ERROR", "Both 'title' and 'body' are required.", 400)

    if category not in VALID_ARTICLE_CATEGORIES:
        return error_response(
            "VALIDATION_ERROR",
            f"category must be one of: {', '.join(sorted(VALID_ARTICLE_CATEGORIES))}.",
            400,
        )

    raw_slug = (data.get("slug") or "").strip()
    slug = _slugify(raw_slug if raw_slug else title)
    if Article.query.filter_by(slug=slug).first():
        return error_response("VALIDATION_ERROR", "An article with that slug already exists.", 409)

    featured_user_id = data.get("featured_user_id")
    if featured_user_id is not None:
        if isinstance(featured_user_id, bool) or not isinstance(featured_user_id, int):
            return error_response("VALIDATION_ERROR", "featured_user_id must be an integer.", 400)
        if not db.session.get(User, featured_user_id):
            return error_response("NOT_FOUND", "Featured player not found.", 404)

    article = Article(
        title=title,
        slug=slug,
        category=category,
        summary=(data.get("summary") or "").strip() or None,
        body=body,
        cover_image_url=(data.get("cover_image_url") or "").strip() or None,
        affiliate_url=(data.get("affiliate_url") or "").strip() or None,
        featured_user_id=featured_user_id,
        is_published=bool(data.get("is_published", True)),
    )
    db.session.add(article)
    db.session.commit()
    return jsonify(article.to_dict()), 201


@editorial_blueprint.route("/articles/<int:article_id>", methods=["PATCH"])
@require_auth
@require_role("admin")
def update_article(article_id):
    """Admin-only endpoint to update or publish/unpublish an article."""
    article = db.session.get(Article, article_id)
    if not article:
        return error_response("NOT_FOUND", "Article not found.", 404)

    data = request.get_json(silent=True) or {}
    if "category" in data:
        cat = (data["category"] or "").strip().lower()
        if cat not in VALID_ARTICLE_CATEGORIES:
            return error_response(
                "VALIDATION_ERROR",
                f"category must be one of: {', '.join(sorted(VALID_ARTICLE_CATEGORIES))}.",
                400,
            )
        article.category = cat

    for field in ("title", "summary", "body", "cover_image_url", "affiliate_url"):
        if field in data:
            val = data[field]
            if field in ("title", "body") and (not isinstance(val, str) or not val.strip()):
                return error_response("VALIDATION_ERROR", f"{field} cannot be empty.", 400)
            setattr(article, field, val.strip() if isinstance(val, str) and val.strip() else None)

    if "is_published" in data:
        if not isinstance(data["is_published"], bool):
            return error_response("VALIDATION_ERROR", "is_published must be a boolean.", 400)
        article.is_published = data["is_published"]

    db.session.commit()
    return jsonify(article.to_dict()), 200


@editorial_blueprint.route("/sponsors", methods=["GET"])
def list_sponsor_banners():
    """Public endpoint returning active local DFW sponsor banners by slot placement."""
    placement = request.args.get("placement", "").strip().lower()
    query = SponsorBanner.query.filter_by(is_active=True)

    if placement:
        if placement not in VALID_BANNER_PLACEMENTS:
            return error_response(
                "VALIDATION_ERROR",
                f"placement must be one of: {', '.join(sorted(VALID_BANNER_PLACEMENTS))}.",
                400,
            )
        query = query.filter_by(placement=placement)

    banners = query.order_by(SponsorBanner.id.asc()).all()
    items = [b.to_dict() for b in banners]
    return jsonify({"items": items, "total": len(items)}), 200


@editorial_blueprint.route("/sponsors", methods=["POST"])
@require_auth
@require_role("admin")
def create_sponsor_banner():
    """Admin-only endpoint to add a paying DFW sponsor banner."""
    data = request.get_json(silent=True) or {}
    sponsor_name = (data.get("sponsor_name") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    target_url = (data.get("target_url") or "").strip()
    placement = (data.get("placement") or "top_banner").strip().lower()

    if not sponsor_name or not image_url or not target_url:
        return error_response(
            "VALIDATION_ERROR",
            "sponsor_name, image_url, and target_url are required.",
            400,
        )

    if placement not in VALID_BANNER_PLACEMENTS:
        return error_response(
            "VALIDATION_ERROR",
            f"placement must be one of: {', '.join(sorted(VALID_BANNER_PLACEMENTS))}.",
            400,
        )

    banner = SponsorBanner(
        sponsor_name=sponsor_name,
        tagline=(data.get("tagline") or "").strip() or None,
        image_url=image_url,
        target_url=target_url,
        placement=placement,
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(banner)
    db.session.commit()
    return jsonify(banner.to_dict()), 201


@editorial_blueprint.route("/sponsors/<int:banner_id>", methods=["PATCH"])
@require_auth
@require_role("admin")
def update_sponsor_banner(banner_id):
    """Admin-only endpoint to edit or pause/activate a sponsor banner."""
    banner = db.session.get(SponsorBanner, banner_id)
    if not banner:
        return error_response("NOT_FOUND", "Sponsor banner not found.", 404)

    data = request.get_json(silent=True) or {}
    if "placement" in data:
        pl = (data["placement"] or "").strip().lower()
        if pl not in VALID_BANNER_PLACEMENTS:
            return error_response(
                "VALIDATION_ERROR",
                f"placement must be one of: {', '.join(sorted(VALID_BANNER_PLACEMENTS))}.",
                400,
            )
        banner.placement = pl

    for field in ("sponsor_name", "tagline", "image_url", "target_url"):
        if field in data:
            val = data[field]
            setattr(banner, field, val.strip() if isinstance(val, str) and val.strip() else None)

    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return error_response("VALIDATION_ERROR", "is_active must be a boolean.", 400)
        banner.is_active = data["is_active"]

    db.session.commit()
    return jsonify(banner.to_dict()), 200



