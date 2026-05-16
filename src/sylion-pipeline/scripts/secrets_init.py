"""Phase 3 W2.2 (scope-fill) — bootstrap a SOPS-encrypted secrets file.

Usage::

    # 1. Generate an operator identity (do this *once*, store the
    #    private key in a password manager or hardware key).
    python -m scripts.secrets_init keygen

    # 2. Initialise a fresh secrets/dev.yaml from the current env-vars.
    SYLION_AGE_IDENTITY="AGE-SECRET-KEY-..." python -m scripts.secrets_init init \\
        --env dev --recipient age1abc... \\
        --keys OPENAI_API_KEY ANTHROPIC_API_KEY DATABASE_URL

    # 3. Inspect (without decrypting):
    python -m scripts.secrets_init list --env dev

    # 4. Add a new operator (re-wraps data key, leaves leaves alone):
    SYLION_AGE_IDENTITY=... python -m scripts.secrets_init grant \\
        --env dev --recipient age1xyz...

The script is intentionally bare-bones; this is a *bootstrap* helper, not
a long-lived secret-management UI. Real ops workflows should drive the
:class:`SopsAgeProvider` programmatically.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _provider():
    from sylion.security.sops_provider import SopsAgeProvider
    return SopsAgeProvider()


def _path_for(env: str, secrets_dir: str | None) -> Path:
    base = Path(secrets_dir) if secrets_dir else Path(os.environ.get(
        "SYLION_SECRETS_DIR",
        Path(__file__).resolve().parent.parent / "secrets",
    ))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{env}.yaml"


def cmd_keygen(_args) -> int:
    from sylion.security.sops_provider import generate_age_identity

    identity, recipient = generate_age_identity()
    print("# Save the private key somewhere safe — e.g. password manager.")
    print(f"SYLION_AGE_IDENTITY=\"{identity}\"")
    print()
    print("# Recipient (public, safe to commit):")
    print(f"# {recipient}")
    return 0


def cmd_init(args) -> int:
    path = _path_for(args.env, args.secrets_dir)
    if path.exists() and not args.force:
        print(f"refusing to overwrite {path} (pass --force to clobber)")
        return 2

    secrets: dict[str, str] = {}
    for name in args.keys or []:
        value = os.environ.get(name, "").strip()
        if not value:
            print(f"warning: env-var {name} is empty/unset — skipping",
                  file=sys.stderr)
            continue
        secrets[name] = value

    if not secrets:
        print("no secrets to write — provide --keys with at least one "
              "non-empty env var", file=sys.stderr)
        return 3

    _provider().encrypt_file(path, secrets, recipients=list(args.recipient))
    print(f"wrote {path} with {len(secrets)} secrets / "
          f"{len(args.recipient)} recipients")
    return 0


def cmd_list(args) -> int:
    path = _path_for(args.env, args.secrets_dir)
    if not path.exists():
        print(f"{path} does not exist", file=sys.stderr)
        return 1
    p = _provider()
    print(f"file:        {path}")
    print(f"recipients:  {p.list_recipients(path)}")
    print(f"secrets:     {p.list_secrets(path)}")
    return 0


def cmd_grant(args) -> int:
    path = _path_for(args.env, args.secrets_dir)
    _provider().add_recipient(path, args.recipient)
    print(f"added recipient {args.recipient} to {path}")
    return 0


def cmd_add(args) -> int:
    path = _path_for(args.env, args.secrets_dir)
    p = _provider()
    if not p.has_identity():
        print("error: SYLION_AGE_IDENTITY[_FILE] required to add a secret",
              file=sys.stderr)
        return 1
    value = os.environ.get(args.from_env, "").strip()
    if not value:
        print(f"env-var {args.from_env} is empty/unset", file=sys.stderr)
        return 2
    p.add_secret(path, args.name, value)
    print(f"added {args.name} from env-var {args.from_env}")
    return 0


def cmd_remove(args) -> int:
    path = _path_for(args.env, args.secrets_dir)
    ok = _provider().remove_secret(path, args.name)
    print(f"{'removed' if ok else 'not found'}: {args.name}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="secrets_init",
                                     description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen").set_defaults(func=cmd_keygen)

    p_init = sub.add_parser("init")
    p_init.add_argument("--env", default="dev")
    p_init.add_argument("--secrets-dir", default=None)
    p_init.add_argument("--recipient", action="append", required=True,
                        help="age1... recipient (repeatable)")
    p_init.add_argument("--keys", nargs="+", required=True,
                        help="env-var names to seed from")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list")
    p_list.add_argument("--env", default="dev")
    p_list.add_argument("--secrets-dir", default=None)
    p_list.set_defaults(func=cmd_list)

    p_grant = sub.add_parser("grant")
    p_grant.add_argument("--env", default="dev")
    p_grant.add_argument("--secrets-dir", default=None)
    p_grant.add_argument("--recipient", required=True)
    p_grant.set_defaults(func=cmd_grant)

    p_add = sub.add_parser("add")
    p_add.add_argument("--env", default="dev")
    p_add.add_argument("--secrets-dir", default=None)
    p_add.add_argument("--name", required=True,
                       help="logical key name to store under")
    p_add.add_argument("--from-env", required=True,
                       help="env-var to read the plaintext from")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("remove")
    p_rm.add_argument("--env", default="dev")
    p_rm.add_argument("--secrets-dir", default=None)
    p_rm.add_argument("--name", required=True)
    p_rm.set_defaults(func=cmd_remove)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
