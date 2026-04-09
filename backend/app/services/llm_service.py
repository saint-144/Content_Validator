"""
LLM Service
Uses NVIDIA NIM for:
1. Analyze and summarize approved template content (training)
2. Compare destination content against trained summaries (validation)

Other providers (Anthropic, OpenAI, Gemini) kept for reference but NIM is primary.
"""

import asyncio
import base64
import json
import logging
import re
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional, Dict, Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# NIM: 32k token window, keep prompts under 24k to leave room for response
MAX_TEMPLATE_FILES_IN_PROMPT = 30


def _encode_image(file_path: str) -> tuple[str, str]:
    """Read image and return base64 + media type."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_map.get(suffix, "image/jpeg")
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8"), media_type


async def analyze_content_for_training(file_path: str, file_type: str, file_name: str) -> Dict[str, Any]:
    """
    Stage 1 - Training:
    Ask the LLM to describe and summarize an approved content file.
    For videos, the file_path should be a pre-extracted key frame (thumbnail).
    """
    type_label = "video frame" if file_type == "video" else "marketing image"

    prompt = f"""Analyze this approved {type_label} carefully. 
Provide a rich, technical, and semantic description so we can identify this content even if it's slightly modified later.

Provide a detailed structured analysis in valid JSON format with these exact fields:

{{
  "summary": "2-3 sentence deep description. Include the focal point, visual style, and core message. Avoid generic phrases.",
  "visual_elements": ["List specific objects, products, people, mascots, and composition details"],
  "color_palette": ["Identify the dominant hex colors and the overall lighting/mood"],
  "detected_text": "Extract ALL text visible, including small disclaimers or call-to-actions",
  "brand_elements": ["Identify logos, brand colors, specific fonts, or trademarked assets"],
  "content_type": "advertisement, social_post, banner, product, or lifestyle",
  "mood_tone": "The emotional feel: energetic, luxury, professional, nostalgic, etc.",
  "compliance_flags": ["Elements that might be regulated: financial claims, age-restricted items, etc."],
  "key_identifiers": ["Unique markers that would distinguish this from other similar brand files"]
}}

Reference filename: {file_name}
Return ONLY the JSON object. Do not include conversational text or headers."""

    return await _call_llm_vision(file_path, prompt)


async def compare_content(
    destination_path: str,
    destination_type: str,
    template_files: list,
    template_name: str,
    pixel_threshold: float = 95.0,
    semantic_threshold: float = 72.0
) -> Dict[str, Any]:
    """
    Stage 2 - Validation:
    Compare destination content against trained template summaries.
    template_files should already be pre-filtered to top 30 by phash before calling this.
    Returns per-file comparison results.
    """
    if not template_files:
        return {
            "matches": [],
            "overall_verdict": "need_review",
            "mcc_compliant": None,
            "post_description": "No template files to compare against"
        }

    if len(template_files) > MAX_TEMPLATE_FILES_IN_PROMPT:
        logger.warning(
            "compare_content received %d files but prompt is capped at %d. "
            "Ensure phash pre-filter is applied before calling this function.",
            len(template_files), MAX_TEMPLATE_FILES_IN_PROMPT
        )
        template_files = template_files[:MAX_TEMPLATE_FILES_IN_PROMPT]

    training_context = "\n\n".join([
        f"FILE {i+1}: {tf['file_name']}\n"
        f"Summary: {tf.get('llm_summary', 'N/A')[:300]}\n"
        f"Visual Elements: {json.dumps(tf.get('visual_elements', []))[:200]}\n"
        f"Detected Text: {tf.get('detected_text', 'N/A')[:150]}\n"
        f"Brand Elements: {json.dumps(tf.get('brand_elements', []))[:150]}"
        for i, tf in enumerate(template_files)
    ])

    prompt = f"""You are a content compliance expert. Analyze the provided destination image/content and compare it against the trained approved content from template "{template_name}".

TRAINED APPROVED CONTENT ({len(template_files)} files, pre-filtered by visual similarity):
{training_context}

