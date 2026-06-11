"""
Gallery Routes - Image listing and retrieval
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.utils.logger import create_logger

logger = create_logger("GalleryRoutes")
router = APIRouter(prefix="/api", tags=["gallery"])

OUTPUTS_DIR = "outputs"


def extract_metadata_from_filename(filename: str) -> dict:
    """Extract metadata from filename"""
    parts = filename.replace(".png", "").split("_")
    metadata = {
        "type": parts[0] if len(parts) > 0 else "unknown",
        "timestamp": parts[1] if len(parts) > 1 else None,
        "seed": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
        "steps": int(parts[3][1:]) if len(parts) > 3 and parts[3].startswith("s") else None,
        "scale": int(parts[4][1:]) if len(parts) > 4 and parts[4].startswith("x") else None
    }
    return metadata


@router.get("/output-gallery")
async def get_output_gallery():
    """Get list of all images from outputs directory"""
    try:
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        files = [f for f in os.listdir(OUTPUTS_DIR) if f.endswith((".png", ".jpg", ".jpeg"))]
        files.sort(key=lambda x: os.path.getmtime(f"{OUTPUTS_DIR}/{x}"), reverse=True)
        return {"images": files, "count": len(files)}
    except Exception as e:
        logger.error(f"Error loading output gallery: {e}")
        return {"images": [], "count": 0, "error": str(e)}


@router.get("/gallery")
async def get_gallery():
    """Get recent images (limited)"""
    try:
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        files = sorted(
            [f for f in os.listdir(OUTPUTS_DIR) if f.endswith(".png")],
            key=lambda x: os.path.getmtime(f"{OUTPUTS_DIR}/{x}"),
            reverse=True
        )[:12]
        return {"images": files}
    except Exception as e:
        logger.error(f"Error loading gallery: {e}")
        return {"images": []}


@router.get("/gallery/images")
async def get_gallery_images():
    """Get all gallery images - for upscaler page library"""
    try:
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        files = sorted(
            [f for f in os.listdir(OUTPUTS_DIR) if f.endswith((".png", ".jpg", ".jpeg", ".webp"))],
            key=lambda x: os.path.getmtime(f"{OUTPUTS_DIR}/{x}"),
            reverse=True
        )
        return {"images": files, "count": len(files)}
    except Exception as e:
        logger.error(f"Error loading gallery images: {e}")
        return {"images": [], "count": 0, "error": str(e)}


@router.get("/output-image/{filename}")
async def get_output_image(filename: str):
    """Get a specific image from outputs directory"""
    filepath = f"{OUTPUTS_DIR}/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(filepath)


@router.post("/recreate-from-output")
async def recreate_from_output(request: dict):
    """Extract settings from output filename for recreation"""
    try:
        filename = request.get("filename", "")
        metadata = extract_metadata_from_filename(filename)
        
        if metadata["seed"] is not None:
            return {
                "success": True,
                "seed": metadata["seed"],
                "steps": metadata.get("steps"),
                "message": f"Extracted seed: {metadata['seed']}, type: {metadata['type']}"
            }
        
        # Fallback parsing
        parts = filename.replace(".png", "").split("_")
        seed = None
        
        for part in parts:
            if part.isdigit() and len(part) >= 4:
                seed = int(part)
                break
        
        if seed is None:
            return {"success": False, "error": "Could not extract seed from filename"}
        
        return {
            "success": True,
            "seed": seed,
            "message": f"Extracted seed: {seed}"
        }
        
    except Exception as e:
        logger.error(f"Recreation failed: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/output-image/{filename}")
async def delete_output_image(filename: str):
    """Delete an image from outputs directory"""
    filepath = f"{OUTPUTS_DIR}/{filename}"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        os.remove(filepath)
        return {"success": True, "message": f"Deleted {filename}"}
    except Exception as e:
        logger.error(f"Failed to delete {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
