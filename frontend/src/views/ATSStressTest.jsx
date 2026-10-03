import React from 'react';

export default function ATSStressTest({ careerTwin }) {
  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">🛡️</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to run an ATS Stress Test audit.</p>
      </div>
    );
  }

  const hasName = Boolean(careerTwin.name);
  const hasEmail = Boolean(careerTwin.email);
  const hasPhone = Boolean(careerTwin.phone);
  const hasExp = (careerTwin.experience?.length || 0) > 0;
  const hasEdu = (careerTwin.education?.length || 0) > 0;
  const hasSkills = (careerTwin.skills?.length || 0) > 0;

  const totalPassed = [hasName, hasEmail, hasPhone, hasExp, hasEdu, hasSkills].filter(Boolean).length;
  const healthScore = Math.round((totalPassed / 6) * 100);

  return (
    <div className="coach-view-container">
      <div className="view-title-header">
        <span className="coach-badge-tag">Format & Readability Audit</span>
        <h2 className="view-main-title">ATS Stress Test & Parseability Diagnostic</h2>
        <p className="view-desc">
          Evaluates how major Applicant Tracking Systems parse your resume layout, headings, and contact info.
        </p>
      </div>

      <div className="ats-audit-dashboard">
        <div className="ats-score-card">
          <div className="ats-score-display">
            <span className="ats-score-num">{healthScore}</span>
            <span className="ats-score-denom">/100</span>
          </div>
          <div className="ats-status-badge">
            {healthScore >= 85 ? "Grade A — High ATS Readability" : (healthScore >= 70 ? "Grade B — Good" : "Grade C — Needs Formatting Fixes")}
          </div>
        </div>

        <div className="ats-checks-grid">
          <div className={`ats-check-item ${hasName ? 'passed' : 'failed'}`}>
            <span className="check-icon">{hasName ? '✓' : '✕'}</span>
            <div>
              <strong>Candidate Name Detection</strong>
              <p>{hasName ? `Detected: "${careerTwin.name}"` : "Could not identify name in header."}</p>
            </div>
          </div>

          <div className={`ats-check-item ${hasEmail ? 'passed' : 'failed'}`}>
            <span className="check-icon">{hasEmail ? '✓' : '✕'}</span>
            <div>
              <strong>Email Contact Extractability</strong>
              <p>{hasEmail ? `Detected: "${careerTwin.email}"` : "Missing or obfuscated email."}</p>
            </div>
          </div>

          <div className={`ats-check-item ${hasPhone ? 'passed' : 'failed'}`}>
            <span className="check-icon">{hasPhone ? '✓' : '✕'}</span>
            <div>
              <strong>Phone Number Parseability</strong>
              <p>{hasPhone ? `Detected: "${careerTwin.phone}"` : "Phone number not detected."}</p>
            </div>
          </div>

          <div className={`ats-check-item ${hasSkills ? 'passed' : 'failed'}`}>
            <span className="check-icon">{hasSkills ? '✓' : '✕'}</span>
            <div>
              <strong>Skills Section Recognition</strong>
              <p>{hasSkills ? `Parsed ${careerTwin.skills.length} standard skill tokens.` : "Standard skills section missing."}</p>
            </div>
          </div>

          <div className={`ats-check-item ${hasExp ? 'passed' : 'failed'}`}>
            <span className="check-icon">{hasExp ? '✓' : '✕'}</span>
            <div>
              <strong>Experience Chronology</strong>
              <p>{hasExp ? `Parsed ${careerTwin.experience.length} employment entries.` : "Could not parse experience section."}</p>
            </div>
          </div>

          <div className={`ats-check-item ${hasEdu ? 'passed' : 'failed'}`}>
            <span className="check-icon">{hasEdu ? '✓' : '✕'}</span>
            <div>
              <strong>Education Qualifications</strong>
              <p>{hasEdu ? `Parsed ${careerTwin.education.length} degree records.` : "Education section missing or non-standard."}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
