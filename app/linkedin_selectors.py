"""Centralized LinkedIn CSS selectors.

All LinkedIn selectors live here so that when LinkedIn changes its markup the
update happens in one place. Each group is an ordered list of fallback
selectors: parsers try them in order and use the first match. Prefer semantic
attributes and stable ``data-*`` hooks; avoid brittle ``nth-child`` chains and
deeply nested descendant selectors.

LinkedIn markup is not a stable public contract, so these selectors will need
periodic maintenance. Keeping them centralized is the mitigation, not a fix.
"""

# --- Search results: job cards ------------------------------------------------

SEARCH_JOB_CARDS: list[str] = [
    "li[data-job-card]",
    "div.job-search-card",
    "li.jobs-search-results__list-item",
    "div.base-card[data-entity-urn]",
]

# --- Card / detail shared fields ---------------------------------------------

JOB_TITLE: list[str] = [
    "[data-test-job-title]",
    "h3.base-search-card__title",
    "h1.top-card-layout__title",
    "a.job-card-list__title",
    "h2.job-title",
]

COMPANY_NAME: list[str] = [
    "[data-test-company-name]",
    "h4.base-search-card__subtitle",
    "a.topcard__org-name-link",
    "span.job-card-container__company-name",
]

LOCATION: list[str] = [
    "[data-test-job-location]",
    "span.job-search-card__location",
    "span.topcard__flavor--bullet",
    "span.job-card-container__metadata-item",
]

JOB_URL: list[str] = [
    "a[data-test-job-link]",
    "a.base-card__full-link",
    "a.job-card-list__title",
    "a.topcard__link",
]

COMPANY_URL: list[str] = [
    "a[data-test-company-link]",
    "a.topcard__org-name-link",
    "a.job-search-card__subtitle-link",
]

# Element that carries the numeric job id, usually via a data attribute.
JOB_ID_CONTAINERS: list[str] = [
    "[data-job-id]",
    "[data-entity-urn]",
    "[data-test-job-id]",
]
JOB_ID_ATTRIBUTES: list[str] = [
    "data-job-id",
    "data-entity-urn",
    "data-test-job-id",
]

POSTED_DATE: list[str] = [
    "[data-test-posted-date]",
    "time.job-search-card__listdate",
    "time.job-search-card__listdate--new",
    "span.posted-time-ago__text",
    "time",
]

EASY_APPLY: list[str] = [
    "[data-test-easy-apply]",
    "span.job-card-container__easy-apply-label",
    "button.jobs-apply-button--easy-apply",
    "li.job-search-card__easy-apply",
]

# --- Job detail only ----------------------------------------------------------

JOB_DESCRIPTION: list[str] = [
    "[data-test-job-description]",
    "div.show-more-less-html__markup",
    "div.description__text",
    "section.jobs-description__content",
]

SALARY: list[str] = [
    "[data-test-salary]",
    "div.salary.compensation__salary",
    "span.job-details-jobs-unified-top-card__salary",
]

APPLICANT_COUNT: list[str] = [
    "[data-test-applicant-count]",
    "figcaption.num-applicants__caption",
    "span.num-applicants__caption",
]

EMPLOYMENT_TYPE: list[str] = [
    "[data-test-employment-type]",
    "span.description__job-criteria-text--employment-type",
]

EXPERIENCE_LEVEL: list[str] = [
    "[data-test-experience-level]",
    "span.description__job-criteria-text--experience-level",
]

WORKPLACE_TYPE: list[str] = [
    "[data-test-workplace-type]",
    "span.job-details-jobs-unified-top-card__workplace-type",
]

RECRUITER_NAME: list[str] = [
    "[data-test-recruiter-name]",
    "h3.message-the-recruiter__name",
    "a.message-the-recruiter__profile-link span",
]

RECRUITER_PROFILE_URL: list[str] = [
    "a[data-test-recruiter-link]",
    "a.message-the-recruiter__profile-link",
]

# --- Page-state signal selectors ---------------------------------------------

CAPTCHA_ELEMENTS: list[str] = [
    "[data-test-captcha]",
    "iframe[src*='captcha']",
    "form[action*='checkpoint/challenge']",
    "div#captcha-internal",
    "input[name='captchaSiteKey']",
]

SIGNIN_WALL_ELEMENTS: list[str] = [
    "[data-test-signin-wall]",
    "div.authwall",
    "section.authwall-join-form",
    "form.google-auth__form",
    "button[data-tracking-control-name='auth_wall_desktop-login_sign-in-button']",
]

ACCESS_RESTRICTED_ELEMENTS: list[str] = [
    "[data-test-access-restricted]",
    "div.error-code-429",
    "section.rate-limit",
]

EMPTY_SEARCH_ELEMENTS: list[str] = [
    "[data-test-no-results]",
    "div.jobs-search-no-results-banner",
    "section.no-results",
    "p.jobs-search-no-results__text",
]

REMOVED_JOB_ELEMENTS: list[str] = [
    "[data-test-job-removed]",
    "figure.closed-job",
    "div.jobs-details-top-card__job-closed",
    "p.top-card-layout__flavor--closed-job",
]
