# LinkChanger

LinkChanger is a Python CLI tool for domain migration and image compression. It can replace old domain URLs with new ones across your website files, and convert/compress images to optimized JPEG using ffmpeg.

## Downloads

The tool is available on the Arch User Repository (AUR) as `linkchanger`. You can install it using an AUR helper like `yay`:

```bash
yay -S linkchanger
# or
paru -S linkchanger
```

### Build from source

Make sure you have Python 3 and `pip` installed, then run:

```bash
git clone https://github.com/RangS-1/LinkChanger.git
cd LinkChanger
pip install .
```

For development (editable install):

```bash
pip install -e .
```

After installing, the `linkchanger` command will be available in your terminal.

## Usage

### Domain migration

Replace all URLs from an old domain to a new domain in your website files:

```bash
linkchanger <old-domain> <new-domain> [options]
```

For example, preview the changes without writing to files:

```bash
linkchanger yourname.vercel.app yourname.com --folder ./website --dry-run
```

Add `--scan` to count canonical links, robots meta tags, Open Graph meta tags, Twitter card meta tags, and absolute URLs in the selected folder:

```bash
linkchanger yourname.vercel.app yourname.com --folder ./website --scan --dry-run
```

To scan without changing URLs, omit both domains:

```bash
linkchanger --folder ./website --scan
```

If the results look correct, run it again without `--dry-run` to apply the changes:

```bash
linkchanger yourname.vercel.app yourname.com --folder ./website
```

#### Arguments and options

| Argument/option | Description |
| --- | --- |
| `old-domain` | The domain to search for, such as `yourname.vercel.app`. |
| `new-domain` | The replacement domain, such as `yourname.com`. |
| `--folder` | The folder to search. Defaults to the current working directory (`.`). |
| `--scan` | Scan the selected folder and report canonical links, robots/Open Graph/Twitter meta tags, and absolute URLs. Can be used without domain arguments. |
| `--dry-run` | Show which files and how many URLs would change without writing changes to files. |

Domains may include an `http://` or `https://` prefix, a `www.` prefix, and a trailing slash; these are removed before searching. Matching URLs are rewritten to use `https://` and the new domain.

Domains must be host names (optionally with a port); empty values, paths, query strings, and fragments are rejected. URL matching checks the host boundary, so a domain such as `yourname.com` does not match `yourname.com.evil`.

### Image compression (`tojpeg`)

Convert and compress all images in a folder to optimized JPEG files using ffmpeg. Works similarly to TinyJPG — file size is reduced while keeping quality nearly identical.

**Requirements:** [ffmpeg](https://ffmpeg.org/download.html) must be installed and available in your PATH.

```bash
linkchanger tojpeg <folder> [options]
```

Preview which files will be converted (dry run):

```bash
linkchanger tojpeg . --dry-run
```

Convert all images in the current folder:

```bash
linkchanger tojpeg .
```

Convert images recursively including subfolders:

```bash
linkchanger tojpeg . --all-dir
```

Set a custom quality level:

```bash
linkchanger tojpeg . --quality 5
```

#### Arguments and options

| Argument/option | Description |
| --- | --- |
| `folder` | Target folder containing images. Use `.` for the current directory. |
| `--dry-run` | Show which files would be converted without actually converting. |
| `--all-dir` | Scan subfolders recursively. |
| `--quality Q` | JPEG quality for ffmpeg `-q:v` (1–31, lower = better quality). Default: `2` (≈95% quality). |

#### How it works

1. Scans the folder for image files (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.webp`, `.gif`, `.tiff`, `.tif`, `.avif`, `.heic`, `.heif`, `.svg`).
2. Converts each image to an optimized `.jpeg` file using ffmpeg.
3. Files that are already `.jpg`/`.jpeg` are recompressed — but only if the result is smaller. If not, the file is skipped.
4. Original files are moved to an `original-img/` subfolder as backup.
5. The output file is named `<original-name>.jpeg`.

#### Example output

```
Converting images to JPEG (quality: 2)...

  [CONVERT] Azriel-The_Last_Candle.png
           1.8 MB -> 797.3 KB (saved 1000.5 KB, 55.7%)
  [RECOMPRESS] OMORI.jpeg
           4.9 MB -> 3.4 MB (saved 1.5 MB, 30.5%)

Done!
  Files processed: 8
  Total original: 20.6 MB
  Total new:      13.6 MB
  Total saved:    7.0 MB (33.8%)
  Originals backed up to: testimg/original-img/
```

## Files processed

For domain migration, LinkChanger recursively searches files with the `.html`, `.htm`, `.xml`, and `.txt` extensions (extension matching is case-insensitive). Directories named `.git`, `node_modules`, and `.vercel` are skipped. Files that cannot be read as UTF-8 are also skipped and reported.

When finished, the tool prints the number of URLs replaced and the number of files changed. A file is written only if at least one URL matches; run with `--dry-run` first to review the scope of the changes.

When `--scan` is used with `--dry-run`, scan counts reflect the simulated replacements without writing to files.
