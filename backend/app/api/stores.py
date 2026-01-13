"""
Stores management API routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from app.models.schemas import Store, StoreCreate
from app.services.auth import require_manager, require_admin
from app.services.database import get_database

router = APIRouter(prefix="/stores", tags=["Stores"])


@router.get("")
async def list_stores(
    active_only: bool = True,
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    List all stores
    """
    query = {"active": True} if active_only else {}
    
    stores = await db.stores.find(query).sort("store_id", 1).to_list(length=None)
    
    for store in stores:
        store["id"] = str(store.pop("_id"))
    
    return stores


@router.get("/{store_id}")
async def get_store(
    store_id: str,
    db = Depends(get_database),
    current_user: dict = Depends(require_manager)
):
    """
    Get a specific store by ID
    """
    store = await db.stores.find_one({"store_id": store_id})
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store["id"] = str(store.pop("_id"))
    return store


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_store(
    store_data: StoreCreate,
    db = Depends(get_database),
    current_user: dict = Depends(require_admin)
):
    """
    Create a new store (admin only)
    """
    # Check if store_id already exists
    existing = await db.stores.find_one({"store_id": store_data.store_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Store {store_data.store_id} already exists"
        )
    
    store_doc = store_data.model_dump()
    result = await db.stores.insert_one(store_doc)
    
    return {
        "id": str(result.inserted_id),
        **store_doc
    }


@router.put("/{store_id}")
async def update_store(
    store_id: str,
    store_data: StoreCreate,
    db = Depends(get_database),
    current_user: dict = Depends(require_admin)
):
    """
    Update a store (admin only)
    """
    result = await db.stores.update_one(
        {"store_id": store_id},
        {"$set": store_data.model_dump()}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"status": "updated", "store_id": store_id}


@router.delete("/{store_id}")
async def deactivate_store(
    store_id: str,
    db = Depends(get_database),
    current_user: dict = Depends(require_admin)
):
    """
    Deactivate a store (soft delete, admin only)
    """
    result = await db.stores.update_one(
        {"store_id": store_id},
        {"$set": {"active": False}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Store not found")
    
    return {"status": "deactivated", "store_id": store_id}


@router.post("/bulk-import")
async def bulk_import_stores(
    stores: list[StoreCreate],
    db = Depends(get_database),
    current_user: dict = Depends(require_admin)
):
    """
    Bulk import stores (admin only)
    """
    imported = 0
    skipped = 0
    
    for store_data in stores:
        existing = await db.stores.find_one({"store_id": store_data.store_id})
        if existing:
            skipped += 1
            continue
        
        await db.stores.insert_one(store_data.model_dump())
        imported += 1
    
    return {
        "imported": imported,
        "skipped": skipped,
        "total": len(stores)
    }
