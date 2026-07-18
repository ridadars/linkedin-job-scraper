"""End-to-end processing of one job (card + optional detail) into saveable data.

Pipeline: merge → normalize → validate → enrich (skills, salary, applicants,
date, country) → classify. Produces a :class:`JobProcessingResult` whose status
is ``complete``, ``partial``, or ``failed``. A job with a valid title and job
URL can still be saved as ``partial`` even when detail data is missing; a job
without a valid title or LinkedIn job URL fails and is never persisted.
"""

from datetime import datetime

from app.exceptions import InvalidLinkedInUrlError
from app.schemas.parsed_job import JobCardData, JobDetailData
from app.schemas.processed_job import (
    JobProcessingResult,
    ProcessedJobData,
    ProcessingStatus,
)
from app.services.applicant_parser_service import parse_applicant_count_detailed
from app.services.date_parser_service import parse_posted_date
from app.services.job_merge_service import merge_job_data
from app.services.salary_parser_service import parse_salary_text
from app.services.skill_extraction_service import extract_skills
from app.utils.job_normalizer import (
    infer_country,
    normalize_company_name,
    normalize_employment_type,
    normalize_experience_level,
    normalize_job_title,
    normalize_job_url,
    normalize_location,
    normalize_workplace_type,
)


class JobProcessingService:
    """Transforms parsed card/detail data into normalized, enriched job data."""

    def process(
        self,
        card: JobCardData,
        detail: JobDetailData | None,
        reference_time: datetime | None = None,
    ) -> JobProcessingResult:
        """Process one job and return a :class:`JobProcessingResult`."""
        merged = merge_job_data(card, detail)
        warnings: list[str] = list(merged["warnings"])

        title = normalize_job_title(merged["title"])
        if not title:
            return JobProcessingResult(
                job=None,
                status=ProcessingStatus.FAILED.value,
                warnings=warnings,
                error_type="processing_failed",
                error_message="Job is missing a usable title.",
            )

        raw_job_url = merged["job_url"]
        if not raw_job_url:
            return JobProcessingResult(
                job=None,
                status=ProcessingStatus.FAILED.value,
                warnings=warnings,
                error_type="invalid_job_url",
                error_message="Job is missing a job URL.",
            )
        try:
            normalized_url = normalize_job_url(raw_job_url)
        except InvalidLinkedInUrlError:
            return JobProcessingResult(
                job=None,
                status=ProcessingStatus.FAILED.value,
                warnings=warnings,
                error_type="invalid_job_url",
                error_message="Job URL is not a valid LinkedIn job URL.",
            )

        location = normalize_location(merged["location"])
        workplace_type = normalize_workplace_type(merged["workplace_type"])
        employment_type = normalize_employment_type(merged["employment_type"])
        experience_level = normalize_experience_level(merged["experience_level"])
        description = merged["description"]

        # Skills: description is primary, title is secondary context.
        skill_text = " ".join(part for part in (description, title) if part)
        skills = extract_skills(skill_text)

        salary = parse_salary_text(merged["salary_text"])
        if salary.period in {"hour", "day", "week", "month"}:
            warnings.append(
                f"salary is per {salary.period}; not annualized."
            )

        applicant_count, applicant_warning = parse_applicant_count_detailed(
            merged["applicant_count_text"]
        )
        if applicant_warning:
            warnings.append(applicant_warning)

        posted_date = parse_posted_date(merged["posted_text"], reference_time)

        processed = ProcessedJobData(
            linkedin_job_id=merged["linkedin_job_id"],
            title=title,
            company_name=normalize_company_name(merged["company_name"]),
            company_url=merged["company_url"],
            job_url=normalized_url,
            normalized_job_url=normalized_url,
            location=location,
            country=infer_country(location),
            workplace_type=workplace_type,
            employment_type=employment_type,
            experience_level=experience_level,
            salary_min=salary.minimum,
            salary_max=salary.maximum,
            salary_currency=salary.currency,
            salary_period=salary.period,
            salary_text=salary.raw_text,
            description=description,
            required_skills=skills,
            applicant_count=applicant_count,
            easy_apply=merged["easy_apply"],
            posted_date=posted_date,
            relative_posted_time=merged["posted_text"],
            recruiter_name=merged["recruiter_name"],
            recruiter_profile_url=merged["recruiter_profile_url"],
        )

        status = self._classify(detail, processed)
        processed.processing_status = status
        processed.processing_warnings = warnings

        return JobProcessingResult(job=processed, status=status, warnings=warnings)

    @staticmethod
    def _classify(detail: JobDetailData | None, job: ProcessedJobData) -> str:
        """Classify a valid job as complete or partial."""
        core_complete = (
            detail is not None
            and bool(job.description)
            and bool(job.employment_type)
            and bool(job.experience_level)
        )
        return (
            ProcessingStatus.COMPLETE.value
            if core_complete
            else ProcessingStatus.PARTIAL.value
        )
