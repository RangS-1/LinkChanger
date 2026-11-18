import argparse
import ipaddress
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Pattern, Tuple
from urllib.parse import urlsplit

EXTENSIONS = {".html", ".htm", ".xml", ".txt"}
SKIP_DIRS = {".git", "node_modules", ".vercel"}
URL_PATTERN = re.compile(r"https?://[^\s\"'<>/?#]+(?:[/?#][^\s\"'<>]*)?", re.IGNORECASE)

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif",
    ".webp", ".gif", ".avif", ".heic", ".heif", ".svg",
}
BACKUP_DIR = "original-img"


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


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


def _collect_images(folder: Path, recursive: bool) -> List[Path]:
    images = []
    if recursive:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                if any(part in SKIP_DIRS or part == BACKUP_DIR for part in path.parts):
                    continue
                images.append(path)
    else:
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(path)
    return images


def _convert_to_jpeg(src: Path, dst: Path, quality: int) -> bool:
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-q:v", str(quality),
        str(dst),
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
        print(f"  [ERROR] ffmpeg failed: {stderr_text}", file=sys.stderr)
        return False
    return True


def cmd_tojpeg(args: argparse.Namespace) -> None:
    if shutil.which("ffmpeg") is None:
        print("[ERROR] ffmpeg is not installed or not in PATH.", file=sys.stderr)
        print("Install ffmpeg first: https://ffmpeg.org/download.html", file=sys.stderr)
        sys.exit(1)

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"[ERROR] '{folder}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    recursive = args.all_dir
    dry_run = args.dry_run
    quality = args.quality
    images = _collect_images(folder, recursive)

    if not images:
        print("No image files found.")
        return

    backup_dir = folder / BACKUP_DIR

    total_original = 0
    total_new = 0
    converted = 0
    skipped = 0

    print(f"{'[DRY RUN] ' if dry_run else ''}Converting images to JPEG (quality: {quality})...\n")

    for img in images:
        original_size = img.stat().st_size
        new_name = img.stem + ".jpeg"
        new_path = img.parent / new_name

        is_already_jpeg = img.suffix.lower() in {".jpg", ".jpeg"}
        action = "RECOMPRESS" if is_already_jpeg else "CONVERT"

        if dry_run:
            status = "WILL BE CONVERTED" if not is_already_jpeg else "WILL BE RECOMPRESSED"
            print(f"  [{status}] {img}")
            print(f"           Size: {_format_size(original_size)}")
            if not is_already_jpeg:
                print(f"           Output: {new_path}")
            converted += 1
            total_original += original_size
            continue

        # Create backup directory
        backup_dir.mkdir(exist_ok=True)

        # For recompression: convert to temp, backup original, replace
        if is_already_jpeg:
            temp_path = img.parent / (img.stem + ".tmp.jpeg")
            success = _convert_to_jpeg(img, temp_path, quality)
            if not success:
                print(f"  [SKIPPED] {img} (ffmpeg error)")
                if temp_path.exists():
                    temp_path.unlink()
                skipped += 1
                continue

            new_size = temp_path.stat().st_size

            # Only replace if the new file is smaller
            if new_size >= original_size:
                print(f"  [SKIPPED] {img} (recompressed file is not smaller)")
                temp_path.unlink()
                skipped += 1
                continue

            # Backup original
            backup_path = backup_dir / img.name
            _safe_move(img, backup_path)

            # Rename temp to final
            temp_path.rename(new_path)

        else:
            # Convert non-JPEG to JPEG
            success = _convert_to_jpeg(img, new_path, quality)
            if not success:
                print(f"  [SKIPPED] {img} (ffmpeg error)")
                if new_path.exists():
                    new_path.unlink()
                skipped += 1
                continue

            new_size = new_path.stat().st_size

            # Backup original
            backup_path = backup_dir / img.name
            _safe_move(img, backup_path)

        total_original += original_size
        total_new += new_size
        converted += 1

        saved = original_size - new_size
        saved_pct = (saved / original_size * 100) if original_size > 0 else 0
        print(f"  [{action}] {img.name}")
        print(f"           {_format_size(original_size)} -> {_format_size(new_size)} (saved {_format_size(saved)}, {saved_pct:.1f}%)")

    # Summary
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Done!")
    print(f"  Files processed: {converted}")
    if skipped > 0:
        print(f"  Files skipped: {skipped}")

    if not dry_run and converted > 0:
        total_saved = total_original - total_new
        total_pct = (total_saved / total_original * 100) if total_original > 0 else 0
        print(f"  Total original: {_format_size(total_original)}")
        print(f"  Total new:      {_format_size(total_new)}")
        print(f"  Total saved:    {_format_size(total_saved)} ({total_pct:.1f}%)")
        print(f"  Originals backed up to: {backup_dir}/")

    if dry_run:
        print("\nNo files were changed (dry run). Remove --dry-run to apply.")


