import React, { useState, useRef, useMemo } from 'react';
import { coachApi } from '../services/api';

export default function JobFit({ careerTwin, onHandoffToResumeCoach }) {
  const [jdFile, setJdFile] = useState(null);
  const [jdText, setJdText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [fitData, setFitData] = useState(null);
  const [error, setError] = useState(null);
  const [activeFilter, setActiveFilter] = useState('ALL'); // 'ALL' | 'REQUIRED' | 'PREFERRED' | 'VISIBILITY' | 'EXPERIENCE' | 'MATCHED'
  const [selectedReqForModal, setSelectedReqForModal] = useState(null);
  const jdInputRef = useRef(null);

  const rawRequirements = fitData?.job_fit_analysis?.requirements;

  const filteredRequirements = useMemo(() => {
    const reqs = rawRequirements || [];
    return reqs.filter(req => {
      if (activeFilter === 'REQUIRED') return req.is_required;
      if (activeFilter === 'PREFERRED') return !req.is_required;
      if (activeFilter === 'MATCHED') return req.status === 'MATCHED';
      if (activeFilter === 'VISIBILITY') return req.gap_type === 'RESUME_VISIBILITY_GAP';
      if (activeFilter === 'EXPERIENCE') return req.gap_type === 'EXPERIENCE_GAP';
      return true;
    });
  }, [rawRequirements, activeFilter]);

  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">🎯</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to analyze your fit against target jobs.</p>
      </div>
    );
  }

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setJdFile(file);
      setJdText('');
      setError(null);
    }
  };

  const handleRunAnalysis = async () => {
    if (!jdFile && !jdText.trim()) {
      setError("Please provide a Job Description PDF or paste JD requirements text.");
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      const res = await coachApi.evaluateJobFit(careerTwin.candidate_id, jdFile, jdText.trim() || null);
      setFitData(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const analysis = fitData?.job_fit_analysis;
  const allReqs = rawRequirements || [];

  const handleHandoff = (req) => {
    if (!onHandoffToResumeCoach) return;
    
    // Find matching opportunity payload if available
    const opp = analysis?.improvement_opportunities?.find(o => o.requirement_id === req.requirement_id);
    const payload = opp?.handoff_payload || {
      requirement_id: req.requirement_id,
      requirement_text: req.requirement_text,
      target_role: analysis?.target_role || fitData?.job_title || "Target Role",
      priority: req.priority,
      gap_type: req.gap_type,
      can_rewrite: req.gap_type === 'RESUME_VISIBILITY_GAP',
      evidence_ids: (req.evidence || []).map(e => e.evidence_id).filter(Boolean),
      existing_evidence_snippets: (req.evidence || []).map(e => e.source_text),
      missing_elements: req.missing_evidence || [],
      action_prompt: req.candidate_action
    };

    onHandoffToResumeCoach(payload);
  };

  return (
    <div className="coach-view-container">
      <div className="view-title-header">
        <span className="coach-badge-tag">Target Role Alignment</span>
        <h2 className="view-main-title">Resume × Job Fit Diagnostic</h2>
        <p className="view-desc">
          Compare your verified Career Twin against any target Job Description.
          Our deterministic hybrid evaluator reveals fulfilled qualifications, partial matches, and critical missing skills.
        </p>
      </div>

      {/* Input Selector Card */}
      <div className="jobfit-input-card">
        <div className="input-split-grid">
          {/* File Upload Option */}
          <div 
            className={`dropzone-mini ${jdFile ? 'active' : ''}`}
            onClick={() => jdInputRef.current?.click()}
          >
            <span className="dropzone-icon">📄</span>
            <h4>{jdFile ? jdFile.name : "Upload Target JD PDF"}</h4>
            <p>{jdFile ? `${(jdFile.size / 1024).toFixed(1)} KB` : "Click to select target job posting"}</p>
            <input 
              type="file" 
              ref={jdInputRef} 
              onChange={handleFileSelect} 
              accept=".pdf,application/pdf" 
              className="file-input-hidden" 
            />
          </div>

          {/* Text Paste Option */}
          <div className="textarea-wrap">
            <textarea
              placeholder="Or paste target Job Description text / requirements here..."
              value={jdText}
              onChange={(e) => { setJdText(e.target.value); setJdFile(null); }}
              rows={4}
              className="jd-textarea"
            />
          </div>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="fit-action-row">
          <button 
            className="btn-primary" 
            onClick={handleRunAnalysis}
            disabled={isAnalyzing || (!jdFile && !jdText.trim())}
          >
            {isAnalyzing ? "Evaluating Hybrid Signals..." : "Evaluate Fit & Gaps →"}
          </button>
        </div>
      </div>

      {/* Fit Results Display */}
      {fitData && (
        <div className="fit-results-section">
          {/* 1. Target Role & Requirement Coverage Card (Section 12) */}
          <div className="coverage-hero-card">
            <div className="coverage-header-row">
              <div>
                <span className="target-role-badge">Target Role Evaluation</span>
                <h3 className="target-role-title">
                  {analysis?.target_role || fitData.job_title}
                  {analysis?.company && <span style={{ fontWeight: 400, color: '#64748B' }}> at {analysis.company}</span>}
                </h3>
              </div>
              <div>
                <span className="grounding-tag">
                  🔒 Grounded in Candidate Evidence Vault
                </span>
              </div>
            </div>

            <div className="coverage-stats-grid">
              <div className="coverage-stat-box">
                <div className="coverage-stat-value">
                  {analysis?.fit_summary ? analysis.fit_summary.evidence_coverage_score.toFixed(0) : fitData.fit_score.toFixed(0)}
                  <span style={{ fontSize: '1rem', color: '#64748B' }}>%</span>
                </div>
                <div className="coverage-stat-label">Evidence Coverage</div>
              </div>

              <div className="coverage-stat-box">
                <div className="coverage-stat-value">
                  {analysis?.fit_summary?.required_matched ?? fitData.score_breakdown?.required_matched_count ?? 0}
                  <span style={{ fontSize: '1.2rem', color: '#94A3B8' }}>/</span>
                  {analysis?.fit_summary?.required_total ?? fitData.score_breakdown?.required_total_count ?? 0}
                </div>
                <div className="coverage-stat-label">Required Criteria Supported</div>
              </div>

              <div className="coverage-stat-box">
                <div className="coverage-stat-value">
                  {analysis?.fit_summary?.preferred_matched ?? 0}
                  <span style={{ fontSize: '1.2rem', color: '#94A3B8' }}>/</span>
                  {analysis?.fit_summary?.preferred_total ?? 0}
                </div>
                <div className="coverage-stat-label">Preferred Criteria Supported</div>
              </div>

              <div className="coverage-stat-box">
                <div className="coverage-stat-value" style={{ color: '#4F46E5', fontSize: '1.4rem' }}>
                  {analysis?.fit_summary?.evidence_strength || "Strong"}
                </div>
                <div className="coverage-stat-label">Evidence Strength</div>
              </div>
            </div>

            <p style={{ marginTop: '1rem', fontSize: '0.9rem', color: '#4B5563', lineHeight: 1.5 }}>
              {analysis?.fit_summary?.narrative || fitData.coaching_summary}
            </p>

            {/* Gap Classification Metric Pills */}
            <div className="coverage-pills-row">
              <span className="coverage-metric-pill matched">
                ✓ {analysis?.matched_requirements?.length ?? 0} Verified Matches
              </span>
              <span className="coverage-metric-pill visibility">
                △ {analysis?.fit_summary?.visibility_gaps_count ?? 0} Visibility Opportunities
              </span>
              <span className="coverage-metric-pill experience">
                ✕ {analysis?.fit_summary?.experience_gaps_count ?? 0} Genuine Experience Gaps
              </span>
              {analysis?.fit_summary?.not_verifiable_count > 0 && (
                <span className="coverage-metric-pill unverifiable">
                  ○ {analysis.fit_summary.not_verifiable_count} Non-Verifiable Qualities
                </span>
              )}
            </div>
          </div>

          {/* 2. Inclusivity Advisory Card if JD Bias Detected (Section 10) */}
          {fitData.bias_audit && fitData.bias_audit.total_flags > 0 && (
            <div className="jd-bias-warning-card">
              <div className="warning-top">
                <span className="warning-shield">🛡️</span>
                <div>
                  <strong>Job Inclusivity Advisory: </strong>
                  The target posting contains {fitData.bias_audit.total_flags} potentially exclusionary phrasing flag(s).
                </div>
              </div>
              <ul className="bias-flags-mini-list">
                {fitData.bias_audit.flags.map((f) => (
                  <li key={f.id}>
                    <em>"{f.matched_text}"</em> — {f.explanation}
                  </li>
                ))}
              </ul>
            </div>
          )}


          {/* Bulk Improve CTA */}
          <div className="bulk-improve-action" style={{marginTop: '1rem', marginBottom: '1rem', textAlign: 'center'}}>
            <button 
              className="btn-primary" 
              style={{fontSize: '1.1rem', padding: '1rem 2rem', background: 'linear-gradient(135deg, #4f46e5, #7c3aed)'}}
              onClick={() => {
                if (!onHandoffToResumeCoach || !fitData?.job_fit_analysis) return;
                
                const gaps = (fitData.job_fit_analysis.requirements || []).filter(req => 
                  req.gap_type === 'RESUME_VISIBILITY_GAP' || req.gap_type === 'EXPERIENCE_GAP' || req.gap_type === 'NOT_VERIFIABLE'
                );
                
                const payloads = gaps.map(req => {
                  const opp = fitData.job_fit_analysis.improvement_opportunities?.find(o => o.requirement_id === req.requirement_id);
                  return opp?.handoff_payload || {
                    requirement_id: req.requirement_id,
                    requirement_text: req.requirement_text,
                    target_role: fitData.job_fit_analysis.target_role || fitData.job_title || "Target Role",
                    priority: req.priority,
                    gap_type: req.gap_type,
                    can_rewrite: req.gap_type === 'RESUME_VISIBILITY_GAP',
                    evidence_ids: (req.evidence || []).map(e => e.evidence_id).filter(Boolean),
                    existing_evidence_snippets: (req.evidence || []).map(e => e.source_text),
                    missing_elements: req.missing_evidence || [],
                    action_prompt: req.candidate_action
                  };
                });

                onHandoffToResumeCoach({ bulk: true, items: payloads, target_role: fitData.job_title });
              }}
            >
              ✨ Improve My Resume for This Job
            </button>
          </div>

          {/* 3. Requirement Breakdown Filter Bar */}
          <div className="jobfit-filter-bar">
            <button
              className={`jobfit-filter-btn ${activeFilter === 'ALL' ? 'active' : ''}`}
              onClick={() => setActiveFilter('ALL')}
            >
              All Requirements ({allReqs.length})
            </button>
            <button
              className={`jobfit-filter-btn ${activeFilter === 'REQUIRED' ? 'active' : ''}`}
              onClick={() => setActiveFilter('REQUIRED')}
            >
              Required Only ({analysis?.required_requirements?.length ?? 0})
            </button>
            <button
              className={`jobfit-filter-btn ${activeFilter === 'PREFERRED' ? 'active' : ''}`}
              onClick={() => setActiveFilter('PREFERRED')}
            >
              Preferred Only ({analysis?.preferred_requirements?.length ?? 0})
            </button>
            <button
              className={`jobfit-filter-btn vis-btn ${activeFilter === 'VISIBILITY' ? 'active' : ''}`}
              onClick={() => setActiveFilter('VISIBILITY')}
            >
              Visibility Opportunities ({analysis?.fit_summary?.visibility_gaps_count ?? 0})
            </button>
            <button
              className={`jobfit-filter-btn ${activeFilter === 'EXPERIENCE' ? 'active' : ''}`}
              onClick={() => setActiveFilter('EXPERIENCE')}
            >
              Experience Gaps ({analysis?.fit_summary?.experience_gaps_count ?? 0})
            </button>
            <button
              className={`jobfit-filter-btn ${activeFilter === 'MATCHED' ? 'active' : ''}`}
              onClick={() => setActiveFilter('MATCHED')}
            >
              Verified Matches ({analysis?.matched_requirements?.length ?? 0})
            </button>
          </div>

          {/* 4. Requirements Cards List */}
          <div className="requirements-list">
            {filteredRequirements.map((req) => {
              const statusClass = req.status === 'MATCHED' ? 'card-matched' : (req.status === 'PARTIAL' ? 'card-partial' : 'card-missing');
              const badgeClass = req.status === 'MATCHED' ? 'status-matched' : (req.status === 'PARTIAL' ? 'status-partial' : 'status-missing');

              return (
                <div key={req.requirement_id} className={`req-item-card ${statusClass}`} onClick={() => setSelectedReqForModal(req)}>
                  <div className="req-card-top">
                    <div className="req-badges-cluster">
                      <span className={`badge-status ${badgeClass}`}>{req.status}</span>
                      <span className={`badge-priority ${req.is_required ? 'required' : ''}`}>
                        {req.priority}
                      </span>
                      {req.gap_type === 'RESUME_VISIBILITY_GAP' && (
                        <span className="badge-gap-type visibility-type">Resume Visibility Opportunity</span>
                      )}
                      {req.gap_type === 'EXPERIENCE_GAP' && (
                        <span className="badge-gap-type experience-type">Genuine Experience Gap</span>
                      )}
                      {req.gap_type === 'NOT_VERIFIABLE' && (
                        <span className="badge-gap-type unverifiable-type">Not Verifiable on CV</span>
                      )}
                    </div>
                    <span style={{ fontSize: '0.78rem', color: '#64748B' }}>
                      Evidence Match: {(req.combined_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <h4 className="req-text-title">{req.requirement_text}</h4>

                  {/* Tenure comparison if present */}
                  {req.required_months && (
                    <div className="req-tenure-tag">
                      ⏱ Required: {(req.required_months / 12).toFixed(1)} yrs • Verified: {req.verified_months ? (req.verified_months / 12).toFixed(1) : 0} yrs
                      {req.tenure_gap_months > 0 && ` • Gap: ${(req.tenure_gap_months / 12).toFixed(1)} yrs`}
                    </div>
                  )}

                  {/* Supporting Evidence Citations */}
                  {req.evidence && req.evidence.length > 0 && (
                    <div className="req-evidence-citations-list">
                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', marginBottom: '0.35rem' }}>
                        Supporting Resume Citations:
                      </div>
                      {req.evidence.map((cit, cIdx) => (
                        <div key={cIdx} className="citation-item">
                          <span className="citation-check">✓</span>
                          <span className="citation-quote">"{cit.source_text}"</span>
                          <span className="citation-meta">
                            {cit.source_section ? `(${cit.source_section} • Page ${cit.page_number || 1})` : ''}
                            {cit.evidence_id ? ` [${cit.evidence_id}]` : ''}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Missing elements tags if partial or missing */}
                  {req.missing_evidence && req.missing_evidence.length > 0 && (
                    <div className="req-missing-row">
                      <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Missing in resume:</span>
                      {req.missing_evidence.map((m, mIdx) => (
                        <span key={mIdx} className="missing-tag">✕ {m}</span>
                      ))}
                    </div>
                  )}

                  {/* Action recommendation */}
                  {req.candidate_action && (
                    <div className={`candidate-action-box ${
                      req.gap_type === 'RESUME_VISIBILITY_GAP' ? 'action-visibility' : 
                      (req.gap_type === 'EXPERIENCE_GAP' ? 'action-experience' : 
                      (req.gap_type === 'NOT_VERIFIABLE' ? 'action-unverifiable' : ''))
                    }`}>
                      <strong>Next Action: </strong>
                      {req.candidate_action}
                    </div>
                  )}

                  {/* Handoff to Resume Coach button (Section 14) */}
                  <div className="req-card-actions">
                    {req.gap_type === 'RESUME_VISIBILITY_GAP' ? (
                      <button 
                        className="btn-improve-resume"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleHandoff(req);
                        }}
                      >
                        Improve Resume with Coach →
                      </button>
                    ) : req.gap_type === 'EXPERIENCE_GAP' ? (
                      <span className="ethical-no-rewrite-notice">
                        ⚠️ No verified evidence. Resume rewriting cannot fabricate ungrounded skills.
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>

          {/* 5. Interactive Detail Modal (Section 13) */}
          {selectedReqForModal && (
            <div className="jobfit-modal-backdrop" onClick={() => setSelectedReqForModal(null)}>
              <div className="jobfit-modal-card" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header-row">
                  <div>
                    <span className={`badge-status status-${selectedReqForModal.status.toLowerCase()}`}>
                      {selectedReqForModal.status}
                    </span>
                    <h3 style={{ margin: '0.5rem 0 0.25rem', fontSize: '1.25rem' }}>
                      {selectedReqForModal.requirement_text}
                    </h3>
                    <div style={{ fontSize: '0.8rem', color: '#64748B' }}>
                      Category: {selectedReqForModal.category} • Priority: {selectedReqForModal.priority}
                    </div>
                  </div>
                  <button className="modal-close-btn" onClick={() => setSelectedReqForModal(null)}>×</button>
                </div>

                <div style={{ margin: '1rem 0' }}>
                  <h4 style={{ fontSize: '0.9rem', marginBottom: '0.4rem', color: '#1E293B' }}>Evaluation Rationale</h4>
                  <p style={{ fontSize: '0.88rem', color: '#475569', lineHeight: 1.5, background: '#F8FAFC', padding: '0.75rem', borderRadius: '8px' }}>
                    {selectedReqForModal.explanation}
                  </p>
                </div>

                {selectedReqForModal.evidence?.length > 0 && (
                  <div style={{ margin: '1rem 0' }}>
                    <h4 style={{ fontSize: '0.9rem', marginBottom: '0.4rem', color: '#1E293B' }}>
                      Verified Evidence in Vault ({selectedReqForModal.evidence.length})
                    </h4>
                    {selectedReqForModal.evidence.map((cit, idx) => (
                      <div key={idx} style={{ padding: '0.6rem', border: '1px solid #E2E8F0', borderRadius: '8px', marginBottom: '0.4rem', fontSize: '0.84rem' }}>
                        <div style={{ fontStyle: 'italic', marginBottom: '0.25rem' }}>"{cit.source_text}"</div>
                        <div style={{ fontSize: '0.74rem', color: '#64748B' }}>
                          Section: {cit.source_section || 'Resume'} • Page: {cit.page_number || 1} {cit.evidence_id ? `• Citation: ${cit.evidence_id}` : ''}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ margin: '1rem 0' }}>
                  <h4 style={{ fontSize: '0.9rem', marginBottom: '0.4rem', color: '#1E293B' }}>Candidate Actionable Guidance</h4>
                  <div className={`candidate-action-box ${
                    selectedReqForModal.gap_type === 'RESUME_VISIBILITY_GAP' ? 'action-visibility' : 
                    (selectedReqForModal.gap_type === 'EXPERIENCE_GAP' ? 'action-experience' : 
                    (selectedReqForModal.gap_type === 'NOT_VERIFIABLE' ? 'action-unverifiable' : ''))
                  }`}>
                    {selectedReqForModal.candidate_action}
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.5rem' }}>
                  <button className="btn-secondary" onClick={() => setSelectedReqForModal(null)}>Close</button>
                  {selectedReqForModal.gap_type === 'RESUME_VISIBILITY_GAP' && (
                    <button 
                      className="btn-improve-resume"
                      onClick={() => {
                        handleHandoff(selectedReqForModal);
                        setSelectedReqForModal(null);
                      }}
                    >
                      Improve Resume with Coach →
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
