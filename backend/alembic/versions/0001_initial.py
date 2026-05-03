"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-02 19:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- enums ---
    user_role = postgresql.ENUM(
        "admin", "contributor", "viewer", name="user_role", create_type=False
    )
    model_status = postgresql.ENUM(
        "draft", "needs_review", "ready", "hidden", "archived",
        name="model_status", create_type=False,
    )
    viewer_status = postgresql.ENUM(
        "pending", "glb_ready", "stl_direct", "conversion_failed",
        name="viewer_status", create_type=False,
    )
    preview_status = postgresql.ENUM(
        "pending", "ready", "generated", "source_image_used",
        "extracted_from_3mf", "placeholder", "failed",
        name="preview_status", create_type=False,
    )
    import_job_status = postgresql.ENUM(
        "queued", "uploading", "extracting", "scanning", "grouping",
        "classifying", "generating_previews", "packaging",
        "completed", "completed_with_warnings", "failed",
        name="import_job_status", create_type=False,
    )
    file_role = postgresql.ENUM(
        "print_file", "preview_image", "gallery_image", "video",
        "instruction", "license", "source", "nested_archive", "other",
        name="file_role", create_type=False,
    )
    file_type = postgresql.ENUM(
        "mesh", "cad", "project", "image", "video", "document", "archive", "other",
        name="file_type", create_type=False,
    )
    tag_type = postgresql.ENUM(
        "topic", "print", "technical", "source", "status",
        name="tag_type", create_type=False,
    )
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    model_status.create(bind, checkfirst=True)
    viewer_status.create(bind, checkfirst=True)
    preview_status.create(bind, checkfirst=True)
    import_job_status.create(bind, checkfirst=True)
    file_role.create(bind, checkfirst=True)
    file_type.create(bind, checkfirst=True)
    tag_type.create(bind, checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- invites ---
    op.create_table(
        "invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("email_hint", sa.String(320)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("used_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token", name="uq_invites_token"),
    )
    op.create_index("ix_invites_token", "invites", ["token"])

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("categories.id", ondelete="SET NULL")),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("path", sa.String(400), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"])
    op.create_index("ix_categories_path", "categories", ["path"])
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    # --- tags ---
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("type", tag_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"])

    # --- import_jobs ---
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", import_job_status, nullable=False),
        sa.Column("progress_pct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_type", sa.String(50)),
        sa.Column("source_name", sa.String(500)),
        sa.Column("package_storage_key", sa.String(500)),
        sa.Column("log_storage_key", sa.String(500)),
        sa.Column("models_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("files_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("warnings_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])

    # --- models ---
    op.create_table(
        "models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_title", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("category_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("categories.id", ondelete="SET NULL")),
        sa.Column("category_confidence", sa.Float),
        sa.Column("status", model_status, nullable=False),
        sa.Column("is_reviewed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_flexi", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_print_in_place", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_multipart", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_assembly", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_stl", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_step", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_3mf", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_images", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_video", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("preview_storage_key", sa.String(500)),
        sa.Column("thumbnail_storage_key", sa.String(500)),
        sa.Column("viewer_storage_key", sa.String(500)),
        sa.Column("package_storage_key", sa.String(500)),
        sa.Column("viewer_status", viewer_status, nullable=False),
        sa.Column("preview_status", preview_status, nullable=False),
        sa.Column("source_type", sa.String(50)),
        sa.Column("source_name", sa.String(500)),
        sa.Column("source_hash", sa.String(80)),
        sa.Column("stl_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("step_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("three_mf_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("image_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("video_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("document_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("import_jobs.id", ondelete="SET NULL")),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("slug", name="uq_models_slug"),
    )
    op.create_index("ix_models_slug", "models", ["slug"])
    op.create_index("ix_models_category_id", "models", ["category_id"])
    op.create_index("ix_models_import_job_id", "models", ["import_job_id"])
    op.create_index("ix_models_imported_at", "models", ["imported_at"])
    op.create_index("ix_models_imported_at_desc", "models", ["imported_at"])
    op.create_index("ix_models_category_status", "models", ["category_id", "status"])

    # --- files ---
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("original_file_name", sa.String(500)),
        sa.Column("extension", sa.String(20)),
        sa.Column("file_type", file_type, nullable=False),
        sa.Column("role", file_role, nullable=False),
        sa.Column("storage_key", sa.String(700), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(40), nullable=False, server_default="ready"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_files_model_id", "files", ["model_id"])
    op.create_index("ix_files_sha256", "files", ["sha256"])
    op.create_index("ix_files_model_role", "files", ["model_id", "role"])

    # --- model_tags ---
    op.create_table(
        "model_tags",
        sa.Column("model_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("models.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("model_tags")
    op.drop_index("ix_files_model_role", table_name="files")
    op.drop_index("ix_files_sha256", table_name="files")
    op.drop_index("ix_files_model_id", table_name="files")
    op.drop_table("files")
    op.drop_index("ix_models_category_status", table_name="models")
    op.drop_index("ix_models_imported_at_desc", table_name="models")
    op.drop_index("ix_models_imported_at", table_name="models")
    op.drop_index("ix_models_import_job_id", table_name="models")
    op.drop_index("ix_models_category_id", table_name="models")
    op.drop_index("ix_models_slug", table_name="models")
    op.drop_table("models")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_index("ix_tags_slug", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_index("ix_categories_path", table_name="categories")
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_table("categories")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_invites_token", table_name="invites")
    op.drop_table("invites")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    bind = op.get_bind()
    for enum_name in ("tag_type", "file_type", "file_role", "import_job_status",
                       "preview_status", "viewer_status", "model_status", "user_role"):
        bind.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name}"))
