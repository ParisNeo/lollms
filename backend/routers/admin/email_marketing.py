from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel
import datetime
import json

from backend.db import get_db
from backend.db.models.email_marketing import EmailProposal, EmailTopic, EmailStatus
from backend.db.models.user import User
from backend.models import UserAuthDetails
from backend.session import get_current_admin_user, get_user_lollms_client
from backend.task_manager import task_manager, Task
from backend.security import send_generic_email
from backend.settings import settings

# Prefix is relative to the admin router which is /api/admin
router = APIRouter(
    prefix="/email-marketing",
    tags=["Admin", "Email Marketing"],
    dependencies=[Depends(get_current_admin_user)]
)

class ProposalRead(BaseModel):
    id: int
    title: str
    content: str
    source_topic: Optional[str]
    status: EmailStatus
    created_at: datetime.datetime
    sent_at: Optional[datetime.datetime]
    admin_feedback: Optional[str]
    recipients_count: int = 0

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

class GenerateProposalRequest(BaseModel):
    topic: str
    tone: Optional[str] = "professional"
    additional_instructions: Optional[str] = ""

# --- PROPOSALS ---

@router.get("/proposals", response_model=List[ProposalRead])
def get_proposals(
    status: Optional[EmailStatus] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    query = db.query(EmailProposal)
    if status:
        query = query.filter(EmailProposal.status == status)
    
    proposals = query.order_by(EmailProposal.created_at.desc()).limit(limit).all()
    
    results = []
    for p in proposals:
        p_data = ProposalRead.model_validate(p)
        p_data.recipients_count = len(p.recipients) if p.recipients else 0
        results.append(p_data)
        
    return results

@router.post("/proposals", response_model=ProposalRead)
def create_manual_proposal(
    title: str = Body(...),
    content: str = Body(...),
    source_topic: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    proposal = EmailProposal(
        title=title,
        content=content,
        source_topic=source_topic,
        status=EmailStatus.DRAFT,
        recipients=[]
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    data = ProposalRead.model_validate(proposal)
    data.recipients_count = 0
    return data

@router.post("/generate-proposal")
async def generate_proposal_content(
    req: GenerateProposalRequest,
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    """Uses AI to generate a subject and body for an email based on a topic."""
    try:
        lc = get_user_lollms_client(current_admin.username)
        
        prompt = f"""Write an engaging email to our users.
Topic: {req.topic}
Tone: {req.tone}
Special Instructions: {req.additional_instructions}

Return the result as a JSON object with:
"subject": "A catchy email subject line",
"body": "The full email body in HTML format (using simple tags like <p>, <strong>, <br>). Include a friendly greeting and sign-off from the LoLLMs Team."
"""
        schema = {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["subject", "body"]
        }
        
        result = lc.generate_structured_content(prompt, schema=schema)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/proposals/{proposal_id}", response_model=ProposalRead)
def update_proposal(
    proposal_id: int,
    payload: ProposalUpdate,
    db: Session = Depends(get_db)
):
    proposal = db.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    if payload.title is not None: proposal.title = payload.title
    if payload.content is not None: proposal.content = payload.content
    if payload.feedback is not None: proposal.admin_feedback = payload.feedback
    
    if payload.status:
        if payload.status == EmailStatus.APPROVED and proposal.status != EmailStatus.SENT:
            proposal.status = EmailStatus.APPROVED
            task_manager.submit_task(
                name=f"Campaign: {proposal.title}",
                target=_send_campaign_task,
                args=(proposal.id, False),
                owner_username="admin"
            )
        else:
            proposal.status = payload.status
             
    db.commit()
    db.refresh(proposal)
    data = ProposalRead.model_validate(proposal)
    data.recipients_count = len(proposal.recipients) if proposal.recipients else 0
    return data

@router.post("/proposals/{proposal_id}/resend", response_model=ProposalRead)
def resend_to_new_users(
    proposal_id: int,
    db: Session = Depends(get_db)
):
    proposal = db.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    task_manager.submit_task(
        name=f"Resend Campaign: {proposal.title}",
        target=_send_campaign_task,
        args=(proposal.id, True),
        owner_username="admin"
    )
    
    return ProposalRead.model_validate(proposal)

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
        topic.is_active = False
        db.commit()
    return {"message": "Topic removed"}

def _send_campaign_task(task: Task, proposal_id: int, resend_only: bool):
    db = next(get_db())
    try:
        proposal = db.query(EmailProposal).filter(EmailProposal.id == proposal_id).first()
        if not proposal: return
        
        already_sent_ids = set(proposal.recipients or [])
        query = db.query(User).filter(User.receive_notification_emails == True, User.is_active == True)
        if resend_only:
            query = query.filter(User.id.notin_(already_sent_ids))
            task.log(f"Resending '{proposal.title}' to new recipients...")
        else:
            task.log(f"Sending campaign '{proposal.title}'...")

        targets = query.all()
        total = len(targets)
        
        if total == 0:
            task.log("No eligible recipients found.")
            proposal.status = EmailStatus.SENT
            db.commit()
            return

        sent_count = 0
        new_recipients = list(already_sent_ids)
        for i, user in enumerate(targets):
            if task.cancellation_event.is_set():
                task.log("Sending cancelled.")
                break
            if user.email:
                try:
                    send_generic_email(user.email, proposal.title, proposal.content)
                    sent_count += 1
                    new_recipients.append(user.id)
                except Exception as e:
                    task.log(f"Failed to send to {user.username}: {str(e)}", "ERROR")
            task.set_progress(int(((i + 1) / total) * 100))

        proposal.recipients = list(set(new_recipients))
        proposal.status = EmailStatus.SENT
        proposal.sent_at = datetime.datetime.utcnow()
        db.commit()
        task.log(f"Campaign task finished. Successfully sent to {sent_count} users.")
    except Exception as e:
        task.log(f"Campaign failed: {e}", "ERROR")
    finally:
        db.close()
