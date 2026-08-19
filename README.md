# JetBrains Noto Maple Mono

A monospace font that fuses:

- **[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono)** — base Latin letterforms and native code ligatures
- **[Noto Sans CJK](https://github.com/notofonts/noto-cjk)** — Chinese/Japanese/Korean glyphs, scaled to exactly twice the Latin advance width
- **[Maple Mono](https://github.com/subframe7536/maple-font)** — the plain-text tag ligature engine (`[INFO]`, `[WARN]`, `[ERROR]`, ...)
- **[Nerd Fonts](https://github.com/ryanoasis/nerd-fonts)** (optional) — terminal/editor icon glyphs via the Nerd Font Patcher

## Why this exists

Font fallback across separate Latin and CJK font files can't guarantee CJK glyphs land at exactly 2x the Latin advance width — each font defines its own metrics independently, so mixed Latin/CJK text drifts out of alignment column by column in a monospace layout. Baking both into a single font file lets the CJK glyphs be scaled and shifted to match the Latin grid exactly.

This project builds by layering official upstream releases rather than forking any upstream's build system: download JetBrains Mono + Noto Sans CJK releases, overlay CJK glyphs onto the JetBrains base (new codepoints only, no overwriting), graft Maple Mono's tag ligature rules on top (compiled fresh from source, not copied from a compiled binary), and optionally run the Nerd Font Patcher. Each step only *adds* glyphs/rules the base doesn't already have, so there's no feature-conflict cleanup to maintain — and tracking upstream updates is just re-running the pipeline against new release URLs.

## License

SIL Open Font License 1.1. See [OFL.txt](./OFL.txt) — JetBrains Mono, Maple Mono, Google (Noto Sans CJK), Adobe (Source Han Sans, Reserved Font Name `Source`), and Nerd Fonts are all credited there.
