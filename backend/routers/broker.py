from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import AngelOneCredential
from auth.dependencies import get_current_user
from database.models import User

router = APIRouter(
    prefix="/brokers",
    tags=["Brokers"]
)

@router.get("/")
async def get_my_brokers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all configured brokers for the current user.
    """
    brokers = []
    
    # Check Angel One
    angel_creds = db.query(AngelOneCredential).filter(AngelOneCredential.user_id == current_user.id).all()
    for cred in angel_creds:
        brokers.append({
            "broker": "Angel One", 
            "client_code": cred.client_code, 
            "status": "Session Active" if cred.jwt_token else "Configured",
            "id": cred.id
        })
        
    return brokers
