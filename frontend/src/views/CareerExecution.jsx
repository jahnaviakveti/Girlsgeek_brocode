import React, { useState, useEffect, useCallback } from 'react';
import { coachApi } from '../services/api';

const EXECUTION_TABS = {
  DASHBOARD: 'dashboard',
  COMPARISON: 'comparison',
  REQUIREMENTS: 'requirements',
  TIMELINE: 'timeline',
};

const ARTIFACT_TYPES = [
  { value: 'GITHUB_REPO', label: 'GitHub Repository' },
  { value: 'DEPLOYED_PROJECT', label: 'Deployed Project / Application' },
  { value: 'PROJECT_REPORT', label: 'Project Technical Report' },
  { value: 'TECHNICAL_DOCUMENT', label: 'Technical Documentation / Architecture' },
  { value: 'PORTFOLIO_ARTIFACT', label: 'Portfolio Artifact / Code Sample' },
  { value: 'CERTIFICATE', label: 'Certification / Exam Verification' },
  { value: 'COURSE_COMPLETION', label: 'Course Completion Evidence' },
  { value: 'INTERNSHIP_WORK', label: 'Internship / Work Artifact' },
  { value: 'RESEARCH_PAPER', label: 'Research Paper / Publication' },
  { value: 'PRESENTATION', label: 'Technical Presentation / Demo' },
];

const CLAIM_SCOPES = [
  { value: 'LEVEL 1 — TECHNOLOGY PRESENCE', label: 'Level 1: Technology Presence (Mentioned / Read about)' },
  { value: 'LEVEL 2 — USAGE', label: 'Level 2: Basic Usage (Tutorials / Exercises)' },
  { value: 'LEVEL 3 — IMPLEMENTATION', label: 'Level 3: Implementation (Built functional project)' },
  { value: 'LEVEL 4 — OPERATIONAL / PRODUCTION', label: 'Level 4: Operational / Production (Deployed, managed, monitored)' },
  { value: 'LEVEL 5 — SPECIFIC SCOPE', label: 'Level 5: Specific Scope (High-scale, cluster admin, multi-region)' },
];

