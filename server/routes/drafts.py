from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import CitationCheck, DraftLetter
from modules.schemas import (
    CitationCheckResponse,
    DraftLetterResponse,
    DraftListResponse,
    DraftUpdateRequest,
)
from services.priorauth_analysis import (
    approve_draft,
    create_prior_auth_draft,
    get_draft,
    list_drafts,
    update_draft,
    verify_citations,
)
from routes.cases import get_case_for_user


router = APIRouter()


def draft_response(draft: DraftLetter) -> DraftLetterResponse:
    return DraftLetterResponse(
        id=draft.id,
        case_id=draft.case_id,
        letter_type=draft.letter_type,
        status=draft.status,
        content_markdown=draft.content_markdown,
        created_by=draft.created_by,
        approved_at=draft.approved_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def citation_response(check: CitationCheck) -> CitationCheckResponse:
    return CitationCheckResponse(
        id=check.id,
        draft_letter_id=check.draft_letter_id,
        verification_status=check.verification_status,
        unsupported_claims=check.unsupported_claims,
        weakly_supported_claims=check.weakly_supported_claims,
        citation_errors=check.citation_errors,
        safe_to_show_user=check.safe_to_show_user,
        created_at=check.created_at,
    )


@router.post("/cases/{case_id}/drafts/prior-auth", response_model=DraftLetterResponse)
async def create_prior_auth_letter(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    draft = create_prior_auth_draft(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return draft_response(draft)


@router.post("/cases/{case_id}/drafts/appeal")
async def appeal_draft_deferred(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    get_case_for_user(db, case_id, current_user)
    raise HTTPException(status_code=501, detail="Appeal drafting is deferred from the first MVP")


@router.get("/cases/{case_id}/drafts", response_model=DraftListResponse)
async def get_case_drafts(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    drafts = list_drafts(db, case_id=case_id, organization_id=current_user.organization_id)
    return DraftListResponse(drafts=[draft_response(draft) for draft in drafts])


@router.get("/drafts/{draft_id}", response_model=DraftLetterResponse)
async def get_draft_letter(
    draft_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return draft_response(get_draft(db, draft_id=draft_id, organization_id=current_user.organization_id))


@router.patch("/drafts/{draft_id}", response_model=DraftLetterResponse)
async def edit_draft_letter(
    draft_id: str,
    payload: DraftUpdateRequest,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    draft = update_draft(
        db,
        draft_id=draft_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        content=payload.content_markdown,
    )
    return draft_response(draft)


@router.post("/drafts/{draft_id}/verify-citations", response_model=CitationCheckResponse)
async def verify_draft_citations(
    draft_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    check = verify_citations(
        db,
        draft_id=draft_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return citation_response(check)


@router.post("/drafts/{draft_id}/approve", response_model=DraftLetterResponse)
async def approve_draft_letter(
    draft_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    draft = approve_draft(
        db,
        draft_id=draft_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return draft_response(draft)
