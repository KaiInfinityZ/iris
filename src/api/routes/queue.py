"""
Queue Routes - Generation queue management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from src.api.services.queue import generation_queue
from src.utils.logger import create_logger

logger = create_logger("QueueRoutes")
router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueueAddRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    width: int = 512
    height: int = 768
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    seed: int = -1
    style: str = "anime_kawai"


class QueueBatchRequest(BaseModel):
    items: List[QueueAddRequest]


@router.get("")
async def get_queue():
    """Get all queue items"""
    return {
        "items": generation_queue.get_all(),
        "stats": generation_queue.get_stats()
    }


@router.post("/add")
async def add_to_queue(request: QueueAddRequest):
    """Add a single item to the queue"""
    item = generation_queue.add(
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        width=request.width,
        height=request.height,
        steps=request.steps,
        cfg_scale=request.cfg_scale,
        seed=request.seed,
        style=request.style
    )
    
    if item is None:
        raise HTTPException(status_code=400, detail="Queue is full")
    
    return {
        "success": True,
        "item": item.to_dict(),
        "queue_position": len(generation_queue.get_pending())
    }


@router.post("/add-batch")
async def add_batch_to_queue(request: QueueBatchRequest):
    """Add multiple items to the queue"""
    added = []
    failed = []
    
    for item_request in request.items:
        item = generation_queue.add(
            prompt=item_request.prompt,
            negative_prompt=item_request.negative_prompt,
            width=item_request.width,
            height=item_request.height,
            steps=item_request.steps,
            cfg_scale=item_request.cfg_scale,
            seed=item_request.seed,
            style=item_request.style
        )
        
        if item:
            added.append(item.to_dict())
        else:
            failed.append(item_request.prompt[:50])
    
    return {
        "success": len(failed) == 0,
        "added": len(added),
        "failed": len(failed),
        "items": added
    }


@router.delete("/{item_id}")
async def remove_from_queue(item_id: str):
    """Remove an item from the queue"""
    success = generation_queue.remove(item_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Item not found or cannot be removed")
    
    return {"success": True, "message": f"Removed {item_id}"}


@router.post("/{item_id}/cancel")
async def cancel_queue_item(item_id: str):
    """Cancel a pending queue item"""
    success = generation_queue.cancel(item_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="Item not found or not pending")
    
    return {"success": True, "message": f"Cancelled {item_id}"}


@router.post("/{item_id}/move-up")
async def move_item_up(item_id: str):
    """Move an item up in the queue"""
    success = generation_queue.move_up(item_id)
    return {"success": success}


@router.post("/{item_id}/move-down")
async def move_item_down(item_id: str):
    """Move an item down in the queue"""
    success = generation_queue.move_down(item_id)
    return {"success": success}


@router.post("/process-next")
async def process_next():
    """Process the next item in the queue"""
    item = await generation_queue.process_next()
    
    if item is None:
        return {"success": False, "message": "No pending items or already processing"}
    
    return {
        "success": True,
        "item": item.to_dict()
    }


@router.post("/process-all")
async def process_all():
    """Start processing all pending items"""
    pending_count = len(generation_queue.get_pending())
    
    if pending_count == 0:
        return {"success": False, "message": "No pending items"}
    
    # Start processing in background
    import asyncio
    asyncio.create_task(generation_queue.process_all())
    
    return {
        "success": True,
        "message": f"Started processing {pending_count} items"
    }


@router.post("/clear-completed")
async def clear_completed():
    """Clear all completed/failed/cancelled items"""
    generation_queue.clear_completed()
    return {"success": True, "message": "Cleared completed items"}


@router.post("/clear-all")
async def clear_all():
    """Clear entire queue (except processing items)"""
    generation_queue.clear_all()
    return {"success": True, "message": "Queue cleared"}


@router.get("/stats")
async def get_queue_stats():
    """Get queue statistics"""
    return generation_queue.get_stats()
