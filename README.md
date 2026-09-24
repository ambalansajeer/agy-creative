# agy-creative

A Claude Code plugin that adds an MCP server for:

- **Image generation**: create PNG images from a text description
- **Emirati Arabic translation**: translate any text into natural UAE (Emirati) dialect, not formal MSA
- **Posters with Emirati captions**: translate a caption and render it on an image in one step

The work is done by the [Antigravity CLI](https://antigravity.google) (`agy`), so no extra API keys are needed.

## Requirements

1. **Claude Code**
2. **uv**, which supplies Python automatically
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
3. **Antigravity CLI (`agy`)**, installed and logged in with your Google account. Check it with `agy models`.

## Install

In Claude Code:

```
/plugin marketplace add ambalansajeer/agy-creative
/plugin install agy-creative@agy-creative
```

Then restart Claude Code and run `/mcp` to confirm `agy-creative` is connected.

## Tools

| Tool | What it does |
|---|---|
| `translate_to_emirati(text, keep_english_terms=True)` | Translates text into Emirati dialect Arabic |
| `generate_image(prompt, output_dir?, filename?, aspect_ratio="1:1")` | Creates a PNG image |
| `create_image_with_emirati_text(image_description, caption_text, output_dir?, filename?, aspect_ratio="1:1")` | Translates the caption to Emirati, then creates an image showing that Arabic text |

### Example prompts

- *"Translate 'We will send the housemaid tomorrow morning' to Emirati Arabic"*
- *"Create a 16:9 image of the Dubai skyline at sunset"*
- *"Make an Instagram poster for a cleaning company with the caption 'Your home, our care'"*

## Where images are saved

1. The `output_dir` argument, if given
2. The `AGY_OUTPUT_DIR` environment variable
3. `generated-images/` in the current project folder
4. `~/Pictures/agy-images/` when there is no project

## Optional settings (environment variables)

| Variable | Default |
|---|---|
| `AGY_TEXT_MODEL` | `gemini-3.8-flash-medium` |
| `AGY_IMAGE_MODEL` | agy default |
| `AGY_TEXT_TIMEOUT` | `120` seconds |
| `AGY_IMAGE_TIMEOUT` | `300` seconds |
| `AGY_BIN` | `agy` on your PATH |

## Notes

- Everything runs on your own computer and uses **your own** `agy` login and quota.
- Image models sometimes misdraw Arabic letters. The poster tool always returns the correct Arabic caption as text too.
- Translations take about 10 seconds and images about 30–60 seconds.

## License

MIT
