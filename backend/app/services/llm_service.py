"""
LLM Service
Uses Anthropic Claude or OpenAI GPT-4V to:
1. Analyze and summarize approved template content (training)
2. Compare destination content against trained summaries (validation)
"""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any

import httpx
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


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
    Stage 1 – Training:
    Ask the LLM to describe and summarize an approved content file.
    For videos, the file_path should be a pre-extracted key frame (thumbnail).
    """
    # Unified high-quality description prompt for both images and video frames
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
    template_files: list,  # List of dicts with {id, file_name, llm_summary, visual_elements, detected_text, phash}
    template_name: str,
    pixel_threshold: float = 95.0,
    semantic_threshold: float = 72.0
) -> Dict[str, Any]:
    """
    Stage 2 – Validation:
    Compare destination content against all trained template summaries.
    Returns per-file comparison results.
    """
    if not template_files:
        return {"matches": [], "overall_verdict": "need_review",
                "mcc_compliant": None, "post_description": "No template files to compare against"}

    # Build context from all trained files
    training_context = "\n\n".join([
        f"FILE {i+1}: {tf['file_name']}\n"
        f"Summary: {tf.get('llm_summary', 'N/A')}\n"
        f"Visual Elements: {json.dumps(tf.get('visual_elements', []))}\n"
        f"Detected Text: {tf.get('detected_text', 'N/A')[:200]}\n"
        f"Brand Elements: {json.dumps(tf.get('brand_elements', []))}"
        for i, tf in enumerate(template_files[:50])  # Cap at 50 for prompt size
    ])

    prompt = f"""You are a content compliance expert. Analyze the provided destination image/content and compare it against the trained approved content from template "{template_name}".

TRAINED APPROVED CONTENT ({len(template_files)} files):
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

    result = await _call_llm_vision(destination_path if destination_type == "image" else None, prompt)
    return result


async def _call_llm_vision(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call configured LLM provider with vision capability."""
    try:
        if settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
            return await _call_anthropic(image_path, prompt)
        elif settings.LLM_PROVIDER == "gemini" and settings.GOOGLE_API_KEY:
            return await _call_gemini(image_path, prompt)
        elif settings.LLM_PROVIDER == "nvidia" and settings.NVIDIA_API_KEY:
            logger.info("Calling NVIDIA NIM with model: %s", settings.NVIDIA_MODEL)
            
            # Optimization: Resize large images before sending to LLM
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
            logger.warning("No LLM API key configured - returning mock analysis")
            return _mock_analysis(image_path)
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return _mock_analysis(image_path, error=str(e))


async def _call_anthropic(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call Anthropic Claude claude-sonnet-4-20250514."""
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
    import asyncio
    
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
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.NVIDIA_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.NVIDIA_MODEL,
                        "max_tokens": 2048,
                        "messages": [{"role": "user", "content": messages_content}],
                        "temperature": 0.2,
                        "top_p": 0.7
                    }
                )
                
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 2
                    logger.warning("NVIDIA NIM rate limit hit (429). Retrying in %ds... (Attempt %d/%d)", 
                                   wait_time, attempt + 1, max_retries)
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                logger.info("NVIDIA NIM response received successfully (status: %d)", response.status_code)
                logger.info("NIM AI Result: %s", text[:300] + "..." if len(text) > 300 else text)
                return _parse_json_response(text)
                
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("NVIDIA NIM call failed after %d attempts: %s", max_retries, e)
                raise
            wait_time = (2 ** attempt) + 2
            logger.warning("NVIDIA NIM call attempt %d failed: %s. Retrying in %ds...", 
                           attempt + 1, e, wait_time)
            await asyncio.sleep(wait_time)
    
    # Should not reach here if retries work or raise
    return _mock_analysis(image_path, error="Max retries reached")


async def _call_gemini(image_path: Optional[str], prompt: str) -> Dict[str, Any]:
    """Call Google Gemini 1.5 Flash (free tier friendly)."""
    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        content = [prompt]
        if image_path and Path(image_path).exists():
            from PIL import Image
            img = Image.open(image_path)
            content.append(img)
            
        # generate_content is synchronous in the library, wrap in run_in_executor if needed
        # but for simple integration we'll call it directly since we are already in an async func
        # and this is the main logic.
        response = model.generate_content(content)
        return _parse_json_response(response.text)
    except Exception as e:
        logger.error("Gemini call failed: %s", e)
        raise


    return await _call_llm_vision(file_path, prompt)


async def analyze_from_url(url: str) -> Dict[str, Any]:
    """Download image from URL and analyze it."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True,
                                    headers={"User-Agent": "ContentValidator/1.0"})
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")

            # Save to temp file
            import tempfile, os
            suffix = ".jpg"
            if "png" in content_type: suffix = ".png"
            elif "gif" in content_type: suffix = ".gif"
            elif "webp" in content_type: suffix = ".webp"

            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(resp.content)
            tmp.close()
            return tmp.name, "image"
    except Exception as e:
        raise ValueError(f"Could not download from URL: {e}")


def _parse_json_response(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response."""
    text = text.strip()
    # Remove markdown code blocks if present
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object from text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {"summary": text, "error": "Could not parse structured response", "_raw": text}


def _mock_analysis(image_path: Optional[str], error: str = "") -> Dict[str, Any]:
    """Return mock analysis when no LLM is configured (dev/demo mode)."""
    import random
    score = random.uniform(45, 95)
    return {
        "summary": f"Mock analysis - configure ANTHROPIC_API_KEY or OPENAI_API_KEY for real analysis. {error}",
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
        "file_matches": []  # Will be populated by caller
    }
