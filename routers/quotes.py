"""
Quotes endpoints - display inspirational quotes with images.

Endpoints:
- GET /api/quotes - Get all active quotes
- GET /api/quotes/{id} - Get specific quote
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Quote
import schemas

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.get("/", response_model=dict)
async def get_quotes(db: Session = Depends(get_db)):
    """
    Get all active quotes with images.
    
    Returns: List of quotes ordered by display order
    """
    try:
        quotes = db.query(Quote).filter(
            Quote.is_active == True
        ).order_by(Quote.order.asc()).all()
        
        return {
            "success": True,
            "quotes": [
                {
                    "id": q.id,
                    "text": q.text,
                    "author": q.author,
                    "image_url": q.image_url,
                    "category": q.category,
                    "order": q.order,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                }
                for q in quotes
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{quote_id}/", response_model=dict)
async def get_quote(
    quote_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific quote by ID.
    
    Returns: Quote details with image
    """
    try:
        quote = db.query(Quote).filter(Quote.id == quote_id).first()
        
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote not found"
            )
        
        return {
            "id": quote.id,
            "text": quote.text,
            "author": quote.author,
            "image_url": quote.image_url,
            "category": quote.category,
            "created_at": quote.created_at.isoformat() if quote.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))