"""Deploy the app to a Hugging Face Docker Space.

    uv run python scripts/deploy_hf_space.py <owner>/<space-name>                 # upload code
    uv run python scripts/deploy_hf_space.py <owner>/<space-name> --set-config    # + secrets/variables

Needs a Hugging Face token with write access: `uv run hf auth login`, or HF_TOKEN in the env.

Uploads the git-tracked files needed at runtime, as they are in the working tree, plus
deploy/hf-space/{Dockerfile,README.md,.dockerignore} at the Space root. The Space then
builds the image itself.

--set-config sets the Space secrets/variables:
  - OPENAI_API_KEY, GOOGLE_CLIENT_ID: read from .env
  - DATABASE_URL: from the NEON_DATABASE_URL environment variable (never the local DB)
  - SESSION_SECRET: a new random value for production
"""
import argparse
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
SPACE_FILES = ROOT / "deploy" / "hf-space"

# Top-level paths the running app needs; everything else (tests, docs, eval, compose...) stays out.
RUNTIME_PATHS = ("app/", "db/", "ingestion/", "update_docs/", "alembic/", "frontend/",
                 "alembic.ini", "config.py", "pyproject.toml", "uv.lock", ".python-version")
EXCLUDE = {"frontend/Dockerfile"}

VARIABLES = {
    "COOKIE_SECURE": "true",
    "PHOENIX_ENABLED": "false",
    "RERANKER_ENABLED": "true",
    "RERANK_CANDIDATE_K": "10",  # 2 shared vCPUs: keep reranking under a few seconds
    "DAILY_MESSAGE_LIMIT": "50",
}


def tracked_runtime_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines()
            if f.startswith(RUNTIME_PATHS) and f not in EXCLUDE and (ROOT / f).is_file()]


def warn_uncommitted(files: list[str]) -> None:
    out = subprocess.run(["git", "status", "--porcelain", "--", *files], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.strip()
    if out:
        print("Note: uploading these files with their uncommitted changes:\n" + out + "\n")


def stage(files: list[str], target: Path) -> None:
    for f in files:
        dest = target / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dest)
    for name in ("Dockerfile", "README.md", ".dockerignore"):
        shutil.copy2(SPACE_FILES / name, target / name)


def set_config(api: HfApi, repo_id: str) -> None:
    env = dotenv_values(ROOT / ".env")
    database_url = os.environ.get("NEON_DATABASE_URL")
    missing = [k for k in ("OPENAI_API_KEY", "GOOGLE_CLIENT_ID") if not env.get(k)]
    if not database_url:
        missing.append("NEON_DATABASE_URL (environment variable)")
    if missing:
        sys.exit(f"Missing: {', '.join(missing)}")

    secret_values = {
        "OPENAI_API_KEY": env["OPENAI_API_KEY"],
        "GOOGLE_CLIENT_ID": env["GOOGLE_CLIENT_ID"],
        "DATABASE_URL": database_url,
        "SESSION_SECRET": secrets.token_urlsafe(48),
    }
    for key, value in secret_values.items():
        api.add_space_secret(repo_id, key, value)
        print(f"secret   {key}")
    for key, value in VARIABLES.items():
        api.add_space_variable(repo_id, key, value)
        print(f"variable {key}={value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo_id", help="<owner>/<space-name>, e.g. congpho/learn-with-heart")
    parser.add_argument("--set-config", action="store_true", help="also set the Space secrets/variables")
    parser.add_argument("--private", action="store_true", help="create the Space as private")
    args = parser.parse_args()

    api = HfApi()
    api.create_repo(args.repo_id, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)

    files = tracked_runtime_files()
    warn_uncommitted(files)
    with tempfile.TemporaryDirectory() as tmp:
        stage(files, Path(tmp))
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="space",
            folder_path=tmp,
            delete_patterns="*",  # mirror: remove files that no longer exist locally
            commit_message="Deploy from local working tree",
        )
    print(f"Uploaded {len(files) + 3} files to https://huggingface.co/spaces/{args.repo_id}")

    if args.set_config:
        set_config(api, args.repo_id)

    owner, name = args.repo_id.split("/")
    print(f"\nBuild logs: https://huggingface.co/spaces/{args.repo_id}?logs=build")
    print(f"App URL:    https://{owner}-{name}.hf.space".replace("_", "-").lower())


if __name__ == "__main__":
    main()
