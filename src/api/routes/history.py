"""
History Routes - Generation history management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from src.api.services.history import generation_history
from src.utils.logger import create_logger

logger = create_logger("HistoryRoutes")
router = APIRouter(prefix="/api/history", tags=["history"])


class UpdateNotesRequest(BaseModel):
    notes: str


class AddTagRequest(BaseModel):
    tag: str


@router.get("/prompts")
async def get_prompts_history(limit: int = 50):
    """Get prompt history (legacy endpoint for compatibility)"""
    items = generation_history.get_all(limit=limit)
    # Extract just prompts for compatibility
    prompts = []
    for item in items:
        if 'prompt' in item:
            prompts.append({
                'prompt': item['prompt'],
                'timestamp': item.get('timestamp', ''),
                'id': item.get('id', '')
            })
    return {"history": prompts}


@router.get("")
async def get_history(limit: int = 100, offset: int = 0):
    """Get paginated generation history"""
    return {
        "items": generation_history.get_all(limit=limit, offset=offset),
        "total": len(generation_history.history),
        "limit": limit,
        "offset": offset
    }


@router.get("/search")
async def search_history(q: str, limit: int = 50):
    """Search history by prompt text"""
    results = generation_history.search(q, limit=limit)
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }


@router.get("/favorites")
async def get_favorites():
    """Get all favorited entries"""
    favorites = generation_history.get_favorites()
    return {
        "items": favorites,
        "count": len(favorites)
    }


@router.get("/stats")
async def get_history_stats():
    """Get history statistics"""
    return generation_history.get_stats()


@router.get("/by-style/{style}")
async def get_by_style(style: str):
    """Get history filtered by style"""
    items = generation_history.filter_by_style(style)
    return {
        "style": style,
        "items": items,
        "count": len(items)
    }


@router.get("/by-seed/{seed}")
async def get_by_seed(seed: int):
    """Get history filtered by seed"""
    items = generation_history.filter_by_seed(seed)
    return {
        "seed": seed,
        "items": items,
        "count": len(items)
    }


@router.get("/{entry_id}")
async def get_entry(entry_id: str):
    """Get a specific history entry"""
    entry = generation_history.get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("/filename/{filename}")
async def get_by_filename(filename: str):
    """Get history entry by filename"""
    entry = generation_history.get_by_filename(filename)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("/{entry_id}/favorite")
async def toggle_favorite(entry_id: str):
    """Toggle favorite status"""
    new_status = generation_history.toggle_favorite(entry_id)
    return {
        "success": True,
        "entry_id": entry_id,
        "favorite": new_status
    }


@router.post("/{entry_id}/tags")
async def add_tag(entry_id: str, request: AddTagRequest):
    """Add a tag to an entry"""
    success = generation_history.add_tag(entry_id, request.tag)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True, "tag": request.tag}


@router.delete("/{entry_id}/tags/{tag}")
async def remove_tag(entry_id: str, tag: str):
    """Remove a tag from an entry"""
    success = generation_history.remove_tag(entry_id, tag)
    if not success:
        raise HTTPException(status_code=404, detail="Entry or tag not found")
    return {"success": True}


@router.put("/{entry_id}/notes")
async def update_notes(entry_id: str, request: UpdateNotesRequest):
    """Update notes for an entry"""
    success = generation_history.update_notes(entry_id, request.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True}


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str):
    """Delete a history entry"""
    success = generation_history.delete(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"success": True}


@router.post("/export")
async def export_history(filepath: str = "history_export.json"):
    """Export history to a file"""
    success = generation_history.export(filepath)
    if not success:
        raise HTTPException(status_code=500, detail="Export failed")
    return {"success": True, "filepath": filepath}
