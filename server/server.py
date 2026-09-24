"""agy-creative MCP server.

Tools:
  - translate_to_emirati            : any text -> Arabic in Emirati (UAE) dialect
  - generate_image                  : text prompt -> PNG file
  - create_image_with_emirati_text  : poster/image with an Emirati Arabic caption

All work is delegated to the Antigravity CLI (`agy -p ...`), so no extra API keys are needed.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer

mcp = MCPServer("agy-creative")

AGY_BIN = os.environ.get("AGY_BIN") or shutil.which("agy") or str(Path.home() / ".local/bin/agy")
TEXT_MODEL = os.environ.get("AGY_TEXT_MODEL", "gemini-3.8-flash-medium")
IMAGE_MODEL = os.environ.get("AGY_IMAGE_MODEL")  # None -> agy default
TEXT_TIMEOUT = int(os.environ.get("AGY_TEXT_TIMEOUT", "120"))
IMAGE_TIMEOUT = int(os.environ.get("AGY_IMAGE_TIMEOUT", "300"))
FALLBACK_DIR = Path.home() / "Pictures" / "agy-images"

EMIRATI_PROMPT = """You are an expert translator from the UAE. Translate the text below into Arabic \
using the natural spoken Emirati (UAE Gulf) dialect, NOT Modern Standard Arabic.
Use genuine Emirati vocabulary and phrasing where natural (e.g. شحالك، شو، وايد، الحين، باجر، \
بنطرش، ما عليه، إن شاء الله، زين، يالله).
Rules:
- Keep personal names, numbers, prices, phone numbers, emails, URLs and brand names unchanged.
{terms_rule}
- Keep the original meaning, tone and line breaks.
- Output ONLY the translation. No quotes, no explanations, no transliteration.

Text:
<<<
{text}
>>>"""


class AgyError(RuntimeError):
    pass


async def run_agy(prompt: str, cwd: Path, timeout: int, model: str | None = None,
                  add_dir: Path | None = None) -> str:
    """Run `agy -p` headlessly and return the response text."""
    if not Path(AGY_BIN).exists():
        raise AgyError(f"agy CLI not found at {AGY_BIN}. Install Antigravity CLI or set AGY_BIN.")
    args = [AGY_BIN, "-p", prompt, "--output-format", "json", "--print-timeout", f"{timeout}s"]
    if model:
        args += ["--model", model]
    if add_dir:
        args += ["--add-dir", str(add_dir)]

    proc = await asyncio.create_subprocess_exec(
        *args, cwd=str(cwd),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout + 30)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise AgyError(f"agy timed out after {timeout}s")

    stdout = out.decode("utf-8", "replace").strip()
    try:
        data = json.loads(stdout.splitlines()[-1]) if stdout else {}
    except json.JSONDecodeError:
        data = {}
    if proc.returncode != 0 or data.get("status") not in (None, "SUCCESS"):
        detail = data.get("response") or err.decode("utf-8", "replace").strip() or stdout
        raise AgyError(f"agy failed (exit {proc.returncode}): {detail[:500]}")
    return (data.get("response") if data else stdout).strip()


def resolve_output_dir(output_dir: str | None) -> Path:
    """Pick where images go: argument > AGY_OUTPUT_DIR > <project>/generated-images > ~/Pictures/agy-images."""
    if output_dir:
        path = Path(output_dir).expanduser()
    elif os.environ.get("AGY_OUTPUT_DIR"):
        path = Path(os.environ["AGY_OUTPUT_DIR"]).expanduser()
    else:
        cwd = Path.cwd()
        # Claude Desktop launches servers with cwd "/" (or the home dir) - not a project.
        if cwd in (Path("/"), Path.home()) or not os.access(cwd, os.W_OK):
            path = FALLBACK_DIR
        else:
            path = cwd / "generated-images"
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_filename(hint: str, filename: str | None) -> str:
    if filename:
        name = Path(filename).name
        return name if name.lower().endswith(".png") else f"{Path(name).stem}.png"
    slug = re.sub(r"[^a-z0-9]+", "-", hint.lower()).strip("-")[:40] or "image"
    return f"{datetime.now():%Y%m%d-%H%M%S}-{slug}.png"


def preview(path: Path) -> Image:
    """Return a downscaled JPEG preview so large PNGs don't bloat the conversation."""
    tmp = Path(tempfile.gettempdir()) / f"agy-preview-{path.stem}.jpg"
    if shutil.which("sips"):
        r = subprocess.run(
            ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70", "-Z", "768",
             str(path), "--out", str(tmp)],
            capture_output=True,
        )
        if r.returncode == 0 and tmp.exists():
            data = tmp.read_bytes()
            tmp.unlink(missing_ok=True)
            return Image(data=data, format="jpeg")
    return Image(path=str(path))


