import React, { useState, useEffect, useCallback } from 'react';
import { coachApi } from '../services/api';

const TABS = {
  READINESS_MAP: 'READINESS_MAP',
  QUESTIONS_COACH: 'QUESTIONS_COACH',
  PROJECT_STORIES: 'PROJECT_STORIES',
  MOCK_INTERVIEW: 'MOCK_INTERVIEW',
};

export default function InterviewCoach({ careerTwin, evidenceVault }) {
  const [targets, setTargets] = useState([]);
  const [selectedTargetId, setSelectedTargetId] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(TABS.READINESS_MAP);

  // New Target Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [targetRoleInput, setTargetRoleInput] = useState('');
  const [targetCompanyInput, setTargetCompanyInput] = useState('');
  const [targetJdTextInput, setTargetJdTextInput] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // Evidence Citation Inspector modal
  const [activeCitation, setActiveCitation] = useState(null);

  // Answer Coach Sandbox state
  const [selectedQuestion, setSelectedQuestion] = useState(null);
  const [draftAnswer, setDraftAnswer] = useState('');
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  // Mock Interview Session state
  const [mockSession, setMockSession] = useState(null);
  const [sessionIndex, setSessionIndex] = useState(0);
  const [sessionAnswerText, setSessionAnswerText] = useState('');
  const [sessionSubmitting, setSessionSubmitting] = useState(false);
  const [sessionFeedback, setSessionFeedback] = useState(null);

  const candidateId = careerTwin?.candidate_id;

  // Load existing interview targets
  const loadTargets = useCallback(async (autoSelectId = null) => {
    if (!candidateId) return;
    try {
      const data = await coachApi.getInterviewTargets(candidateId);
      setTargets(data);
      if (data.length > 0) {
        const toSelect = autoSelectId
          ? data.find(t => t.interview_target_id === autoSelectId) || data[0]
          : data[0];
        setSelectedTargetId(toSelect.interview_target_id);
      } else {
        setSelectedTargetId(null);
        setReadiness(null);
      }
    } catch (err) {
      console.error("Failed to load interview targets:", err);
      setError(err.message);
    }
  }, [candidateId]);

  // Load readiness data for selected target
  const loadReadiness = useCallback(async (targetId) => {
    if (!candidateId || !targetId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await coachApi.getInterviewReadiness(candidateId, targetId);
      setReadiness(data);
      if (data.questions && data.questions.length > 0) {
        setSelectedQuestion(data.questions[0]);
      }
    } catch (err) {
      console.error("Failed to load interview readiness:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [candidateId]);

  useEffect(() => {
    let isMounted = true;
    const timer = setTimeout(() => {
      if (isMounted) {
        loadTargets();
      }
    }, 0);
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [loadTargets]);

  useEffect(() => {
    let isMounted = true;
    if (selectedTargetId) {
      const timer = setTimeout(() => {
        if (isMounted) {
          loadReadiness(selectedTargetId);
        }
      }, 0);
      return () => {
        isMounted = false;
        clearTimeout(timer);
      };
    }
  }, [selectedTargetId, loadReadiness]);

  // Create new interview target
  const handleCreateTarget = async (e) => {
    e.preventDefault();
    if (!targetRoleInput.trim()) return;
    setCreateSubmitting(true);
    setError(null);
    try {
      const newTarget = await coachApi.createInterviewTarget(
        candidateId,
        targetRoleInput.trim(),
        targetCompanyInput.trim() || null,
        targetJdTextInput.trim() || null
      );
      setShowCreateModal(false);
      setTargetRoleInput('');
      setTargetCompanyInput('');
      setTargetJdTextInput('');
      await loadTargets(newTarget.interview_target_id);
    } catch (err) {
      console.error("Target creation failed:", err);
      setError(err.message);
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Refresh readiness
  const handleRefreshReadiness = async () => {
    if (!selectedTargetId || !candidateId) return;
    setRefreshing(true);
    setError(null);
    try {
      const refreshed = await coachApi.refreshInterviewReadiness(selectedTargetId, candidateId);
      setReadiness(refreshed);
    } catch (err) {
      console.error("Readiness refresh failed:", err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  // Validate candidate answer in sandbox
  const handleValidateAnswer = async () => {
    if (!draftAnswer.trim() || !candidateId) return;
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await coachApi.validateInterviewAnswer(
        candidateId,
        selectedQuestion?.question_id || 'custom_q',
        draftAnswer.trim(),
        selectedQuestion?.requirement_id || null,
        selectedTargetId
      );
      setValidationResult(res);
    } catch (err) {
      console.error("Answer validation error:", err);
      setError(err.message);
    } finally {
      setValidating(false);
    }
  };

  // Start mock interview session
  const handleStartMockSession = async () => {
    if (!selectedTargetId || !candidateId) return;
    setLoading(true);
    setError(null);
    try {
      const session = await coachApi.createInterviewSession(candidateId, selectedTargetId);
      setMockSession(session);
      setSessionIndex(0);
      setSessionAnswerText('');
      setSessionFeedback(null);
      setActiveTab(TABS.MOCK_INTERVIEW);
    } catch (err) {
      console.error("Failed to start mock session:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Submit answer in ongoing mock session
  const handleSubmitSessionAnswer = async () => {
    if (!mockSession || !sessionAnswerText.trim()) return;
    const currentItem = mockSession.items[sessionIndex];
    if (!currentItem) return;

    setSessionSubmitting(true);
    setSessionFeedback(null);
    try {
      const updatedSess = await coachApi.submitSessionAnswer(
        mockSession.session_id,
        candidateId,
        currentItem.question_id,
        sessionAnswerText.trim()
      );
      setMockSession(updatedSess);
      const answeredItem = updatedSess.items.find(i => i.question_id === currentItem.question_id);
      setSessionFeedback(answeredItem?.validation_result || null);
    } catch (err) {
      console.error("Session answer submit failed:", err);
      setError(err.message);
    } finally {
      setSessionSubmitting(false);
    }
  };

  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">🎙️</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to generate evidence-grounded interview readiness.</p>
      </div>
    );
  }

  const selectedTarget = targets.find(t => t.interview_target_id === selectedTargetId);
  const currentMockItem = mockSession?.items?.[sessionIndex];

  return (
    <div className="coach-view-container">
      {/* Top Header */}
      <div className="twin-grounding-banner">
        <span className="grounding-tag">
          <span className="live-dot" />
          Evidence-Grounded Interview & Application Readiness
        </span>
        <span className="grounding-meta">
          Twin ID: {careerTwin.twin_id} • Vault Items: {evidenceVault?.total_items || careerTwin.skills?.length || 0}
        </span>
      </div>

      {/* Target Selector Bar */}
      <div className="vault-controls-bar">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-theme-muted)' }}>Target Role:</span>
            {targets.length > 0 ? (
              <select
                className="select-custom"
                style={{ padding: '0.4rem 0.8rem', borderRadius: '8px', border: '1px solid var(--color-theme-border)', fontSize: '0.9rem' }}
                value={selectedTargetId || ''}
                onChange={(e) => setSelectedTargetId(e.target.value)}
              >
                {targets.map(t => (
                  <option key={t.interview_target_id} value={t.interview_target_id}>
                    {t.target_role} {t.company ? `(${t.company})` : ''}
                  </option>
                ))}
              </select>
            ) : (
              <span style={{ fontSize: '0.85rem', color: 'var(--color-theme-muted)', fontStyle: 'italic' }}>
                No target selected
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn-secondary" onClick={() => setShowCreateModal(true)}>
              + Add Target
            </button>
            {selectedTargetId && (
              <button className="btn-secondary" onClick={handleRefreshReadiness} disabled={refreshing}>
                {refreshing ? 'Refreshing...' : '↻ Refresh Readiness'}
              </button>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="warning-banner" style={{ background: '#fef2f2', borderColor: '#fca5a5', color: '#991b1b', marginBottom: '1.5rem' }}>
          <strong>Notice: </strong>{error}
        </div>
      )}

      {/* Hero Diagnostic Card */}
      {readiness && selectedTarget && (
        <div className="coverage-hero-card" style={{ marginBottom: '1.5rem' }}>
          <div className="coverage-header-row">
            <div>
              <span className="target-role-badge">INTERVIEW PREPARATION</span>
              <h2 className="target-role-title">
                {selectedTarget.target_role}
                {selectedTarget.company && <span style={{ fontWeight: 400, color: 'var(--color-theme-muted)', marginLeft: '0.5rem' }}>@ {selectedTarget.company}</span>}
              </h2>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className="badge-status status-matched" style={{ fontSize: '0.85rem', padding: '0.35rem 0.85rem' }}>
                {readiness.preparation_progress_metric || `Reviewed: ${readiness.ready_count} / ${readiness.total_requirements}`}
              </span>
            </div>
          </div>

          <div className="coverage-stats-grid">
            <div className="coverage-stat-box" style={{ borderLeft: '4px solid #10b981' }}>
              <div className="coverage-stat-value" style={{ color: '#047857' }}>{readiness.ready_count}</div>
              <div className="coverage-stat-label">Ready to Discuss</div>
            </div>
            <div className="coverage-stat-box" style={{ borderLeft: '4px solid #f59e0b' }}>
              <div className="coverage-stat-value" style={{ color: '#b45309' }}>{readiness.review_count}</div>
              <div className="coverage-stat-label">Areas to Review</div>
            </div>
            <div className="coverage-stat-box" style={{ borderLeft: '4px solid #ef4444' }}>
              <div className="coverage-stat-value" style={{ color: '#b91c1c' }}>{readiness.prepare_count}</div>
              <div className="coverage-stat-label">Areas to Prepare</div>
            </div>
            <div className="coverage-stat-box" style={{ borderLeft: '4px solid #64748b' }}>
              <div className="coverage-stat-value" style={{ color: '#475569' }}>{readiness.not_verifiable_count}</div>
              <div className="coverage-stat-label">Unverifiable</div>
            </div>
          </div>

          <p style={{ margin: '1rem 0 0', fontSize: '0.82rem', color: 'var(--color-theme-muted)', fontStyle: 'italic' }}>
            🔒 {readiness.guardrail_notice}
          </p>
        </div>
      )}

      {/* Navigation Subtabs */}
      <div className="twin-subnav" style={{ marginBottom: '1.5rem' }}>
        <button
          className={`subnav-btn ${activeTab === TABS.READINESS_MAP ? 'active' : ''}`}
          onClick={() => setActiveTab(TABS.READINESS_MAP)}
        >
          📋 Readiness Map
        </button>
        <button
          className={`subnav-btn ${activeTab === TABS.QUESTIONS_COACH ? 'active' : ''}`}
          onClick={() => setActiveTab(TABS.QUESTIONS_COACH)}
        >
          🎙️ Practice Questions & Answer Coach
        </button>
        <button
          className={`subnav-btn ${activeTab === TABS.PROJECT_STORIES ? 'active' : ''}`}
          onClick={() => setActiveTab(TABS.PROJECT_STORIES)}
        >
          📖 Project Stories ({readiness?.project_stories?.length || 0})
        </button>
        <button
          className={`subnav-btn ${activeTab === TABS.MOCK_INTERVIEW ? 'active' : ''}`}
          onClick={() => setActiveTab(TABS.MOCK_INTERVIEW)}
        >
          ⏱️ Mock Interview Mode
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <div className="spinner" />
          <p style={{ color: 'var(--color-theme-muted)' }}>Analyzing candidate evidence & generating readiness mapping...</p>
        </div>
      )}

      {/* TAB 1: READINESS MAP */}
      {!loading && activeTab === TABS.READINESS_MAP && readiness && (
        <div>
          {/* READY TO DISCUSS */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 className="card-section-title" style={{ color: '#047857', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>✓</span> READY TO DISCUSS ({readiness.ready_to_discuss?.length || 0})
            </h3>
            <p className="card-section-desc">Verified evidence exists in your Evidence Vault. You can prepare to speak to these confidently from concrete past work:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {(readiness.ready_to_discuss || []).map((req) => (
                <div key={req.requirement_id} className="req-item-card card-matched">
                  <div className="req-card-top">
                    <span className="badge-status status-matched">READY</span>
                    <span className="badge-priority required">{req.priority}</span>
                  </div>
                  <h4 className="req-text-title">{req.requirement_text}</h4>
                  <p style={{ fontSize: '0.85rem', color: '#4b5563', margin: '0.25rem 0 0.5rem' }}>{req.rationale}</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {req.evidence_ids.map(eid => (
                        <span key={eid} className="provenance-chip">ID: {eid}</span>
                      ))}
                    </div>
                    {req.evidence_ids.length > 0 && (
                      <button
                        className="btn-secondary"
                        style={{ padding: '0.25rem 0.65rem', fontSize: '0.75rem' }}
                        onClick={() => {
                          const ev = evidenceVault?.items?.find(it => req.evidence_ids.includes(it.evidence_id));
                          if (ev) setActiveCitation(ev);
                        }}
                      >
                        [Review Evidence]
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* AREAS TO REVIEW */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 className="card-section-title" style={{ color: '#b45309', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>⚠</span> AREAS TO REVIEW ({readiness.areas_to_review?.length || 0})
            </h3>
            <p className="card-section-desc">Evidence exists in your vault, but you should review specific projects to articulate your ownership and outcomes clearly:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {(readiness.areas_to_review || []).map((req) => (
                <div key={req.requirement_id} className="req-item-card card-partial">
                  <div className="req-card-top">
                    <span className="badge-status status-partial">REVIEW</span>
                    <span className="badge-priority">{req.priority}</span>
                  </div>
                  <h4 className="req-text-title">{req.requirement_text}</h4>
                  <p style={{ fontSize: '0.85rem', color: '#4b5563', margin: '0.25rem 0 0.5rem' }}>{req.rationale}</p>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {req.evidence_ids.map(eid => (
                        <span key={eid} className="provenance-chip">ID: {eid}</span>
                      ))}
                    </div>
                    {req.evidence_ids.length > 0 && (
                      <button
                        className="btn-secondary"
                        style={{ padding: '0.25rem 0.65rem', fontSize: '0.75rem' }}
                        onClick={() => {
                          const ev = evidenceVault?.items?.find(it => req.evidence_ids.includes(it.evidence_id));
                          if (ev) setActiveCitation(ev);
                        }}
                      >
                        [Review Evidence]
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* AREAS TO PREPARE */}
          <div style={{ marginBottom: '2rem' }}>
            <h3 className="card-section-title" style={{ color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>○</span> AREAS TO PREPARE ({readiness.areas_to_prepare?.length || 0})
            </h3>
            <p className="card-section-desc">No verified experience currently present in Evidence Vault. The system encourages honesty and conceptual mastery rather than fabricating claims:</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {(readiness.areas_to_prepare || []).map((req) => (
                <div key={req.requirement_id} className="req-item-card card-missing">
                  <div className="req-card-top">
                    <span className="badge-status status-missing">PREPARE</span>
                    <span className="badge-priority required">{req.priority}</span>
                  </div>
                  <h4 className="req-text-title">{req.requirement_text}</h4>
                  <p style={{ fontSize: '0.85rem', color: '#991b1b', margin: '0.25rem 0 0.5rem' }}>
                    {req.rationale}
                  </p>
                  {(() => {
                    const relatedEv = evidenceVault?.items?.find(it => 
                      it.related_skill && req.requirement_text.toLowerCase().includes(it.related_skill.toLowerCase())
                    );
                    if (relatedEv) {
                      return (
                        <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.5rem 0.75rem', margin: '0.5rem 0', fontSize: '0.8rem' }}>
                          <span style={{ fontWeight: 600, color: '#334155' }}>Verified Technology: </span>
                          <span style={{ color: '#0f172a' }}>{relatedEv.related_skill}</span>
                          <span style={{ color: '#64748b' }}> (appears in {relatedEv.related_project || relatedEv.source_section})</span>
                          <div style={{ marginTop: '0.25rem', color: '#475569' }}>
                            <strong>Status: </strong>Experience Gap — Role requires specific operational/production scope not yet verified in your Evidence Vault.
                          </div>
                        </div>
                      );
                    }
                    return null;
                  })()}
                  <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '0.65rem 0.85rem', marginTop: '0.5rem' }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#92400e', display: 'block', marginBottom: '0.2rem' }}>
                      Preparation Strategy:
                    </span>
                    <p style={{ fontSize: '0.82rem', color: '#78350f', margin: 0 }}>
                      Study architectural concepts, articulate your foundational understanding honestly, and explain how your adjacent skills enable rapid ramp-up.
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: QUESTIONS & ANSWER COACH */}
      {!loading && activeTab === TABS.QUESTIONS_COACH && readiness && (
        <div className="coach-two-col-grid">
          {/* Left Column: Question List */}
          <div className="interview-left-card">
            <h3 className="card-section-title">Evidence-Grounded Questions</h3>
            <p className="card-section-desc">Click a question to inspect evidence citations and practice your answer:</p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {readiness.questions.map((q) => {
                const isSelected = selectedQuestion?.question_id === q.question_id;
                return (
                  <div
                    key={q.question_id}
                    className={`req-item-card ${isSelected ? 'card-matched' : ''}`}
                    style={{ cursor: 'pointer', padding: '1rem', border: isSelected ? '2px solid #4f46e5' : '1px solid var(--color-theme-border)' }}
                    onClick={() => {
                      setSelectedQuestion(q);
                      setValidationResult(null);
                    }}
                  >
                    <div className="req-card-top">
                      <span className="badge-status status-partial" style={{ fontSize: '0.7rem' }}>{q.question_type}</span>
                      <span className="badge-priority">{q.source}</span>
                    </div>
                    <h4 style={{ fontSize: '0.95rem', margin: '0.35rem 0', color: 'var(--color-theme-text)' }}>
                      {q.question}
                    </h4>
                    <p style={{ fontSize: '0.8rem', color: 'var(--color-theme-muted)', margin: 0 }}>
                      Area: {q.preparation_area}
                    </p>
                    {q.citations && q.citations.length > 0 && (
                      <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                        {q.citations.map(cit => (
                          <span
                            key={cit.evidence_id}
                            className="provenance-chip"
                            style={{ cursor: 'pointer', background: '#e0e7ff', color: '#4338ca' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveCitation(cit);
                            }}
                          >
                            📖 {cit.evidence_id} ({cit.source_document || 'Resume'})
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Evidence-Locked Answer Coach */}
          <div className="interview-right-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span className="coach-badge-tag">Evidence-Locked Answer Coach</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-theme-muted)' }}>Zero Hallucination Guarantee</span>
            </div>

            {selectedQuestion ? (
              <div>
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '1rem', marginBottom: '1.25rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase' }}>Selected Question</span>
                  <h4 style={{ margin: '0.35rem 0', fontSize: '1.05rem', color: '#1e293b' }}>{selectedQuestion.question}</h4>
                  <p style={{ fontSize: '0.82rem', color: '#64748b', margin: 0 }}>{selectedQuestion.rationale}</p>
                </div>

                {/* STAR Scaffolding Prompts */}
                {selectedQuestion.star_prompts && (
                  <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', padding: '0.85rem', marginBottom: '1rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#15803d', textTransform: 'uppercase', display: 'block', marginBottom: '0.4rem' }}>
                      Recommended STAR Scaffold:
                    </span>
                    <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.82rem', color: '#166534', lineHeight: 1.5 }}>
                      <li><strong>Situation:</strong> {selectedQuestion.star_prompts.situation}</li>
                      <li><strong>Task:</strong> {selectedQuestion.star_prompts.task}</li>
                      <li><strong>Action:</strong> {selectedQuestion.star_prompts.action}</li>
                      <li><strong>Result:</strong> {selectedQuestion.star_prompts.result}</li>
                    </ul>
                  </div>
                )}

                <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                  Your Draft Response:
                </label>
                <textarea
                  className="star-input-area"
                  rows={6}
                  placeholder="Draft your response using your actual project work. Avoid claiming unverified metrics or technologies..."
                  value={draftAnswer}
                  onChange={(e) => setDraftAnswer(e.target.value)}
                />

                <button
                  className="btn-primary"
                  onClick={handleValidateAnswer}
                  disabled={validating || !draftAnswer.trim()}
                  style={{ width: '100%', marginBottom: '1rem' }}
                >
                  {validating ? 'Validating against Evidence Vault...' : 'Validate Answer with Evidence-Lock →'}
                </button>

                {/* Live Validation Results */}
                {validationResult && (
                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Validation Verdict:</span>
                      <span className={`badge-status ${validationResult.verdict === 'SUPPORTED' ? 'status-matched' : validationResult.verdict === 'PARTIALLY_SUPPORTED' ? 'status-partial' : 'status-missing'}`}>
                        {validationResult.verdict}
                      </span>
                    </div>

                    <p style={{ fontSize: '0.85rem', color: '#4b5563', margin: '0 0 0.75rem' }}>
                      {validationResult.explanation}
                    </p>

                    {/* Unsupported Claims Alert */}
                    {validationResult.unsupported_claims && validationResult.unsupported_claims.length > 0 && (
                      <div className="warning-banner" style={{ background: '#fef2f2', borderColor: '#fca5a5', color: '#991b1b', marginBottom: '1rem' }}>
                        <strong>Unsupported Claims Detected:</strong>
                        <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.2rem' }}>
                          {validationResult.unsupported_claims.map((claim, idx) => (
                            <li key={idx} style={{ marginTop: '0.2rem' }}>{claim}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Supported Claims & Technologies */}
                    {validationResult.supported_claims && validationResult.supported_claims.length > 0 && (
                      <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '0.75rem', marginBottom: '1rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#166534', display: 'block', marginBottom: '0.25rem' }}>
                          Verified Grounded Claims:
                        </span>
                        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                          {validationResult.supported_claims.map((claim, idx) => (
                            <span key={idx} className="coverage-metric-pill matched" style={{ fontSize: '0.75rem' }}>✓ {claim}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* STAR Breakdown */}
                    {validationResult.star_breakdown && (
                      <div className="star-results-card" style={{ marginTop: '0.5rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-theme-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.4rem' }}>
                          STAR Coverage:
                        </span>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', textAlign: 'center' }}>
                          <span className={`star-item ${validationResult.star_breakdown.situation ? 'valid' : 'missing'}`}>
                            {validationResult.star_breakdown.situation ? '✓' : '○'} Situation
                          </span>
                          <span className={`star-item ${validationResult.star_breakdown.task ? 'valid' : 'missing'}`}>
                            {validationResult.star_breakdown.task ? '✓' : '○'} Task
                          </span>
                          <span className={`star-item ${validationResult.star_breakdown.action ? 'valid' : 'missing'}`}>
                            {validationResult.star_breakdown.action ? '✓' : '○'} Action
                          </span>
                          <span className={`star-item ${validationResult.star_breakdown.result ? 'valid' : 'missing'}`}>
                            {validationResult.star_breakdown.result ? '✓' : '○'} Result
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Coaching Recommendations */}
                    {validationResult.coaching_recommendations && validationResult.coaching_recommendations.length > 0 && (
                      <div style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: '#4b5563' }}>
                        <strong>Coaching Recommendations:</strong>
                        <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.2rem' }}>
                          {validationResult.coaching_recommendations.map((rec, idx) => (
                            <li key={idx} style={{ marginTop: '0.2rem' }}>{rec}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <p style={{ color: 'var(--color-theme-muted)', textAlign: 'center', padding: '2rem' }}>
                Select a question on the left to begin practice.
              </p>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: PROJECT STORY BUILDER */}
      {!loading && activeTab === TABS.PROJECT_STORIES && readiness && (
        <div>
          <div className="section-title-wrap">
            <div>
              <span className="section-label">Authentic Experience Scaffolding</span>
              <h3 className="section-title">Project Story Builder</h3>
            </div>
          </div>
          <p className="view-desc" style={{ marginBottom: '1.5rem' }}>
            Structured STAR outlines derived strictly from verified projects in your Evidence Vault. No answers are fabricated.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
            {(readiness.project_stories || []).map((story) => (
              <div key={story.project_id} className="table-card" style={{ padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                  <h4 style={{ margin: 0, fontSize: '1.25rem', fontFamily: 'var(--font-serif)' }}>{story.project_name}</h4>
                  <span className="badge-status status-matched" style={{ fontSize: '0.72rem' }}>VERIFIED PROJECT</span>
                </div>

                <div style={{ marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-theme-muted)', textTransform: 'uppercase' }}>Verified Technologies:</span>
                  <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                    {story.technologies.map((t, idx) => (
                      <span key={idx} className="tech-tag-small">{t}</span>
                    ))}
                  </div>
                </div>

                {/* Likely Discussion Areas */}
                <div style={{ marginBottom: '1rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-theme-muted)', textTransform: 'uppercase' }}>Discussion Prompts:</span>
                  <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.2rem', fontSize: '0.84rem', color: '#4b5563', lineHeight: 1.45 }}>
                    {story.likely_discussion_areas.map((area, idx) => (
                      <li key={idx}>{area}</li>
                    ))}
                  </ul>
                </div>

                {/* STAR Scaffolding */}
                {story.star_preparation && (
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '1rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#334155', textTransform: 'uppercase', display: 'block', marginBottom: '0.4rem' }}>
                      STAR Preparation Guide:
                    </span>
                    <div style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                      <div><strong>S (Situation):</strong> {story.star_preparation.situation}</div>
                      <div><strong>T (Task):</strong> {story.star_preparation.task}</div>
                      <div><strong>A (Action):</strong> {story.star_preparation.action}</div>
                      <div style={{ color: story.star_preparation.result.includes('not currently supported') ? '#b45309' : '#15803d' }}>
                        <strong>R (Result):</strong> {story.star_preparation.result}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: MOCK INTERVIEW MODE */}
      {!loading && activeTab === TABS.MOCK_INTERVIEW && (
        <div className="table-card" style={{ padding: '2rem', maxWidth: '850px', margin: '0 auto' }}>
          {!mockSession ? (
            <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎙️</div>
              <h3 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.75rem', margin: '0 0 0.5rem' }}>Practice Interview Studio</h3>
              <p style={{ color: 'var(--color-theme-muted)', maxWidth: '520px', margin: '0 auto 1.75rem', fontSize: '0.95rem' }}>
                Practice answering evidence-grounded questions. The system tracks preparation progress and flags unsupported assertions in real-time.
              </p>
              <button className="btn-primary" onClick={handleStartMockSession}>
                Start Mock Interview Session →
              </button>
            </div>
          ) : (
            <div>
              {/* Session Progress Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--color-theme-border)', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
                <div>
                  <span className="coach-badge-tag">PRACTICE SESSION</span>
                  <h4 style={{ margin: '0.2rem 0', fontSize: '1.25rem' }}>
                    Question {sessionIndex + 1} of {mockSession.items.length}
                  </h4>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span className="badge-status status-matched">
                    Reviewed: {mockSession.requirements_reviewed_count || 0} / {mockSession.total_target_requirements}
                  </span>
                </div>
              </div>

              {currentMockItem && (
                <div>
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem', marginBottom: '1.25rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase' }}>Interviewer Prompt</span>
                    <h3 style={{ margin: '0.4rem 0', fontSize: '1.2rem', color: '#1e293b' }}>{currentMockItem.question_text}</h3>
                  </div>

                  <label style={{ fontSize: '0.88rem', fontWeight: 600, display: 'block', marginBottom: '0.4rem' }}>
                    Your Candidate Response:
                  </label>
                  <textarea
                    className="star-input-area"
                    rows={6}
                    placeholder="Provide your response using authentic work experience..."
                    value={sessionAnswerText}
                    onChange={(e) => setSessionAnswerText(e.target.value)}
                  />

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
                    <button
                      className="btn-secondary"
                      disabled={sessionIndex === 0}
                      onClick={() => {
                        const newIdx = sessionIndex - 1;
                        setSessionIndex(newIdx);
                        setSessionAnswerText(mockSession.items[newIdx]?.candidate_answer || '');
                        setSessionFeedback(mockSession.items[newIdx]?.validation_result || null);
                      }}
                    >
                      ← Previous Question
                    </button>

                    <button
                      className="btn-primary"
                      onClick={handleSubmitSessionAnswer}
                      disabled={sessionSubmitting || !sessionAnswerText.trim()}
                    >
                      {sessionSubmitting ? 'Evaluating with Evidence Vault...' : 'Submit & Validate Answer →'}
                    </button>

                    <button
                      className="btn-secondary"
                      disabled={sessionIndex >= mockSession.items.length - 1}
                      onClick={() => {
                        const newIdx = sessionIndex + 1;
                        setSessionIndex(newIdx);
                        setSessionAnswerText(mockSession.items[newIdx]?.candidate_answer || '');
                        setSessionFeedback(mockSession.items[newIdx]?.validation_result || null);
                      }}
                    >
                      Next Question →
                    </button>
                  </div>

                  {/* Immediate Session Feedback */}
                  {sessionFeedback && (
                    <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--color-theme-border)', paddingTop: '1.25rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Answer Feedback:</span>
                        <span className={`badge-status ${sessionFeedback.verdict === 'SUPPORTED' ? 'status-matched' : sessionFeedback.verdict === 'PARTIALLY_SUPPORTED' ? 'status-partial' : 'status-missing'}`}>
                          {sessionFeedback.verdict}
                        </span>
                      </div>

                      <p style={{ fontSize: '0.85rem', color: '#4b5563', margin: '0 0 0.5rem' }}>
                        {sessionFeedback.explanation}
                      </p>

                      {sessionFeedback.unsupported_claims && sessionFeedback.unsupported_claims.length > 0 && (
                        <div className="warning-banner" style={{ background: '#fef2f2', borderColor: '#fca5a5', color: '#991b1b', marginTop: '0.5rem' }}>
                          <strong>Flagged Unsupported Assertions:</strong>
                          <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.2rem' }}>
                            {sessionFeedback.unsupported_claims.map((claim, idx) => (
                              <li key={idx}>{claim}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* CREATE TARGET MODAL */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" style={{ maxWidth: '580px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-label">Interview Preparation</span>
                <h3 className="detail-section-title" style={{ margin: 0 }}>Add Interview Target</h3>
              </div>
              <button className="btn-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>

            <form onSubmit={handleCreateTarget} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
              <div>
                <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                  Target Role Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Senior Backend Engineer"
                  value={targetRoleInput}
                  onChange={(e) => setTargetRoleInput(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--color-theme-border)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                  Target Company (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Acme Fintech Corp"
                  value={targetCompanyInput}
                  onChange={(e) => setTargetCompanyInput(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--color-theme-border)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.85rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                  Job Description / Requirements (Optional)
                </label>
                <textarea
                  rows={5}
                  placeholder="Paste job description requirements to extract target interview criteria..."
                  value={targetJdTextInput}
                  onChange={(e) => setTargetJdTextInput(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--color-theme-border)', fontFamily: 'inherit', fontSize: '0.85rem' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={createSubmitting || !targetRoleInput.trim()}>
                  {createSubmitting ? 'Creating...' : 'Create Target →'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EVIDENCE CITATION MODAL */}
      {activeCitation && (
        <div className="modal-overlay" onClick={() => setActiveCitation(null)}>
          <div className="modal-content" style={{ maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="section-label">Evidence Provenance</span>
                <h3 className="detail-section-title" style={{ margin: 0 }}>Evidence Citation</h3>
              </div>
              <button className="btn-close" onClick={() => setActiveCitation(null)}>✕</button>
            </div>

            <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span className="vault-type-badge">{activeCitation.evidence_type || 'EXPERIENCE_BULLET'}</span>
                <span className="vault-section-badge">Section: {activeCitation.source_section || activeCitation.section || 'Experience'}</span>
                <span className="vault-page-badge">Page: {activeCitation.page_number || 1}</span>
              </div>

              <div className="evidence-box" style={{ background: '#f8fafc', padding: '1rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-theme-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem' }}>
                  Source Text in {activeCitation.source_document || 'Resume'}:
                </span>
                <p className="evidence-quote" style={{ fontSize: '0.95rem', color: '#1e293b', margin: 0 }}>
                  "{activeCitation.source_text}"
                </p>
              </div>

              {activeCitation.normalized_facts && activeCitation.normalized_facts.length > 0 && (
                <div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-theme-muted)', textTransform: 'uppercase', display: 'block', marginBottom: '0.35rem' }}>
                    Normalized Facts:
                  </span>
                  <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                    {activeCitation.normalized_facts.map((fact, idx) => (
                      <span key={idx} className="vault-fact-pill">✓ {fact}</span>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ borderTop: '1px solid var(--color-theme-border)', paddingTop: '0.75rem', display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--color-theme-muted)' }}>
                <span>Evidence ID: <code>{activeCitation.evidence_id}</code></span>
                <span>Document: {activeCitation.source_document || 'Resume'}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
