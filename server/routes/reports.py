from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import ReadinessReport
from modules.schemas import ReadinessReportResponse
from services.priorauth_analysis import generate_readiness_report, latest_report


router = APIRouter()


def report_response(report: ReadinessReport) -> ReadinessReportResponse:
    return ReadinessReportResponse(
        id=report.id,
        case_id=report.case_id,
        readiness_score=report.readiness_score,
        overall_status=report.overall_status,
        summary=report.summary,
        highest_risk_items=report.highest_risk_items,
        recommended_next_steps=report.recommended_next_steps,
        report_json=report.report_json,
        created_at=report.created_at,
    )


@router.post("/cases/{case_id}/reports/readiness", response_model=ReadinessReportResponse)
async def create_readiness_report(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    report = generate_readiness_report(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return report_response(report)


@router.get("/cases/{case_id}/reports/latest", response_model=ReadinessReportResponse)
async def get_latest_report(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = latest_report(db, case_id=case_id, organization_id=current_user.organization_id)
    return report_response(report)