async def _translate(text: str, keep_english_terms: bool) -> str:
    terms_rule = ("- Keep common English business/technical terms in English when Emiratis "
                  "normally say them in English." if keep_english_terms
                  else "- Translate everything into Arabic except names and numbers.")
    prompt = EMIRATI_PROMPT.format(text=text, terms_rule=terms_rule)
    result = await run_agy(prompt, cwd=Path(tempfile.gettempdir()), timeout=TEXT_TIMEOUT,
                           model=TEXT_MODEL)
    return result.strip().strip('"').strip("<>").strip()


async def _generate(prompt: str, output_dir: str | None, filename: str | None,
                    aspect_ratio: str) -> Path:
    out_dir = resolve_output_dir(output_dir)
    target = out_dir / make_filename(prompt, filename)
    instruction = (
        f"Generate an image with aspect ratio {aspect_ratio} based on this description:\n"
        f"{prompt}\n\n"
        f"Save the image as a PNG file at exactly this path: {target}\n"
        "Do not create any other files. Reply only with the saved file path."
    )
    await run_agy(instruction, cwd=out_dir, timeout=IMAGE_TIMEOUT, model=IMAGE_MODEL,
                  add_dir=out_dir)
    if not target.exists() or target.stat().st_size == 0:
        raise AgyError(f"agy finished but no image was saved at {target}")
    return target


@mcp.tool()
async def translate_to_emirati(text: str, keep_english_terms: bool = True) -> str:
    """Translate any text (English or other language) into Arabic in the Emirati (UAE) dialect.

    Args:
        text: The text to translate.
        keep_english_terms: Keep common English business/tech words as Emiratis would say them.
    """
    if not text.strip():
        return "Error: text is empty."
    try:
        return await _translate(text, keep_english_terms)
    except AgyError as e:
        return f"Error: {e}"


@mcp.tool()
async def generate_image(prompt: str, output_dir: str | None = None,
                         filename: str | None = None, aspect_ratio: str = "1:1"):
    """Create an image from a text description and save it as a PNG.

    Images are saved to `output_dir` if given, otherwise to `generated-images/` in the current
    project (or ~/Pictures/agy-images when there is no project).

    Args:
        prompt: Description of the image to create.
        output_dir: Optional folder to save into.
        filename: Optional file name (".png" is added if missing).
        aspect_ratio: e.g. "1:1", "16:9", "9:16", "4:5".
    """
    try:
        path = await _generate(prompt, output_dir, filename, aspect_ratio)
    except AgyError as e:
        return f"Error: {e}"
    return [f"Image saved to: {path}", preview(path)]


@mcp.tool()
async def create_image_with_emirati_text(image_description: str, caption_text: str,
                                         output_dir: str | None = None,
                                         filename: str | None = None,
                                         aspect_ratio: str = "1:1"):
    """Create an image/poster whose caption is written in Emirati Arabic.

    The caption is first translated to Emirati dialect, then rendered on the image.

    Args:
        image_description: What the image should show (scene, style, colours, layout).
        caption_text: Caption in any language; it will be translated to Emirati Arabic.
        output_dir: Optional folder to save into.
        filename: Optional file name.
        aspect_ratio: e.g. "1:1", "16:9", "9:16", "4:5".
    """
    try:
        arabic = await _translate(caption_text, keep_english_terms=False)
        prompt = (
            f"{image_description}\n\n"
            f"The image must clearly display this exact Arabic text, written right-to-left with "
            f"correctly connected Arabic letters, in a clean bold Arabic font, large and legible:\n"
            f"«{arabic}»\n"
            "Do not add any other text."
        )
        path = await _generate(prompt, output_dir, filename or make_filename(caption_text, None),
                               aspect_ratio)
    except AgyError as e:
        return f"Error: {e}"
    return [
        f"Image saved to: {path}\nEmirati caption used: {arabic}\n"
        "(If any Arabic letters look wrong in the image, the correct text is above.)",
        preview(path),
    ]


if __name__ == "__main__":
    mcp.run()
