import argparse
import ipaddress
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Pattern, Tuple
from urllib.parse import urlsplit

EXTENSIONS = {".html", ".htm", ".xml", ".txt"}
SKIP_DIRS = {".git", "node_modules", ".vercel"}
URL_PATTERN = re.compile(r"https?://[^\s\"'<>/?#]+(?:[/?#][^\s\"'<>]*)?", re.IGNORECASE)


def clear_domain(domain: str) -> str:
    domain = domain.strip()
    domain = re.sub(r"^https?://", "", domain, flags=re.I)
    domain = domain.rstrip("/")
    domain = re.sub(r"^www\.", "", domain, flags=re.I)

    try:
        parsed = urlsplit(f"//{domain}")
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid domain: {domain!r}") from error

    if (
        not domain
        or hostname is None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or any(character in domain for character in "?#")
        or parsed.username is not None
        or parsed.password is not None
        or any(character.isspace() for character in domain)
        or domain.endswith(":")
        or (port is not None and not 1 <= port <= 65535)
        or not _is_valid_hostname(hostname)
    ):
        raise ValueError(f"invalid domain: {domain!r}")

    return domain


def _is_valid_hostname(hostname: str) -> bool:
    if ":" in hostname:
        try:
            ipaddress.IPv6Address(hostname)
        except ValueError:
            return False
        return True

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    labels = ascii_hostname.rstrip(".").split(".")
    return len(ascii_hostname) <= 254 and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
        and len(label) <= 63
        for label in labels
    )


class MetadataCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical = 0
        self.robots = 0
        self.open_graph = 0
        self.twitter = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        if tag == "link" and "canonical" in (attributes.get("rel") or "").lower().split():
            self.canonical += 1
        if tag != "meta":
            return

        name = (attributes.get("name") or "").lower()
        property_name = (attributes.get("property") or "").lower()
        self.robots += name == "robots"
        self.open_graph += property_name.startswith("og:")
        self.twitter += name.startswith("twitter:") or property_name.startswith("twitter:")


def scan_folder(
    root: Path,
    transform: Optional[Tuple[Pattern[str], str]] = None,
) -> Tuple[int, int, int, int, int]:
    canonical_count = 0
    open_graph_count = 0
    twitter_count = 0
    robots_count = 0
    URL_founded = 0
    for path in root.rglob("*"):
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

        if transform is not None:
            content = transform[0].sub(transform[1], content)

        counter = MetadataCounter()
        counter.feed(content)
        counter.close()
        canonical_count += counter.canonical
        open_graph_count += counter.open_graph
        twitter_count += counter.twitter
        robots_count += counter.robots
        URL_founded += len(URL_PATTERN.findall(content))

    return canonical_count, open_graph_count, URL_founded, twitter_count, robots_count


def main():
    parser = argparse.ArgumentParser(description="This is LinkChanger for your migration to a new domain.")
    parser.add_argument("old_domain", nargs="?", help="example: yourname.vercel.app")
    parser.add_argument("new_domain", nargs="?", help="example: yourname.com")
    parser.add_argument("--folder", default=".", help="folder website (default: this folder)")
    parser.add_argument("--scan", action="store_true", help="scan the selected folder after processing")
    parser.add_argument("--dry-run", action="store_true", help="show what will be changed without writing to files")
    args = parser.parse_args()

    if (args.old_domain is None) != (args.new_domain is None):
        parser.error("old_domain and new_domain must be provided together")
    if args.old_domain is None and not args.scan:
        parser.error("old_domain and new_domain are required unless --scan is used")

    root = Path(args.folder)
    transform = None
    if args.old_domain is not None:
        try:
            old = clear_domain(args.old_domain)
            new = clear_domain(args.new_domain)
        except ValueError as error:
            parser.error(str(error))

        pola = re.compile(
            r"https?://(?:www\.)?" + re.escape(old) + r"(?![\w.-])",
            re.IGNORECASE,
        )
        changer = f"https://{new}"
        transform = (pola, changer)

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

    if args.scan:
        scan_transform = transform if args.dry_run else None
        canonical_founded, open_graph_founded, URL_founded, twitter_founded, robots_founded = scan_folder(
            root, scan_transform
        )
        print(f"\nScan results:")
        print(f"Canonical tags found: {canonical_founded}")
        print(f"Robots tags found: {robots_founded}")
        print(f"Open Graph tags found: {open_graph_founded}")
        print(f"Total URLs found: {URL_founded}")
        print(f"Twitter tags found: {twitter_founded}")

if __name__ == "__main__":
    main()