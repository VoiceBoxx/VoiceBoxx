# ChatGPT Export Converter: enterprise deployment kit

This folder turns the ChatGPT Export Converter release zip into a package an IT department can
deploy. It adds an MSI, a silent script installer, an admin guide, a security review, checksums,
detection and AppLocker scripts, and the program icon in every format the tools ask for.

The program binaries are **not** stored here. The build takes them from the original release zip.

| Path | What it is |
|---|---|
| `package/` | Files laid over the release. `@VERSION@`-style placeholders are filled in at build time |
| `package/Deploy/ADMIN-GUIDE.md` | Deployment guide (MSI, Install.cmd, Intune, ConfigMgr, GPO, AppLocker/WDAC, privacy) |
| `package/Deploy/SECURITY-REVIEW.md` | Review findings and open items for the next program release |
| `build/product.wxs` | MSI definition (wixl / WiX 3 syntax) |
| `build/build_package.py` | Build script |

## Build

Needs Linux or WSL with `msitools` and `wixl` (`apt install msitools wixl`), Python 3.10+, and
`pip install cairosvg`.

```bash
python3 build/build_package.py --source-zip ChatGPTExportConverter-1.2.2.zip --out dist
```

Output: `dist/ChatGPTExportConverter-<ver>.zip`, `dist/ChatGPTExportConverter-<ver>-x64.msi`
and their `.sha256` files.

## Releasing a new version

1. Update `package/VERSION.txt` (first line) and add a section to `package/CHANGELOG.txt`.
2. Add a new ProductCode GUID for the version to `PRODUCT_CODES` in `build/build_package.py`.
   **Never change the UpgradeCode.**
3. Build, test in a pilot ring, then publish the zip, the MSI and the `.sha256` files.
