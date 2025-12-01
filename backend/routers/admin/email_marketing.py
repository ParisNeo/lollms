from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import datetime

from backend.db import get_db
from backend.db.models.email_marketing import EmailProposal, EmailTopic, EmailStatus
from backend.models import UserAuthDetails
from backend.session import get_current_active_user
from backend.task_manager import task_manager

# Import email sending utility (assuming standard location or mocking if not present)
# In a real scenario, this would import from backend.services.email or similar
# For this implementation, we will simulate the send or use a placeholder

router = APIRouter(
    prefix="/api/admin/email-marketing",
    tags=["Admin", "Email Marketing"],
    dependencies=[Depends(get_current_active_user)]
)

class ProposalRead(BaseModel):
    id: int
    title: str
    content: str
    source_topic: Optional[str]
    status: EmailStatus
    created_at: datetime.datetime
    admin_feedback: Optional[str]

    class Config:
        from_attributes = True

class ProposalUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[EmailStatus] = None
    feedback: Optional[str] = None

class TopicCreate(BaseModel):
    topic: str

class TopicRead(BaseModel):
    id: int
    topic: str
    is_active: bool
    source: str
    class Config:
        from_attributes = True

# --- PROPOSALS ---

@router.get("/proposals", response_model=List[ProposalRead])
def get_proposals(
    status: Optional[EmailStatus] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(EmailProposal)
    if status:
        query = query.filter(EmailProposal.status == status)
    return query.order_by(EmailProposal.created_at.desc()).limit(limit).all()

@router.put("/proposals/{proposal_id}", response_model=ProposalRead)
def update_proposal(
    proposal_id: int,
    payload: ProposalUpdate,
    db: Session = Depends(get_db)
):
    proposal = db.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if payload.title: proposal.title = payload.title
    if payload.content: proposal.content = payload.content
    if payload.feedback: proposal.admin_feedback = payload.feedback
    
    # Handle Status Changes
    if payload.status:
        # If approving/sending
        if payload.status == EmailStatus.APPROVED and proposal.status != EmailStatus.APPROVED:
            proposal.status = EmailStatus.APPROVED
            # Trigger Send Task
            task_manager.submit_task(
                name=f"Sending Email: {proposal.title}",
                target=_send_email_task_wrapper,
                args=(proposal.id,),
                owner_username="admin"
            )
        elif payload.status == EmailStatus.REJECTED:
             proposal.status = EmailStatus.REJECTED
        elif payload.status == EmailStatus.ARCHIVED:
             proposal.status = EmailStatus.ARCHIVED
             
    db.commit()
    db.refresh(proposal)
    return proposal

@router.delete("/proposals/{proposal_id}")
def delete_proposal(proposal_id: int, db: Session = Depends(get_db)):
    proposal = db.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
    if proposal:
        db.delete(proposal)
        db.commit()
    return {"message": "Deleted"}

# --- TOPICS ---

@router.get("/topics", response_model=List[TopicRead])
def get_topics(db: Session = Depends(get_db)):
    return db.query(EmailTopic).filter(EmailTopic.is_active == True).order_by(EmailTopic.created_at.desc()).all()

@router.post("/topics", response_model=TopicRead)
def add_topic(payload: TopicCreate, db: Session = Depends(get_db)):
    topic = EmailTopic(topic=payload.topic, source="admin")
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic

@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(EmailTopic).filter(EmailTopic.id == topic_id).first()
    if topic:
        topic.is_active = False # Soft delete
        db.commit()
    return {"message": "Topic removed"}

# --- INTERNAL HELPER (Task Target) ---
def _send_email_task_wrapper(task, proposal_id: int):
    # This function would call the actual email service
    db = next(get_db())
    try:
        proposal = db.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
        if not proposal: return
        
        task.log(f"Sending email '{proposal.title}' to all subscribed users...")
        
        # [Simulate Sending Logic]
        # 1. Get users with receive_notification_emails=True
        # 2. Iterate and send (using smtplib or backend.services.email if it existed)
        
        proposal.status = EmailStatus.SENT
        proposal.sent_at = datetime.datetime.utcnow()
        db.commit()
        task.log("Email campaign completed successfully.")
    except Exception as e:
        task.log(f"Failed to send email: {e}", "ERROR")
    finally:
        db.close()
