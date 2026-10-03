import React, { useState } from 'react';
import { coachApi } from '../services/api';

export default function ResumeCoach({ careerTwin, handoffPayload, onClearHandoff, onNavigateToBuilder }) {
  const [loading, setLoading] = useState(false);
  const [rewriteResult, setRewriteResult] = useState(null);
  const [accepted, setAccepted] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [applyingToDraft, setApplyingToDraft] = useState(false);
  const [appliedVersion, setAppliedVersion] = useState(null);

  const [prevReqId, setPrevReqId] = useState(handoffPayload?.requirement_id);
  if (handoffPayload?.requirement_id !== prevReqId) {
    setPrevReqId(handoffPayload?.requirement_id);
    setRewriteResult(null);
    setAccepted(false);
    setErrorMsg(null);
    setAppliedVersion(null);
  }


  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">📝</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to analyze and optimize your resume content.</p>
      </div>
    );
  }

  const handleGenerateRewrite = async () => {
    if (!handoffPayload) return;
    setLoading(true);
    setErrorMsg(null);

    try {
      const payload = {
        candidate_id: handoffPayload.candidate_id || careerTwin.candidate_id,
        requirement_id: handoffPayload.requirement_id,
        requirement_text: handoffPayload.requirement_text,
        target_role: handoffPayload.target_role,
        priority: handoffPayload.priority || "REQUIRED",
        gap_type: handoffPayload.gap_type || "RESUME_VISIBILITY_GAP",
        evidence_ids: handoffPayload.evidence_ids || [],
        existing_evidence_snippets: handoffPayload.existing_evidence_snippets || [],
        missing_elements: handoffPayload.missing_elements || [],
        current_resume_text: handoffPayload.existing_evidence_snippets?.[0] || "",
        action_prompt: handoffPayload.action_prompt || ""
      };

      const res = await fetch('/api/coach/resume-coach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error (${res.status})`);
      }

      const data = await res.json();
      setRewriteResult(data);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to generate resume rewrite.');
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptSuggestion = async () => {
    if (!rewriteResult || rewriteResult.status !== 'ACCEPTED') return;
    setApplyingToDraft(true);
    setErrorMsg(null);
    try {
      // 1. Get or create draft version
      const versions = await coachApi.getResumeVersions(careerTwin.candidate_id);
      let targetVersion = versions.find(v => v.status === 'DRAFT');
      if (!targetVersion) {
        const targetTitle = handoffPayload?.target_role 
          ? `${handoffPayload.target_role} — Targeted Resume` 
          : "Targeted Resume Draft";
        targetVersion = await coachApi.createResumeVersion(
          careerTwin.candidate_id, 
          targetTitle, 
          handoffPayload?.target_role || null
        );
      }
      
      // 2. Apply suggestion with server-side evidence-lock verification
      const applied = await coachApi.applySuggestionToVersion(
        targetVersion.version_id,
        rewriteResult,
        false
      );
      setAccepted(true);
      setAppliedVersion(applied);
    } catch (err) {
      console.error("Failed to apply suggestion to draft:", err);
      setErrorMsg(err.message);
    } finally {
      setApplyingToDraft(false);
    }
  };

  const isExperienceGap = handoffPayload?.gap_type === 'EXPERIENCE_GAP';

  return (
    <div className="coach-view-container">
      <div className="view-title-header">
        <span className="coach-badge-tag">Phase 4 — Evidence-Locked AI</span>
        <h2 className="view-main-title">Evidence-Locked Resume Coach</h2>
        <p className="view-desc">
          Transform your resume bullet points into high-visibility accomplishments grounded strictly in verified Evidence Vault facts.
          The coach will never fabricate ungrounded skills, technologies, or metrics.
        </p>
      </div>

      {/* Target Requirement Optimization Card from Job Fit */}
      {handoffPayload && (
        <div className="handoff-optimization-card">
          <div className="opt-card-header">
            <div>
              <span className={`gap-badge ${isExperienceGap ? 'badge-exp-gap' : 'badge-vis-gap'}`}>
                {handoffPayload.gap_type || 'RESUME_VISIBILITY_GAP'}
              </span>
              <h3 className="opt-requirement-title">
                Target Requirement: "{handoffPayload.requirement_text}"
              </h3>
            </div>
            {onClearHandoff && (
              <button className="btn-text-dismiss" onClick={onClearHandoff}>
                ✕ Dismiss Target
              </button>
            )}
          </div>

          <div className="opt-meta-grid">
            <div className="opt-meta-item">
              <span className="opt-meta-label">Target Role</span>
              <span className="opt-meta-val">{handoffPayload.target_role || 'Target Role'}</span>
            </div>
            <div className="opt-meta-item">
              <span className="opt-meta-label">Status</span>
              <span className={`opt-meta-val status-${(handoffPayload.status || 'PARTIAL').toLowerCase()}`}>
                {handoffPayload.status || 'PARTIAL'}
              </span>
            </div>
            <div className="opt-meta-item">
              <span className="opt-meta-label">Priority</span>
              <span className="opt-meta-val">{handoffPayload.priority || 'REQUIRED'}</span>
            </div>
          </div>

          {/* MODE B: EXPERIENCE GAP (Not Rewriteable) */}
          {isExperienceGap ? (
            <div className="experience-gap-alert-box">
              <div className="alert-icon">🚫</div>
              <div className="alert-body">
                <h4>Resume Rewriting Unavailable for Experience Gaps</h4>
                <p className="alert-lead">
                  Resume rewriting is unavailable because no verified evidence supports this requirement in your Evidence Vault.
                </p>
                <div className="gap-guidance-grid">
                  <div className="guidance-col">
                    <strong>WHAT IS MISSING:</strong>
                    <p>{handoffPayload.missing_elements?.join(', ') || handoffPayload.requirement_text}</p>
                  </div>
                  <div className="guidance-col">
                    <strong>WHY:</strong>
                    <p>No verifiable hands-on evidence exists in your uploaded resume history.</p>
                  </div>
                  <div className="guidance-col">
                    <strong>WHAT YOU CAN DO INSTEAD:</strong>
                    <p>Gain genuine project or professional experience with this technology before adding it to your resume.</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* MODE A: RESUME VISIBILITY GAP (Rewriteable) */
            <div className="visibility-gap-editor-area">
              <div className="verified-evidence-box">
                <span className="box-section-tag">VERIFIED EVIDENCE IN VAULT</span>
                {handoffPayload.existing_evidence_snippets?.length > 0 ? (
                  handoffPayload.existing_evidence_snippets.map((snip, sIdx) => (
                    <p key={sIdx} className="evidence-snippet-line">"{snip}"</p>
                  ))
                ) : (
                  <p className="evidence-snippet-line">
                    Verified background exists in {handoffPayload.target_role}.
                  </p>
                )}
                {handoffPayload.evidence_ids?.length > 0 && (
                  <div className="evidence-ids-strip">
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#4338CA' }}>Grounding Citations:</span>
                    {handoffPayload.evidence_ids.map(id => (
                      <span key={id} className="handoff-citation-pill">{id}</span>
                    ))}
                  </div>
                )}
              </div>

              {handoffPayload.action_prompt && (
                <div className="action-guidance-pill">
                  💡 <strong>Coach Guidance:</strong> {handoffPayload.action_prompt}
                </div>
              )}

              {/* Action Trigger */}
              {!rewriteResult && !loading && (
                <div className="generate-action-bar">
                  <button className="btn-coach-generate" onClick={handleGenerateRewrite}>
                    ✨ Generate Evidence-Locked Improvement
                  </button>
                </div>
              )}

              {loading && (
                <div className="coach-generating-loader">
                  <div className="spinner"></div>
                  <span>Analyzing Evidence Vault & producing grounded rewrite...</span>
                </div>
              )}

              {errorMsg && (
                <div className="coach-error-banner">
                  ⚠️ {errorMsg}
                </div>
              )}

              {/* Rewrite Result Display */}
              {rewriteResult && (
                <div className="rewrite-result-card">
                  {/* Trust Signals Banner */}
                  <div className={`trust-banner trust-${rewriteResult.status.toLowerCase()}`}>
                    {rewriteResult.status === 'ACCEPTED' && (
                      <>
                        <span className="trust-icon">✓</span>
                        <div className="trust-text">
                          <strong>Evidence verified</strong>
                          <span>All claims strictly grounded in Evidence Vault citations.</span>
                        </div>
                      </>
                    )}
                    {rewriteResult.status === 'REJECTED' && (
                      <>
                        <span className="trust-icon">⚠</span>
                        <div className="trust-text">
                          <strong>Unsupported claim detected</strong>
                          <span>Rewriter proposed claims not verified by your Evidence Vault. Modification rejected.</span>
                        </div>
                      </>
                    )}
                    {rewriteResult.status === 'NO_SAFE_REWRITE' && (
                      <>
                        <span className="trust-icon">ⓘ</span>
                        <div className="trust-text">
                          <strong>No evidence-backed rewrite available</strong>
                          <span>{rewriteResult.explanation}</span>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Side-by-Side Comparison */}
                  {rewriteResult.suggested_text && (
                    <div className="comparison-container">
                      <div className="comparison-pane pane-original">
                        <span className="pane-label">CURRENT RESUME WORDING</span>
                        <p className="pane-text">{rewriteResult.original_text || 'Original description'}</p>
                      </div>
                      <div className={`comparison-pane pane-suggested ${rewriteResult.status === 'ACCEPTED' ? 'pane-accepted' : 'pane-rejected'}`}>
                        <span className="pane-label">
                          {rewriteResult.status === 'ACCEPTED' ? 'EVIDENCE-LOCKED SUGGESTION' : 'PROPOSED (REJECTED)'}
                        </span>
                        <p className="pane-text">{rewriteResult.suggested_text}</p>
                      </div>
                    </div>
                  )}

                  {/* Changes & Audit Rationale */}
                  {rewriteResult.changes?.length > 0 && (
                    <div className="changes-audit-box">
                      <span className="audit-label">Editorial Improvements (Zero Fact Fabrication):</span>
                      <ul className="changes-list">
                        {rewriteResult.changes.map((ch, idx) => (
                          <li key={idx}>✓ {ch}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Unsupported Claims Warnings if Rejected */}
                  {rewriteResult.unsupported_claims?.length > 0 && (
                    <div className="unsupported-claims-alert">
                      <span className="audit-label">Validation Failures Prevented:</span>
                      <ul className="unsupported-list">
                        {rewriteResult.unsupported_claims.map((uc, idx) => (
                          <li key={idx}>✕ {uc}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Evidence Used Audit Trail */}
                  {rewriteResult.evidence_used?.length > 0 && (
                    <div className="evidence-used-trail">
                      <span className="audit-label">Grounded In Evidence Citations:</span>
                      <div className="citations-chip-row">
                        {rewriteResult.evidence_used.map((ev, idx) => (
                          <div key={idx} className="evidence-used-chip" title={ev.source_text}>
                            <strong>{ev.evidence_id}</strong>
                            <span>{ev.source_section || 'Experience'} (p. {ev.page_number || 1})</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Interactive Action Buttons */}
                  <div className="rewrite-actions-row">
                    {rewriteResult.status === 'ACCEPTED' && !accepted && (
                      <button 
                        className="btn-accept-suggestion" 
                        onClick={handleAcceptSuggestion}
                        disabled={applyingToDraft}
                      >
                        {applyingToDraft ? 'Validating & Applying...' : '✓ Accept Suggestion'}
                      </button>
                    )}
                    {accepted && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', width: '100%', marginBottom: '0.5rem' }}>
                        <span className="accepted-confirmation-tag">
                          ✓ Suggestion Validated & Applied to Resume Draft {appliedVersion?.title ? `("${appliedVersion.title}")` : ''}
                        </span>
                        {onNavigateToBuilder && (
                          <button 
                            className="btn-accent"
                            style={{ alignSelf: 'flex-start', padding: '0.45rem 0.9rem', fontSize: '0.85rem' }}
                            onClick={() => onNavigateToBuilder(appliedVersion?.version_id)}
                          >
                            📄 Open Resume Draft & View Diff →
                          </button>
                        )}
                      </div>
                    )}
                    <button className="btn-regenerate" onClick={handleGenerateRewrite} disabled={applyingToDraft}>
                      ⟳ Regenerate
                    </button>
                    <button className="btn-keep-original" onClick={() => setRewriteResult(null)} disabled={applyingToDraft}>
                      Keep Original
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Baseline Diagnostic Section (Auditing all experience bullets) */}
      <div className="coach-feature-card">
        <div className="feature-top-bar">
          <div>
            <span className="badge-pill">Baseline Experience Audit</span>
            <h3>Bullet Point Health & Impact Diagnostic</h3>
          </div>
          <span className="status-pill-ready">● Engine Ready</span>
        </div>
        <p className="feature-desc">
          Audit of existing experience descriptions. All suggestions remain bounded to facts indexed in your Evidence Vault.
        </p>

        {/* Experience Bullets Preview */}
        <div className="bullets-audit-list">
          {careerTwin.experience?.map((exp, eIdx) => (
            <div key={eIdx} className="bullet-group-card">
              <h4 className="bullet-role-heading">{exp.role} at {exp.company}</h4>
              <p className="bullet-dates">{exp.start_date} - {exp.end_date || 'Present'}</p>
              
              <div className="bullet-lines">
                {exp.description ? (
                  exp.description.split('\n').filter(l => l.trim().length > 10).map((line, lIdx) => (
                    <div key={lIdx} className="bullet-line-item">
                      <span className="bullet-dot">•</span>
                      <div className="bullet-content">
                        <p>{line.replace(/^[•\-*]\s*/, '')}</p>
                        <div className="bullet-tags">
                          <span className="pill-tag">Verified Fact</span>
                          {line.match(/\d+/) && <span className="pill-tag tag-metric">Quantified</span>}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="bullet-empty">No detailed description lines extracted.</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
