import React, { useState, useMemo } from 'react';
import { coachApi } from '../services/api';

export default function CareerTwin({ careerTwin, evidenceVault, onUploadNew }) {
  const [activeTab, setActiveTab] = useState('skills'); // 'skills' | 'timeline' | 'projects' | 'achievements' | 'vault'
  const [selectedSkill, setSelectedSkill] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null);
  const [selectedType, setSelectedType] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Claim validation tester state
  const [claimInput, setClaimInput] = useState('');
  const [claimResult, setClaimResult] = useState(null);
  const [isValidating, setIsValidating] = useState(false);

  // Filter evidence items
  const rawItems = evidenceVault?.items;

  const filteredVaultItems = useMemo(() => {
    const allItems = rawItems || [];
    return allItems.filter(item => {
      // Type filter
      if (selectedType !== 'ALL') {
        const itemType = (item.evidence_type || '').toUpperCase();
        if (selectedType === 'EXPERIENCE' && !['EXPERIENCE', 'ROLE', 'RESPONSIBILITY', 'EXPERIENCE_ROLE', 'EXPERIENCE_BULLET'].includes(itemType)) {
          return false;
        } else if (selectedType !== 'EXPERIENCE' && itemType !== selectedType) {
          return false;
        }
      }

      // Skill filter
      if (selectedSkill) {
        const sk = selectedSkill.toLowerCase();
        const matchesSkill = 
          (item.related_skill && item.related_skill.toLowerCase() === sk) ||
          (item.related_technologies || []).some(t => t.toLowerCase() === sk) ||
          (item.normalized_facts || []).some(f => f.toLowerCase() === sk) ||
          item.source_text.toLowerCase().includes(sk);
        if (!matchesSkill) return false;
      }

      // Project filter
      if (selectedProject) {
        const pr = selectedProject.toLowerCase();
        const matchesProj = 
          (item.related_project && item.related_project.toLowerCase().includes(pr)) ||
          item.source_text.toLowerCase().includes(pr);
        if (!matchesProj) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesSearch = 
          item.source_text.toLowerCase().includes(q) ||
          (item.source_section && item.source_section.toLowerCase().includes(q)) ||
          (item.normalized_facts || []).some(f => f.toLowerCase().includes(q)) ||
          (item.evidence_id && item.evidence_id.toLowerCase().includes(q));
        if (!matchesSearch) return false;
      }

      return true;
    });
  }, [rawItems, selectedType, selectedSkill, selectedProject, searchQuery]);

  // Jump to Evidence Vault filtered by a specific skill
  const handleInspectSkillEvidence = (skillName) => {
    setSelectedSkill(skillName);
    setSelectedProject(null);
    setSelectedType('ALL');
    setSearchQuery('');
    setActiveTab('vault');
  };

  // Jump to Evidence Vault filtered by a specific project
  const handleInspectProjectEvidence = (projectName) => {
    setSelectedProject(projectName);
    setSelectedSkill(null);
    setSelectedType('ALL');
    setSearchQuery('');
    setActiveTab('vault');
  };

  // Clear all filters
  const handleClearFilters = () => {
    setSelectedSkill(null);
    setSelectedProject(null);
    setSelectedType('ALL');
    setSearchQuery('');
  };

  // Run live claim validation test
  const handleValidateClaim = async (e) => {
    e.preventDefault();
    if (!claimInput.trim() || !careerTwin?.candidate_id) return;
    setIsValidating(true);
    setClaimResult(null);
    try {
      const res = await coachApi.validateClaim(careerTwin.candidate_id, claimInput.trim());
      setClaimResult(res);
    } catch (err) {
      setClaimResult({
        supported: false,
        explanation: err.message || "Failed to validate claim against Evidence Vault."
      });
    } finally {
      setIsValidating(false);
    }
  };

  if (!careerTwin) {
    return (
      <div className="coach-empty-state">
        <div className="empty-icon">👤</div>
        <h3>No Career Twin Initialized</h3>
        <p>Upload a candidate resume PDF in the Dashboard to build your digital twin and Evidence Vault.</p>
      </div>
    );
  }

  const projectsList = careerTwin.project_nodes && careerTwin.project_nodes.length > 0 
    ? careerTwin.project_nodes 
    : careerTwin.projects || [];

  return (
    <div className="coach-view-container">
      {/* Grounding & Provenance Notice */}
      <div className="twin-grounding-banner">
        <span className="grounding-tag">
          🔒 Extracted from your resume • Verifiable Ground Truth
        </span>
        <span className="grounding-meta">
          Every entity is anchored to deterministic citations in the Evidence Vault. Zero AI fabrication.
        </span>
      </div>

      {/* Header Profile Bar */}
      <div className="twin-profile-banner">
        <div className="banner-left">
          <div className="avatar-circle">
            {(careerTwin.name ? careerTwin.name[0] : 'C')}
          </div>
          <div>
            <h2 className="banner-name">{careerTwin.name || "Candidate Profile"}</h2>
            <p className="banner-contact">
              {careerTwin.email || 'No email provided'} • {careerTwin.phone || 'No phone provided'}
            </p>
            {careerTwin.summary && (
              <p className="banner-summary">"{careerTwin.summary}"</p>
            )}
          </div>
        </div>
        <div className="banner-stats">
          <div className="stat-pill">
            <strong>{careerTwin.total_experience_months}</strong> mos experience
          </div>
          <div className="stat-pill">
            <strong>{careerTwin.skills?.length || 0}</strong> skills
          </div>
          <div className="stat-pill">
            <strong>{evidenceVault?.total_items || careerTwin.evidence_count}</strong> evidence facts
          </div>
          {onUploadNew && (
            <button className="btn-secondary" style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }} onClick={onUploadNew}>
              ↻ Ingest New
            </button>
          )}
        </div>
      </div>

      {/* Education & Experience Summary Cards */}
      <div className="twin-summary-grid">
        <div className="twin-summary-card">
          <div className="twin-summary-title">Education & Credentials</div>
          <div className="twin-summary-content">
            {careerTwin.education && careerTwin.education.length > 0 ? (
              careerTwin.education.map((edu, idx) => (
                <div key={idx} style={{ marginBottom: '0.4rem' }}>
                  <strong>{edu.degree || 'Degree'} {edu.field_of_study ? `in ${edu.field_of_study}` : ''}</strong>
                  <div style={{ fontSize: '0.82rem', color: '#6B7280' }}>
                    {edu.institution} {edu.grade_or_gpa ? `• GPA: ${edu.grade_or_gpa}` : ''}
                  </div>
                </div>
              ))
            ) : (
              <span style={{ color: '#9CA3AF' }}>No formal education entries extracted.</span>
            )}
          </div>
        </div>

        <div className="twin-summary-card">
          <div className="twin-summary-title">Experience Scope</div>
          <div className="twin-summary-content">
            <div><strong>{careerTwin.experience?.length || 0}</strong> Professional Roles</div>
            <div style={{ fontSize: '0.82rem', color: '#6B7280', marginTop: '0.2rem' }}>
              {(careerTwin.total_experience_months / 12).toFixed(1)} years total recorded tenure
            </div>
            {careerTwin.experience && careerTwin.experience[0] && (
              <div style={{ fontSize: '0.82rem', color: '#4F46E5', marginTop: '0.3rem' }}>
                Latest: {careerTwin.experience[0].role} at {careerTwin.experience[0].company}
              </div>
            )}
          </div>
        </div>

        <div className="twin-summary-card">
          <div className="twin-summary-title">Evidence Distribution</div>
          <div className="twin-summary-content">
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '0.2rem' }}>
              <span>Skills & Tech:</span>
              <strong>{careerTwin.evidence_summary?.skills || careerTwin.skills?.length || 0}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '0.2rem' }}>
              <span>Experience & Roles:</span>
              <strong>{careerTwin.evidence_summary?.experience || careerTwin.experience?.length || 0}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span>Quantified Metrics:</span>
              <strong>{careerTwin.evidence_summary?.metrics || careerTwin.achievements?.length || 0}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Internal Tabs */}
      <div className="twin-subnav">
        <button 
          className={`subnav-btn ${activeTab === 'skills' ? 'active' : ''}`}
          onClick={() => { setActiveTab('skills'); handleClearFilters(); }}
        >
          Skill Map ({careerTwin.skills?.length || 0})
        </button>
        <button 
          className={`subnav-btn ${activeTab === 'timeline' ? 'active' : ''}`}
          onClick={() => setActiveTab('timeline')}
        >
          Experience Timeline ({careerTwin.timeline?.length || 0})
        </button>
        <button 
          className={`subnav-btn ${activeTab === 'projects' ? 'active' : ''}`}
          onClick={() => setActiveTab('projects')}
        >
          Projects ({projectsList.length})
        </button>
        <button 
          className={`subnav-btn ${activeTab === 'achievements' ? 'active' : ''}`}
          onClick={() => setActiveTab('achievements')}
        >
          Achievements ({careerTwin.achievements?.length || 0})
        </button>
        <button 
          className={`subnav-btn ${activeTab === 'vault' ? 'active' : ''}`}
          onClick={() => setActiveTab('vault')}
        >
          Evidence Vault ({evidenceVault?.total_items || careerTwin.evidence_count})
        </button>
      </div>

      {/* Tab 1: Skills Map */}
      {activeTab === 'skills' && (
        <div className="skills-graph-view">
          <p style={{ fontSize: '0.85rem', color: '#6B7280', marginBottom: '1rem' }}>
            Click on any skill to inspect its supporting source citations in the Evidence Vault.
          </p>
          <div className="skills-tags-cluster">
            {careerTwin.skill_nodes && careerTwin.skill_nodes.length > 0 ? (
              careerTwin.skill_nodes.map((node, idx) => (
                <div 
                  key={idx} 
                  className={`skill-node-chip ${selectedSkill === node.name ? 'selected' : ''}`}
                  onClick={() => handleInspectSkillEvidence(node.name)}
                  title={`Click to view citations for ${node.name}`}
                >
                  <span className="skill-name">{node.name}</span>
                  {node.occurrence_count > 1 && (
                    <span className="skill-occurrence" title="Occurrences in CV">{node.occurrence_count}×</span>
                  )}
                  {node.verified_tenure_months && (
                    <span className="skill-tenure">{node.verified_tenure_months}m</span>
                  )}
                  {node.related_roles?.length > 0 && (
                    <span className="skill-role-badge">{node.related_roles[0]}</span>
                  )}
                </div>
              ))
            ) : (
              careerTwin.skills?.map((s, idx) => (
                <div 
                  key={idx} 
                  className="skill-node-chip"
                  onClick={() => handleInspectSkillEvidence(s)}
                >
                  <span className="skill-name">{s}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Timeline */}
      {activeTab === 'timeline' && (
        <div className="timeline-view">
          <div className="timeline-track">
            {careerTwin.timeline?.map((evt, idx) => (
              <div key={idx} className={`timeline-item type-${evt.event_type}`}>
                <div className="timeline-marker" />
                <div className="timeline-content">
                  <div className="timeline-date">{evt.date_display}</div>
                  <h4 className="timeline-title">{evt.title}</h4>
                  {evt.organization && <div className="timeline-org">{evt.organization}</div>}
                  {evt.description && <p className="timeline-desc">{evt.description}</p>}
                  {evt.evidence_id && (
                    <button 
                      className="evidence-count-button" 
                      style={{ marginTop: '0.4rem' }}
                      onClick={() => {
                        setSearchQuery(evt.evidence_id);
                        setActiveTab('vault');
                      }}
                    >
                      Cite: {evt.evidence_id}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Projects */}
      {activeTab === 'projects' && (
        <div className="projects-view">
          <div className="projects-grid">
            {projectsList.length > 0 ? (
              projectsList.map((proj, idx) => (
                <div key={idx} className="project-card">
                  <div>
                    <div className="project-header">
                      <h4 className="project-title">{proj.name}</h4>
                      <button 
                        className="evidence-count-button"
                        onClick={() => handleInspectProjectEvidence(proj.name)}
                        title="View citations in Evidence Vault"
                      >
                        {proj.evidence_references?.length || 1} Evidence Items →
                      </button>
                    </div>

                    {proj.description && (
                      <p className="project-desc">{proj.description}</p>
                    )}

                    {proj.responsibilities && proj.responsibilities.length > 0 && (
                      <ul className="project-bullets-list">
                        {proj.responsibilities.map((r, rIdx) => (
                          <li key={rIdx}>{r}</li>
                        ))}
                      </ul>
                    )}

                    {proj.metrics && proj.metrics.length > 0 && (
                      <div style={{ marginBottom: '0.65rem' }}>
                        {proj.metrics.map((m, mIdx) => (
                          <span key={mIdx} className="project-metric-pill">📈 {m}</span>
                        ))}
                      </div>
                    )}
                  </div>

                  {proj.technologies && proj.technologies.length > 0 && (
                    <div className="project-tech-tags">
                      {proj.technologies.map((t, tIdx) => (
                        <span 
                          key={tIdx} 
                          className="tech-tag-small"
                          style={{ cursor: 'pointer' }}
                          onClick={() => handleInspectSkillEvidence(t)}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="empty-subtext">No distinct project entries extracted from resume.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Achievements */}
      {activeTab === 'achievements' && (
        <div className="achievements-view">
          <div className="achievements-grid">
            {careerTwin.achievements && careerTwin.achievements.length > 0 ? (
              careerTwin.achievements.map((ach, idx) => (
                <div key={idx} className="achievement-card">
                  <div className="ach-metric-badge">{ach.metric || "Key Metric"}</div>
                  <p className="ach-headline">"{ach.headline}"</p>
                  <span className="ach-context">{ach.context}</span>
                  {ach.evidence_id && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <button 
                        className="evidence-count-button"
                        onClick={() => {
                          setSearchQuery(ach.evidence_id);
                          setActiveTab('vault');
                        }}
                      >
                        Evidence: {ach.evidence_id}
                      </button>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <p className="empty-subtext">No quantified metrics detected yet in experience bullets.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab 5: Evidence Vault Explorer */}
      {activeTab === 'vault' && (
        <div className="vault-view">
          {/* Active Filter Bar Notice */}
          {(selectedSkill || selectedProject || searchQuery || selectedType !== 'ALL') && (
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              background: '#EEF2FF', 
              padding: '0.65rem 1rem', 
              borderRadius: '8px', 
              marginBottom: '1rem',
              fontSize: '0.85rem',
              color: '#3730A3'
            }}>
              <span>
                Filtered by: {selectedSkill ? `Skill "${selectedSkill}"` : ''} 
                {selectedProject ? `Project "${selectedProject}"` : ''}
                {selectedType !== 'ALL' ? ` Type [${selectedType}]` : ''}
                {searchQuery ? ` Search "${searchQuery}"` : ''}
              </span>
              <button 
                className="btn-secondary" 
                style={{ fontSize: '0.78rem', padding: '0.2rem 0.6rem' }}
                onClick={handleClearFilters}
              >
                Clear Filters (Show All)
              </button>
            </div>
          )}

          {/* Filter Controls Bar */}
          <div className="vault-controls-bar">
            <div className="vault-type-filters">
              {['ALL', 'SKILL', 'EXPERIENCE', 'PROJECT', 'EDUCATION', 'CERTIFICATION', 'METRIC'].map((t) => (
                <button
                  key={t}
                  className={`type-filter-chip ${selectedType === t ? 'active' : ''}`}
                  onClick={() => setSelectedType(t)}
                >
                  {t}
                </button>
              ))}
            </div>

            <div className="vault-search-row">
              <input
                type="text"
                placeholder="Search verbatim quotes, sections, normalized facts, or evidence IDs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="vault-search-input"
              />
              {(selectedSkill || selectedProject || searchQuery || selectedType !== 'ALL') && (
                <button className="btn-secondary" onClick={handleClearFilters}>
                  Reset
                </button>
              )}
            </div>
          </div>

          <div style={{ fontSize: '0.82rem', color: '#6B7280', marginBottom: '0.75rem' }}>
            Showing {filteredVaultItems.length} of {rawItems?.length || evidenceVault?.total_items || careerTwin.evidence_count || 0} verified facts extracted from resume
          </div>

          {/* Evidence Grid */}
          <div className="vault-items-grid">
            {filteredVaultItems.map((item, idx) => (
              <div key={item.evidence_id || idx} className="vault-item-card">
                <div className="vault-item-top">
                  <span className="vault-type-badge">{item.evidence_type}</span>
                  {item.source_section && (
                    <span className="vault-section-badge">Section: {item.source_section}</span>
                  )}
                  {item.page_number && (
                    <span className="vault-page-badge">Page {item.page_number}</span>
                  )}
                  {item.related_entity && (
                    <span className="vault-section-badge" style={{ background: '#F0FDF4', color: '#166534' }}>
                      {item.related_entity}
                    </span>
                  )}
                </div>

                <p className="vault-text">"{item.source_text}"</p>

                {item.normalized_facts && item.normalized_facts.length > 0 && (
                  <div className="vault-facts-container">
                    <span style={{ fontSize: '0.72rem', color: '#6B7280', fontWeight: 600 }}>Facts:</span>
                    {item.normalized_facts.map((fact, fIdx) => (
                      <span key={fIdx} className="vault-fact-pill">{fact}</span>
                    ))}
                  </div>
                )}

                <div className="vault-item-meta">
                  <span className="vault-id">ID: {item.evidence_id}</span>
                  <span className="vault-conf">Verified Confidence: {(item.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>

          {/* Zero-Hallucination Claim Validation Tester Widget */}
          <div className="claim-validator-box">
            <h4 className="claim-validator-title">Zero-Hallucination Claim Verification</h4>
            <p className="claim-validator-desc">
              Test candidate assertions against the Evidence Vault to verify that facts, metrics, and technical skills are 100% grounded in source documents.
            </p>
            <form onSubmit={handleValidateClaim} className="claim-input-row">
              <input
                type="text"
                placeholder="e.g. 'Kubernetes' or 'Flask' or 'Improved performance by 40%'"
                value={claimInput}
                onChange={(e) => setClaimInput(e.target.value)}
                style={{ flex: 1, padding: '0.5rem 0.85rem', borderRadius: '8px', border: '1px solid #CBD5E1', fontSize: '0.85rem' }}
              />
              <button 
                type="submit" 
                className="btn-primary" 
                style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
                disabled={isValidating || !claimInput.trim()}
              >
                {isValidating ? "Validating..." : "Verify Claim Grounding"}
              </button>
            </form>

            {claimResult && (
              <div className={`claim-result-card ${claimResult.supported ? 'supported' : 'rejected'}`}>
                <div style={{ fontWeight: 600, marginBottom: '0.2rem' }}>
                  {claimResult.supported ? "✅ Grounded in Evidence Vault" : "❌ Rejected (Unsupported Claim)"}
                </div>
                <div>{claimResult.explanation}</div>
                {claimResult.supporting_evidence_ids?.length > 0 && (
                  <div style={{ marginTop: '0.4rem', fontSize: '0.78rem' }}>
                    <strong>Citations:</strong> {claimResult.supporting_evidence_ids.join(', ')}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
