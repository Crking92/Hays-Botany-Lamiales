#!/usr/bin/env python3
"""Small gallery display copies before Git publication, preserving source proofs.

The original image is NOT overwritten. The full-size source must be retained
in the source archive (a future same-repository GitHub Release can hold it).
"""
import io
from pathlib import Path
from PIL import Image, ImageOps

DISPLAY_LIMIT_BYTES = 650_000
SITE_LIMIT_BYTES = 850_000_000
SITE_WARN_BYTES = 750_000_000

def make_display_bytes(source: bytes, filename: str):
    """Return (web_bytes, changed), with unchanged file extension and format."""
    ext = Path(filename).suffix.lower()
    fmt = {".jpg":"JPEG",".jpeg":"JPEG",".png":"PNG",".webp":"WEBP"}.get(ext)
    if not fmt:
        raise ValueError("Unsupported photo extension")
    with Image.open(io.BytesIO(source)) as opened:
        opened.load()
        if opened.format != fmt:
            raise ValueError("File name does not match image format")
        if len(source) <= DISPLAY_LIMIT_BYTES and max(opened.size) <= 2600:
            return source, False
        img = ImageOps.exif_transpose(opened)
        if fmt == "PNG" and "A" in img.getbands():
            raise ValueError("Large transparent PNG requires manual display handling")
        if fmt in ("JPEG","WEBP") and img.mode != "RGB":
            img = img.convert("RGB")
        profile = opened.info.get("icc_profile")
        if profile and len(profile) > 131072:
            profile = None
        best = None
        for edge, quality in ((2400,84),(2200,82),(2000,80),
                              (1800,78),(1650,76),(1500,73),
                              (1400,70),(1250,68)):
            candidate_img = img.copy()
            candidate_img.thumbnail((edge,edge),Image.Resampling.LANCZOS)
            out = io.BytesIO()
            if fmt == "JPEG":
                candidate_img.save(out,format="JPEG",quality=quality,
                                   optimize=True,progressive=True,
                                   subsampling=2,icc_profile=profile)
            elif fmt == "WEBP":
                candidate_img.save(out,format="WEBP",quality=quality,
                                   method=5,icc_profile=profile)
            else:
                candidate_img.save(out,format="PNG",optimize=True)
            web = out.getvalue()
            if best is None or len(web)<len(best):
                best=web
            if len(web)<=DISPLAY_LIMIT_BYTES and len(web)<len(source):
                return web, True
        if best is not None and len(best)<=DISPLAY_LIMIT_BYTES and len(best)<len(source):
            return best, True
        raise ValueError("WEB_DISPLAY_SIZE_HOLD: cannot safely fit image under 650 KB")

def ensure_site_budget(site, incoming_bytes, new_photo_count):
    current = sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
    estimate = current + incoming_bytes + 4000*new_photo_count + 100000
    if estimate > SITE_LIMIT_BYTES:
        raise ValueError("PUBLIC_SITE_SIZE_HOLD: estimated "+
                         str(estimate)+" bytes exceeds "+str(SITE_LIMIT_BYTES)+
                         " byte website safeguard; optimize more existing display copies")
    return {"existing_site_bytes":current,
            "projected_site_bytes":estimate,
            "site_budget_bytes":SITE_LIMIT_BYTES,
            "warning":estimate>=SITE_WARN_BYTES}
