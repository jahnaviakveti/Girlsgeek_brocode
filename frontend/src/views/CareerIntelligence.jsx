import React, { useState, useEffect, useCallback } from 'react';
import { coachApi } from '../services/api';
import './CareerIntelligence.css';

const CollapsibleSection = ({ title, count, children, defaultOpen = false, icon = '' }) => {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);
  return (
    <div className="ci-collapse-panel">
      <div className="ci-collapse-header" onClick={() => setIsOpen(!isOpen)}>
        <div style={{display: 'flex', alignItems: 'center', gap: '0.75rem'}}>
          <span className="col-icon" style={{background: 'none', width: 'auto', fontSize: '1.25rem'}}>{icon}</span>
          <span className="ci-collapse-title">{title}</span>
        </div>
        <div className="ci-collapse-right">
          <span className="ci-collapse-count">{count}</span>
          <span className="ci-collapse-icon">{isOpen ? '▲' : '▼'}</span>
        </div>
      </div>
      {isOpen && <div className="ci-collapse-content">{children}</div>}
    </div>
  );
};

export function formatCoverage(val) {
  if (val === null || val === undefined || isNaN(val)) return '0.0%';
  const num = Number(val);
  const pct = (num > 0 && num <= 1.0) ? num * 100 : num;
  return `${pct.toFixed(1)}%`;
}

