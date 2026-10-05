import React, { useState, useEffect, useCallback } from 'react';
import { coachApi } from '../services/api';

export default function ResumeBuilder({ careerTwin, selectedVersionId, onNavigateToCoach, onNavigateToJobFit }) {
  const [versions, setVersions] = useState([]);
  const [activeVersion, setActiveVersion] = useState(null);
  const [diffData, setDiffData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('sections'); // 'sections' | 'diff' | 'recheck'
  
  // Re-check Job Fit state
  const [jobText, setJobText] = useState('');
  const [recheckResult, setRecheckResult] = useState(null);
  const [recheckLoading, setRecheckLoading] = useState(false);
  
  // Clone / New version state
  const [cloneTitle, setCloneTitle] = useState('');
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [exportLoading, setExportLoading] = useState(false);

  const candidateId = careerTwin?.candidate_id;

  const loadDiff = useCallback(async (versionId) => {
    setDiffLoading(true);
    try {
      const diff = await coachApi.getVersionDiff(versionId);
      setDiffData(diff);
    } catch (err) {
      console.error("Error loading diff:", err);
    } finally {
      setDiffLoading(false);
    }
  }, []);

  const loadVersionDetail = useCallback(async (versionId) => {
    if (!candidateId || !versionId) return;
    try {
      const detail = await coachApi.getResumeVersionDetail(candidateId, versionId);
      setActiveVersion(detail);
      await loadDiff(detail.version_id);
    } catch (err) {
      console.error("Error loading version detail:", err);
      setError(err.message);
    }
  }, [candidateId, loadDiff]);

  // Load versions list
  const loadVersions = useCallback(async (selectId = null) => {
    if (!candidateId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await coachApi.getResumeVersions(candidateId);
      const versionList = Array.isArray(data) ? data : [];
      setVersions(versionList);
      if (versionList.length > 0) {
        const toSelect = selectId 
          ? versionList.find(v => v.version_id === selectId) || versionList[0]
          : versionList[0];
        await loadVersionDetail(toSelect.version_id);
      } else {
        setActiveVersion(null);
        setDiffData(null);
      }
    } catch (err) {
      console.error("Error loading resume versions:", err);
      setError(err.message || "Failed to load resume versions.");
    } finally {
      setLoading(false);
    }
  }, [candidateId, loadVersionDetail]);

  useEffect(() => {
    let isMounted = true;
    if (candidateId) {
      // Defer loading so setState does not run synchronously during render
      const timer = setTimeout(() => {
        if (isMounted) {
          loadVersions(selectedVersionId);
        }
      }, 0);
      return () => {
        isMounted = false;
        clearTimeout(timer);
      };
    }
  }, [candidateId, selectedVersionId, loadVersions]);

  const handleSelectVersion = async (vSummary) => {
    setActionSuccess(null);
    setRecheckResult(null);
    await loadVersionDetail(vSummary.version_id);
  };

  const handleCloneVersion = async () => {
    try {
      let newVersion;
      if (activeVersion) {
        const title = cloneTitle.trim() || `Draft from ${activeVersion.title}`;
        newVersion = await coachApi.cloneResumeVersion(activeVersion.version_id, title);
      } else {
        const title = cloneTitle.trim() || "New Resume Draft";
        newVersion = await coachApi.createResumeVersion(candidateId, title);
      }
      setShowCloneModal(false);
      setCloneTitle('');
      setActionSuccess(`Created new draft version: "${newVersion.title}"`);
      await loadVersions(newVersion.version_id);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRecheckJobFit = async () => {
    if (!activeVersion || !jobText.trim()) return;
    setRecheckLoading(true);
    setError(null);
    try {
      const result = await coachApi.recheckJobFit(
        activeVersion.version_id,
        jobText,
        activeVersion.target_role || "Target Role"
      );
      setRecheckResult(result);
    } catch (err) {
      console.error("Job Fit re-check failed:", err);
      setError(err.message);
    } finally {
      setRecheckLoading(false);
    }
  };

  const handleExportPdf = async () => {
    if (!activeVersion || exportLoading) return;
    setExportLoading(true);
    setError(null);
    try {
      const blob = await coachApi.exportResumeVersionPdf(activeVersion.version_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${activeVersion.title.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.error("PDF export failed:", err);
      setError(err.message || "Failed to export PDF.");
    } finally {
      setExportLoading(false);
    }
  };

  if (!careerTwin) {
    return (
      <div className="view-card empty-state-box">
        <div className="empty-icon">📄</div>
        <h3>No Candidate Profile Loaded</h3>
        <p>Please upload a resume first to create evidence-grounded resume versions.</p>
      </div>
    );
  }

  return (
    <div className="view-card resume-builder-container">
      {/* Top Banner */}
      <div className="feature-top-bar" style={{ marginBottom: '1.25rem' }}>
        <div>
          <span className="badge-pill">Phase 5 • Evidence-Grounded Resume Builder</span>
          <h2>Resume Versions & Evidence Grounding</h2>
          <p className="feature-desc" style={{ marginTop: '0.25rem' }}>
            Inspect, branch, compare, and export verified resume drafts. The original resume is permanently immutable; all applied improvements remain evidence-locked.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {activeVersion && (
            <button
              type="button"
              id="export-resume-pdf-btn"
              onClick={handleExportPdf}
              disabled={exportLoading}
              className="btn-accent"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', textDecoration: 'none' }}
              title="Download deterministic PDF export"
            >
              {exportLoading ? '⏳ Exporting…' : '📥 Export PDF'}
            </button>
          )}
          <button 
            className={activeVersion ? "btn-secondary" : "btn-accent"}
            onClick={() => setShowCloneModal(true)}
            title={activeVersion ? "Create a new draft branching from this version" : "Create a new resume draft"}
          >
            {activeVersion ? "⎇ Branch / Clone Draft" : "+ Create New Version"}
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="alert-box alert-success" style={{ marginBottom: '1rem' }}>
          <span>✓ {actionSuccess}</span>
          <button className="btn-text-dismiss" onClick={() => setActionSuccess(null)}>✕</button>
        </div>
      )}

      {error && (
        <div className="alert-box alert-error" style={{ marginBottom: '1rem' }}>
          <span>⚠ {error}</span>
          <button className="btn-text-dismiss" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Main Grid: Sidebar (Versions) + Main (Content & Diff) */}
      <div className="resume-builder-grid" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '1.5rem', alignItems: 'start' }}>
        
        {/* Left Column: Version History */}
        <div className="version-history-panel" style={{ background: '#F8FAFC', padding: '1rem', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: '#1E293B' }}>Version History</h4>
            <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
              {versions.length > 0 ? `${versions.length} versions` : 'No versions yet'}
            </span>
          </div>

          {loading && <div style={{ fontSize: '0.75rem', color: '#64748B', padding: '0.25rem 0' }}>Loading versions...</div>}

          {!loading && versions.length === 0 && (
            <div style={{ padding: '1.5rem 0.5rem', textAlign: 'center', color: '#64748B', fontSize: '0.85rem' }}>
              No versions yet
            </div>
          )}

          <div className="version-list" style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {versions.map((ver) => {
              const isSelected = activeVersion?.version_id === ver.version_id;
              const isOrig = ver.version_id.startsWith('ver_orig');
              return (
                <div
                  key={ver.version_id}
                  onClick={() => handleSelectVersion(ver)}
                  style={{
                    padding: '0.75rem',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    background: isSelected ? '#EEF2FF' : '#FFFFFF',
                    border: isSelected ? '1.5px solid #4F46E5' : '1px solid #E2E8F0',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                    <strong style={{ fontSize: '0.85rem', color: isSelected ? '#4338CA' : '#1E293B', lineHeight: 1.3 }}>
                      {ver.title}
                    </strong>
                    <span 
                      style={{
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: isOrig ? '#E0E7FF' : ver.status === 'ACTIVE' ? '#DCFCE7' : '#FEF3C7',
                        color: isOrig ? '#3730A3' : ver.status === 'ACTIVE' ? '#166534' : '#92400E'
                      }}
                    >
                      {isOrig ? 'ORIGINAL' : ver.status}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.75rem', color: '#64748B', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span>Target: {ver.target_role || 'General'}</span>
                    <span>Accepted changes: {ver.accepted_changes_count}</span>
                    <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>{new Date(ver.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Version Inspector & Tools */}
        <div className="version-content-panel">
          {activeVersion ? (
            <div>
              {/* Header Card for Active Version */}
              <div style={{ background: '#FFFFFF', padding: '1.25rem', borderRadius: '12px', border: '1px solid #E2E8F0', marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#0F172A' }}>{activeVersion.title}</h3>
                    <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#64748B' }}>
                      Target Role: <strong>{activeVersion.target_role || 'General'}</strong> • Lineage: {activeVersion.parent_version_id ? `Derived from ${activeVersion.parent_version_id}` : 'Root Document (Immutable)'}
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#4F46E5', background: '#EEF2FF', padding: '4px 8px', borderRadius: '6px' }}>
                      🛡️ {activeVersion.evidence_ids?.length || 0} Grounded Evidence Citations
                    </span>
                  </div>
                </div>

                {/* Sub-tab Navigation */}
                <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid #E2E8F0', paddingTop: '0.75rem' }}>
                  <button
                    onClick={() => setActiveTab('sections')}
                    style={{
                      padding: '0.5rem 1rem',
                      background: 'none',
                      border: 'none',
                      borderBottom: activeTab === 'sections' ? '2px solid #4F46E5' : '2px solid transparent',
                      color: activeTab === 'sections' ? '#4F46E5' : '#64748B',
                      fontWeight: activeTab === 'sections' ? 600 : 500,
                      cursor: 'pointer'
                    }}
                  >
                    Structured Resume
                  </button>
                  <button
                    onClick={() => setActiveTab('diff')}
                    style={{
                      padding: '0.5rem 1rem',
                      background: 'none',
                      border: 'none',
                      borderBottom: activeTab === 'diff' ? '2px solid #4F46E5' : '2px solid transparent',
                      color: activeTab === 'diff' ? '#4F46E5' : '#64748B',
                      fontWeight: activeTab === 'diff' ? 600 : 500,
                      cursor: 'pointer'
                    }}
                  >
                    Evidence Diff View ({diffData?.total_changes || 0})
                  </button>
                  <button
                    onClick={() => setActiveTab('recheck')}
                    style={{
                      padding: '0.5rem 1rem',
                      background: 'none',
                      border: 'none',
                      borderBottom: activeTab === 'recheck' ? '2px solid #4F46E5' : '2px solid transparent',
                      color: activeTab === 'recheck' ? '#4F46E5' : '#64748B',
                      fontWeight: activeTab === 'recheck' ? 600 : 500,
                      cursor: 'pointer'
                    }}
                  >
                    Re-check Job Fit
                  </button>
                </div>
              </div>

              {/* TAB 1: Structured Sections */}
              {activeTab === 'sections' && (
                <div className="structured-sections-view" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {activeVersion.sections?.map((section) => (
                    <div 
                      key={section.section_id} 
                      style={{ background: '#FFFFFF', padding: '1.25rem', borderRadius: '12px', border: '1px solid #E2E8F0' }}
                    >
                      <h4 style={{ margin: '0 0 0.75rem 0', color: '#1E293B', borderBottom: '1px solid #F1F5F9', paddingBottom: '0.4rem' }}>
                        {section.name}
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {section.items?.map((item, idx) => (
                          <div 
                            key={idx} 
                            style={{ 
                              padding: '0.75rem', 
                              background: '#F8FAFC', 
                              borderRadius: '8px',
                              border: item.is_modified ? '1px solid #A5B4FC' : '1px solid #E2E8F0'
                            }}
                          >
                            <p style={{ margin: 0, fontSize: '0.9rem', color: '#1E293B', whiteSpace: 'pre-wrap' }}>
                              {item.content}
                            </p>
                            <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.35rem', alignItems: 'center' }}>
                              {item.is_modified && (
                                <span style={{ fontSize: '0.65rem', fontWeight: 700, color: '#4338CA', background: '#E0E7FF', padding: '2px 6px', borderRadius: '4px' }}>
                                  ✓ EVIDENCE-GROUNDED REWRITE
                                </span>
                              )}
                              {item.evidence_ids?.map((eid) => (
                                <span 
                                  key={eid} 
                                  style={{ fontSize: '0.65rem', color: '#475569', background: '#F1F5F9', padding: '2px 6px', borderRadius: '4px', border: '1px solid #CBD5E1' }}
                                >
                                  {eid}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 2: Candidate-Facing Diff View (BEFORE, AFTER, WHY, EVIDENCE) */}
              {activeTab === 'diff' && (
                <div className="diff-view-container">
                  {diffLoading ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#64748B' }}>Computing verified changes...</div>
                  ) : diffData && diffData.changes && diffData.changes.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                      <div style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', padding: '0.75rem 1rem', borderRadius: '8px', color: '#166534', fontSize: '0.85rem' }}>
                        Showing {diffData.total_changes} evidence-grounded modification(s) against parent {diffData.parent_version_id || 'root'}.
                      </div>
                      {diffData.changes.map((change, cIdx) => (
                        <div 
                          key={cIdx} 
                          style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#4F46E5', textTransform: 'uppercase' }}>
                              Section: {change.section_name}
                            </span>
                            <span style={{ fontSize: '0.75rem', color: '#64748B' }}>{change.timestamp}</span>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                            <div style={{ background: '#FEF2F2', padding: '0.75rem', borderRadius: '8px', border: '1px solid #FCA5A5' }}>
                              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#991B1B' }}>BEFORE</span>
                              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#7F1D1D' }}>
                                {change.original_text}
                              </p>
                            </div>
                            <div style={{ background: '#F0FDF4', padding: '0.75rem', borderRadius: '8px', border: '1px solid #86EFAC' }}>
                              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#166534' }}>AFTER (EVIDENCE-LOCKED)</span>
                              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#14532D' }}>
                                {change.suggested_text}
                              </p>
                            </div>
                          </div>

                          <div style={{ background: '#F8FAFC', padding: '0.75rem', borderRadius: '8px', border: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                            <div>
                              <strong style={{ fontSize: '0.75rem', color: '#334155' }}>WHY: </strong>
                              <span style={{ fontSize: '0.8rem', color: '#475569' }}>{change.why}</span>
                            </div>
                            <div>
                              <strong style={{ fontSize: '0.75rem', color: '#334155' }}>EVIDENCE CITATION: </strong>
                              <span style={{ fontSize: '0.8rem', color: '#4F46E5' }}>{change.evidence_citation}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ background: '#FFFFFF', padding: '2.5rem', textAlign: 'center', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
                      <p style={{ margin: 0, color: '#64748B' }}>No modifications applied to this version. Content is identical to baseline.</p>
                      {onNavigateToCoach && (
                        <button 
                          className="btn-accent" 
                          style={{ marginTop: '1rem' }}
                          onClick={onNavigateToCoach}
                        >
                          Go to Resume Coach to Apply Suggestions
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: Re-check Job Fit */}
              {activeTab === 'recheck' && (
                <div className="recheck-container" style={{ background: '#FFFFFF', padding: '1.25rem', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
                  <h4 style={{ margin: '0 0 0.5rem 0', color: '#0F172A' }}>Re-evaluate Job Fit with Updated Draft</h4>
                  <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1rem' }}>
                    Re-run the deterministic Job Fit diagnostic against a target job description to measure how accepted evidence rewrites improved requirement visibility.
                  </p>

                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#334155', marginBottom: '0.35rem' }}>
                      Target Job Description Text
                    </label>
                    <textarea
                      rows={5}
                      className="form-control"
                      placeholder="Paste the job description here to re-evaluate diagnostic coverage..."
                      value={jobText}
                      onChange={(e) => setJobText(e.target.value)}
                      style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '1px solid #CBD5E1', fontSize: '0.85rem' }}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <button
                      className="btn-accent"
                      onClick={handleRecheckJobFit}
                      disabled={recheckLoading || !jobText.trim()}
                    >
                      {recheckLoading ? 'Evaluating Fit...' : '🎯 Re-check Job Fit'}
                    </button>
                    {onNavigateToJobFit && (
                      <button
                        className="btn-secondary"
                        onClick={onNavigateToJobFit}
                      >
                        Open in Job Fit Engine →
                      </button>
                    )}
                  </div>

                  {/* Re-check Diagnostic Results */}
                  {recheckResult && (
                    <div style={{ marginTop: '1.5rem', borderTop: '1px solid #E2E8F0', paddingTop: '1.25rem' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                        <div style={{ background: '#F8FAFC', padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                          <span style={{ fontSize: '0.7rem', color: '#64748B' }}>PREVIOUS COVERAGE</span>
                          <h3 style={{ margin: '0.2rem 0 0 0', color: '#334155' }}>{recheckResult.previous_coverage}%</h3>
                        </div>
                        <div style={{ background: '#EEF2FF', padding: '0.75rem', borderRadius: '8px', textAlign: 'center', border: '1px solid #C7D2FE' }}>
                          <span style={{ fontSize: '0.7rem', color: '#4338CA' }}>CURRENT COVERAGE</span>
                          <h3 style={{ margin: '0.2rem 0 0 0', color: '#4338CA' }}>{recheckResult.current_coverage}%</h3>
                        </div>
                        <div style={{ background: '#F0FDF4', padding: '0.75rem', borderRadius: '8px', textAlign: 'center', border: '1px solid #BBF7D0' }}>
                          <span style={{ fontSize: '0.7rem', color: '#166534' }}>COVERAGE DELTA</span>
                          <h3 style={{ margin: '0.2rem 0 0 0', color: '#166534' }}>
                            {recheckResult.coverage_delta >= 0 ? `+${recheckResult.coverage_delta}%` : `${recheckResult.coverage_delta}%`}
                          </h3>
                        </div>
                        <div style={{ background: '#FFFBEB', padding: '0.75rem', borderRadius: '8px', textAlign: 'center', border: '1px solid #FDE68A' }}>
                          <span style={{ fontSize: '0.7rem', color: '#92400E' }}>REMAINING GAPS</span>
                          <h3 style={{ margin: '0.2rem 0 0 0', color: '#92400E' }}>{recheckResult.remaining_gaps_count}</h3>
                        </div>
                      </div>

                      <div style={{ background: '#F1F5F9', padding: '0.75rem 1rem', borderRadius: '8px', fontSize: '0.85rem', color: '#334155', marginBottom: '1rem' }}>
                        {recheckResult.narrative}
                      </div>

                      {recheckResult.requirements_improved?.length > 0 && (
                        <div style={{ marginBottom: '1rem' }}>
                          <strong style={{ fontSize: '0.8rem', color: '#166534' }}>Requirements Improved via Verified Suggestions:</strong>
                          <ul style={{ margin: '0.5rem 0 0 1.25rem', padding: 0, fontSize: '0.85rem', color: '#14532D' }}>
                            {recheckResult.requirements_improved.map((r, idx) => (
                              <li key={idx}>✓ {r.requirement_text} ({r.category})</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div style={{ fontSize: '0.75rem', color: '#64748B', fontStyle: 'italic' }}>
                        Disclaimer: This score measures resume alignment with job requirements; it does not predict hiring probability.
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: '#64748B', background: '#FFFFFF', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📄</div>
              <h4 style={{ color: '#1E293B', marginBottom: '0.5rem' }}>
                {versions.length === 0 ? "No versions yet" : "No Version Selected"}
              </h4>
              <p style={{ margin: '0 auto', maxWidth: '400px', fontSize: '0.85rem' }}>
                {versions.length === 0 
                  ? "Create your first evidence-grounded resume draft to begin tailoring sections and tracking version diffs." 
                  : "Select a version from the history list to inspect its content and diff."}
              </p>
              {versions.length === 0 && (
                <button 
                  className="btn-accent" 
                  style={{ marginTop: '1rem' }} 
                  onClick={() => setShowCloneModal(true)}
                >
                  + Create First Resume Version
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Clone / Branch Modal */}
      {showCloneModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{ background: '#FFFFFF', padding: '1.5rem', borderRadius: '12px', width: '420px', maxWidth: '90%' }}>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>
              {activeVersion ? "Branch / Clone Version" : "Create Resume Version"}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', margin: '0 0 1rem 0' }}>
              {activeVersion 
                ? `Create a new draft version branching from "${activeVersion.title}". Historical versions remain untouched.` 
                : "Initialize a new evidence-grounded version from your Career Twin."}
            </p>
            <input
              type="text"
              className="form-control"
              placeholder={activeVersion ? "e.g., Draft 3 — Backend Engineer Targeted" : "e.g., Targeted Resume Draft"}
              value={cloneTitle}
              onChange={(e) => setCloneTitle(e.target.value)}
              style={{ width: '100%', padding: '0.6rem', borderRadius: '6px', border: '1px solid #CBD5E1', marginBottom: '1rem' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={() => setShowCloneModal(false)}>Cancel</button>
              <button className="btn-accent" onClick={handleCloneVersion}>
                {activeVersion ? "Create Branch" : "Create Version"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
