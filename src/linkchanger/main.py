import argparse
import re
from pathlib import Path

EXTENSIONS = {".html", ".htm", ".xml", ".txt"}
SKIP_DIRS = {".git", "node_modules", ".vercel"}


def clear_domain(domain: str) -> str:
    domain = domain.strip().rstrip("/")
    domain = re.sub(r"^https?://", "", domain, flags=re.I)
    domain = re.sub(r"^www\.", "", domain, flags=re.I)
    return domain


def main():
    parser = argparse.ArgumentParser(description="This is LinkChanger for your migration to a new domain.")
    parser.add_argument("old_domain", help="example: yourname.vercel.app")
    parser.add_argument("new_domain", help="example: yourname.com")
    parser.add_argument("--folder", default=".", help="folder website (default: this folder)")
    parser.add_argument("--dry-run", action="store_true", help="show what will be changed without writing to files")
    args = parser.parse_args()

    old = clear_domain(args.old_domain)
    new = clear_domain(args.new_domain)

    pola = re.compile(r"https?://(?:www\.)?" + re.escape(old), re.IGNORECASE)
    changer = f"https://{new}"

    root = Path(args.folder)
    total_file = 0
    total_changed = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        try:
            with open(path, encoding="utf-8", newline="") as f:
                content = f.read()
        except UnicodeDecodeError:
            print(f"[SKIPPED] {path} (NOT UTF-8)")
            continue

        add_new, amount = pola.subn(changer, content)
        if amount == 0:
            continue

        total_file += 1
        total_changed += amount
        status = "WILL BE CHANGED" if args.dry_run else "CHANGED"
        print(f"[{status}] {path}  ({amount} URL)")

        if not args.dry_run:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(add_new)

    print(f"\nDone: {total_changed} URL in {total_file} file.")
    if args.dry_run:
        print("Changes not written to files (dry run). Remove --dry-run to apply changes.")


if __name__ == "__main__":
    main()