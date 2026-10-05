import re
import sys

with open('frontend/src/views/CareerExecution.jsx', 'r') as f:
    content = f.read()

# Add deduplication and sorting logic for unexecutedActions
dedup_logic = """  // Deduplicate and filter available actions
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
"""

# We need to replace the old unexecutedActions logic
content = re.sub(
    r"  // Actions not yet executed\n  const executedActionIds = new Set\(executions\.map\(e => e\.action_id\)\);\n  const unexecutedActions = availableActions\.filter\(a => !executedActionIds\.has\(a\.action_id\)\);",
    dedup_logic,
    content
)

# New dashboard grid JSX
new_dashboard = """      {/* TAB 1: DASHBOARD */}
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
      )}"""

# Extract the old block
start_marker = '{/* TAB 1: DASHBOARD */}'
end_marker = '{/* TAB 2: BEFORE / AFTER DELTA */}'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers.")
    sys.exit(1)

content = content[:start_idx] + new_dashboard + "\n\n      " + content[end_idx:]

with open('frontend/src/views/CareerExecution.jsx', 'w') as f:
    f.write(content)

print("Updated CareerExecution.jsx successfully.")