def _safe_move(src: Path, dst: Path) -> None:
    if dst.exists():
        base = dst.stem
        ext = dst.suffix
        counter = 1
        while dst.exists():
            dst = dst.parent / f"{base}_{counter}{ext}"
            counter += 1
    shutil.move(str(src), str(dst))


def cmd_domain(args: argparse.Namespace) -> None:
    root = Path(args.folder)
    transform = None

    if args.old_domain is not None:
        try:
            old = clear_domain(args.old_domain)
            new = clear_domain(args.new_domain)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            sys.exit(1)

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


def _build_tojpeg_parser(subparsers=None):
    if subparsers is not None:
        p = subparsers.add_parser(
            "tojpeg",
            help="Convert and compress images to JPEG using ffmpeg.",
            description="Convert all images in a folder to optimized JPEG files using ffmpeg.",
        )
    else:
        p = argparse.ArgumentParser(
            prog="linkchanger tojpeg",
            description="Convert all images in a folder to optimized JPEG files using ffmpeg.",
        )
    p.add_argument(
        "folder",
        help="target folder containing images (use '.' for current directory)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="show which files would be converted without actually converting",
    )
    p.add_argument(
        "--all-dir",
        action="store_true",
        help="scan subfolders recursively",
    )
    p.add_argument(
        "--quality",
        type=int,
        default=2,
        metavar="Q",
        help="JPEG quality for ffmpeg -q:v (1-31, lower=better, default: 2)",
    )
    return p


def _build_domain_parser():
    p = argparse.ArgumentParser(
        description="This is LinkChanger for your migration to a new domain.",
    )
    p.add_argument("old_domain", nargs="?", help="example: yourname.vercel.app")
    p.add_argument("new_domain", nargs="?", help="example: yourname.com")
    p.add_argument("--folder", default=".", help="folder website (default: this folder)")
    p.add_argument("--scan", action="store_true", help="scan the selected folder after processing")
    p.add_argument("--dry-run", action="store_true", help="show what will be changed without writing to files")
    return p


SUBCOMMANDS = {"tojpeg", "domain"}


def main():
    # Detect whether the first positional arg is a known subcommand.
    # If not, fall back to the original (domain) CLI for backward compatibility.
    argv = sys.argv[1:]

    # Find the first non-flag argument
    first_positional = None
    for arg in argv:
        if not arg.startswith("-"):
            first_positional = arg
            break

    if first_positional == "tojpeg":
        # Strip "tojpeg" from argv and parse with tojpeg parser
        tojpeg_argv = argv[argv.index("tojpeg") + 1:]
        parser = _build_tojpeg_parser()
        args = parser.parse_args(tojpeg_argv)
        cmd_tojpeg(args)

    elif first_positional == "domain":
        # Strip "domain" from argv and parse with domain parser
        domain_argv = argv[argv.index("domain") + 1:]
        parser = _build_domain_parser()
        args = parser.parse_args(domain_argv)

        if (args.old_domain is None) != (args.new_domain is None):
            parser.error("old_domain and new_domain must be provided together")
        if args.old_domain is None and not args.scan:
            parser.error("old_domain and new_domain are required unless --scan is used")

        cmd_domain(args)

    else:
        # Backward compatibility: treat as the original domain-change CLI
        parser = _build_domain_parser()
        args = parser.parse_args(argv)

        if (args.old_domain is None) != (args.new_domain is None):
            parser.error("old_domain and new_domain must be provided together")
        if args.old_domain is None and not args.scan:
            parser.error("old_domain and new_domain are required unless --scan is used")

        cmd_domain(args)


if __name__ == "__main__":
    main()
