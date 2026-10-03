import React, { useState, useEffect, useCallback } from 'react';
import { coachApi } from '../services/api';

export default function CareerIntelligence({ careerTwin, evidenceVault, onHandoffToResumeCoach, onNavigateToVault }) {
  const [targets, setTargets] = useState([]);
  const [selectedTargetId, setSelectedTargetId] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [actionFilter, setActionFilter] = useState('ALL'); // 'ALL' | 'TODO' | 'IN_PROGRESS' | 'COMPLETED'
  const [selectedEvidenceStrength, setSelectedEvidenceStrength] = useState(null);

  // New Target Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [targetRoleInput, setTargetRoleInput] = useState('');
  const [targetCompanyInput, setTargetCompanyInput] = useState('');
  const [targetJdTextInput, setTargetJdTextInput] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);

  const candidateId = careerTwin?.candidate_id;

  // Load targets
  const loadTargets = useCallback(async (autoSelectId = null) => {
    if (!candidateId) return;
    try {
      const data = await coachApi.getCareerTargets(candidateId);
      setTargets(data);
      if (data.length > 0) {
        const toSelect = autoSelectId 
          ? data.find(t => t.target_id === autoSelectId) || data[0]
          : data[0];
        setSelectedTargetId(toSelect.target_id);
      } else {
        setSelectedTargetId(null);
        setIntelligence(null);
      }
    } catch (err) {
      console.error("Failed to load career targets:", err);
      setError(err.message);
    }
  }, [candidateId]);

  // Load intelligence & actions for selected target
  const loadTargetData = useCallback(async (targetId, prevCoverage = null) => {
    if (!candidateId || !targetId) return;
    setLoading(true);
    setError(null);
    try {
      const [intelData, actionsData] = await Promise.all([
        coachApi.getCareerIntelligence(candidateId, targetId, prevCoverage),
        coachApi.getCareerActions(candidateId, targetId),
      ]);
      setIntelligence(intelData);
      setActions(actionsData);
    } catch (err) {
      console.error("Failed to load career intelligence:", err);
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
          loadTargetData(selectedTargetId);
        }
      }, 0);
      return () => {
        isMounted = false;
        clearTimeout(timer);
      };
    }
  }, [selectedTargetId, loadTargetData]);

  // Refresh intelligence
  const handleRefresh = async () => {
    if (!selectedTargetId || !candidateId) return;
    setRefreshing(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const prevCov = intelligence?.evidence_coverage || null;
      const refreshedIntel = await coachApi.refreshCareerIntelligence(selectedTargetId, candidateId, prevCov);
      setIntelligence(refreshedIntel);
      const updatedActions = await coachApi.getCareerActions(candidateId, selectedTargetId);
      setActions(updatedActions);
      setSuccessMsg("Career Intelligence diagnostic successfully re-evaluated against current Career Twin and Evidence Vault.");
    } catch (err) {
      console.error("Failed to refresh career intelligence:", err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  // Create target
  const handleCreateTarget = async (e) => {
    e.preventDefault();
    if (!candidateId) return;
    if (!targetRoleInput.trim()) {
      setError("Please specify a target role name.");
      return;
    }

    setCreateSubmitting(true);
    setError(null);
    try {
      const newTarget = await coachApi.createCareerTarget({
        candidate_id: candidateId,
        target_role: targetRoleInput.trim(),
        target_company: targetCompanyInput.trim() || null,
        job_description_text: targetJdTextInput.trim() || null,
      });
      setShowCreateModal(false);
      setTargetRoleInput('');
      setTargetCompanyInput('');
      setTargetJdTextInput('');
      setSuccessMsg(`Created target '${newTarget.target_role}' successfully.`);
      await loadTargets(newTarget.target_id);
    } catch (err) {
      console.error("Failed to create career target:", err);
      setError(err.message);
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Add Action from Gap
  const handleAddActionFromGap = async (gap, actionType, customTitle = null) => {
    if (!candidateId || !selectedTargetId) return;
    setActionLoading(true);
    setError(null);
    try {
      const title = customTitle || `${actionType.replace('_', ' ')}: ${gap.requirement_text}`;
      const rationale = gap.explanation || gap.priority_rationale;
      const created = await coachApi.createCareerAction({
        candidate_id: candidateId,
        target_id: selectedTargetId,
        requirement_id: gap.requirement_id,
        action_type: actionType,
        title,
        description: `Action planned for target requirement: "${gap.requirement_text}"`,
        rationale,
      });
      setActions(prev => [created, ...prev]);
      setSuccessMsg(`Added "${title}" to your Action Plan.`);
    } catch (err) {
      console.error("Failed to create action:", err);
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Action status changes
  const handleCompleteAction = async (actionId) => {
    if (!candidateId) return;
    setActionLoading(true);
    try {
      const updated = await coachApi.completeCareerAction(actionId, candidateId);
      setActions(prev => prev.map(a => a.action_id === actionId ? updated : a));
      setSuccessMsg("Action marked completed. (Note: Only genuine evidence added to your Evidence Vault updates requirement evaluations).");
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDismissAction = async (actionId) => {
    if (!candidateId) return;
    setActionLoading(true);
    try {
      const updated = await coachApi.dismissCareerAction(actionId, candidateId);
      setActions(prev => prev.map(a => a.action_id === actionId ? updated : a));
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handoff visibility gap to Resume Coach
  const handleHandoff = (gap) => {
    if (!onHandoffToResumeCoach) return;
    onHandoffToResumeCoach({
      requirement_id: gap.requirement_id,
      requirement_text: gap.requirement_text,
      target_role: intelligence?.target_role || "Target Role",
      gap_type: 'RESUME_VISIBILITY_GAP',
      can_rewrite: true,
      evidence_ids: gap.evidence_ids || [],
    });
  };

  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">🧭</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to begin Career Intelligence and Gap Planning.</p>
      </div>
    );
  }

  const selectedTarget = targets.find(t => t.target_id === selectedTargetId);
  const filteredActions = actions.filter(a => {
    if (actionFilter === 'ALL') return true;
    return a.status === actionFilter;
  });

  return (
    <div className="career-intelligence-view">
      {/* Top Header & Target Selector */}
      <div className="ci-header-panel">
        <div className="ci-header-left">
          <div className="ci-badge">🧭 Phase 6 • Evidence-Grounded Career Intelligence</div>
          <h2 className="ci-title">Career Intelligence & Gap Planning</h2>
          <p className="ci-subtitle">
            Diagnostic career-development and resume-evidence gap analysis. Answers: <em>"What should I work on next to become better aligned with target roles?"</em>
          </p>
        </div>

        <div className="ci-header-actions">
          {targets.length > 0 && (
            <div className="target-select-wrap">
              <label htmlFor="target-select" className="target-select-label">Active Target:</label>
              <select
                id="target-select"
                className="target-dropdown"
                value={selectedTargetId || ''}
                onChange={(e) => setSelectedTargetId(e.target.value)}
              >
                {targets.map(t => (
                  <option key={t.target_id} value={t.target_id}>
                    {t.target_role} {t.target_company ? `(${t.target_company})` : ''} [{t.status}]
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowCreateModal(true)}
          >
            + New Career Target
          </button>

          {selectedTarget && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRefresh}
              disabled={refreshing || loading}
            >
              {refreshing ? 'Refreshing...' : '🔄 Refresh Intelligence'}
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="alert-banner alert-error" style={{ marginBottom: '1.25rem' }}>
          <span>⚠️ {error}</span>
          <button type="button" className="close-btn" onClick={() => setError(null)}>×</button>
        </div>
      )}

      {successMsg && (
        <div className="alert-banner alert-success" style={{ marginBottom: '1.25rem' }}>
          <span>✓ {successMsg}</span>
          <button type="button" className="close-btn" onClick={() => setSuccessMsg(null)}>×</button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="ci-loading-state">
          <div className="spinner" />
          <p>Evaluating Career Intelligence and Evidence Vault alignment...</p>
        </div>
      )}

      {/* Empty State when no targets exist */}
      {!loading && targets.length === 0 && (
        <div className="coach-empty-state">
          <div className="empty-icon">🎯</div>
          <h3>No Career Targets Defined</h3>
          <p>Set a career target (e.g. "Senior Backend Engineer" or "DevOps Architect") to diagnose your strengths, resume visibility gaps, and experience gaps.</p>
          <button
            type="button"
            className="btn btn-primary"
            style={{ marginTop: '1rem' }}
            onClick={() => setShowCreateModal(true)}
          >
            + Create First Career Target
          </button>
        </div>
      )}

      {/* Intelligence Dashboard */}
      {!loading && intelligence && (
        <>
          {/* Diagnostic Evidence Coverage Banner */}
          <div className="ci-coverage-card">
            <div className="coverage-card-main">
              <div className="coverage-metric-col">
                <span className="coverage-metric-label">DIAGNOSTIC EVIDENCE COVERAGE</span>
                <div className="coverage-metric-val-wrap">
                  {intelligence.progress_summary?.previous_coverage !== null && intelligence.progress_summary?.previous_coverage !== undefined ? (
                    <div className="coverage-delta-display">
                      <span className="coverage-val-prev">{(intelligence.progress_summary.previous_coverage * 100).toFixed(1)}%</span>
                      <span className="coverage-arrow">→</span>
                      <span className="coverage-val-curr">{(intelligence.evidence_coverage * 100).toFixed(1)}%</span>
                      {intelligence.progress_summary.coverage_delta !== 0 && (
                        <span className={`coverage-delta-tag ${intelligence.progress_summary.coverage_delta > 0 ? 'tag-positive' : 'tag-neutral'}`}>
                          {intelligence.progress_summary.coverage_delta > 0 ? `+${(intelligence.progress_summary.coverage_delta * 100).toFixed(1)}%` : `${(intelligence.progress_summary.coverage_delta * 100).toFixed(1)}%`}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="coverage-val-curr">{(intelligence.evidence_coverage * 100).toFixed(1)}%</span>
                  )}
                </div>
                <div className="coverage-guardrail-notice">
                  🛡️ Diagnostic Evidence State — Not a hiring prediction, candidate ranking, or probability score.
                </div>
              </div>

              {/* Requirement Counts Breakdown */}
              <div className="coverage-breakdown-col">
                <div className="breakdown-stat-grid">
                  <div className="b-stat b-stat-matched">
                    <span className="b-num">{intelligence.progress_summary?.matched_count || 0}</span>
                    <span className="b-lbl">Matched</span>
                  </div>
                  <div className="b-stat b-stat-partial">
                    <span className="b-num">{intelligence.progress_summary?.partial_count || 0}</span>
                    <span className="b-lbl">Partial</span>
                  </div>
                  <div className="b-stat b-stat-missing">
                    <span className="b-num">{intelligence.progress_summary?.missing_count || 0}</span>
                    <span className="b-lbl">Missing</span>
                  </div>
                  <div className="b-stat b-stat-nv">
                    <span className="b-num">{intelligence.progress_summary?.not_verifiable_count || 0}</span>
                    <span className="b-lbl">Not Verifiable</span>
                  </div>
                </div>

                <div className="gap-type-summary-row">
                  <span className="gap-tag gap-tag-vis">
                    Visibility Gaps: {intelligence.progress_summary?.visibility_gaps_count || 0}
                  </span>
                  <span className="gap-tag gap-tag-exp">
                    Experience Gaps: {intelligence.progress_summary?.experience_gaps_count || 0}
                  </span>
                </div>
              </div>
            </div>

            {/* Narrative Summary */}
            {intelligence.progress_summary?.narrative && (
              <div className="coverage-narrative-box">
                <span className="narrative-icon">📌</span>
                <span className="narrative-text">{intelligence.progress_summary.narrative}</span>
              </div>
            )}

            {/* Before / After Progress Comparison (if delta or change exists) */}
            {intelligence.progress_summary?.improved_requirements?.length > 0 && (
              <div className="ci-before-after-box">
                <div className="ba-header">
                  <span className="ba-title">📈 Target Progress Comparison</span>
                  <span className="ba-sub">Observable requirement changes against this target:</span>
                </div>
                <div className="ba-grid">
                  <div className="ba-col ba-col-improved">
                    <span className="ba-col-title">✓ Newly Demonstrated / Improved:</span>
                    <ul>
                      {intelligence.progress_summary.improved_requirements.map((reqText, idx) => (
                        <li key={idx}>{reqText}</li>
                      ))}
                    </ul>
                  </div>
                  {intelligence.progress_summary.remaining_experience_gaps?.length > 0 && (
                    <div className="ba-col ba-col-remaining">
                      <span className="ba-col-title">⏳ Remaining Experience Gaps:</span>
                      <ul>
                        {intelligence.progress_summary.remaining_experience_gaps.map((reqText, idx) => (
                          <li key={idx}>{reqText}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Main 4-Column Diagnostic Grid */}
          <div className="ci-columns-grid">
            {/* 1. Verified Strengths */}
            <div className="ci-column ci-col-strengths">
              <div className="ci-col-header">
                <div className="col-title-wrap">
                  <span className="col-icon">✓</span>
                  <h3 className="col-title">Verified Strengths</h3>
                </div>
                <span className="col-count-badge">{intelligence.strengths?.length || 0}</span>
              </div>
              <p className="col-desc">Requirements supported by genuine, verified evidence in your Evidence Vault.</p>

              <div className="ci-card-list">
                {intelligence.strengths?.length === 0 ? (
                  <div className="ci-empty-card">No verified strengths matched for this target yet.</div>
                ) : (
                  intelligence.strengths.map(s => (
                    <div key={s.requirement_id} className="ci-item-card strength-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{s.requirement_text}</span>
                        <span className="category-pill">{s.category}</span>
                      </div>
                      <p className="ci-item-exp">{s.explanation}</p>
                      
                      {/* Evidence Citations */}
                      {s.evidence_ids?.length > 0 && (
                        <div className="ci-evidence-chips">
                          <span className="ev-label">Evidence Citations:</span>
                          {s.evidence_ids.map(eid => (
                            <button
                              key={eid}
                              type="button"
                              className="ev-chip-btn"
                              onClick={() => setSelectedEvidenceStrength(s)}
                            >
                              🔍 {eid}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 2. Resume Visibility Gaps */}
            <div className="ci-column ci-col-visibility">
              <div className="ci-col-header">
                <div className="col-title-wrap">
                  <span className="col-icon">📝</span>
                  <h3 className="col-title">Resume Visibility Gaps</h3>
                </div>
                <span className="col-count-badge">{intelligence.visibility_gaps?.length || 0}</span>
              </div>
              <p className="col-desc">
                <strong>Evidence already exists:</strong> Verified in your Evidence Vault, but not clearly surfaced on your resume.
              </p>

              <div className="ci-card-list">
                {intelligence.visibility_gaps?.length === 0 ? (
                  <div className="ci-empty-card">No resume visibility gaps detected for this target.</div>
                ) : (
                  intelligence.visibility_gaps.map(gap => (
                    <div key={gap.gap_id} className="ci-item-card visibility-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{gap.requirement_text}</span>
                        <span className={`prio-badge prio-${gap.priority.toLowerCase()}`}>
                          {gap.priority}
                        </span>
                      </div>
                      <p className="ci-item-rationale">{gap.priority_rationale}</p>
                      <p className="ci-item-exp">{gap.explanation}</p>

                      <div className="ci-item-actions">
                        <button
                          type="button"
                          className="btn btn-sm btn-coach-action"
                          onClick={() => handleHandoff(gap)}
                        >
                          ✍️ Improve Resume in Coach
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() => handleAddActionFromGap(gap, 'RESUME_IMPROVEMENT', `Improve resume wording for ${gap.requirement_text}`)}
                          disabled={actionLoading}
                        >
                          + Add to Plan
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 3. Genuine Experience Gaps */}
            <div className="ci-column ci-col-experience">
              <div className="ci-col-header">
                <div className="col-title-wrap">
                  <span className="col-icon">🔨</span>
                  <h3 className="col-title">Experience Gaps</h3>
                </div>
                <span className="col-count-badge">{intelligence.experience_gaps?.length || 0}</span>
              </div>
              <p className="col-desc">
                <strong>Genuine experience missing:</strong> No verified evidence exists. The system will NOT fabricate claims or rewrite your resume for these.
              </p>

              <div className="ci-card-list">
                {intelligence.experience_gaps?.length === 0 ? (
                  <div className="ci-empty-card">No missing experience gaps for this target.</div>
                ) : (
                  intelligence.experience_gaps.map(gap => (
                    <div key={gap.gap_id} className="ci-item-card experience-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{gap.requirement_text}</span>
                        <span className={`prio-badge prio-${gap.priority.toLowerCase()}`}>
                          {gap.priority}
                        </span>
                      </div>
                      <p className="ci-item-rationale">{gap.priority_rationale}</p>
                      <p className="ci-item-exp">{gap.explanation}</p>

                      <div className="ci-what-to-do-box">
                        <span className="wtd-label">Safe Next Actions:</span>
                        <div className="wtd-btn-group">
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-action"
                            onClick={() => handleAddActionFromGap(gap, 'BUILD_PROJECT', `Build project: ${gap.requirement_text}`)}
                            disabled={actionLoading}
                          >
                            🏗️ Build Project
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-action"
                            onClick={() => handleAddActionFromGap(gap, 'LEARN_SKILL', `Learn skill: ${gap.requirement_text}`)}
                            disabled={actionLoading}
                          >
                            📚 Learn Skill
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-action"
                            onClick={() => handleAddActionFromGap(gap, 'DOCUMENT_EVIDENCE', `Document genuine experience for ${gap.requirement_text}`)}
                            disabled={actionLoading}
                          >
                            📄 Document Work
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 4. Not Verifiable */}
            <div className="ci-column ci-col-nv">
              <div className="ci-col-header">
                <div className="col-title-wrap">
                  <span className="col-icon">❓</span>
                  <h3 className="col-title">Not Verifiable</h3>
                </div>
                <span className="col-count-badge">{intelligence.not_verifiable_gaps?.length || 0}</span>
              </div>
              <p className="col-desc">
                <strong>Insufficient evidence:</strong> Available documentation is inconclusive. Add artifacts to substantiate.
              </p>

              <div className="ci-card-list">
                {intelligence.not_verifiable_gaps?.length === 0 ? (
                  <div className="ci-empty-card">All requirements were confidently evaluated.</div>
                ) : (
                  intelligence.not_verifiable_gaps.map(gap => (
                    <div key={gap.gap_id} className="ci-item-card nv-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{gap.requirement_text}</span>
                        <span className={`prio-badge prio-${gap.priority.toLowerCase()}`}>
                          {gap.priority}
                        </span>
                      </div>
                      <p className="ci-item-rationale">{gap.priority_rationale}</p>
                      <p className="ci-item-exp">{gap.explanation}</p>

                      <div className="ci-item-actions">
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() => handleAddActionFromGap(gap, 'DOCUMENT_EVIDENCE', `Upload supporting evidence for ${gap.requirement_text}`)}
                          disabled={actionLoading}
                        >
                          📎 Add Evidence Action
                        </button>
                        {onNavigateToVault && (
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-action"
                            onClick={onNavigateToVault}
                          >
                            🔍 Open Evidence Explorer
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Action Plan Section */}
          <div className="ci-action-plan-section">
            <div className="action-plan-header">
              <div className="plan-title-wrap">
                <h3 className="plan-title">📋 Career Action Plan</h3>
                <span className="plan-subtitle">
                  Structured developmental roadmap for target: <strong>{intelligence.target_role}</strong>
                </span>
              </div>

              {/* Action Filter Tabs */}
              <div className="plan-filters">
                {['ALL', 'TODO', 'IN_PROGRESS', 'COMPLETED'].map(status => (
                  <button
                    key={status}
                    type="button"
                    className={`filter-btn ${actionFilter === status ? 'active' : ''}`}
                    onClick={() => setActionFilter(status)}
                  >
                    {status.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {/* Safety Notice */}
            <div className="ci-safety-callout">
              <span className="callout-icon">🛡️</span>
              <div className="callout-text">
                <strong>Critical Evidence Rule:</strong> Marking an action completed does NOT automatically grant you a skill or alter your Evidence Vault. Only genuine verified evidence added to your Evidence Vault can change requirement evaluations upon refresh.
              </div>
            </div>

            {/* Actions List */}
            <div className="actions-list">
              {filteredActions.length === 0 ? (
                <div className="ci-empty-card" style={{ padding: '2rem', textAlign: 'center' }}>
                  No actions currently in '{actionFilter}'. Click "+ Add to Plan", "Build Project", or "Learn Skill" above to populate your action roadmap.
                </div>
              ) : (
                filteredActions.map(action => (
                  <div key={action.action_id} className={`action-card status-${action.status.toLowerCase()}`}>
                    <div className="action-card-left">
                      <span className={`action-status-badge badge-${action.status.toLowerCase()}`}>
                        {action.status.replace('_', ' ')}
                      </span>
                      <div className="action-type-pill">{action.action_type.replace('_', ' ')}</div>
                      <div className="action-details">
                        <h4 className="action-title">{action.title}</h4>
                        <p className="action-desc">{action.description}</p>
                        {action.rationale && <p className="action-rationale"><em>Rationale:</em> {action.rationale}</p>}
                      </div>
                    </div>

                    <div className="action-card-right">
                      {action.status !== 'COMPLETED' && (
                        <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          onClick={() => handleCompleteAction(action.action_id)}
                          disabled={actionLoading}
                        >
                          ✓ Mark Completed
                        </button>
                      )}
                      {action.status !== 'DISMISSED' && (
                        <button
                          type="button"
                          className="btn btn-sm btn-ghost"
                          onClick={() => handleDismissAction(action.action_id)}
                          disabled={actionLoading}
                        >
                          Dismiss
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      {/* Create Target Modal */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h3 className="modal-title">🎯 Create New Career Target</h3>
              <button type="button" className="close-btn" onClick={() => setShowCreateModal(false)}>×</button>
            </div>

            <form onSubmit={handleCreateTarget} className="modal-form">
              <div className="form-group">
                <label className="form-label" htmlFor="role-input">Target Role Title *</label>
                <input
                  id="role-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Senior Backend Engineer"
                  value={targetRoleInput}
                  onChange={e => setTargetRoleInput(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="company-input">Target Company (Optional)</label>
                <input
                  id="company-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Stripe, OpenAI, Datadog"
                  value={targetCompanyInput}
                  onChange={e => setTargetCompanyInput(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="jd-text-input">Target Job Description / Requirements Text</label>
                <textarea
                  id="jd-text-input"
                  className="form-textarea"
                  rows={6}
                  placeholder={`Paste target job requirements here, for example:\n\nRequirements:\n- Python microservices\n- PostgreSQL database\n- Kubernetes cluster orchestration\n\nPreferred:\n- Rust experience`}
                  value={targetJdTextInput}
                  onChange={e => setTargetJdTextInput(e.target.value)}
                />
                <span className="form-hint">
                  Requirements will be deterministically analyzed using the existing Job Fit engine.
                </span>
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={createSubmitting || !targetRoleInput.trim()}
                >
                  {createSubmitting ? 'Creating...' : 'Create Career Target'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Evidence Provenance Modal / Drawer */}
      {selectedEvidenceStrength && (
        <div className="modal-backdrop" onClick={() => setSelectedEvidenceStrength(null)}>
          <div className="modal-card" onClick={e => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="modal-header">
              <h3 className="modal-title">🔍 Evidence Provenance</h3>
              <button type="button" className="close-btn" onClick={() => setSelectedEvidenceStrength(null)}>×</button>
            </div>

            <div className="modal-body" style={{ padding: '1.25rem 0' }}>
              <div className="ev-provenance-info">
                <h4>{selectedEvidenceStrength.requirement_text}</h4>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1rem' }}>
                  {selectedEvidenceStrength.explanation}
                </p>

                <h5 style={{ fontSize: '0.85rem', color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Associated Evidence Citations:
                </h5>
                <ul style={{ listStyle: 'none', padding: 0, marginTop: '0.5rem' }}>
                  {selectedEvidenceStrength.evidence_ids.map(eid => {
                    const vaultItem = evidenceVault?.items?.find(it => it.evidence_id === eid);
                    return (
                      <li key={eid} style={{ background: '#1e293b', padding: '0.75rem', borderRadius: '6px', marginBottom: '0.5rem', border: '1px solid #334155' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                          <span style={{ fontFamily: 'monospace', color: '#10b981', fontWeight: 600 }}>{eid}</span>
                          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                            {vaultItem?.source_document || 'Uploaded Resume'} {vaultItem?.page_number ? `(Page ${vaultItem.page_number})` : ''}
                          </span>
                        </div>
                        {vaultItem?.source_section && (
                          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                            Section: <em>{vaultItem.source_section}</em>
                          </div>
                        )}
                        <p style={{ margin: 0, fontSize: '0.85rem', color: '#cbd5e1', fontStyle: 'italic' }}>
                          "{vaultItem?.source_text || (selectedEvidenceStrength.source_snippets?.[0] || 'Verified candidate evidence record')}"
                        </p>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedEvidenceStrength(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