TASK: For each trained file, determine similarity and compliance.

Return a JSON object with this exact structure:
{{
  "destination_description": "describe what you see in the destination content in 2-3 sentences",
  "detected_text_in_destination": "all text visible in destination",
  "post_timestamp_hint": "if any date/time visible in content, extract it, else null",
  "platform_hint": "if platform watermark/UI visible (Instagram, Facebook, etc), else null",
  "mcc_compliant": true or false (false if content contains explicit/adult/violent content OR if it fails to be a valid variation of the training materials provided),
  "mcc_issues": ["list any compliance issues found, including if it doesn't match the brand kit"],
  "overall_verdict": "appropriate" (matches approved content), "escalate" (violations or unapproved content), "need_review" (minor differences),
  "verdict_reasoning": "brief explanation of overall verdict",
  "file_matches": [
    {{
      "file_name": "exact file name from training data",
      "llm_similarity_score": 0-100 (how semantically similar is the destination to this file),
      "is_suspected_match": true/false (true if >65% similar),
      "match_reasoning": "brief explanation of similarity or differences",
      "matched_elements": ["list of elements that match between destination and this file"],
      "visual_differences": "key visual differences if any"
    }}
  ]
}}

Return ONLY valid JSON, no other text."""

    image_path_for_llm = destination_path if destination_path and Path(destination_path).exists() else None
    result = await _call_llm_vision(image_path_for_llm, prompt)

    if "error" in result and "_raw" in result:
        logger.error(
            "LLM returned malformed JSON for template '%s'. Raw response: %s",
            template_name, str(result.get("_raw", ""))[:500]
        )
        raise ValueError(f"LLM returned malformed JSON response: {result.get('error')}")

    return result


async def _call_llm_vision(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call configured LLM provider with vision capability."""
    if settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
        return await _call_anthropic(image_path, prompt)
    elif settings.LLM_PROVIDER == "gemini" and settings.GOOGLE_API_KEY:
        return await _call_gemini(image_path, prompt)
    elif settings.LLM_PROVIDER == "nvidia" and settings.NVIDIA_API_KEY:
        logger.info("Calling NVIDIA NIM with model: %s", settings.NVIDIA_MODEL)
        from app.services.image_service import optimize_image_for_llm, cleanup_temp_file
        optimized_path = None
        if image_path:
            optimized_path = optimize_image_for_llm(image_path)
        try:
            result = await _call_nvidia(optimized_path or image_path, prompt)
            return result
        finally:
            if optimized_path and optimized_path != image_path:
                cleanup_temp_file(optimized_path)
    else:
        logger.warning("No LLM provider configured - returning mock analysis")
        return _mock_analysis(image_path)


async def _call_anthropic(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call Anthropic Claude."""
    content = []
    if image_path and Path(image_path).exists():
        img_b64, media_type = _encode_image(image_path)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_b64}
        })
    content.append({"type": "text", "text": prompt})

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": content}]
            }
        )
        response.raise_for_status()
        data = response.json()
        text = data["content"][0]["text"]
        return _parse_json_response(text)


async def _call_openai(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call OpenAI GPT-4V."""
    messages_content = []
    if image_path and Path(image_path).exists():
        img_b64, media_type = _encode_image(image_path)
        messages_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{img_b64}"}
        })
    messages_content.append({"type": "text", "text": prompt})

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": messages_content}]
            }
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_json_response(text)