export function formatCoverageDelta(val) {
  if (val === null || val === undefined || isNaN(val)) return '0.0%';
  const num = Number(val);
  const pct = (Math.abs(num) > 0 && Math.abs(num) <= 1.0) ? num * 100 : num;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}


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


  // Compute Top Gaps for Next Steps
  let topGaps = [];
  if (intelligence) {
    const allGaps = [
      ...(intelligence.visibility_gaps || []).map(g => ({ ...g, gapType: 'VISIBILITY' })),
      ...(intelligence.experience_gaps || []).map(g => ({ ...g, gapType: 'EXPERIENCE' }))
    ];
    const prioValue = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
    allGaps.sort((a, b) => (prioValue[b.priority] || 0) - (prioValue[a.priority] || 0));
    topGaps = allGaps.slice(0, 3);
  }

  return (
    <div className="ci-dashboard">
      {/* 1. Compact Header */}
      <div className="ci-dash-header">
        <div className="ci-dash-header-title">
          <h2>Career Intelligence</h2>
          <p>Your evidence-based roadmap for becoming a stronger candidate.</p>
        </div>
        <div className="ci-dash-header-actions">
          {targets.length > 0 && (
            <select
              className="ci-compact-select"
              value={selectedTargetId || ''}
              onChange={(e) => setSelectedTargetId(e.target.value)}
            >
              {targets.map(t => (
                <option key={t.target_id} value={t.target_id}>
                  {t.target_role} {t.target_company ? `(${t.target_company})` : ''}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowCreateModal(true)}
          >
            + New Career Target
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="alert-banner alert-error" style={{ marginBottom: '0' }}>
          <span>⚠️ {error}</span>
          <button type="button" className="close-btn" onClick={() => setError(null)}>×</button>
        </div>
      )}
      {successMsg && (
        <div className="alert-banner alert-success" style={{ marginBottom: '0' }}>
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

            {showCreateModal ? (
        <div className="ci-create-target-card">
          <div className="ci-create-left">
            <div className="ci-create-icon">🎯</div>
            <h3 className="ci-create-title">{targets.length === 0 ? "No Career Target Defined" : "Create your career target"}</h3>
            <p className="ci-create-desc">
              Set a target role and Vettora will analyze your verified evidence against its requirements.
            </p>
            <ul className="ci-create-benefits">
              <li>✓ Evidence alignment</li>
              <li>✓ Gap analysis</li>
              <li>✓ Career action planning</li>
            </ul>
          </div>
          <div className="ci-create-right">
            <div className="ci-create-right-header">
              <h4>Create New Career Target</h4>
            </div>
            <form onSubmit={handleCreateTarget} className="ci-create-form">
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
                <label className="form-label" htmlFor="jd-text-input">Job Description / Requirements</label>
                <textarea
                  id="jd-text-input"
                  className="form-textarea"
                  rows={6}
                  placeholder={`Paste target job requirements here, for example:

Requirements:
- Python microservices
- PostgreSQL database
- Kubernetes cluster orchestration

Preferred:
- Rust experience`}
                  value={targetJdTextInput}
                  onChange={e => setTargetJdTextInput(e.target.value)}
                />
                <span className="form-hint">
                  Requirements are deterministically analyzed using the existing Job Fit engine.
                </span>
              </div>

              <div className="ci-create-actions">
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
      ) : (
        <>
{/* Empty State when no targets exist */}
      {!loading && targets.length === 0 && (
        <div className="coach-empty-state">
          <div className="empty-icon">🎯</div>
          <h3>No Career Targets Defined</h3>
          <p>Set a career target (e.g. "Senior Backend Engineer") to diagnose your strengths and gaps.</p>
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
          {/* 2. Unified Target + Coverage Card */}
          <div className="ci-unified-card">
            <div className="ci-unified-left">
              <span className="ci-unified-label">Target Role</span>
              <h3 className="ci-unified-role">{intelligence.target_role}</h3>
              {intelligence.target_company && <p className="ci-unified-company">{intelligence.target_company}</p>}
              <div className="ci-unified-actions">
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleRefresh}
                  disabled={refreshing}
                >
                  {refreshing ? 'Refreshing...' : '↻ Refresh Intelligence'}
                </button>
              </div>
            </div>
            <div className="ci-unified-right">
              <span className="ci-unified-label">Evidence Coverage</span>
              <h2 className="ci-unified-score">{formatCoverage(intelligence.evidence_coverage)}</h2>
              <div className="ci-unified-progress-bg">
                <div className="ci-unified-progress-bar" style={{ width: formatCoverage(intelligence.evidence_coverage) }}></div>
              </div>
              <div className="ci-unified-stats">
                <span>{intelligence.strengths?.length || 0} verified</span>
                <span>{intelligence.visibility_gaps?.length || 0} visibility gaps</span>
                <span>{intelligence.experience_gaps?.length || 0} experience gaps</span>
              </div>
            </div>
          </div>

          {/* 3. Diagnostic Summary (Compact Cards) */}
          <div className="ci-summary-grid">
            <div className="ci-summary-card ci-sum-card-verified">
              <div className="ci-sum-icon">✓</div>
              <div className="ci-sum-body">
                <div className="ci-sum-count">{intelligence.strengths?.length || 0}</div>
                <div className="ci-sum-label">Verified</div>
                <div className="ci-sum-exp">Requirements with evidence</div>
              </div>
            </div>
            <div className="ci-summary-card ci-sum-card-vis">
              <div className="ci-sum-icon">✎</div>
              <div className="ci-sum-body">
                <div className="ci-sum-count">{intelligence.visibility_gaps?.length || 0}</div>
                <div className="ci-sum-label">Visibility Gaps</div>
                <div className="ci-sum-exp">Evidence exists, resume hides it</div>
              </div>
            </div>
            <div className="ci-summary-card ci-sum-card-exp">
              <div className="ci-sum-icon">⚠</div>
              <div className="ci-sum-body">
                <div className="ci-sum-count">{intelligence.experience_gaps?.length || 0}</div>
                <div className="ci-sum-label">Experience Gaps</div>
                <div className="ci-sum-exp">Genuine experience missing</div>
              </div>
            </div>
            <div className="ci-summary-card ci-sum-card-nv">
              <div className="ci-sum-icon">❓</div>
              <div className="ci-sum-body">
                <div className="ci-sum-count">{intelligence.not_verifiable_gaps?.length || 0}</div>
                <div className="ci-sum-label">Not Verifiable</div>
                <div className="ci-sum-exp">Insufficient documentation</div>
              </div>
            </div>
          </div>

          {/* 4. Target Progress */}
          {intelligence.progress_summary?.improved_requirements?.length > 0 && (
            <div className="ci-target-progress-card">
              <h4>TARGET PROGRESS</h4>
              <p>Observable requirement changes against this target.</p>
              <div className="ci-progress-list">
                {intelligence.progress_summary.improved_requirements.slice(0, 2).map((req, i) => (
                  <div key={i} className="ci-progress-item">
                    <span className="ci-progress-icon">✓</span>
                    <span>{req}</span>
                  </div>
                ))}
              </div>
              {intelligence.progress_summary.improved_requirements.length > 2 && (
                <button className="ci-view-all-btn">
                  [ View all {intelligence.progress_summary.improved_requirements.length} changes ]
                </button>
              )}
            </div>
          )}

          {/* 5. What to work on next */}
          {topGaps.length > 0 && (
            <div className="ci-next-steps-section">
              <h3>What To Work On Next</h3>
              <div className="ci-next-steps-grid">
                {topGaps.map(gap => (
                  <div key={gap.gap_id} className={`ci-next-step-card ${gap.priority === 'MEDIUM' ? 'medium-prio' : ''}`}>
                    <span className="ci-prio-badge">{gap.priority} PRIORITY</span>
                    <h4 className="ci-req-title">{gap.requirement_text}</h4>
                    <p className="ci-req-why">{gap.priority_rationale || gap.explanation}</p>
                    
                    <span className="ci-req-rec">
                      Recommended action: {gap.gapType === 'VISIBILITY' ? 'Improve resume wording' : 'Build project / Learn skill'}
                    </span>
                    <div className="ci-req-action">
                      {gap.gapType === 'VISIBILITY' ? (
                        <button className="btn btn-sm btn-coach-action" onClick={() => handleHandoff(gap)}>
                          ✍️ Improve in Coach
                        </button>
                      ) : (
                        <button className="btn btn-sm btn-outline-action" onClick={() => handleAddActionFromGap(gap, 'BUILD_PROJECT', `Build project: ${gap.requirement_text}`)}>
                          🏗️ View Action
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 6. All Diagnostics Below (Collapsible) */}
          <div className="ci-detailed-diagnostics">
            
            <CollapsibleSection title="Verified Strengths" count={intelligence.strengths?.length || 0} icon="✓">
              <div className="ci-card-list">
                {(!intelligence.strengths || intelligence.strengths.length === 0) ? (
                  <div className="ci-empty-card">No verified strengths matched for this target yet.</div>
                ) : (
                  intelligence.strengths.map(s => (
                    <div key={s.requirement_id} className="ci-item-card strength-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{s.requirement_text}</span>
                        <span className="category-pill">{s.category}</span>
                      </div>
                      <p className="ci-item-exp">{s.explanation}</p>
                      {s.evidence_ids?.length > 0 && (
                        <div className="ci-evidence-chips">
                          <span className="ev-label">Evidence Citations:</span>
                          {s.evidence_ids.map(eid => (
                            <button key={eid} type="button" className="ev-chip-btn" onClick={() => setSelectedEvidenceStrength(s)}>
                              🔍 {eid}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CollapsibleSection>

            <CollapsibleSection title="Resume Visibility Gaps" count={intelligence.visibility_gaps?.length || 0} icon="📝">
              <div className="ci-card-list">
                {(!intelligence.visibility_gaps || intelligence.visibility_gaps.length === 0) ? (
                  <div className="ci-empty-card">No resume visibility gaps detected for this target.</div>
                ) : (
                  intelligence.visibility_gaps.map(gap => (
                    <div key={gap.gap_id} className="ci-item-card visibility-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{gap.requirement_text}</span>
                        <span className={`prio-badge prio-${gap.priority.toLowerCase()}`}>{gap.priority}</span>
                      </div>
                      <p className="ci-item-rationale">{gap.priority_rationale}</p>
                      <p className="ci-item-exp">{gap.explanation}</p>
                      <div className="ci-item-actions">
                        <button type="button" className="btn btn-sm btn-coach-action" onClick={() => handleHandoff(gap)}>
                          ✍️ Improve Resume in Coach
                        </button>
                        <button type="button" className="btn btn-sm btn-secondary" onClick={() => handleAddActionFromGap(gap, 'RESUME_IMPROVEMENT', `Improve resume wording for ${gap.requirement_text}`)}>
                          + Add to Plan
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CollapsibleSection>

            <CollapsibleSection title="Experience Gaps" count={intelligence.experience_gaps?.length || 0} icon="🔨">
              <div className="ci-card-list">
                {(!intelligence.experience_gaps || intelligence.experience_gaps.length === 0) ? (
                  <div className="ci-empty-card">No missing experience gaps for this target.</div>
                ) : (
                  intelligence.experience_gaps.map(gap => (
                    <div key={gap.gap_id} className="ci-item-card experience-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{gap.requirement_text}</span>
                        <span className={`prio-badge prio-${gap.priority.toLowerCase()}`}>{gap.priority}</span>
                      </div>
                      <p className="ci-item-rationale">{gap.priority_rationale}</p>
                      <p className="ci-item-exp">{gap.explanation}</p>
                      <div className="ci-what-to-do-box">
                        <span className="wtd-label">Safe Next Actions:</span>
                        <div className="wtd-btn-group">
                          <button type="button" className="btn btn-sm btn-outline-action" onClick={() => handleAddActionFromGap(gap, 'BUILD_PROJECT', `Build project: ${gap.requirement_text}`)}>
                            🏗️ Build Project
                          </button>
                          <button type="button" className="btn btn-sm btn-outline-action" onClick={() => handleAddActionFromGap(gap, 'LEARN_SKILL', `Learn skill: ${gap.requirement_text}`)}>
                            📚 Learn Skill
                          </button>
                          <button type="button" className="btn btn-sm btn-outline-action" onClick={() => handleAddActionFromGap(gap, 'DOCUMENT_EVIDENCE', `Document genuine experience for ${gap.requirement_text}`)}>
                            📄 Document Work
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CollapsibleSection>

            <CollapsibleSection title="Not Verifiable" count={intelligence.not_verifiable_gaps?.length || 0} icon="❓">
              <div className="ci-card-list">
                {(!intelligence.not_verifiable_gaps || intelligence.not_verifiable_gaps.length === 0) ? (
                  <div className="ci-empty-card">All requirements were confidently evaluated.</div>
                ) : (
                  intelligence.not_verifiable_gaps.map(gap => (
                    <div key={gap.gap_id} className="ci-item-card nv-card">
                      <div className="ci-item-header">
                        <span className="ci-item-title">{gap.requirement_text}</span>
                        <span className={`prio-badge prio-${gap.priority.toLowerCase()}`}>{gap.priority}</span>
                      </div>
                      <p className="ci-item-rationale">{gap.priority_rationale}</p>
                      <p className="ci-item-exp">{gap.explanation}</p>
                      <div className="ci-item-actions">
                        <button type="button" className="btn btn-sm btn-secondary" onClick={() => handleAddActionFromGap(gap, 'DOCUMENT_EVIDENCE', `Upload supporting evidence for ${gap.requirement_text}`)}>
                          📎 Add Evidence Action
                        </button>
                        {onNavigateToVault && (
                          <button type="button" className="btn btn-sm btn-outline-action" onClick={onNavigateToVault}>
                            🔍 Open Evidence Explorer
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CollapsibleSection>
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

              </>
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
