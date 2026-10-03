import React, { useRef } from 'react';
import { VIEWS } from '../types';

export default function Dashboard({ careerTwin, evidenceVault, onUploadResume, onNavigate, isUploading, uploadError }) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onUploadResume(file);
    }
  };

  return (
    <div className="coach-view-container">
      {/* Hero Welcome */}
      <section className="coach-hero">
        <span className="coach-badge-tag">AI-Powered Career Intelligence</span>
        <h2 className="coach-hero-title">Prepare Your Resume. Ace Your Interviews.</h2>
        <p className="coach-hero-desc">
          Vettora transforms your raw resume into a verified Career Twin, stress-tests it against real ATS filters,
          measures exact fit against target jobs, and coaches you through STAR-structured mock interviews.
        </p>

        {/* Upload Trigger */}
        <div className="dashboard-upload-box">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,application/pdf"
            className="file-input-hidden"
          />
          <button
            className="btn-primary-large"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? "Parsing Resume & Building Twin..." : (careerTwin ? "↻ Upload New Resume (PDF)" : "↑ Ingest Resume to Build Career Twin (PDF)")}
          </button>
          {uploadError && <p className="upload-error-text">{uploadError}</p>}
        </div>
      </section>

      {/* Active Profile Status */}
      {careerTwin ? (
        <section className="twin-active-card">
          <div className="twin-card-header">
            <div>
              <span className="status-pill-online">● Career Twin Active</span>
              <h3 className="twin-candidate-name">{careerTwin.name || "Candidate Profile"}</h3>
              <p className="twin-candidate-meta">
                {careerTwin.email} • {careerTwin.total_experience_months} months verified experience • {careerTwin.skills?.length || 0} skills identified
              </p>
            </div>
            <div className="twin-header-actions">
              <button className="btn-secondary" onClick={() => onNavigate(VIEWS.CAREER_TWIN)}>
                Inspect Career Twin →
              </button>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div className="coach-metrics-grid">
            <div className="coach-metric-card" onClick={() => onNavigate(VIEWS.CAREER_TWIN)}>
              <span className="metric-icon">👤</span>
              <div className="metric-val">{careerTwin.skills?.length || 0}</div>
              <div className="metric-lbl">Extracted Skills & Tech</div>
            </div>
            <div className="coach-metric-card" onClick={() => onNavigate(VIEWS.CAREER_TWIN)}>
              <span className="metric-icon">📂</span>
              <div className="metric-val">{evidenceVault?.total_items || careerTwin.evidence_count || 0}</div>
              <div className="metric-lbl">Evidence Vault Facts</div>
            </div>
            <div className="coach-metric-card" onClick={() => onNavigate(VIEWS.RESUME_COACH)}>
              <span className="metric-icon">📝</span>
              <div className="metric-val">{careerTwin.experience?.length || 0}</div>
              <div className="metric-lbl">Experience Milestones</div>
            </div>
            <div className="coach-metric-card" onClick={() => onNavigate(VIEWS.JOB_FIT)}>
              <span className="metric-icon">🎯</span>
              <div className="metric-val">Ready</div>
              <div className="metric-lbl">Resume × Job Fit Audit</div>
            </div>
          </div>
        </section>
      ) : (
        <section className="modules-overview-grid">
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">👤</span>
            <h4>1. Career Twin</h4>
            <p>Constructs a digital knowledge graph of your skills, tenure, and verified work milestones from your CV.</p>
          </div>
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">🎯</span>
            <h4>2. Resume × Job Fit</h4>
            <p>Bi-directional hybrid evaluation measuring exact required vs preferred alignment against any JD.</p>
          </div>
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">🎙️</span>
            <h4>3. Interview Coach</h4>
            <p>Targeted interview simulations with STAR answer analysis and evidence consistency checks.</p>
          </div>
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">🛡️</span>
            <h4>4. ATS Stress Test</h4>
            <p>Audits multi-column readability, heading recognition, and formatting compliance.</p>
          </div>
        </section>
      )}
    </div>
  );
}