async def _call_nvidia(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call Nvidia NIM (OpenAI compatible) with exponential backoff retries."""
    messages_content = []
    if image_path and Path(image_path).exists():
        img_b64, media_type = _encode_image(image_path)
        messages_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{img_b64}"}
        })
    messages_content.append({"type": "text", "text": prompt})

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{settings.NVIDIA_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.NVIDIA_MODEL,
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": messages_content}],
                        "temperature": 0.2,
                        "top_p": 0.7
                    }
                )

                if not response.is_success:
                    error_detail = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_json.get("message", response.text))
                    except Exception:
                        pass

                    logger.error("NVIDIA NIM API Error (Status %d): %s", response.status_code, error_detail)
                    if response.status_code == 429:
                        wait_time = (2 ** attempt) + 2
                        logger.warning("NIM Rate limit (429). Retrying in %ds...", wait_time)
                        await asyncio.sleep(wait_time)
                        continue

                    raise ValueError(f"NVIDIA NIM {response.status_code}: {error_detail}")

                data = response.json()
                text = data["choices"][0]["message"]["content"]
                logger.info("NVIDIA NIM Success (Status: %d)", response.status_code)
                return _parse_json_response(text)

        except httpx.ConnectError as ce:
            logger.error("NVIDIA NIM Connection Error: %s", ce)
            raise ValueError(f"Could not connect to NVIDIA NIM: {ce}")
        except httpx.TimeoutException:
            logger.error("NVIDIA NIM Timeout (attempt %d/%d)", attempt + 1, max_retries)
            if attempt == max_retries - 1:
                raise ValueError(f"NVIDIA NIM timed out after all {max_retries} attempts")
            wait_time = (2 ** attempt) + 10
            logger.warning("Timeout — retrying in %ds...", wait_time)
            await asyncio.sleep(wait_time)
            continue
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("NVIDIA NIM final failure: %s", e)
                raise
            wait_time = (2 ** attempt) + 2
            logger.warning("NIM Attempt %d failed: %s. Retrying in %ds...", attempt + 1, e, wait_time)
            await asyncio.sleep(wait_time)

    raise RuntimeError("NVIDIA NIM max retries reached")


async def _call_gemini(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call Google Gemini — wrapped in executor to avoid blocking event loop."""
    try:
        import google.generativeai as genai
        from PIL import Image

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        content = [prompt]
        if image_path and Path(image_path).exists():
            img = Image.open(image_path)
            content.append(img)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: model.generate_content(content))
        return _parse_json_response(response.text)
    except Exception as e:
        logger.error("Gemini call failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# URL download helpers
# ---------------------------------------------------------------------------

async def analyze_from_url(url: str) -> tuple[str, str]:
    """
    Download content from a social media or direct URL.
    Returns (temp_file_path, file_type) where file_type is 'image' or 'video'.

    Routing logic:
    - Direct image URL (.jpg/.png/etc)  → direct download
    - Instagram reel                    → yt-dlp → og:image fallback
    - Instagram post (image)            → instaloader → og:image fallback
    - X/Twitter                         → og:image (skip yt-dlp, too slow/blocked)
    - Facebook, YouTube, other video    → yt-dlp → og:image fallback
    - Unknown                           → og:image → direct download fallback
    """
    DIRECT_IMAGE_PATTERNS = [
        r'\.(jpg|jpeg|png|gif|webp|bmp)(\?.*)?$',
    ]
    INSTAGRAM_REEL_PATTERNS = [
        r'instagram\.com/reel',
        r'instagram\.com/reels',
    ]
    INSTAGRAM_POST_PATTERNS = [
        r'instagram\.com/p/',
    ]
    TWITTER_PATTERNS = [
        r'x\.com/.*/status/',
        r'twitter\.com/.*/status/',
    ]
    VIDEO_PLATFORM_PATTERNS = [
        r'facebook\.com/',
        r'fb\.watch/',
        r'youtube\.com/watch',
        r'youtu\.be/',
        r'youtube\.com/shorts/',
    ]

    is_direct_image = any(re.search(p, url, re.IGNORECASE) for p in DIRECT_IMAGE_PATTERNS)
    is_instagram_reel = any(re.search(p, url, re.IGNORECASE) for p in INSTAGRAM_REEL_PATTERNS)
    is_instagram_post = any(re.search(p, url, re.IGNORECASE) for p in INSTAGRAM_POST_PATTERNS)
    is_twitter = any(re.search(p, url, re.IGNORECASE) for p in TWITTER_PATTERNS)
    is_video_platform = any(re.search(p, url, re.IGNORECASE) for p in VIDEO_PLATFORM_PATTERNS)

    # Direct image — straight download
    if is_direct_image:
        logger.info("URL identified as direct image: %s", url)
        return await _download_direct_image(url)

    # Instagram reel — yt-dlp, fall back to og:image
    if is_instagram_reel:
        logger.info("URL identified as Instagram reel: %s", url)
        try:
            result = await _download_via_ytdlp(url)
            if result:
                return result
        except Exception as e:
            logger.warning("yt-dlp failed for Instagram reel %s: %s — trying og:image", url, e)
        return await _extract_og_image(url)

    # Instagram post — instaloader first, og:image fallback
    if is_instagram_post:
        logger.info("URL identified as Instagram post: %s", url)
        try:
            result = await _download_instagram_image(url)
            if result:
                return result
        except Exception as e:
            logger.warning("instaloader failed for %s: %s — trying og:image", url, e)
        try:
            return await _extract_og_image(url)
        except Exception as e:
            logger.warning("og:image also failed for Instagram post: %s", e)
            raise ValueError(
                f"Could not extract image from Instagram post — Instagram is blocking all access: {url}"
            )

    # X/Twitter — skip yt-dlp entirely, go straight to og:image
    if is_twitter:
        logger.info("URL identified as X/Twitter: %s", url)
        return await _extract_og_image(url)

    # Other video platforms — yt-dlp, fall back to og:image
    if is_video_platform:
        logger.info("URL identified as video platform: %s", url)
        try:
            result = await _download_via_ytdlp(url)
            if result:
                return result
        except Exception as e:
            logger.warning("yt-dlp failed for %s: %s — trying og:image", url, e)
        return await _extract_og_image(url)

    # Unknown URL — og:image first, direct download fallback
    logger.info("URL type unknown, attempting og:image extraction: %s", url)
    try:
        return await _extract_og_image(url)
    except Exception as e:
        logger.warning("og:image extraction failed: %s — trying direct download", e)
        return await _download_direct_image(url)


async def _download_direct_image(url: str) -> tuple[str, str]:
    """Download a direct image URL to a temp file."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        suffix = ".jpg"
        if "png" in content_type: suffix = ".png"
        elif "gif" in content_type: suffix = ".gif"
        elif "webp" in content_type: suffix = ".webp"

        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(resp.content)
        tmp.close()
        logger.info("Downloaded direct image from %s -> %s", url, tmp.name)
        return tmp.name, "image"


async def _extract_og_image(url: str) -> tuple[str, str]:
    """
    Fetch a social media page and extract og:image meta tag.
    Works for public Facebook posts, X/Twitter posts.
    Instagram blocks this — use instaloader instead.
    """
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")

    og_image = None
    for attrs in [
        {"property": "og:image"},
        {"name": "twitter:image"},
        {"property": "twitter:image"},
        {"name": "og:image"},
    ]:
        tag = soup.find("meta", attrs)
        if tag and tag.get("content"):
            og_image = tag["content"]
            break

    if not og_image:
        raise ValueError(f"No og:image meta tag found for URL: {url}")

    logger.info("Extracted og:image from %s -> %s", url, og_image[:120])

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        img_resp = await client.get(og_image, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        img_resp.raise_for_status()

    content_type = img_resp.headers.get("content-type", "image/jpeg")
    suffix = ".jpg"
    if "png" in content_type: suffix = ".png"
    elif "webp" in content_type: suffix = ".webp"

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(img_resp.content)
    tmp.close()
    logger.info("Downloaded og:image to temp file: %s", tmp.name)
    return tmp.name, "image"


async def _download_via_ytdlp(url: str) -> tuple[str, str] | None:
    """
    Download video using yt-dlp.
    Returns (temp_file_path, file_type) or raises on failure.
    """
    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize", "100m",
        "-f", "best[ext=mp4]/mp4/best",
        "-o", output_template,
        "--quiet",
        url
    ]

    logger.info("Running yt-dlp for: %s", url)
    loop = asyncio.get_event_loop()

    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        )
    except subprocess.TimeoutExpired:
        raise ValueError("yt-dlp timed out after 60s")

    if result.returncode != 0:
        raise ValueError(f"yt-dlp exited {result.returncode}: {result.stderr[:300]}")

    files = [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)]
    if not files:
        raise ValueError("yt-dlp ran successfully but no output file found")

    image_files = [f for f in files if Path(f).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']]
    video_files = [f for f in files if Path(f).suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv', '.webm']]

    if image_files:
        logger.info("yt-dlp downloaded image: %s", image_files[0])
        return image_files[0], "image"
    elif video_files:
        logger.info("yt-dlp downloaded video: %s", video_files[0])
        return video_files[0], "video"
    else:
        raise ValueError(f"yt-dlp downloaded unknown file type: {files[0]}")


async def _download_instagram_image(url: str) -> tuple[str, str] | None:
    """
    Download an Instagram post image using instaloader.
    Works anonymously for public posts.
    Returns (temp_file_path, 'image') or raises on failure.
    """
    import instaloader

    match = re.search(r'/p/([A-Za-z0-9_-]+)', url)
    if not match:
        raise ValueError(f"Could not extract Instagram shortcode from URL: {url}")

    shortcode = match.group(1)
    logger.info("Attempting instaloader download for shortcode: %s", shortcode)

    tmp_dir = tempfile.mkdtemp()
    loop = asyncio.get_event_loop()

    def _do_download():
        L = instaloader.Instaloader(
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
            dirname_pattern=tmp_dir,
            filename_pattern="{shortcode}"
        )
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=tmp_dir)

    try:
        await loop.run_in_executor(None, _do_download)
    except Exception as e:
        raise ValueError(f"instaloader failed for {shortcode}: {e}")

    image_files = [
        os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir)
        if Path(f).suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']
    ]

    if not image_files:
        raise ValueError(f"instaloader ran but no image found in {tmp_dir}")

    logger.info("instaloader downloaded image: %s", image_files[0])
    return image_files[0], "image"


# ---------------------------------------------------------------------------
# JSON parsing + mock
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response.
    Handles clean JSON, markdown-wrapped JSON, and truncated JSON (token limit hit).
    """
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    # Try clean parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object via regex
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    # Try fixing truncated JSON — hits max_tokens and cuts off mid-response
    try:
        fixed = text
        if fixed.count('"') % 2 != 0:
            fixed += '"'
        open_brackets = fixed.count('[') - fixed.count(']')
        open_braces = fixed.count('{') - fixed.count('}')
        fixed += ']' * max(0, open_brackets)
        fixed += '}' * max(0, open_braces)
        parsed = json.loads(fixed)
        logger.warning("Recovered truncated JSON response — some fields may be incomplete")
        return parsed
    except Exception:
        pass

    logger.error("Failed to parse LLM JSON response. Raw text: %s", text[:500])
    return {"summary": text, "error": "Could not parse structured response", "_raw": text}


def _mock_analysis(image_path: Optional[str], error: str = "") -> Dict[str, Any]:
    """Return mock analysis when no LLM is configured (dev/demo mode)."""
    import random
    score = random.uniform(45, 95)
    return {
        "summary": f"Mock analysis - configure LLM provider for real analysis. {error}",
        "visual_elements": ["logo", "product image", "text overlay", "brand colors"],
        "color_palette": ["#2563EB", "#FFFFFF", "#1F2937"],
        "detected_text": "Sample Brand Text | Campaign 2024",
        "brand_elements": ["company logo", "tagline"],
        "content_type": "advertisement",
        "mood_tone": "professional",
        "compliance_flags": [],
        "key_identifiers": ["logo placement", "color scheme"],
        "destination_description": "Mock destination content description for demo purposes.",
        "detected_text_in_destination": "Demo text content",
        "post_timestamp_hint": None,
        "platform_hint": None,
        "mcc_compliant": True,
        "mcc_issues": [],
        "overall_verdict": "appropriate" if score > 75 else ("escalate" if score < 55 else "need_review"),
        "verdict_reasoning": "Mock verdict - LLM not configured",
        "file_matches": []
    }