export default function CareerExecution({ careerTwin }) {
  const [targets, setTargets] = useState([]);
  const [selectedTargetId, setSelectedTargetId] = useState(null);
  const [executions, setExecutions] = useState([]);
  const [availableActions, setAvailableActions] = useState([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState(null);
  const [targetProgress, setTargetProgress] = useState(null);
  const [activeTab, setActiveTab] = useState(EXECUTION_TABS.DASHBOARD);

  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [actionFilter, setActionFilter] = useState('ALL');

  // Modals & form state
  const [showArtifactModal, setShowArtifactModal] = useState(false);
  const [artifactForm, setArtifactForm] = useState({
    title: '',
    artifact_type: 'GITHUB_REPO',
    uri: '',
    description: '',
    section: '',
    technologies: '',
    claimed_scope: 'LEVEL 3 — IMPLEMENTATION',
    is_operational_production: false,
  });

  const [showBlockerModal, setShowBlockerModal] = useState(false);
  const [blockerForm, setBlockerForm] = useState({
    reason: '',
    next_step: '',
  });

  const [progressUpdatePercent, setProgressUpdatePercent] = useState(50);
  const [newNoteText, setNewNoteText] = useState('');
  const [confirmVerification, setConfirmVerification] = useState(false);

  const candidateId = careerTwin?.candidate_id;

  // Load targets
  const loadTargets = useCallback(async () => {
    if (!candidateId) return;
    try {
      const data = await coachApi.getCareerTargets(candidateId);
      setTargets(data);
      if (data.length > 0 && !selectedTargetId) {
        setSelectedTargetId(data[0].target_id);
      }
    } catch (err) {
      console.error("Failed to load targets:", err);
      setError(err.message);
    }
  }, [candidateId, selectedTargetId]);

  // Load executions for candidate and actions for current target
  const loadExecutionsAndData = useCallback(async () => {
    if (!candidateId) return;
    setLoading(true);
    setError(null);
    try {
      const [execList, actionsList] = await Promise.all([
        coachApi.getCareerExecutions(candidateId),
        selectedTargetId ? coachApi.getCareerActions(candidateId, selectedTargetId) : Promise.resolve([]),
      ]);
      setExecutions(execList);
      setAvailableActions(actionsList);

      if (selectedTargetId) {
        const prog = await coachApi.getCareerTargetProgress(selectedTargetId, candidateId);
        setTargetProgress(prog);
      }
    } catch (err) {
      console.error("Failed to load execution data:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [candidateId, selectedTargetId]);

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
    const timer = setTimeout(() => {
      if (isMounted) {
        loadExecutionsAndData();
      }
    }, 0);
    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [loadExecutionsAndData]);

  // Derived selected execution
  const selectedExecution = selectedExecutionId 
    ? (executions.find(e => e.execution_id === selectedExecutionId) || null)
    : null;

  // Sync progress slider with selected execution progress
  useEffect(() => {
    if (selectedExecution) {
      setProgressUpdatePercent(selectedExecution.progress_percent ?? 0);
    }
  }, [selectedExecution?.execution_id, selectedExecution?.progress_percent]);

  // Handle start execution
  const handleStartExecution = async (executionId) => {
    setActionLoading(true);
    setError(null);
    try {
      const updated = await coachApi.startCareerExecution(executionId, {
        candidate_id: candidateId,
      });
      setExecutions(prev => prev.map(e => e.execution_id === executionId ? updated : e));
      setSelectedExecutionId(updated.execution_id);
      setSuccessMsg("Action moved to IN_PROGRESS.");
      await loadExecutionsAndData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle create execution for an existing career action
  const handleCreateExecutionForAction = async (action) => {
    setActionLoading(true);
    setError(null);
    try {
      const newExec = await coachApi.createCareerExecution({
        candidate_id: candidateId,
        action_id: action.action_id,
        target_id: selectedTargetId || action.target_id,
        title: action.title,
        notes: action.description,
      });
      setExecutions(prev => [...prev.filter(e => e.execution_id !== newExec.execution_id), newExec]);
      setSelectedExecutionId(newExec.execution_id);
      setSuccessMsg(`Created execution for: ${action.title}`);
      await loadExecutionsAndData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle update progress
  const handleUpdateProgress = async (executionId) => {
    setActionLoading(true);
    setError(null);
    try {
      const pct = parseInt(progressUpdatePercent, 10);
      const note = newNoteText.trim() ? newNoteText.trim() : undefined;
      const updated = await coachApi.updateCareerExecutionProgress(executionId, {
        candidate_id: candidateId,
        progress_percent: pct,
        note: note,
        notes: note,
      });
      setExecutions(prev => prev.map(e => e.execution_id === executionId ? updated : e));
      setProgressUpdatePercent(updated.progress_percent ?? pct);
      setSelectedExecutionId(updated.execution_id);
      setNewNoteText('');
      setSuccessMsg("Progress updated.");
      await loadExecutionsAndData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle blocker report
  const handleReportBlocker = async (executionId) => {
    if (!blockerForm.reason.trim()) {
      setError("Please describe the blocker reason.");
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await coachApi.blockCareerExecution(executionId, {
        candidate_id: candidateId,
        blocker_reason: blockerForm.reason.trim(),
        next_step: blockerForm.next_step.trim() || undefined,
      });
      setExecutions(prev => prev.map(e => e.execution_id === executionId ? updated : e));
      setSelectedExecutionId(updated.execution_id);
      setShowBlockerModal(false);
      setBlockerForm({ reason: '', next_step: '' });
      setSuccessMsg("Action marked as BLOCKED.");
      await loadExecutionsAndData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle self-reported completion
  const handleCompleteSelfReported = async (executionId) => {
    setActionLoading(true);
    setError(null);
    try {
      const noteContent = "Completed work. Ready for evidence submission.";
      const updated = await coachApi.completeCareerExecution(executionId, {
        candidate_id: candidateId,
        final_notes: noteContent,
        notes: noteContent,
      });
      setExecutions(prev => prev.map(e => e.execution_id === executionId ? updated : e));
      setProgressUpdatePercent(100);
      setSelectedExecutionId(updated.execution_id);
      setSuccessMsg("Action marked as COMPLETED (Self-Reported). Note: Genuine evidence must be validated before skills/experience are granted.");
      await loadExecutionsAndData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle submit artifact
  const handleSubmitArtifact = async (executionId) => {
    if (!artifactForm.title.trim()) {
      setError("Artifact title is required.");
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const techs = artifactForm.technologies
        ? artifactForm.technologies.split(',').map(s => s.trim()).filter(Boolean)
        : [];
      
      const updated = await coachApi.submitCareerExecutionArtifact(executionId, {
        candidate_id: candidateId,
        name: artifactForm.title.trim(),
        title: artifactForm.title.trim(),
        artifact_type: artifactForm.artifact_type,
        url_or_path: artifactForm.uri.trim() || undefined,
        uri: artifactForm.uri.trim() || undefined,
        description: artifactForm.description.trim() || undefined,
        technologies: techs,
        artifact: {
          title: artifactForm.title.trim(),
          name: artifactForm.title.trim(),
          artifact_type: artifactForm.artifact_type,
          uri: artifactForm.uri.trim() || undefined,
          url_or_path: artifactForm.uri.trim() || undefined,
          description: artifactForm.description.trim() || undefined,
          section: artifactForm.section.trim() || undefined,
          technologies: techs,
          claimed_scope: artifactForm.claimed_scope,
          is_operational_production: artifactForm.is_operational_production,
        },
      });
      setExecutions(prev => prev.map(e => e.execution_id === executionId ? updated : e));
      setSelectedExecutionId(updated.execution_id);
      setShowArtifactModal(false);
      setArtifactForm({
        title: '',
        artifact_type: 'GITHUB_REPO',
        uri: '',
        description: '',
        section: '',
        technologies: '',
        claimed_scope: 'LEVEL 3 — IMPLEMENTATION',
        is_operational_production: false,
      });
      setSuccessMsg("Artifact submitted. Status updated to EVIDENCE_SUBMITTED.");
      await loadExecutionsAndData();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Handle verify evidence
  const handleVerifyEvidence = async (executionId) => {
    if (!confirmVerification) {
      setError("You must explicitly confirm that this evidence is genuine and ready for verification.");
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const result = await coachApi.verifyCareerExecutionEvidence(executionId, {
        candidate_id: candidateId,
        confirm_genuine: true,
      });
      const verifiedCount = result.verified_count ?? result.evidence_ids?.length ?? 0;
      setSuccessMsg(`Verification complete! ${verifiedCount} item(s) verified and added to Evidence Vault. Career Twin and Job Fit refreshed.`);
      setConfirmVerification(false);
      await loadExecutionsAndData();
      setSelectedExecutionId(executionId);
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">🚀</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to begin Career Execution & Progress Tracking.</p>
      </div>
    );
  }

  const selectedTarget = targets.find(t => t.target_id === selectedTargetId);
  const filteredExecutions = executions.filter(e => {
    if (!selectedTargetId) return true;
    return e.target_id === selectedTargetId;
  });

  // Deduplicate and filter available actions
  const uniqueActions = [];
  const seenActionIds = new Set();
  for (const action of availableActions) {
    if (!seenActionIds.has(action.action_id)) {
      seenActionIds.add(action.action_id);
      uniqueActions.push(action);
    }
  }

  const executedActionIds = new Set(executions.map(e => e.action_id));
  const unexecutedActions = uniqueActions.filter(a => !executedActionIds.has(a.action_id));

  // Sort by Priority (HIGH > MEDIUM > LOW), preserving stable order within the same priority
  const PRIORITY_ORDER = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
  unexecutedActions.sort((a, b) => (PRIORITY_ORDER[b.priority] || 0) - (PRIORITY_ORDER[a.priority] || 0));

  const displayActions = unexecutedActions.filter(a => {
    if (actionFilter === 'ALL') return true;
    if (['HIGH', 'MEDIUM', 'LOW'].includes(actionFilter)) return a.priority === actionFilter;
    if (actionFilter === 'RESUME') return a.action_type === 'RESUME_REWRITE';
    if (actionFilter === 'LEARN') return a.action_type === 'LEARN_CONCEPT';
    if (actionFilter === 'BUILD') return a.action_type === 'BUILD_PROJECT';
    if (actionFilter === 'EXPERIENCE') return a.action_type === 'GAIN_EXPERIENCE';
    return true;
  });


  return (
    <div className="career-execution-view">
      {/* Header Panel */}
      <div className="ce-header-panel">
        <div className="ce-header-left">
          <div className="ce-badge">🚀 Phase 8 • Career Execution & Evidence-Based Progress</div>
          <h2 className="ce-title">Career Execution & Progress Tracking</h2>
          <p className="ce-subtitle">
            Bridge the gap between ambition and verifiable qualification. 
            <strong> Principle: Action Completion ≠ Skill Acquisition.</strong> Only verified evidence in the Evidence Vault elevates your Career Twin.
          </p>
        </div>

        <div className="ce-header-actions">
          {targets.length > 0 && (
            <div className="target-select-wrap">
              <label htmlFor="target-select" className="target-select-label">Career Target:</label>
              <select
                id="target-select"
                className="target-dropdown"
                value={selectedTargetId || ''}
                onChange={(e) => {
                  setSelectedTargetId(e.target.value);
                  setSelectedExecutionId(null);
                }}
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
            className="btn-secondary btn-sm" 
            onClick={loadExecutionsAndData} 
            disabled={loading}
          >
            {loading ? 'Refreshing...' : '🔄 Refresh Progress'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="ce-alert ce-alert-error" role="alert">
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">{error}</div>
          <button className="alert-close" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {successMsg && (
        <div className="ce-alert ce-alert-success" role="alert">
          <span className="alert-icon">✅</span>
          <div className="alert-content">{successMsg}</div>
          <button className="alert-close" onClick={() => setSuccessMsg(null)}>✕</button>
        </div>
      )}

      {/* Core Principle Callout */}
      <div className="ce-principle-banner">
        <div className="principle-icon">⚖️</div>
        <div className="principle-body">
          <h4 className="principle-title">EVIDENCE INTEGRITY RULE</h4>
          <p className="principle-desc">
            Marking an action as complete is <strong>self-reported progress</strong>. 
            It does not alter your Career Twin or satisfy job requirements. To turn effort into verified qualification, 
            submit authentic artifacts and confirm verification through the Evidence Vault.
          </p>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="ce-subtabs">
        <button
          className={`ce-subtab-btn ${activeTab === EXECUTION_TABS.DASHBOARD ? 'active' : ''}`}
          onClick={() => setActiveTab(EXECUTION_TABS.DASHBOARD)}
        >
          📋 Execution Dashboard ({filteredExecutions.length})
        </button>
        <button
          className={`ce-subtab-btn ${activeTab === EXECUTION_TABS.COMPARISON ? 'active' : ''}`}
          onClick={() => setActiveTab(EXECUTION_TABS.COMPARISON)}
        >
          📊 Target Before / After Delta
        </button>
        <button
          className={`ce-subtab-btn ${activeTab === EXECUTION_TABS.REQUIREMENTS ? 'active' : ''}`}
          onClick={() => setActiveTab(EXECUTION_TABS.REQUIREMENTS)}
        >
          🎯 Requirement Progress & Scope
        </button>
        <button
          className={`ce-subtab-btn ${activeTab === EXECUTION_TABS.TIMELINE ? 'active' : ''}`}
          onClick={() => setActiveTab(EXECUTION_TABS.TIMELINE)}
        >
          ⏱️ Execution Timeline ({targetProgress?.timeline?.length || 0})
        </button>
      </div>

            {/* TAB 1: DASHBOARD */}
      {activeTab === EXECUTION_TABS.DASHBOARD && (
        <div className="ce-workspace-grid">
          {/* Left Column: Recommended Actions & Active Executions */}
          <div className="ce-workspace-left">
            
            {/* Active Executions (Compact) */}
            {filteredExecutions.length > 0 && (
              <div className="ce-active-executions-section">
                <h4 className="ce-section-title">ACTIVE EXECUTIONS</h4>
                <div className="ce-active-exec-list">
                  {filteredExecutions.map(exec => {
                    const isSelected = selectedExecution?.execution_id === exec.execution_id;
                    const artifactsCount = exec.artifact_references?.length || 0;
                    return (
                      <div 
                        key={exec.execution_id} 
                        className={`ce-active-exec-row ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedExecutionId(exec.execution_id);
                          setProgressUpdatePercent(exec.progress_percent || 0);
                        }}
                      >
                        <div className="exec-row-left">
                          <div className={`status-dot ${exec.status.toLowerCase()}`}></div>
                          <div className="exec-row-info">
                            <span className="exec-row-title">{exec.title}</span>
                            <span className="exec-row-meta">{exec.progress_percent}% · {artifactsCount} artifact{artifactsCount !== 1 ? 's' : ''}</span>
                          </div>
                        </div>
                        <button className="btn-ghost btn-xs">
                          {isSelected ? 'Opened' : 'Open'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Recommended Career Actions */}
            <div className="ce-recommended-section">
              <div className="ce-section-header-compact">
                <div>
                  <h4 className="ce-section-title">Recommended Career Actions</h4>
                  <p className="ce-section-subtitle">Turn your current career gaps into measurable progress.</p>
                </div>
                <span className="ce-count-badge-minimal">{unexecutedActions.length}</span>
              </div>

              {unexecutedActions.length > 0 && (
                <div className="ce-action-filters">
                  <div className="filter-group">
                    <button className={`filter-btn ${actionFilter === 'ALL' ? 'active' : ''}`} onClick={() => setActionFilter('ALL')}>All</button>
                    <button className={`filter-btn ${actionFilter === 'HIGH' ? 'active' : ''}`} onClick={() => setActionFilter('HIGH')}>High Priority</button>
                    <button className={`filter-btn ${actionFilter === 'MEDIUM' ? 'active' : ''}`} onClick={() => setActionFilter('MEDIUM')}>Medium</button>
                    <button className={`filter-btn ${actionFilter === 'LOW' ? 'active' : ''}`} onClick={() => setActionFilter('LOW')}>Low</button>
                  </div>
                  <div className="filter-group">
                    <button className={`filter-btn ${actionFilter === 'RESUME' ? 'active' : ''}`} onClick={() => setActionFilter('RESUME')}>Resume</button>
                    <button className={`filter-btn ${actionFilter === 'LEARN' ? 'active' : ''}`} onClick={() => setActionFilter('LEARN')}>Learn</button>
                    <button className={`filter-btn ${actionFilter === 'BUILD' ? 'active' : ''}`} onClick={() => setActionFilter('BUILD')}>Build</button>
                    <button className={`filter-btn ${actionFilter === 'EXPERIENCE' ? 'active' : ''}`} onClick={() => setActionFilter('EXPERIENCE')}>Experience</button>
                  </div>
                </div>
              )}

              {displayActions.length === 0 ? (
                <div className="ce-empty-card-compact">No actions match the selected filter.</div>
              ) : (
                <div className="ce-action-card-list">
                  {displayActions.map(action => (
                    <div key={action.action_id} className="ce-compact-action-card">
                      <div className="action-card-header">
                        <span className={`priority-indicator priority-${action.priority?.toLowerCase() || 'low'}`}>
                          {action.priority || 'LOW'}
                        </span>
                        <span className="type-indicator">{action.action_type ? action.action_type.replace('_', ' ') : ''}</span>
                      </div>
                      
                      <h5 className="action-card-title">{action.title}</h5>
                      
                      {action.target_requirement_text && (
                        <div className="action-card-req">
                          <span className="req-label">Target requirement</span>
                          <span className="req-text">{action.target_requirement_text}</span>
                        </div>
                      )}
                      
                      <div className="action-card-footer">
                        <button
                          className="btn-primary btn-sm action-start-btn"
                          onClick={() => handleCreateExecutionForAction(action)}
                          disabled={actionLoading}
                        >
                          Start Tracking →
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Execution Detail Panel (The Workspace) */}
          <div className="ce-workspace-right">
            {selectedExecution ? (
              <div className="ce-active-workspace">
                <div className="workspace-header">
                  <span className="workspace-label">CURRENT EXECUTION</span>
                  <span className={`workspace-priority priority-${selectedExecution.priority?.toLowerCase() || 'medium'}`}>
                    [{selectedExecution.priority || 'MEDIUM'} PRIORITY]
                  </span>
                </div>
                
                <h3 className="workspace-title">{selectedExecution.title}</h3>
                
                {selectedExecution.target_requirement_text && (
                  <div className="workspace-req">
                    <span className="req-label">Target requirement</span>
                    <span className="req-text">{selectedExecution.target_requirement_text}</span>
                  </div>
                )}
                
                <div className="workspace-divider"></div>

                {/* Progress Visualizer */}
                <div className="workspace-flow-visual">
                  <div className={`flow-step ${selectedExecution.status !== 'NOT_STARTED' ? 'active' : ''}`}>
                    <div className="flow-icon">⚡</div>
                    <span>ACTION</span>
                  </div>
                  <div className="flow-connector"></div>
                  <div className={`flow-step ${selectedExecution.progress_percent > 0 ? 'active' : ''}`}>
                    <div className="flow-icon">📈</div>
                    <span>PROGRESS</span>
                  </div>
                  <div className="flow-connector"></div>
                  <div className={`flow-step ${(selectedExecution.artifact_references?.length || 0) > 0 ? 'active' : ''}`}>
                    <div className="flow-icon">📎</div>
                    <span>ARTIFACT</span>
                  </div>
                  <div className="flow-connector"></div>
                  <div className={`flow-step ${selectedExecution.progress_state === 'VERIFIED' ? 'active-verified' : ''}`}>
                    <div className="flow-icon">🛡️</div>
                    <span>VERIFICATION</span>
                  </div>
                </div>

                <div className="workspace-divider"></div>
                
                {/* Progress Section */}
                <div className="workspace-section">
                  <div className="workspace-section-header">
                    <h4>Progress</h4>
                    <span className="workspace-percent">{progressUpdatePercent}%</span>
                  </div>
                  <div className="progress-control-row">
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="5"
                      value={progressUpdatePercent}
                      onChange={(e) => setProgressUpdatePercent(e.target.value)}
                      className="progress-slider"
                      disabled={selectedExecution.status === 'NOT_STARTED'}
                    />
                    <button
                      className="btn-secondary btn-sm"
                      onClick={() => handleUpdateProgress(selectedExecution.execution_id)}
                      disabled={actionLoading || selectedExecution.status === 'NOT_STARTED'}
                    >
                      Save Progress
                    </button>
                  </div>
                  {selectedExecution.status === 'NOT_STARTED' && (
                    <button
                      className="btn-primary start-work-btn"
                      onClick={() => handleStartExecution(selectedExecution.execution_id)}
                      disabled={actionLoading}
                    >
                      ▶️ Start Work
                    </button>
                  )}
                </div>

                <div className="workspace-divider"></div>

                {/* Artifacts Section */}
                <div className="workspace-section">
                  <div className="workspace-section-header">
                    <h4>Artifacts</h4>
                    <span className="artifacts-count">
                      {(!selectedExecution.artifact_references || selectedExecution.artifact_references.length === 0) ? 'No artifacts submitted' : `${selectedExecution.artifact_references.length} artifact(s) submitted`}
                    </span>
                  </div>
                  
                  {selectedExecution.artifact_references && selectedExecution.artifact_references.length > 0 && (
                    <div className="workspace-artifacts-list">
                      {selectedExecution.artifact_references.map((art, idx) => (
                        <div key={art.artifact_id || idx} className="workspace-artifact-item">
                          <span className="art-type">{art.artifact_type}</span>
                          <span className="art-title">{art.title}</span>
                          {art.uri && <a href={art.uri} target="_blank" rel="noopener noreferrer" className="art-link">🔗 Link</a>}
                        </div>
                      ))}
                    </div>
                  )}

                  <button
                    className="btn-outline btn-sm add-artifact-btn"
                    onClick={() => setShowArtifactModal(true)}
                    disabled={actionLoading || selectedExecution.status === 'NOT_STARTED'}
                  >
                    + Submit Artifact
                  </button>
                </div>

                <div className="workspace-divider"></div>

                {/* Blockers Section */}
                <div className="workspace-section">
                  <div className="workspace-section-header">
                    <h4>Blockers</h4>
                    <span className="blocker-status">
                      {selectedExecution.status === 'BLOCKED' ? <span className="text-danger">Action is blocked</span> : 'No blockers reported'}
                    </span>
                  </div>
                  
                  {selectedExecution.status === 'BLOCKED' && selectedExecution.blocker_reason && (
                    <div className="workspace-blocker-info">
                      <strong>Reason:</strong> {selectedExecution.blocker_reason}
                    </div>
                  )}

                  <div className="blocker-actions-row">
                    {selectedExecution.status === 'BLOCKED' ? (
                      <button
                        className="btn-primary btn-sm"
                        onClick={() => handleStartExecution(selectedExecution.execution_id)}
                        disabled={actionLoading}
                      >
                        🔄 Resume Work (Unblock)
                      </button>
                    ) : (
                      <button
                        className="btn-ghost-danger btn-sm"
                        onClick={() => setShowBlockerModal(true)}
                        disabled={actionLoading || selectedExecution.status === 'NOT_STARTED'}
                      >
                        Report Blocker
                      </button>
                    )}
                  </div>
                </div>

                <div className="workspace-divider"></div>

                {/* Completion Section */}
                <div className="workspace-footer-actions">
                  <button
                    className="btn-success full-width"
                    onClick={() => handleCompleteSelfReported(selectedExecution.execution_id)}
                    disabled={actionLoading || selectedExecution.status === 'NOT_STARTED' || selectedExecution.status === 'COMPLETED'}
                  >
                    Mark Self-Reported Complete
                  </button>
                  
                  {selectedExecution.artifact_references && selectedExecution.artifact_references.length > 0 && selectedExecution.progress_state !== 'VERIFIED' && (
                    <div className="verify-callout-compact">
                      <div className="verify-callout-text">
                        <strong>Ready for Validation?</strong> Verify submitted artifacts to establish ground truth in your Evidence Vault.
                      </div>
                      <label className="verify-checkbox-label">
                        <input
                          type="checkbox"
                          checked={confirmVerification}
                          onChange={(e) => setConfirmVerification(e.target.checked)}
                        />
                        I confirm this evidence is genuine.
                      </label>
                      <button
                        className="btn-primary btn-sm verify-btn"
                        onClick={() => handleVerifyEvidence(selectedExecution.execution_id)}
                        disabled={!confirmVerification || actionLoading}
                      >
                        🛡️ Verify Evidence
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="ce-empty-workspace">
                <span className="workspace-label">CURRENT EXECUTION</span>
                <h3 className="empty-workspace-title">No execution selected</h3>
                <p className="empty-workspace-desc">Choose a recommended action to begin.</p>
                
                <div className="empty-workspace-steps">
                  <div className="empty-step"><span className="step-num">1</span> Choose an action</div>
                  <div className="empty-step"><span className="step-num">2</span> Track progress</div>
                  <div className="empty-step"><span className="step-num">3</span> Submit artifacts</div>
                  <div className="empty-step"><span className="step-num">4</span> Verify evidence</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: BEFORE / AFTER DELTA */}
      {activeTab === EXECUTION_TABS.COMPARISON && (
        <div className="ce-comparison-view">
          <div className="comparison-banner">
            <div>
              <h3>Target Progress Comparison: {targetProgress?.target_role || selectedTarget?.target_role || 'Target'}</h3>
              <p className="disclaimer-text">
                ⚠️ <strong>Diagnostic Progress Only:</strong> This view reflects verifiable requirement coverage deltas based on authentic Evidence Vault records. We never compute employability scores, hiring probabilities, or candidate rankings.
              </p>
            </div>
            <button className="btn-secondary btn-sm" onClick={loadExecutionsAndData}>
              🔄 Refresh Snapshot
            </button>
          </div>

          {targetProgress ? (
            <>
              {/* Before vs After Summary Cards */}
              <div className="comparison-cards-grid">
                <div className="comparison-card before-card">
                  <div className="comp-card-badge">BEFORE EXECUTION</div>
                  <h4 className="comp-card-title">Initial Baseline</h4>
                  <div className="comp-stats-list">
                    <div className="comp-stat-row">
                      <span>Matched Requirements:</span>
                      <strong className="text-matched">{targetProgress.before_matched ?? targetProgress.before_summary?.matched ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Partial Requirements:</span>
                      <strong className="text-partial">{targetProgress.before_partial ?? targetProgress.before_summary?.partial ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Missing Requirements:</span>
                      <strong className="text-missing">{targetProgress.before_missing ?? targetProgress.before_summary?.missing ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Visibility Gaps:</span>
                      <strong>{targetProgress.before_visibility_gaps ?? targetProgress.before_summary?.visibility_gaps ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Experience Gaps:</span>
                      <strong>{targetProgress.before_experience_gaps ?? targetProgress.before_summary?.experience_gaps ?? 0}</strong>
                    </div>
                  </div>
                </div>

                <div className="comparison-card after-card">
                  <div className="comp-card-badge">CURRENT / AFTER VERIFICATION</div>
                  <h4 className="comp-card-title">Verified Progress State</h4>
                  <div className="comp-stats-list">
                    <div className="comp-stat-row">
                      <span>Matched Requirements:</span>
                      <strong className="text-matched">{targetProgress.after_matched ?? targetProgress.after_summary?.matched ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Partial Requirements:</span>
                      <strong className="text-partial">{targetProgress.after_partial ?? targetProgress.after_summary?.partial ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Missing Requirements:</span>
                      <strong className="text-missing">{targetProgress.after_missing ?? targetProgress.after_summary?.missing ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Visibility Gaps:</span>
                      <strong>{targetProgress.after_visibility_gaps ?? targetProgress.after_summary?.visibility_gaps ?? 0}</strong>
                    </div>
                    <div className="comp-stat-row">
                      <span>Experience Gaps:</span>
                      <strong>{targetProgress.after_experience_gaps ?? targetProgress.after_summary?.experience_gaps ?? 0}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Requirement Changes Delta Table */}
              <div className="delta-table-section">
                <h4>Requirement State Deltas ({(targetProgress.deltas || targetProgress.delta || []).length})</h4>
                <p className="delta-subtext">
                  Shows requirements whose classification or claim scope moved based on verified Evidence Vault entries.
                </p>

                {(!(targetProgress.deltas || targetProgress.delta) || (targetProgress.deltas || targetProgress.delta).length === 0) ? (
                  <div className="delta-empty-box">
                    <p>No requirement state changes detected yet.</p>
                    <p className="subtext">Submit authentic artifacts and validate them in the Execution Dashboard to advance requirement coverage.</p>
                  </div>
                ) : (
                  <div className="delta-table-wrap">
                    <table className="delta-table">
                      <thead>
                        <tr>
                          <th>Requirement</th>
                          <th>Previous State</th>
                          <th>New Verified State</th>
                          <th>Claim Scope Shift</th>
                          <th>Reason & Provenance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(targetProgress.deltas || targetProgress.delta || []).map((d, i) => (
                          <tr key={d.requirement_id || i}>
                            <td className="req-text-cell">{d.requirement_text}</td>
                            <td>
                              <span className={`status-pill status-${(d.previous_classification || '').toLowerCase()}`}>
                                {d.previous_classification}
                              </span>
                            </td>
                            <td>
                              <span className={`status-pill status-${(d.new_classification || '').toLowerCase()}`}>
                                {d.new_classification}
                              </span>
                            </td>
                            <td>
                              <span className="scope-shift">
                                {d.previous_scope || d.previous_claim_scope || 'None'} → <strong>{d.new_scope || d.new_claim_scope || 'None'}</strong>
                              </span>
                            </td>
                            <td className="reason-cell">
                              <div>{d.reason}</div>
                              {d.supporting_evidence_ids && d.supporting_evidence_ids.length > 0 && (
                                <div className="evidence-tags">
                                  {d.supporting_evidence_ids.map(eid => (
                                    <span key={eid} className="evidence-tag">🔒 {eid}</span>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="ce-empty-card">
              <p>Loading progress comparison snapshot...</p>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: REQUIREMENT PROGRESS & CLAIM SCOPE */}
      {activeTab === EXECUTION_TABS.REQUIREMENTS && (
        <div className="ce-requirements-view">
          <div className="ce-section-header">
            <div>
              <h3>Target Requirement Matrix</h3>
              <p className="ce-subtitle">
                Authoritative claim scopes (Level 1–5) and verified Evidence Vault backing for each requirement.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="ce-empty-card">
              <p>Loading target requirements...</p>
            </div>
          ) : (!(targetProgress?.requirements || targetProgress?.requirement_progress) || (targetProgress.requirements || targetProgress.requirement_progress).length === 0) ? (
            <div className="ce-empty-card">
              <p>No requirements loaded for this target.</p>
            </div>
          ) : (
            <div className="requirements-grid">
              {(targetProgress.requirements || targetProgress.requirement_progress || []).map((req, idx) => {
                const latestSnippet = req.latest_evidence_snippet || req.latest_verified_evidence?.source_text;
                const relatedActionsText = Array.isArray(req.related_actions)
                  ? req.related_actions
                      .map(a => (typeof a === 'string' ? a : (a.title || a.action_id)))
                      .filter(Boolean)
                      .join(', ')
                  : (req.related_actions ? String(req.related_actions) : '');

                return (
                  <div key={req.requirement_id || idx} className="req-card">
                    <div className="req-card-top">
                      <span className={`status-pill status-${(req.current_state || '').toLowerCase()}`}>
                        {req.current_state}
                      </span>
                      <span className="req-evidence-badge">
                        {req.evidence_count} evidence item{req.evidence_count !== 1 ? 's' : ''}
                      </span>
                    </div>

                    <h4 className="req-title">{req.requirement_text}</h4>

                    <div className="req-scope-box">
                      <span className="scope-lbl">Claim Scope:</span>
                      <span className="scope-val">{req.claim_scope}</span>
                    </div>

                    {latestSnippet && (
                      <div className="req-snippet-box">
                        <div className="snippet-lbl">Authoritative Evidence:</div>
                        <p className="snippet-quote">"{latestSnippet}"</p>
                      </div>
                    )}

                    {relatedActionsText && (
                      <div className="req-actions-box">
                        <span className="rel-lbl">Related Action:</span>
                        <span className="rel-val">{relatedActionsText}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: CHRONOLOGICAL TIMELINE */}
      {activeTab === EXECUTION_TABS.TIMELINE && (
        <div className="ce-timeline-view">
          <div className="ce-section-header">
            <div>
              <h3>Target Execution Timeline</h3>
              <p className="ce-subtitle">
                Chronological audit trail of all target events, artifact submissions, and verified Evidence Vault updates.
              </p>
            </div>
          </div>

          {(!targetProgress?.timeline || targetProgress.timeline.length === 0) ? (
            <div className="ce-empty-card">
              <p>No timeline events recorded yet.</p>
            </div>
          ) : (
            <div className="timeline-track">
              {targetProgress.timeline.map((evt, idx) => {
                const eventIcons = {
                  TARGET_CREATED: '🎯',
                  ACTION_STARTED: '▶️',
                  PROGRESS_UPDATED: '📈',
                  BLOCKER_RECORDED: '⚠️',
                  ARTIFACT_SUBMITTED: '📎',
                  SELF_REPORTED_COMPLETE: '🏁',
                  EVIDENCE_VERIFIED: '🛡️',
                  CAREER_TWIN_REFRESHED: '👤',
                  JOB_FIT_REFRESHED: '🎯',
                  REQUIREMENT_STATE_CHANGED: '🔄',
                };
                const icon = eventIcons[evt.event_type] || '📌';

                return (
                  <div key={evt.event_id || idx} className="timeline-item">
                    <div className="timeline-marker">{icon}</div>
                    <div className="timeline-body">
                      <div className="timeline-header">
                        <span className="event-type-badge">{evt.event_type.replace(/_/g, ' ')}</span>
                        <span className="event-timestamp">{new Date(evt.timestamp).toLocaleString()}</span>
                      </div>
                      <div className="event-desc">{evt.description}</div>
                      {evt.evidence_ids && evt.evidence_ids.length > 0 && (
                        <div className="event-evidence-links">
                          {evt.evidence_ids.map(eid => (
                            <span key={eid} className="evidence-tag">🔒 {eid}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ARTIFACT SUBMISSION MODAL */}
      {showArtifactModal && (
        <div className="ce-modal-overlay">
          <div className="ce-modal">
            <div className="ce-modal-header">
              <h3>📎 Submit Genuine Artifact</h3>
              <button className="modal-close" onClick={() => setShowArtifactModal(false)}>✕</button>
            </div>
            <div className="ce-modal-body">
              <p className="modal-subtext">
                Attach proof of your work. Note that artifacts undergo evidence validation before any skills are recorded in your Career Twin.
              </p>

              <div className="form-group">
                <label>Artifact Title *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Kubernetes Cluster Deployment & Helm Charts"
                  value={artifactForm.title}
                  onChange={(e) => setArtifactForm({ ...artifactForm, title: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Artifact Type</label>
                <select
                  className="form-select"
                  value={artifactForm.artifact_type}
                  onChange={(e) => setArtifactForm({ ...artifactForm, artifact_type: e.target.value })}
                >
                  {ARTIFACT_TYPES.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>URL / URI (Optional)</label>
                <input
                  type="url"
                  className="form-input"
                  placeholder="https://github.com/user/k8s-infra or live demo"
                  value={artifactForm.uri}
                  onChange={(e) => setArtifactForm({ ...artifactForm, uri: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Claimed Scope Level</label>
                <select
                  className="form-select"
                  value={artifactForm.claimed_scope}
                  onChange={(e) => setArtifactForm({ ...artifactForm, claimed_scope: e.target.value })}
                >
                  {CLAIM_SCOPES.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Technologies Used (comma separated)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Kubernetes, Docker, Helm, Prometheus"
                  value={artifactForm.technologies}
                  onChange={(e) => setArtifactForm({ ...artifactForm, technologies: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Detailed Description & Scope Notes</label>
                <textarea
                  className="form-textarea"
                  rows="3"
                  placeholder="Describe what was built, deployment configuration, and operational context..."
                  value={artifactForm.description}
                  onChange={(e) => setArtifactForm({ ...artifactForm, description: e.target.value })}
                />
              </div>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={artifactForm.is_operational_production}
                  onChange={(e) => setArtifactForm({ ...artifactForm, is_operational_production: e.target.checked })}
                />
                <span>Includes genuine production / live operational deployment evidence</span>
              </label>
            </div>

            <div className="ce-modal-footer">
              <button className="btn-secondary" onClick={() => setShowArtifactModal(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={() => selectedExecution && handleSubmitArtifact(selectedExecution.execution_id)}
                disabled={actionLoading || !artifactForm.title.trim()}
              >
                {actionLoading ? 'Submitting...' : 'Submit Artifact'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BLOCKER MODAL */}
      {showBlockerModal && (
        <div className="ce-modal-overlay">
          <div className="ce-modal">
            <div className="ce-modal-header">
              <h3>⚠️ Report Execution Blocker</h3>
              <button className="modal-close" onClick={() => setShowBlockerModal(false)}>✕</button>
            </div>
            <div className="ce-modal-body">
              <div className="form-group">
                <label>Blocker Reason *</label>
                <textarea
                  className="form-textarea"
                  rows="3"
                  placeholder="e.g. Waiting for cloud credits, need access to production cluster dataset..."
                  value={blockerForm.reason}
                  onChange={(e) => setBlockerForm({ ...blockerForm, reason: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Next Step to Unblock (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Request access from mentor / setup local Minikube cluster"
                  value={blockerForm.next_step}
                  onChange={(e) => setBlockerForm({ ...blockerForm, next_step: e.target.value })}
                />
              </div>
            </div>

            <div className="ce-modal-footer">
              <button className="btn-secondary" onClick={() => setShowBlockerModal(false)}>
                Cancel
              </button>
              <button
                className="btn-warning"
                onClick={() => selectedExecution && handleReportBlocker(selectedExecution.execution_id)}
                disabled={actionLoading || !blockerForm.reason.trim()}
              >
                {actionLoading ? 'Reporting...' : 'Mark as Blocked'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
