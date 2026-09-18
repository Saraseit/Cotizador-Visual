from fastapi import APIRouter

router = APIRouter(tags=["salud"])


@router.get("/salud")
async def salud() -> dict[str, str]:
    return {"estado": "ok"}
