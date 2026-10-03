import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
from app.schemas.bias import (
    BiasCategory,
    BiasSeverity,
    BiasFlag,
    JDBiasAudit,
)
from app.schemas.domain import JobDescription, RequirementCategory

class BiasRule:
    def __init__(
        self,
        category: BiasCategory,
        severity: BiasSeverity,
        pattern: re.Pattern,
        explanation: str,
        inclusive_alternative: str,
    ):
        self.category = category
        self.severity = severity
        self.pattern = pattern
        self.explanation = explanation
        self.inclusive_alternative = inclusive_alternative

# Curated bias and exclusionary phrasing rules
BIAS_RULES: List[BiasRule] = [
    # 1. GENDER-CODED & HYPER-AGGRESSIVE PHRASING
    BiasRule(
        category=BiasCategory.GENDER_CODED,
        severity=BiasSeverity.HIGH,
        pattern=re.compile(r'\b(rock[\s\-]?star(?:s)?|ninja(?:s)?|wizard(?:s)?|guru(?:s)?)\b', re.IGNORECASE),
        explanation="Hyper-masculine jargon and superhero terminology research shows discourages female and underrepresented candidates while having zero correlation with software competence.",
        inclusive_alternative="Replace with 'skilled software engineer', 'collaborative developer', or specific technical proficiencies."
    ),
    BiasRule(
        category=BiasCategory.GENDER_CODED,
        severity=BiasSeverity.MEDIUM,
        pattern=re.compile(r'\b(work\s+hard[\s,]+play\s+hard|crush\s+(?:it|the\s+competition)|beast\s+mode|killer\s+instinct)\b', re.IGNORECASE),
        explanation="Burnout-heavy, hyper-aggressive corporate culture phrasing signals exclusionary work-life balance and alienates candidates with family obligations.",
        inclusive_alternative="Focus on team collaboration, curiosity, and sustainable problem-solving."
    ),
    BiasRule(
        category=BiasCategory.GENDER_CODED,
        severity=BiasSeverity.MEDIUM,
        pattern=re.compile(r'\b(dominant|dominate\s+the\s+market|aggressive\s+(?:growth|personality|attitude)|ruthless|alpha)\b', re.IGNORECASE),
        explanation="Overly aggressive phrasing creates a perception of an adversarial or hostile work culture.",
        inclusive_alternative="Use 'impact-oriented', 'driven by excellence', or 'proactive'."
    ),

    # 2. PEDIGREE & DEGREE GATEKEEPING
    BiasRule(
        category=BiasCategory.PEDIGREE_DEGREE,
        severity=BiasSeverity.HIGH,
        pattern=re.compile(r'\b(tier[\s\-]1\s+(?:colleges?|universit(?:y|ies)|institutes?|engineering)|ivy[\s\-]league|top[\s\-]10\s+(?:colleges?|universit(?:y|ies)|institutes?|engineering|schools?)|premier\s+institutes?\s+only)\b', re.IGNORECASE),
        explanation="Restricting roles strictly to elite universities introduces socioeconomic bias and excludes exceptional self-taught or diverse-background talent.",
        inclusive_alternative="Evaluate candidates on practical skills, code repositories, and demonstrable project outcomes regardless of institutional pedigree."
    ),
    BiasRule(
        category=BiasCategory.PEDIGREE_DEGREE,
        severity=BiasSeverity.MEDIUM,
        pattern=re.compile(r'\b(strictly\s+(?:b\.?tech|computer\s+science)\s+(?:graduates?\s+)?only|strict\s+4[\s\-]year\s+cs\s+degree\s+only|no\s+bootcamps?|no\s+self[\s\-]taught)\b', re.IGNORECASE),
        explanation="Inflexible degree-only filters without practical experience equivalence exclude highly capable bootcamp graduates and self-taught software engineers.",
        inclusive_alternative="Add 'B.S. in Computer Science or equivalent practical experience/portfolio'."
    ),

    # 3. AGE & GENERATIONAL CODING
    BiasRule(
        category=BiasCategory.AGE_GENERATIONAL,
        severity=BiasSeverity.HIGH,
        pattern=re.compile(r'\b(digital\s+native(?:s)?|young\s+and\s+(?:energetic|dynamic)|recent\s+graduates?\s+only|fresh\s+blood)\b', re.IGNORECASE),
        explanation="Phrasing targeting youth or generational labels ('digital native') constitutes age bias and discourages non-traditional career switchers.",
        inclusive_alternative="Specify concrete technological proficiencies rather than generational labels."
    ),

    # 4. ABLEIST & PHYSICAL EXCLUSION
    BiasRule(
        category=BiasCategory.ABLEIST_PHYSICAL,
        severity=BiasSeverity.HIGH,
        pattern=re.compile(r'\b(must\s+lift\s+\d+\s*(?:lbs|pounds|kg)|stand\s+for\s+extended\s+periods|stand\s+all\s+day)\b', re.IGNORECASE),
        explanation="Physical demands in a software engineering position introduce ableist barriers unless physically essential to the role.",
        inclusive_alternative="Remove non-essential physical requirements from desk software engineering positions."
    ),
    BiasRule(
        category=BiasCategory.ABLEIST_PHYSICAL,
        severity=BiasSeverity.MEDIUM,
        pattern=re.compile(r'\b(native\s+english\s+speaker\s+only|flawless\s+(?:native\s+)?accent)\b', re.IGNORECASE),
        explanation="Demanding 'native speaker' rather than technical language proficiency discriminates against qualified multilingual candidates.",
        inclusive_alternative="State 'Strong professional written and verbal communication skills in English'."
    ),
]

