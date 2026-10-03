import React, { useState, useRef } from 'react';
import { coachApi } from '../services/api';

export default function RecruiterPortal() {
  // Navigation & Workflow state
  const [view, setView] = useState('upload'); // 'upload' | 'processing' | 'results'
  
  // File inputs
  const [jdFile, setJdFile] = useState(null);
  const [resumeFiles, setResumeFiles] = useState([]);
  const [uploadError, setUploadError] = useState(null);
  
  // Processing state
  const [processingStep, setProcessingStep] = useState('');
  
  // Analysis results
  const [analysisData, setAnalysisData] = useState(null);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [showBiasAudit, setShowBiasAudit] = useState(false);
  
  const jdInputRef = useRef(null);
  const resumeInputRef = useRef(null);

  // File selection handlers
  const handleJdSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Job Description must be a PDF file.');
      return;
    }
    setJdFile(file);
    setUploadError(null);
  };

  const handleResumeSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    const nonPdfs = files.filter(f => !f.name.toLowerCase().endsWith('.pdf'));
    if (nonPdfs.length > 0) {
      setUploadError(`All candidate resumes must be PDFs. Found: ${nonPdfs.map(f => f.name).join(', ')}`);
      return;
    }
    setResumeFiles(files);
    if (files.length < 1) {
      setUploadError('Batch size requirement: At least 1 candidate resume required.');
    } else if (files.length > 25) {
      setUploadError(`Batch size requirement: Maximum 25 candidate resumes allowed (currently ${files.length} selected). Please remove ${files.length - 25} resume(s).`);
    } else {
      setUploadError(null);
    }
  };

  const isBatchValid = resumeFiles.length >= 1 && resumeFiles.length <= 25;

  // Submit batch analysis to backend
  const handleStartAnalysis = async () => {
    if (!jdFile) {
      setUploadError('Please select a Job Description PDF.');
      return;
    }
    if (!isBatchValid) {
      setUploadError(`Requirement: Between 1 and 25 candidate resumes are required for shortlisting (currently ${resumeFiles.length} selected).`);
      return;
    }

    setView('processing');
    setProcessingStep('Sending documents to local analysis pipeline...');

    try {
      setProcessingStep('Extracting requirements & parsing candidate profiles...');
      const data = await coachApi.analyzeRecruiterBatch(jdFile, resumeFiles);

      setProcessingStep('Ranking candidates & generating evidence-backed explanations...');
      setAnalysisData(data);
      setView('results');
    } catch (err) {
      console.error('Analysis failed:', err);
      setUploadError(`Analysis failed: ${err.message}`);
      setView('upload');
    }
  };

  const handleReset = () => {
    setJdFile(null);
    setResumeFiles([]);
    setAnalysisData(null);
    setSelectedCandidate(null);
    setShowBiasAudit(false);
    setUploadError(null);
    setView('upload');
  };

  return (
    <div className="recruiter-portal-wrap">
      {/* SCREEN 1: UPLOAD VIEW */}
      {view === 'upload' && (
        <section aria-label="Upload Job Description and Resumes">
          <div className="upload-hero">
            <p className="hero-subtitle">Recruiter Intelligence • Batch Mode</p>
            <h2 className="hero-title">Evidence-First Candidate Shortlisting.</h2>
            <p className="hero-desc">
              Upload a Job Description and a batch of candidate resumes (1–25 PDFs).
              Our local engine parses, matches, and ranks every candidate with auditable evidence provenance.
            </p>
          </div>

          {uploadError && (
            <div className="warning-banner" role="alert" style={{ maxWidth: '720px', margin: '0 auto 2rem' }}>
              <strong>Attention: </strong> {uploadError}
            </div>
          )}

          <div className="upload-grid">
            {/* JD Upload Dropzone */}
            <div 
              className={`upload-card ${jdFile ? 'has-file' : ''}`}
              onClick={() => jdInputRef.current?.click()}
              tabIndex={0}
              role="button"
              aria-label="Upload Job Description PDF"
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') jdInputRef.current?.click(); }}
            >
              <div className="upload-icon">📄</div>
              <h3 className="upload-label">Job Description</h3>
              <p className="upload-hint">Click or drop 1 Job Description PDF</p>
              {jdFile ? (
                <div className="file-status-pill">
                  <span>✓</span>
                  <span>{jdFile.name} ({(jdFile.size / 1024).toFixed(1)} KB)</span>
                </div>
              ) : (
                <span className="btn-secondary">Choose JD PDF</span>
              )}
              <input 
                type="file" 
                ref={jdInputRef} 
                onChange={handleJdSelect} 
                accept=".pdf,application/pdf" 
                className="file-input-hidden" 
              />
            </div>

            {/* Resumes Upload Dropzone */}
            <div 
              className={`upload-card ${resumeFiles.length > 0 ? 'has-file' : ''}`}
              onClick={() => resumeInputRef.current?.click()}
              tabIndex={0}
              role="button"
              aria-label="Upload Candidate Resumes batch PDFs"
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') resumeInputRef.current?.click(); }}
            >
              <div className="upload-icon">👥</div>
              <h3 className="upload-label">Candidate Resumes</h3>
              <p className="upload-hint">Click or drop 1–25 Candidate Resume PDFs</p>
              {resumeFiles.length > 0 ? (
                isBatchValid ? (
                  <div className="file-status-pill" style={{ background: '#E8F5E9', color: '#2E7D32', border: '1px solid #C8E6C9' }}>
                    <span>✓</span>
                    <span>{resumeFiles.length} resume{resumeFiles.length === 1 ? '' : 's'} (Valid batch)</span>
                  </div>
                ) : (
                  <div className="file-status-pill" style={{ background: '#FFEBEE', color: '#C62828', border: '1px solid #FFCDD2' }}>
                    <span>⚠️</span>
                    <span>{resumeFiles.length} resumes (1–25 required)</span>
                  </div>
                )
              ) : (
                <span className="btn-secondary">Choose Resumes Batch (1–25 PDFs)</span>
              )}
              <input 
                type="file" 
                ref={resumeInputRef} 
                onChange={handleResumeSelect} 
                accept=".pdf,application/pdf" 
                multiple 
                className="file-input-hidden" 
              />
            </div>
          </div>

          <div className="action-bar">
            <button 
              className="btn-primary" 
              onClick={handleStartAnalysis}
              disabled={!jdFile || !isBatchValid}
            >
              {!jdFile 
                ? "1. Select Job Description PDF"
                : resumeFiles.length === 0 
                ? "2. Select Candidate Resumes (1–25 PDFs)"
                : !isBatchValid 
                ? `Select Valid Batch (${resumeFiles.length} selected — 1–25 required)`
                : `Analyze Candidates (${resumeFiles.length} Resume${resumeFiles.length === 1 ? '' : 's'}) →`}
            </button>
          </div>
        </section>
      )}

      {/* PROCESSING VIEW */}
      {view === 'processing' && (
        <section className="processing-card" aria-live="polite">
          <div className="spinner" />
          <h2 className="section-title" style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>
            Processing Candidates Locally
          </h2>
          <p className="processing-step">{processingStep}</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--color-theme-muted)', marginTop: '2rem' }}>
            Running local Sentence-Transformers & Hybrid Scorer (HF_HUB_OFFLINE=1)
          </p>
        </section>
      )}

      {/* SCREEN 2: RESULTS DASHBOARD */}
      {view === 'results' && analysisData && (
        <section aria-label="Analysis Results">
          <div className="dashboard-header">
            <div>
              <p className="section-label">Job Assessment</p>
              <h2 className="job-meta-title">{analysisData.job?.job_title || 'Position Analysis'}</h2>
              <div className="job-meta-stats">
                <span className="stat-item">
                  Candidates Evaluated: <strong>{analysisData.total_ranked}</strong> of {analysisData.total_resumes_received}
                </span>
                <span className="stat-item">
                  Requirements: <strong>{analysisData.job?.total_requirements}</strong> ({analysisData.job?.required_count} Required, {analysisData.job?.preferred_count} Preferred)
                </span>
                {analysisData.job?.bias_audit && (
                  <button 
                    type="button"
                    className={`stat-item bias-stat-pill ${analysisData.job.bias_audit.bias_free ? 'bias-clean' : 'bias-flagged'}`}
                    onClick={() => setShowBiasAudit(!showBiasAudit)}
                    aria-label="Toggle JD Inclusivity and Bias Audit"
                  >
                    <span className="bias-icon">{analysisData.job.bias_audit.bias_free ? '🛡️' : '⚠️'}</span>
                    <span>Inclusivity Score: <strong>{analysisData.job.bias_audit.inclusivity_score}/100 ({analysisData.job.bias_audit.inclusivity_grade})</strong></span>
                    <span className="bias-toggle-action">{showBiasAudit ? '▲ Hide Phrasing Audit' : '▼ View Phrasing Audit'}</span>
                  </button>
                )}
              </div>
            </div>
            <button className="btn-secondary" onClick={handleReset}>
              ← Analyze New Batch
            </button>
          </div>

          {/* JD INCLUSIVITY & PHRASING AUDIT CARD */}
          {analysisData.job?.bias_audit && showBiasAudit && (
            <div className="bias-audit-card" role="region" aria-label="Job Description Inclusivity Audit">
              <div className="bias-audit-header">
                <div className="bias-audit-header-left">
                  <span className="bonus-pill">Bonus Feature 1</span>
                  <h3 className="bias-audit-title">Job Description Inclusivity & Phrasing Audit</h3>
                </div>
                <div className={`bias-score-badge-large grade-${analysisData.job.bias_audit.inclusivity_grade.toLowerCase().replace('+', '-plus')}`}>
                  <div className="bias-score-text-wrap">
                    <span className="bias-score-num">{analysisData.job.bias_audit.inclusivity_score}</span>
                    <span className="bias-score-denom">/100</span>
                  </div>
                  <span className="bias-grade-chip">Grade {analysisData.job.bias_audit.inclusivity_grade}</span>
                </div>
              </div>

              <p className="bias-audit-summary">{analysisData.job.bias_audit.summary}</p>

              {analysisData.job.bias_audit.flags.length === 0 ? (
                <div className="bias-clean-box">
                  <span className="clean-check-icon">✓</span>
                  <div>
                    <h4 className="clean-box-title">Zero Exclusionary Phrasing Detected</h4>
                    <p className="clean-box-desc">
                      The Job Description demonstrates exemplary inclusive phrasing without pedigree locks, hyper-aggressive language, or unrealistic experience barriers.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="bias-flags-list">
                  <div className="bias-flags-list-title">Detected Phrasing Flags & Inclusive Recommendations ({analysisData.job.bias_audit.flags.length}):</div>
                  <div className="bias-flags-grid">
                    {analysisData.job.bias_audit.flags.map((flag) => (
                      <div key={flag.id} className={`bias-flag-card severity-${flag.severity}`}>
                        <div className="bias-flag-top">
                          <span className={`bias-category-tag cat-${flag.category}`}>
                            {flag.category === 'gender_coded' && '🚻 Gender-Coded / Hyper-Aggressive'}
                            {flag.category === 'pedigree_degree' && '🎓 Pedigree / Degree Lock'}
                            {flag.category === 'unrealistic_experience' && '⏳ Unrealistic Experience Ceiling'}
                            {flag.category === 'age_generational' && '🎂 Age / Generational Coding'}
                            {flag.category === 'ableist_physical' && '♿ Physical / Non-Essential Constraint'}
                          </span>
                          <span className={`bias-severity-pill sev-${flag.severity}`}>
                            {flag.severity.toUpperCase()} IMPACT
                          </span>
                        </div>

                        <div className="bias-flag-body">
                          <div className="flag-row">
                            <span className="flag-label">Flagged Phrasing:</span>
                            <span className="flagged-term-highlight">"{flag.matched_text}"</span>
                          </div>

                          {flag.context_snippet && (
                            <div className="flag-context-snippet">
                              <span className="context-label">JD Context:</span>
                              <em>"{flag.context_snippet}"</em>
                            </div>
                          )}

                          <div className="flag-explanation">
                            <strong>Why it excludes talent:</strong> {flag.explanation}
                          </div>

                          <div className="flag-recommendation">
                            <span className="recommendation-icon">💡</span>
                            <div>
                              <strong>Inclusive Alternative:</strong> {flag.inclusive_alternative}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Processing Failures Alert */}
          {analysisData.failed_candidates && analysisData.failed_candidates.length > 0 && (
            <div className="warning-banner" role="alert">
              <strong>Notice: </strong>
              {analysisData.failed_candidates.length} candidate resume(s) could not be parsed and were isolated:
              <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem' }}>
                {analysisData.failed_candidates.map((f, idx) => (
                  <li key={idx}><strong>{f.filename}:</strong> {f.error}</li>
                ))}
              </ul>
            </div>
          )}

          {/* TOP 3 PODIUM SECTION */}
          <div className="section-title-wrap">
            <div>
              <p className="section-label">Executive Recommendation</p>
              <h3 className="section-title">Top 3 Shortlist.</h3>
            </div>
          </div>

          <div className="podium-grid">
            {analysisData.ranked_candidates.slice(0, 3).map((candidate) => (
              <article key={candidate.candidate_id} className={`top-card rank-${candidate.rank}`}>
                <div>
                  <div className="card-top-header">
                    <span className={`rank-badge rank-${candidate.rank}`}>
                      Rank #{candidate.rank}
                    </span>
                    <div className="score-display">
                      <span className="score-number">{candidate.overall_score.toFixed(1)}</span>
                      <span className="score-max">/100</span>
                    </div>
                  </div>

                  <h4 className="candidate-name">{candidate.candidate_name || candidate.candidate_id}</h4>

                  <div className="why-ranked-box">
                    <div className="why-ranked-label">Why Ranked Here:</div>
                    <p>{candidate.why_ranked_here}</p>
                  </div>

                  {candidate.strengths && candidate.strengths.length > 0 && (
                    <ul className="top-strengths-list">
                      {candidate.strengths.slice(0, 3).map((st, idx) => (
                        <li key={idx}>
                          <span className="strength-bullet">✓</span>
                          <span>{st}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="card-footer">
                  <span className="req-quick-summary">
                    {candidate.matched_requirements?.length || 0} matched • {candidate.missing_required_requirements?.length || 0} missing req
                  </span>
                  <button 
                    className="btn-inspect" 
                    onClick={() => setSelectedCandidate(candidate)}
                  >
                    View Evidence →
                  </button>
                </div>
              </article>
            ))}
          </div>

          {/* FULL CANDIDATE RANKING TABLE */}
          <div className="section-title-wrap">
            <div>
              <p className="section-label">Complete Cohort</p>
              <h3 className="section-title">Full Candidate Rankings.</h3>
            </div>
          </div>

          <div className="table-card">
            <div className="table-responsive-wrapper">
              <table className="ranking-table">
                <thead>
                  <tr>
                    <th style={{ width: '80px' }}>Rank</th>
                    <th>Candidate</th>
                    <th style={{ width: '120px' }}>Score</th>
                    <th style={{ width: '130px' }}>Required Met</th>
                    <th style={{ width: '130px' }}>Preferred Met</th>
                    <th>Status Summary</th>
                    <th style={{ width: '120px', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {analysisData.ranked_candidates.map((cand) => (
                    <tr key={cand.candidate_id} onClick={() => setSelectedCandidate(cand)}>
                      <td className="table-rank">#{cand.rank}</td>
                      <td className="table-candidate-name">
                        <strong>{cand.candidate_name || cand.candidate_id}</strong>
                        {cand.is_top_3 && (
                          <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', color: '#B8860B', fontWeight: 600 }}>
                            ★ TOP 3
                          </span>
                        )}
                      </td>
                      <td>
                        <span className="score-badge">
                          {cand.overall_score.toFixed(1)}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: 'var(--color-matched)', fontWeight: 600 }}>
                          {cand.score_breakdown?.required_matched_count || 0}
                        </span>
                        <span style={{ color: 'var(--color-theme-muted)' }}>
                          /{cand.score_breakdown?.required_total_count || 0}
                        </span>
                      </td>
                      <td>
                        <span style={{ color: 'var(--color-theme-text)', fontWeight: 500 }}>
                          {Math.max(0, (cand.score_breakdown?.matched_count || 0) - (cand.score_breakdown?.required_matched_count || 0))}
                        </span>
                        <span style={{ color: 'var(--color-theme-muted)' }}>
                          /{Math.max(0, (cand.score_breakdown?.total_requirements || 0) - (cand.score_breakdown?.required_total_count || 0))}
                        </span>
                      </td>
                      <td>
                        <p className="status-summary-text" title={cand.why_ranked_here}>
                          {cand.why_ranked_here}
                        </p>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button 
                          className="btn-inspect" 
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedCandidate(cand);
                          }}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* CANDIDATE DETAIL MODAL */}
      {selectedCandidate && (
        <div 
          className="modal-overlay" 
          onClick={() => setSelectedCandidate(null)}
          role="dialog"
          aria-modal="true"
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                  <span className={`rank-badge rank-${Math.min(selectedCandidate.rank, 3)}`}>
                    Rank #{selectedCandidate.rank}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-theme-muted)' }}>
                    Candidate ID: {selectedCandidate.candidate_id}
                  </span>
                </div>
                <h2 className="section-title" style={{ fontSize: '2.25rem' }}>
                  {selectedCandidate.candidate_name || selectedCandidate.candidate_id}
                </h2>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                <div className="score-display">
                  <span className="score-number">{selectedCandidate.overall_score.toFixed(1)}</span>
                  <span className="score-max">/100</span>
                </div>
                <button 
                  className="btn-close" 
                  onClick={() => setSelectedCandidate(null)}
                  aria-label="Close details modal"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Executive Rationale */}
            <div className="detail-section">
              <h3 className="detail-section-title">Why This Candidate Ranked Here</h3>
              <div className="narrative-card">
                <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>{selectedCandidate.why_ranked_here}</p>
                <p style={{ color: '#4A4642' }}>{selectedCandidate.summary}</p>
              </div>
            </div>

            {/* Strengths */}
            {selectedCandidate.strengths && selectedCandidate.strengths.length > 0 && (
              <div className="detail-section">
                <h3 className="detail-section-title">Key Strengths</h3>
                <ul className="top-strengths-list">
                  {selectedCandidate.strengths.map((s, idx) => (
                    <li key={idx} style={{ fontSize: '0.9rem' }}>
                      <span className="strength-bullet">✓</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Score Breakdown */}
            <div className="detail-section">
              <h3 className="detail-section-title">Score Breakdown</h3>
              <div className="score-breakdown-grid">
                {(() => {
                  const reqTotal = selectedCandidate.score_breakdown?.required_total_count || 0;
                  const reqMatched = selectedCandidate.score_breakdown?.required_matched_count || 0;
                  const total = selectedCandidate.score_breakdown?.total_requirements || 0;
                  const allMatched = selectedCandidate.score_breakdown?.matched_count || 0;
                  const prefTotal = Math.max(0, total - reqTotal);
                  const prefMatched = Math.max(0, allMatched - reqMatched);
                  return (
                    <>
                      <div className="score-mini-card">
                        <div className="mini-score-value">
                          {reqMatched} / {reqTotal}
                        </div>
                        <div className="mini-score-label">Required Criteria Met</div>
                      </div>
                      <div className="score-mini-card">
                        <div className="mini-score-value">
                          {prefMatched} / {prefTotal}
                        </div>
                        <div className="mini-score-label">Preferred Criteria Met</div>
                      </div>
                      <div className="score-mini-card">
                        <div className="mini-score-value">
                          {selectedCandidate.score_breakdown?.keyword_contribution != null 
                            ? `${selectedCandidate.score_breakdown.keyword_contribution.toFixed(1)}%` 
                            : '0.0%'}
                        </div>
                        <div className="mini-score-label">Keyword Match Signal</div>
                      </div>
                      <div className="score-mini-card">
                        <div className="mini-score-value">
                          {selectedCandidate.score_breakdown?.semantic_contribution != null 
                            ? `${selectedCandidate.score_breakdown.semantic_contribution.toFixed(1)}%` 
                            : '0.0%'}
                        </div>
                        <div className="mini-score-label">Semantic Match Signal</div>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>

            {/* Requirements Breakdown */}
            <div className="detail-section">
              <h3 className="detail-section-title">Requirements & Auditable Evidence</h3>

              {/* Fully Matched */}
              {selectedCandidate.matched_requirements?.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--color-matched)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem', fontWeight: 700 }}>
                    ✓ Fully Matched Criteria ({selectedCandidate.matched_requirements.length})
                  </h4>
                  {selectedCandidate.matched_requirements.map((req) => (
                    <div key={req.requirement_id} className="requirement-card matched">
                      <div className="req-header">
                        <span className="req-text">{req.requirement_text}</span>
                        <span className="verdict-tag matched">Matched (+{req.contribution_to_score.toFixed(1)} pts)</span>
                      </div>
                      <p className="req-explanation-text">{req.explanation}</p>
                      
                      {req.supporting_evidence?.length > 0 && (
                        <div className="evidence-box">
                          {req.supporting_evidence.map((ev, eIdx) => (
                            <div key={eIdx} style={{ marginBottom: eIdx < req.supporting_evidence.length - 1 ? '0.75rem' : 0 }}>
                              <p className="evidence-quote">"{ev.evidence_text}"</p>
                              <div className="evidence-provenance-chips">
                                <span className="provenance-chip">🏷 {ev.evidence_type}</span>
                                {ev.source_section && <span className="provenance-chip">📂 Section: {ev.source_section}</span>}
                                {ev.page_number && <span className="provenance-chip">📄 Page {ev.page_number}</span>}
                                {ev.match_method && <span className="provenance-chip">🔍 Method: {ev.match_method}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Partially Matched */}
              {selectedCandidate.partial_requirements?.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--color-partial)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem', fontWeight: 700 }}>
                    △ Partially Matched Criteria ({selectedCandidate.partial_requirements.length})
                  </h4>
                  {selectedCandidate.partial_requirements.map((req) => (
                    <div key={req.requirement_id} className="requirement-card partial">
                      <div className="req-header">
                        <span className="req-text">{req.requirement_text}</span>
                        <span className="verdict-tag partial">Partial (+{req.contribution_to_score.toFixed(1)} pts)</span>
                      </div>
                      <p className="req-explanation-text">{req.explanation}</p>
                      {req.supporting_evidence?.length > 0 && (
                        <div className="evidence-box">
                          {req.supporting_evidence.map((ev, eIdx) => (
                            <div key={eIdx} style={{ marginBottom: eIdx < req.supporting_evidence.length - 1 ? '0.75rem' : 0 }}>
                              <p className="evidence-quote">"{ev.evidence_text}"</p>
                              <div className="evidence-provenance-chips">
                                <span className="provenance-chip">🏷 {ev.evidence_type}</span>
                                {ev.source_section && <span className="provenance-chip">📂 Section: {ev.source_section}</span>}
                                {ev.page_number && <span className="provenance-chip">📄 Page {ev.page_number}</span>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Missing Required */}
              {selectedCandidate.missing_required_requirements?.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--color-missing)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem', fontWeight: 700 }}>
                    ✕ Missing Required Criteria ({selectedCandidate.missing_required_requirements.length})
                  </h4>
                  {selectedCandidate.missing_required_requirements.map((req) => (
                    <div key={req.requirement_id} className="requirement-card missing">
                      <div className="req-header">
                        <span className="req-text">{req.requirement_text}</span>
                        <span className="verdict-tag missing">Missing Required (0 pts)</span>
                      </div>
                      <p className="req-explanation-text">{req.explanation}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Missing Preferred */}
              {selectedCandidate.missing_preferred_requirements?.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--color-theme-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem', fontWeight: 700 }}>
                    ○ Unfulfilled Preferred Criteria ({selectedCandidate.missing_preferred_requirements.length})
                  </h4>
                  {selectedCandidate.missing_preferred_requirements.map((req) => (
                    <div key={req.requirement_id} className="requirement-card preferred">
                      <div className="req-header">
                        <span className="req-text">{req.requirement_text}</span>
                        <span className="verdict-tag preferred">Preferred (0 pts)</span>
                      </div>
                      <p className="req-explanation-text">{req.explanation}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div style={{ textAlign: 'right', marginTop: '2rem' }}>
              <button className="btn-secondary" onClick={() => setSelectedCandidate(null)}>
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
