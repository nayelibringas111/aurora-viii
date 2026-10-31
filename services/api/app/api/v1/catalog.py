from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.modules.catalog import FAMILIES, FUNDAMENTALS, GLOSSARY

router = APIRouter(tags=["fundamentals"], dependencies=[Depends(get_current_user)])


@router.get("/fundamentals")
def fundamentals():
    return {"sections": FUNDAMENTALS, "glossary": [{"term": t, "definition": d} for t, d in GLOSSARY]}


@router.get("/families")
def families():
    return FAMILIES