class JDBiasDetector:
    """
    Local, deterministic Job Description Bias & Inclusivity Auditor (Bonus Task 1).
    Scans the raw JD text and extracted requirements to flag exclusionary phrasing,
    calculate an inclusivity score (0–100), and suggest actionable inclusive alternatives.
    """

    def __init__(self, rules: Optional[List[BiasRule]] = None):
        self.rules = rules or BIAS_RULES

    def _extract_context(self, text: str, match_start: int, match_end: int) -> str:
        """
        Extracts the surrounding sentence or line for context snippet.
        """
        # Look backwards for newline or sentence boundary (. ! ?)
        start = match_start
        while start > 0 and text[start - 1] not in ('\n', '.', '!', '?'):
            start -= 1

        # Look forwards for newline or sentence boundary
        end = match_end
        while end < len(text) and text[end] not in ('\n', '.', '!', '?'):
            end += 1

        snippet = text[start:end].strip()
        # Clean up excessive whitespace
        snippet = re.sub(r'\s+', ' ', snippet)
        return snippet

    def _audit_experience_ceilings(self, jd: JobDescription, raw_text: str) -> List[BiasFlag]:
        """
        Audits whether an entry-level/internship role is placing unrealistic multi-year experience demands.
        """
        flags: List[BiasFlag] = []
        is_intern_or_junior = False

        title_lower = (jd.title or "").lower()
        if any(term in title_lower for term in ["intern", "internship", "junior", "entry level", "fresher", "trainee", "associate"]):
            is_intern_or_junior = True
        elif any(term in raw_text.lower() for term in ["internship", "intern role", "entry-level", "freshers"]):
            is_intern_or_junior = True

        if is_intern_or_junior:
            for req in jd.requirements:
                if req.category == RequirementCategory.EXPERIENCE or req.min_years:
                    years = req.min_years or 0
                    if not years:
                        # Extract years from text if min_years wasn't populated
                        m = re.search(r'(\d+)\+?\s*years?', req.requirement_text, re.IGNORECASE)
                        if m:
                            years = float(m.group(1))

                    if years >= 3.0:
                        flags.append(
                            BiasFlag(
                                id=f"flag_{uuid.uuid4().hex[:8]}",
                                category=BiasCategory.UNREALISTIC_EXPERIENCE,
                                severity=BiasSeverity.HIGH,
                                matched_text=f"{years:g}+ years experience",
                                context_snippet=req.requirement_text,
                                explanation=f"Demanding {years:g}+ years of experience for an internship/junior role creates an impossible barrier for target student applicants.",
                                inclusive_alternative="Adjust requirement to 'Demonstrated academic coursework, personal projects, or open-source contributions'."
                            )
                        )
                    elif years >= 2.0:
                        flags.append(
                            BiasFlag(
                                id=f"flag_{uuid.uuid4().hex[:8]}",
                                category=BiasCategory.UNREALISTIC_EXPERIENCE,
                                severity=BiasSeverity.MEDIUM,
                                matched_text=f"{years:g}+ years experience",
                                context_snippet=req.requirement_text,
                                explanation=f"Requiring {years:g}+ years for an internship may unnecessarily restrict qualified candidates.",
                                inclusive_alternative="Consider accepting hands-on project experience or 0–1 year of internship experience."
                            )
                        )
        return flags

    def audit_jd(self, jd: JobDescription, raw_text: Optional[str] = None) -> JDBiasAudit:
        """
        Performs complete bias & inclusivity audit on the given Job Description.
        """
        text_to_scan = raw_text or jd.raw_text or jd.normalized_text or ""
        flags: List[BiasFlag] = []
        seen_matches = set()

        # 1. Scan text with curated bias rules
        for rule in self.rules:
            for match in rule.pattern.finditer(text_to_scan):
                matched_phrase = match.group(0).strip()
                normalized_match = matched_phrase.lower()
                
                # Deduplicate identical matched phrases
                if normalized_match in seen_matches:
                    continue
                seen_matches.add(normalized_match)

                context = self._extract_context(text_to_scan, match.start(), match.end())
                flags.append(
                    BiasFlag(
                        id=f"flag_{uuid.uuid4().hex[:8]}",
                        category=rule.category,
                        severity=rule.severity,
                        matched_text=matched_phrase,
                        context_snippet=context or matched_phrase,
                        explanation=rule.explanation,
                        inclusive_alternative=rule.inclusive_alternative,
                    )
                )

        # 2. Check for experience threshold anomalies in entry-level/intern JDs
        exp_flags = self._audit_experience_ceilings(jd, text_to_scan)
        for ef in exp_flags:
            if ef.matched_text.lower() not in seen_matches:
                seen_matches.add(ef.matched_text.lower())
                flags.append(ef)

        # 3. Calculate Inclusivity Score (100 base, deductions based on severity)
        score = 100
        for flag in flags:
            if flag.severity == BiasSeverity.HIGH:
                score -= 15
            elif flag.severity == BiasSeverity.MEDIUM:
                score -= 8
            else:
                score -= 4

        score = max(0, min(100, score))

        # 4. Determine Grade
        if score >= 95:
            grade = "A+"
        elif score >= 85:
            grade = "A"
        elif score >= 70:
            grade = "B"
        elif score >= 50:
            grade = "C"
        else:
            grade = "D"

        # 5. Executive Summary
        if len(flags) == 0:
            summary = "The Job Description demonstrates exemplary inclusive language with zero detected exclusionary filters or biased phrasing."
            bias_free = True
        else:
            high_count = sum(1 for f in flags if f.severity == BiasSeverity.HIGH)
            med_count = sum(1 for f in flags if f.severity == BiasSeverity.MEDIUM)
            summary = (
                f"Audited {len(flags)} potential phrasing concern(s) ({high_count} High, {med_count} Medium). "
                f"Addressing these suggestions will maximize the diversity and quality of the applicant pool."
            )
            bias_free = (high_count == 0 and med_count == 0)

        return JDBiasAudit(
            inclusivity_score=score,
            inclusivity_grade=grade,
            total_flags=len(flags),
            flags=flags,
            summary=summary,
            bias_free=bias_free
        )
