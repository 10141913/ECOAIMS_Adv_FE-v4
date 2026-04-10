from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ecoaims_backend.contracts.registry import canonical_contract_index, canonical_contract_manifest


router = APIRouter(prefix="/api/contracts", tags=["contracts"])


@router.get("/index")
def contracts_index() -> Dict[str, Any]:
    return canonical_contract_index()


@router.get("/{manifest_id}")
def contracts_manifest(manifest_id: str) -> Dict[str, Any]:
    m = canonical_contract_manifest(manifest_id)
    if m is None:
        raise HTTPException(status_code=404, detail={"error": "manifest_not_found", "manifest_id": manifest_id})
    return m

