# LinkChanger

LinkChanger is a simple Python script that replaces URLs using an old domain with URLs using a new domain. It can be useful when migrating a website from a temporary hosting domain to your own domain.

## Downloads

The script is available for download on arch user repository (AUR) as `linkchanger`. You can install it using an AUR helper like `yay`:

```bash
yay -S linkchanger
# or
paru -S linkchanger
```

## Usage

Run the script from the project directory:

```bash
python src/linkchanger/main.py <old-domain> <new-domain> [options]
```

For example, preview the changes without writing to files:

```bash
python src/linkchanger/main.py yourname.vercel.app yourname.com --folder ./website --dry-run
```

Add `--scan` to count canonical links, robots meta tags, Open Graph meta tags, Twitter card meta tags, and absolute URLs in the selected folder:

```bash
python src/linkchanger/main.py yourname.vercel.app yourname.com --folder ./website --scan --dry-run
```

To scan without changing URLs, omit both domains:

```bash
python src/linkchanger/main.py --folder ./website --scan
```

If the results look correct, run it again without `--dry-run` to apply the changes:

```bash
python src/linkchanger/main.py yourname.vercel.app yourname.com --folder ./website
```

### Arguments and options

| Argument/option | Description |
| --- | --- |
| `old-domain` | The domain to search for, such as `yourname.vercel.app`. |
| `new-domain` | The replacement domain, such as `yourname.com`. |
| `--folder` | The folder to search. Defaults to the current working directory (`.`). |
| `--scan` | Scan the selected folder and report canonical links, robots/Open Graph/Twitter meta tags, and absolute URLs. Can be used without domain arguments. |
| `--dry-run` | Show which files and how many URLs would change without writing changes to files. |

Domains may include an `http://` or `https://` prefix, a `www.` prefix, and a trailing slash; these are removed before searching. Matching URLs are rewritten to use `https://` and the new domain.

Domains must be host names (optionally with a port); empty values, paths, query strings, and fragments are rejected. URL matching checks the host boundary, so a domain such as `yourname.com` does not match `yourname.com.evil`.

## Files processed

The script recursively searches files with the `.html`, `.htm`, `.xml`, and `.txt` extensions (extension matching is case-insensitive). Directories named `.git`, `node_modules`, and `.vercel` are skipped. Files that cannot be read as UTF-8 are also skipped and reported.

When finished, the script prints the number of URLs replaced and the number of files changed. A file is written only if at least one URL matches; run with `--dry-run` first to review the scope of the changes.

When `--scan` is used with `--dry-run`, scan counts reflect the simulated replacements without writing to files.