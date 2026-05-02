"""
Visual DOM diffing — screenshot before/after each action, PIL pixel diff.
Diff type classification: content | modal | nav | ad | minimal | none
"""
import io
import base64
import numpy as np
from PIL import Image
from typing import Optional

# ── Diff thresholds ────────────────────────────────────────────────────────────
PIXEL_DIFF_THRESHOLD = 0.02      # 2% pixel change = page actually changed
MIN_DIFF_PIXELS     = 500         # fewer pixels changed than this = noise/none
SIGNIFICANT_CHANGE  = 0.05       # 5% = real content change (retry-worthy)

# Diff type labels
DIFF_TYPES = {
    "content":  "content",   # page content actually changed
    "modal":    "modal",     # modal/popup appeared
    "nav":      "nav",       # navigation happened
    "ad":       "ad",        # ad loaded
    "minimal":  "minimal",  # tiny change (JS tick, animation)
    "none":     "none",      # no detectable change
}


def pixels_changed(before_b64: str, after_b64: str) -> tuple[float, str, Optional[dict]]:
    """
    Compare two base64-encoded screenshots.
    Returns (pct_changed, diff_type, diff_info)
    diff_info: {before_pixels, after_pixels, diff_pixels, changed_coords}
    """
    try:
        before_bytes = base64.b64decode(before_b64)
        after_bytes  = base64.b64decode(after_b64)
    except Exception:
        return 0.0, "none", None

    try:
        before_img = Image.open(io.BytesIO(before_bytes)).convert("RGB")
        after_img  = Image.open(io.BytesIO(after_bytes)).convert("RGB")
    except Exception:
        return 0.0, "none", None

    # Resize to same size if mismatch
    if before_img.size != after_img.size:
        after_img = after_img.resize(before_img.size, Image.LANCZOS)

    w, h = before_img.size
    total_pixels = w * h

    # Convert to numpy for fast comparison
    before_arr = np.array(before_img, dtype=np.float32)
    after_arr  = np.array(after_img,  dtype=np.float32)

    # Per-pixel squared difference
    diff = np.abs(before_arr - after_arr)
    # Count pixels where ANY channel changed meaningfully
    channel_diff = diff.sum(axis=2)  # sum across R,G,B
    changed_mask = channel_diff > 10  # threshold: 10/255 per channel
    n_changed = int(changed_mask.sum())
    pct_changed = n_changed / total_pixels

    # ── Diff type classification ────────────────────────────────────────────
    if pct_changed < 0.001:
        diff_type = "none"
    elif pct_changed < 0.01:
        diff_type = "minimal"
    elif _is_modal(before_arr, after_arr, changed_mask, w, h):
        diff_type = "modal"
    elif _is_nav(before_arr, after_arr, changed_mask, w, h):
        diff_type = "nav"
    elif _is_ad(before_arr, after_arr, changed_mask, w, h):
        diff_type = "ad"
    else:
        diff_type = "content"

    diff_info = {
        "before_pixels": total_pixels,
        "after_pixels":   total_pixels,
        "diff_pixels":   n_changed,
        "pct_changed":   round(pct_changed * 100, 2),
        "width": w,
        "height": h,
    }
    return pct_changed, diff_type, diff_info


def _is_modal(before: np.ndarray, after: np.ndarray,
              mask: np.ndarray, w: int, h: int) -> bool:
    """Modal/popup: big solid-color region appeared in center."""
    # Find large contiguous changed region in center third
    cx, cy = w // 2, h // 2
    # Look for changed pixels concentrated in center 60%
    x0, x1 = int(w * 0.2), int(w * 0.8)
    y0, y1 = int(h * 0.2), int(h * 0.8)
    center_changed = mask[y0:y1, x0:x1].sum()
    total_changed  = mask.sum()
    if total_changed == 0:
        return False
    # If >40% of changes are in center, likely a modal
    return (center_changed / total_changed) > 0.4 and center_changed > 5000


def _is_nav(before: np.ndarray, after: np.ndarray,
            mask: np.ndarray, w: int, h: int) -> bool:
    """Navigation: top or bottom strip changed significantly."""
    # Check top 10% and bottom 10% strips
    top_strip    = mask[:int(h * 0.1), :].sum()
    bottom_strip = mask[int(h * 0.9):, :].sum()
    total_changed = mask.sum()
    if total_changed == 0:
        return False
    return (top_strip + bottom_strip) / total_changed > 0.5


def _is_ad(before: np.ndarray, after: np.ndarray,
           mask: np.ndarray, w: int, h: int) -> bool:
    """Ad: small rectangular region in typical ad positions."""
    # Right sidebar (common ad zone): right 15%, not full height
    right = mask[:, int(w * 0.85):].sum()
    total_changed = mask.sum()
    if total_changed == 0:
        return False
    # Ad pixels tend to be small and in sidebar/header zones
    if right / total_changed > 0.6 and right < w * h * 0.05:
        return True
    return False


def diff_result(pct: float, diff_type: str) -> dict:
    """Build a result dict for a diff comparison."""
    return {
        "pct_changed":    round(pct * 100, 2),
        "diff_type":     diff_type,
        "significant":    pct >= SIGNIFICANT_CHANGE,
        "retry_needed":  diff_type in ("none", "minimal"),
    }
