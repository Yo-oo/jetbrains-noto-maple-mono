# JetBrains Noto Maple Mono

A monospace font that fuses:

- **[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono)** — base Latin letterforms and native code ligatures
- **[Noto Sans CJK](https://github.com/notofonts/noto-cjk)** — Chinese/Japanese/Korean glyphs, scaled to exactly twice the Latin advance width
- **[Maple Mono](https://github.com/subframe7536/maple-font)** — the plain-text tag ligature engine (`[INFO]`, `[WARN]`, `[ERROR]`, ...)
- **[Nerd Fonts](https://github.com/ryanoasis/nerd-fonts)** (optional, separate `NF` release variant) — terminal/editor icon glyphs, copied from Nerd Fonts' own pre-patched JetBrains Mono release

## Features

- 8 weights (Thin–ExtraBold), each with Regular and Italic
- Plain and `NF` (Nerd Font icons) variants, installable side by side
- TTF and WOFF2 formats
- Maple Mono tag ligatures (`[INFO]`, `[WARN]`, `[ERROR]`, ...) — see [OpenType Features](#opentype-features)

## OpenType Features

Most OpenType features are identical to JetBrains Mono — see [JetBrains Mono's wiki](https://github.com/JetBrains/JetBrainsMono/wiki/OpenType-features).

This project's only differences:

| Feature | Difference                                                                                                                                                                                                 |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `calt`  | In addition to JetBrains Mono's native ligatures, also includes Maple Mono-style plain-text tag ligatures (`[INFO]`, `[WARN]`, `[ERROR]`, ...) drawn as rounded badges, triggered only on exact uppercase. |
| `ss03`  | New feature, not present in JetBrains Mono. Same tag badges as above, but case-insensitive (`[info]`, `[Info]`, `[INFO]` all trigger) — must be enabled manually.                                          |

## Why this exists

Font fallback across separate Latin and CJK font files can't guarantee CJK glyphs land at exactly 2x the Latin advance width — each font defines its own metrics independently, so mixed Latin/CJK text drifts out of alignment column by column in a monospace layout. Baking both into a single font file lets the CJK glyphs be scaled and shifted to match the Latin grid exactly.

This project builds by layering official upstream releases rather than forking any upstream's build system: download JetBrains Mono + Noto Sans CJK releases, overlay CJK glyphs onto the JetBrains base (new codepoints only, no overwriting), graft Maple Mono's tag ligature rules on top (compiled fresh from source, not copied from a compiled binary), and optionally copy Nerd Font icon glyphs from Nerd Fonts' own pre-patched JetBrains Mono release. Each step only _adds_ glyphs/rules the base doesn't already have, so there's no feature-conflict cleanup to maintain — and tracking upstream updates is just re-running the pipeline against new release URLs.

## Building from source

### Locally

```bash
pip install .
python -m scripts.build --weights regular,bold --styles regular,italic --nerd-font
```

Output lands in `dist/fonts/` (both `.ttf` and `.woff2`). Run `python -m scripts.build --help` for the full list of flags (weights, styles, Nerd Font, Han-priority locale, and per-build overrides for every `config.json` value).

### Via GitHub Actions

Fork this repo and run the **Build** workflow (Actions tab → Build → Run workflow) — same flags as above, exposed as workflow inputs. The build artifact is downloadable from the workflow run once it finishes.

## Configuration

All tunable values live in `config.json`.

| Key                   | Meaning                                                                               |
| --------------------- | ------------------------------------------------------------------------------------- |
| `family_name`         | Font family name baked into the name table.                                           |
| `upstream_versions.*` | JetBrains Mono / Noto Sans CJK / Maple Mono / Nerd Fonts versions to build against.   |
| `cjk.fill_ratio`      | CJK glyph ink shrink-toward-center ratio (cosmetic).                                  |
| `cjk.italic_angle`    | Synthetic CJK italic shear angle, matched to JetBrains Mono's own.                    |
| `cjk.han_priority`    | Which locale (`tc`/`hk`/`sc`/`jp`/`kr`) provides Han + shared CJK punctuation glyphs. |
| `build_defaults.*`    | Default `--weights`/`--styles`/`--nerd-font` when not passed on the CLI.              |

## License

SIL Open Font License 1.1. See [OFL.txt](./OFL.txt) — JetBrains Mono, Maple Mono, Google (Noto Sans CJK), Adobe (Source Han Sans, Reserved Font Name `Source`), and Nerd Fonts are all credited there.
