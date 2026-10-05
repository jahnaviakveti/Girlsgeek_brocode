import React, { useState, useMemo } from 'react';
import { coachApi } from '../services/api';
import './ResumeCoach.css'; // Let's create a new specific CSS file

const cleanBulletText = (text) => {
  if (!text) return '';
  return text
    .replace(/^[•\u2022\u25cf\u25aa\u25e6\u25cb\u2043\u2219\u2023\u25b8\uf0b7\-*?~·]\s*/, '')
    .trim();
};

export default function ResumeCoach({ careerTwin, handoffPayload, onClearHandoff, onNavigateToBuilder }) {
  const [loadingIds, setLoadingIds] = useState(new Set());
  const [results, setResults] = useState({});
  const [accepted, setAccepted] = useState({});
  const [errorMsg, setErrorMsg] = useState(null);
  const [applyingToDraft, setApplyingToDraft] = useState(false);
  const [filter, setFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const isBulk = handoffPayload?.bulk;
  const items = useMemo(() => {
    return isBulk ? (handoffPayload.items || []) : (handoffPayload ? [handoffPayload] : []);
  }, [isBulk, handoffPayload]);

  const handleGenerateRewrite = async (item) => {
    if (!item) return;
    setLoadingIds(prev => new Set(prev).add(item.requirement_id));
    setErrorMsg(null);

    try {
      const payload = {
        candidate_id: item.candidate_id || careerTwin.candidate_id,
        requirement_id: item.requirement_id,
        requirement_text: item.requirement_text,
        target_role: item.target_role,
        priority: item.priority || "REQUIRED",
        gap_type: item.gap_type || "RESUME_VISIBILITY_GAP",
        evidence_ids: item.evidence_ids || [],
        existing_evidence_snippets: item.existing_evidence_snippets || [],
        missing_elements: item.missing_elements || [],
        current_resume_text: cleanBulletText(item.existing_evidence_snippets?.[0] || ""),
        action_prompt: item.action_prompt || ""
      };

      const data = await coachApi.generateResumeRewrite(payload);
      setResults(prev => ({...prev, [item.requirement_id]: data}));
      setAccepted(prev => ({...prev, [item.requirement_id]: data.status === 'ACCEPTED'}));
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message || 'Failed to generate resume rewrite.');
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(item.requirement_id);
        return next;
      });
    }
  };

  const handleBulkGenerateAll = async () => {
    const visibilityGaps = items.filter(i => i.gap_type === 'RESUME_VISIBILITY_GAP' && !results[i.requirement_id]);
    for (const item of visibilityGaps) {
      await handleGenerateRewrite(item);
    }
  };

  const handleCreateTailoredVersion = async () => {
    setApplyingToDraft(true);
    try {
      const targetTitle = handoffPayload?.target_role 
        ? `${handoffPayload.target_role} — Targeted Resume` 
        : "Targeted Resume Draft";
      
      let targetVersion = await coachApi.createResumeVersion(
        careerTwin.candidate_id, 
        targetTitle, 
        handoffPayload?.target_role || null
      );
      
      const itemsToApply = Object.values(results).filter(r => accepted[r.requirement_id] && r.status === 'ACCEPTED');
      for (const sug of itemsToApply) {
        targetVersion = await coachApi.applySuggestionToVersion(targetVersion.version_id, sug, false);
      }
      
      if(onNavigateToBuilder) onNavigateToBuilder(targetVersion.version_id);
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message);
    } finally {
      setApplyingToDraft(false);
    }
  };

  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">📝</div>
        <h3>No Active Career Twin</h3>
        <p>Please upload your resume in the Dashboard to analyze and optimize your resume content.</p>
      </div>
    );
  }

  const metrics = {
    total: items.length,
    visibility: items.filter(i => i.gap_type === 'RESUME_VISIBILITY_GAP').length,
    experience: items.filter(i => i.gap_type === 'EXPERIENCE_GAP').length,
    aiImprovements: Object.values(results).filter(r => r.status === 'ACCEPTED').length
  };

  const filteredItems = items.filter(item => {
    if (searchQuery && !item.requirement_text.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    const res = results[item.requirement_id];
    if (filter === 'ALL') return true;
    if (filter === 'AI_IMPROVEMENTS') return res?.status === 'ACCEPTED';
    if (filter === 'EXPERIENCE_GAPS') return item.gap_type === 'EXPERIENCE_GAP';
    if (filter === 'REJECTED') return res?.status === 'REJECTED' || res?.status === 'NO_SAFE_REWRITE';
    return true;
  });

  const acceptedCount = Object.values(accepted).filter(Boolean).length;
  const isGeneratingAny = loadingIds.size > 0;

  return (
    <div className="rc-container">
      {/* 1. PAGE HEADER */}
      <header className="rc-header">
        <div className="rc-header-content">
          <div className="rc-header-main">
            <span className="rc-badge-phase">PHASE 4</span>
            <h1 className="rc-title">Evidence-Locked AI Resume Coach</h1>
            <p className="rc-subtitle">Turn your existing experience into stronger, job-targeted resume language — without inventing anything.</p>
          </div>
          <div className="rc-header-target">
            <div className="rc-target-card">
              <div className="rc-target-label">Target Role</div>
              <div className="rc-target-value">{handoffPayload?.target_role || 'General Frontend / Full Stack'}</div>
            </div>
            <button className="rc-btn-primary" onClick={handleBulkGenerateAll} disabled={isGeneratingAny}>
              ✨ Generate AI Improvements
            </button>
            <div className="rc-validation-note">AI suggestions are always validated against your Evidence Vault.</div>
          </div>
        </div>
      </header>

      {/* 2. JOB ALIGNMENT SUMMARY */}
      <div className="rc-summary-cards">
        <div className="rc-summary-card">
          <div className="rc-summary-value">{metrics.total}</div>
          <div className="rc-summary-label">Requirements analyzed</div>
        </div>
        <div className="rc-summary-card">
          <div className="rc-summary-value">{metrics.visibility}</div>
          <div className="rc-summary-label">Visibility gaps</div>
        </div>
        <div className="rc-summary-card">
          <div className="rc-summary-value">{metrics.experience}</div>
          <div className="rc-summary-label">Experience gaps</div>
        </div>
        <div className="rc-summary-card rc-summary-highlight">
          <div className="rc-summary-value">{metrics.aiImprovements}</div>
          <div className="rc-summary-label">AI improvements</div>
        </div>
      </div>

      {/* 11. GENERATION STATE (Global) */}
      {isGeneratingAny && (
        <div className="rc-global-loader">
          <div className="rc-spinner"></div>
          <span>✨ Analyzing your resume against the target role...</span>
        </div>
      )}
      {errorMsg && <div className="rc-error-banner">{errorMsg}</div>}

      {/* 3. FILTER BAR */}
      <div className="rc-filter-bar">
        <div className="rc-filter-tabs">
          <button className={`rc-tab ${filter === 'ALL' ? 'active' : ''}`} onClick={() => setFilter('ALL')}>All</button>
          <button className={`rc-tab ${filter === 'AI_IMPROVEMENTS' ? 'active' : ''}`} onClick={() => setFilter('AI_IMPROVEMENTS')}>AI Improvements</button>
          <button className={`rc-tab ${filter === 'EXPERIENCE_GAPS' ? 'active' : ''}`} onClick={() => setFilter('EXPERIENCE_GAPS')}>Experience Gaps</button>
          <button className={`rc-tab ${filter === 'REJECTED' ? 'active' : ''}`} onClick={() => setFilter('REJECTED')}>Rejected / Unsafe</button>
        </div>
        <div className="rc-search-box">
          <input 
            type="text" 
            placeholder="Search requirements..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="rc-search-input"
          />
        </div>
      </div>

      {/* 4. REQUIREMENT CARDS LIST */}
      <div className="rc-cards-list">
        {filteredItems.map(item => {
          const isExpGap = item.gap_type === 'EXPERIENCE_GAP';
          const isLoading = loadingIds.has(item.requirement_id);
          const res = results[item.requirement_id];
          const isAccepted = accepted[item.requirement_id];

          return (
            <div key={item.requirement_id} className={`rc-card ${isAccepted ? 'rc-card-accepted' : ''}`}>
              
              {/* Card Header */}
              <div className="rc-card-header">
                <span className={`rc-gap-badge ${isExpGap ? 'rc-gap-exp' : 'rc-gap-vis'}`}>
                  {isExpGap ? '🎯 EXPERIENCE GAP' : 'RESUME VISIBILITY GAP'}
                </span>
                <h3 className="rc-req-title">{item.requirement_text}</h3>
              </div>

              {/* 9. EXPERIENCE GAP (No AI rewrite) */}
              {isExpGap ? (
                <div className="rc-exp-gap-content">
                  <p className="rc-exp-msg">This requirement isn't currently supported by verified evidence in your Evidence Vault.</p>
                  <div className="rc-exp-next-steps">
                    <strong>Recommended next steps:</strong>
                    <div className="rc-exp-actions">
                      <button className="rc-btn-outline">Learn this skill</button>
                      <button className="rc-btn-outline">Build a project</button>
                      <button className="rc-btn-outline">Document evidence</button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rc-vis-gap-content">
                  
                  {/* Generation State per card */}
                  {isLoading ? (
                    <div className="rc-card-loader">
                      <div className="rc-spinner-small"></div>
                      <div className="rc-loader-steps">
                        <span>Analyzing requirement...</span>
                        <span>Retrieving verified evidence...</span>
                        <span>Generating rewrite...</span>
                        <span>Validating claims...</span>
                      </div>
                    </div>
                  ) : !res ? (
                    <div className="rc-pre-gen">
                      <div className="rc-section-label">CURRENT RESUME</div>
                      <p className="rc-text-block">{cleanBulletText(item.existing_evidence_snippets?.[0]) || 'No matching excerpt found.'}</p>
                      <div className="rc-card-actions">
                        <button className="rc-btn-secondary" onClick={() => handleGenerateRewrite(item)}>✨ Generate AI Improvement</button>
                      </div>
                    </div>
                  ) : (
                    <div className="rc-post-gen">
                      
                      {/* 12. ACCEPTED STATE */}
                      {isAccepted ? (
                        <div className="rc-accepted-state">
                          <div className="rc-accepted-header">
                            <span className="rc-accepted-title">✓ Suggestion accepted</span>
                            <span className="rc-evidence-badge">Evidence validated</span>
                          </div>
                          <div className="rc-diff-view">
                            <div className="rc-diff-original">
                              <span className="rc-diff-label">Original</span>
                              <p>{cleanBulletText(res.original_text)}</p>
                            </div>
                            <div className="rc-diff-arrow">→</div>
                            <div className="rc-diff-updated">
                              <span className="rc-diff-label">Updated</span>
                              <p>{cleanBulletText(res.suggested_text)}</p>
                            </div>
                          </div>
                          <div className="rc-card-actions">
                            <button className="rc-btn-text" onClick={() => handleGenerateRewrite(item)}>↻ Regenerate</button>
                            <button className="rc-btn-text" onClick={() => setAccepted(prev => ({...prev, [item.requirement_id]: false}))}>Undo</button>
                          </div>
                        </div>
                      ) : (
                        <>
                          {/* AI SUGGESTION AREA or REJECTIONS */}
                          {res.status === 'ACCEPTED' && (
                            <div className="rc-suggestion-panel">
                              <div className="rc-comparison">
                                <div className="rc-comp-side">
                                  <div className="rc-section-label">CURRENT RESUME</div>
                                  <p className="rc-text-block">{cleanBulletText(res.original_text)}</p>
                                </div>
                                <div className="rc-comp-side rc-comp-suggested">
                                  <div className="rc-section-label-ai">✨ AI SUGGESTION</div>
                                  <p className="rc-text-block">{cleanBulletText(res.suggested_text)}</p>
                                </div>
                              </div>
                              <div className="rc-rationale">
                                <strong>Why this helps</strong>
                                <p>{res.explanation}</p>
                              </div>
                              <div className="rc-evidence">
                                <strong>Evidence</strong>
                                <div className="rc-evidence-chips">
                                  {res.evidence_used?.map((ev, idx) => (
                                    <div key={idx} className="rc-chip" title={`${ev.source_text} (${ev.evidence_id})`}>
                                      {ev.evidence_id.substring(0, 8)}
                                    </div>
                                  ))}
                                </div>
                              </div>
                              
                              {/* 6. ACTION BUTTONS */}
                              <div className="rc-card-actions rc-card-actions-right">
                                <button className="rc-btn-text" onClick={() => setResults(prev => { const n = {...prev}; delete n[item.requirement_id]; return n; })}>Keep Original</button>
                                <button className="rc-btn-secondary" onClick={() => handleGenerateRewrite(item)}>↻ Regenerate</button>
                                <button className="rc-btn-primary" onClick={() => setAccepted(prev => ({...prev, [item.requirement_id]: true}))}>✓ Accept Suggestion</button>
                              </div>
                            </div>
                          )}

                          {/* 7. REJECTED / UNSAFE STATE */}
                          {res.status === 'REJECTED' && (
                            <div className="rc-rejected-panel">
                              <div className="rc-rejected-header">
                                <span className="rc-warn-icon">⚠️</span>
                                <h4>AI suggestion blocked</h4>
                              </div>
                              <p className="rc-warn-msg">Vettora found claims that could not be verified against your Evidence Vault.</p>
                              
                              <details className="rc-rejected-details">
                                <summary>Unsupported claims detected: {res.unsupported_claims?.length || 0} <span className="rc-view-details">[ View details ]</span></summary>
                                <div className="rc-details-content">
                                  <p className="rc-backend-reason">{res.explanation}</p>
                                  <ul>
                                    {res.unsupported_claims?.map((uc, i) => <li key={i}>{uc}</li>)}
                                  </ul>
                                </div>
                              </details>

                              <div className="rc-card-actions">
                                <button className="rc-btn-secondary" onClick={() => handleGenerateRewrite(item)}>↻ Regenerate</button>
                                <button className="rc-btn-text" onClick={() => setResults(prev => { const n = {...prev}; delete n[item.requirement_id]; return n; })}>Keep Original</button>
                              </div>
                            </div>
                          )}

                          {/* 8. NO_SAFE_REWRITE */}
                          {res.status === 'NO_SAFE_REWRITE' && (
                            <div className="rc-no-rewrite-panel">
                              <div className="rc-shield-header">
                                <span className="rc-shield-icon">🛡</span>
                                <h4>No safe rewrite available</h4>
                              </div>
                              <p className="rc-shield-msg">Vettora couldn't produce a stronger version without risking unsupported claims.</p>
                              <div className="rc-card-actions">
                                <button className="rc-btn-secondary" onClick={() => handleGenerateRewrite(item)}>↻ Regenerate</button>
                                <button className="rc-btn-text" onClick={() => setResults(prev => { const n = {...prev}; delete n[item.requirement_id]; return n; })}>Keep Original</button>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {filteredItems.length === 0 && (
          <div className="rc-empty-filter">No requirements match the current filter.</div>
        )}
      </div>

      {/* 10. BULK ACTION BAR */}
      {isBulk && acceptedCount > 0 && (
        <div className="rc-sticky-action-bar">
          <div className="rc-sticky-content">
            <span className="rc-sticky-text">{acceptedCount} AI improvements accepted</span>
            <div className="rc-sticky-actions">
              <button className="rc-btn-secondary" onClick={handleBulkGenerateAll} disabled={isGeneratingAny}>
                Generate All
              </button>
              <button className="rc-btn-primary" onClick={handleCreateTailoredVersion} disabled={applyingToDraft}>
                {applyingToDraft ? 'Applying...' : 'Create Tailored Resume Version'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
