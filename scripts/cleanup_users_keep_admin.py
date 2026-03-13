#!/usr/bin/env python3
"""
Cleanup users in the current database, preserving only specified admin emails.

Default behavior:
- Dry-run only (no changes)
- Keep only admin@eliza.com
- Disable access for all other users (safe mode)

Optional hard delete:
- Pass --hard-delete to attempt physical deletion after dependency checks.
"""

import argparse
import os
import secrets
import sys
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.orm import sessionmaker


DEFAULT_KEEP_EMAIL = "admin@eliza.com"


@dataclass
class UserRow:
    id: int
    email: str
    username: str
    customer_id: str
    is_active: bool
    is_superuser: bool


def get_database_url() -> str | None:
    """Resolve DB URL from environment first, then app settings."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.core.config import get_settings

        settings = get_settings()
        return settings.database_url
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Disable/delete all users except one or more admin emails."
    )
    parser.add_argument(
        "--keep-email",
        action="append",
        default=[DEFAULT_KEEP_EMAIL],
        help="Email to preserve. Repeat for multiple users. Default: admin@eliza.com",
    )
    parser.add_argument(
        "--hard-delete",
        action="store_true",
        help="Attempt physical deletion after dependency checks. Default is safe disable mode.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. If omitted, runs dry-run only.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt in apply mode.",
    )
    return parser.parse_args()


def _fetch_target_users(db, keep_emails: list[str]) -> list[UserRow]:
    keep_lower = [email.strip().lower() for email in keep_emails if email.strip()]
    stmt = text(
        """
        SELECT id, email, username, customer_id, is_active, is_superuser
        FROM users
        WHERE lower(email) NOT IN :keep_emails
        ORDER BY id
        """
    ).bindparams(bindparam("keep_emails", expanding=True))

    rows = db.execute(stmt, {"keep_emails": keep_lower}).mappings().all()
    return [
        UserRow(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            customer_id=row["customer_id"],
            is_active=row["is_active"],
            is_superuser=row["is_superuser"],
        )
        for row in rows
    ]


def _count_rows_for_users(db, table_name: str, user_column: str, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    stmt = text(
        f'SELECT COUNT(*) FROM "{table_name}" WHERE "{user_column}" IN :user_ids'
    ).bindparams(bindparam("user_ids", expanding=True))
    return int(db.execute(stmt, {"user_ids": user_ids}).scalar() or 0)


def _print_summary(target_users: list[UserRow], keep_emails: list[str]) -> None:
    print("=" * 72)
    print("User Cleanup Preview")
    print("=" * 72)
    print(f"Keep emails: {', '.join(sorted(set(keep_emails)))}")
    print(f"Users targeted: {len(target_users)}")
    print()
    if not target_users:
        print("No users to clean up. Database already matches target state.")
        print("=" * 72)
        return

    for user in target_users:
        print(
            f"- id={user.id:<4} email={user.email:<35} "
            f"active={str(user.is_active):<5} superuser={str(user.is_superuser):<5} "
            f"tenant={user.customer_id}"
        )
    print("=" * 72)


def _discover_fk_references(db) -> list[tuple[str, str, str]]:
    """
    Returns list of (schema, table, column) for all FK columns pointing to users.id.
    Postgres-specific query.
    """
    query = text(
        """
        SELECT
            tc.table_schema,
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'users'
          AND ccu.column_name = 'id'
          AND tc.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY tc.table_schema, tc.table_name, kcu.column_name
        """
    )
    rows = db.execute(query).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def _count_fk_refs(
    db, references: Iterable[tuple[str, str, str]], user_ids: list[int]
) -> list[tuple[str, str, str, int]]:
    results: list[tuple[str, str, str, int]] = []
    for schema, table_name, column_name in references:
        stmt = text(
            f'SELECT COUNT(*) FROM "{schema}"."{table_name}" WHERE "{column_name}" IN :user_ids'
        ).bindparams(bindparam("user_ids", expanding=True))
        count = int(db.execute(stmt, {"user_ids": user_ids}).scalar() or 0)
        if count > 0:
            results.append((schema, table_name, column_name, count))
    return results


def _apply_disable_mode(db, user_ids: list[int]) -> None:
    import bcrypt

    disabled_password = bcrypt.hashpw(
        secrets.token_urlsafe(48).encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # Revoke auth/access vectors first.
    delete_commands = [
        ('DELETE FROM "platform_admins" WHERE "user_id" IN :user_ids', "platform_admins"),
        ('DELETE FROM "user_sessions" WHERE "user_id" IN :user_ids', "user_sessions"),
        ('DELETE FROM "password_history" WHERE "user_id" IN :user_ids', "password_history"),
        ('DELETE FROM "user_mfa" WHERE "user_id" IN :user_ids', "user_mfa"),
        ('DELETE FROM "user_sso_identities" WHERE "user_id" IN :user_ids', "user_sso_identities"),
        ('DELETE FROM "user_tenant_memberships" WHERE "user_id" IN :user_ids', "user_tenant_memberships"),
        ('DELETE FROM "user_roles" WHERE "user_id" IN :user_ids', "user_roles"),
        (
            'DELETE FROM "temporary_role_assignments" '
            'WHERE "user_id" IN :user_ids OR "granted_by" IN :user_ids OR "revoked_by" IN :user_ids',
            "temporary_role_assignments",
        ),
    ]
    for sql, _ in delete_commands:
        db.execute(text(sql).bindparams(bindparam("user_ids", expanding=True)), {"user_ids": user_ids})

    # Break nullable FK links to cleaned users so they retain no control paths.
    nullify_commands = [
        ('UPDATE "user_roles" SET "assigned_by" = NULL WHERE "assigned_by" IN :user_ids', "user_roles.assigned_by"),
        ('UPDATE "role_permissions" SET "granted_by" = NULL WHERE "granted_by" IN :user_ids', "role_permissions.granted_by"),
        ('UPDATE "roles" SET "created_by" = NULL WHERE "created_by" IN :user_ids', "roles.created_by"),
        ('UPDATE "permissions" SET "created_by" = NULL WHERE "created_by" IN :user_ids', "permissions.created_by"),
        ('UPDATE "platform_admins" SET "created_by" = NULL WHERE "created_by" IN :user_ids', "platform_admins.created_by"),
    ]
    for sql, _ in nullify_commands:
        db.execute(text(sql).bindparams(bindparam("user_ids", expanding=True)), {"user_ids": user_ids})

    # Finally disable the user records themselves.
    db.execute(
        text(
            """
            UPDATE users
            SET
                is_active = false,
                is_superuser = false,
                hashed_password = :disabled_password,
                api_key_hash = NULL,
                api_key_created_at = NULL,
                mfa_enabled = false,
                mfa_secret = NULL,
                failed_login_attempts = 0,
                locked_until = NULL,
                last_failed_login = NULL,
                force_password_change = true,
                updated_at = NOW()
            WHERE id IN :user_ids
            """
        ).bindparams(bindparam("user_ids", expanding=True)),
        {"user_ids": user_ids, "disabled_password": disabled_password},
    )


def _apply_hard_delete(db, user_ids: list[int]) -> None:
    references = _discover_fk_references(db)
    ref_counts = _count_fk_refs(db, references, user_ids)

    # Tables this script explicitly cleans before deleting users.
    handled_tables = {
        "platform_admins",
        "user_sessions",
        "password_history",
        "user_mfa",
        "user_sso_identities",
        "user_tenant_memberships",
        "user_roles",
        "temporary_role_assignments",
        "user_audit_log",  # user_id nullable and can remain; not a blocker
    }

    blockers = [r for r in ref_counts if r[1] not in handled_tables]
    if blockers:
        print("❌ Hard delete blocked by existing FK references in non-auth tables:")
        for schema, table_name, column_name, count in blockers:
            print(f"  - {schema}.{table_name}.{column_name}: {count} rows")
        print()
        print("Use safe mode (without --hard-delete) to revoke all access without data loss.")
        raise RuntimeError("Hard delete aborted due to foreign key dependencies.")

    # Safe to remove auth-linked rows then users.
    _apply_disable_mode(db, user_ids)
    db.execute(
        text('DELETE FROM "users" WHERE "id" IN :user_ids').bindparams(
            bindparam("user_ids", expanding=True)
        ),
        {"user_ids": user_ids},
    )


def main() -> None:
    args = parse_args()
    keep_emails = sorted(set([e.strip().lower() for e in args.keep_email if e.strip()]))

    if not keep_emails:
        print("❌ At least one --keep-email is required.")
        sys.exit(1)

    database_url = get_database_url()
    if not database_url:
        print("❌ DATABASE_URL not found in environment or settings.")
        sys.exit(1)

    print("Connecting to database...")
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        target_users = _fetch_target_users(db, keep_emails)
        _print_summary(target_users, keep_emails)

        if not target_users:
            return

        target_ids = [u.id for u in target_users]
        print("Related records (for visibility):")
        print(f"  user_roles: {_count_rows_for_users(db, 'user_roles', 'user_id', target_ids)}")
        print(f"  user_sessions: {_count_rows_for_users(db, 'user_sessions', 'user_id', target_ids)}")
        print(f"  platform_admins: {_count_rows_for_users(db, 'platform_admins', 'user_id', target_ids)}")
        print(f"  user_tenant_memberships: {_count_rows_for_users(db, 'user_tenant_memberships', 'user_id', target_ids)}")
        print(f"  password_history: {_count_rows_for_users(db, 'password_history', 'user_id', target_ids)}")
        print(f"  user_mfa: {_count_rows_for_users(db, 'user_mfa', 'user_id', target_ids)}")
        print(f"  user_sso_identities: {_count_rows_for_users(db, 'user_sso_identities', 'user_id', target_ids)}")
        print()

        mode = "HARD DELETE" if args.hard_delete else "SAFE DISABLE"
        print(f"Mode: {mode}")
        if not args.apply:
            print("Dry-run only. Re-run with --apply to execute.")
            return

        if not args.yes:
            confirmation = input("Proceed with cleanup? Type 'yes' to continue: ").strip().lower()
            if confirmation != "yes":
                print("Cancelled.")
                return

        if args.hard_delete:
            _apply_hard_delete(db, target_ids)
        else:
            _apply_disable_mode(db, target_ids)

        db.commit()
        print("✅ Cleanup completed successfully.")

    except Exception as exc:
        db.rollback()
        print(f"❌ Cleanup failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
