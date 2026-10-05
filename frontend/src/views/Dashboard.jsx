import React, { useRef, useState, useEffect } from 'react';
import { VIEWS } from '../types';
import { coachApi } from '../services/api';

export default function Dashboard({ careerTwin, evidenceVault, onUploadResume, onNavigate, isUploading, uploadError }) {
  const fileInputRef = useRef(null);
  const [showcaseInfo, setShowcaseInfo] = useState(null);
  const [targetInfo, setTargetInfo] = useState(null);
  const [executionStats, setExecutionStats] = useState({
    activeCount: 0,
    completedCount: 0,
    awaitingEvidenceCount: 0,
  });

  const candidateId = careerTwin?.candidate_id;

  useEffect(() => {
    if (!candidateId) return;

    let isMounted = true;

    // Load showcase status
    coachApi
      .getShowcase(candidateId)
      .then((data) => {
        if (isMounted) setShowcaseInfo(data);
      })
      .catch(() => {});

    // Load active target & execution progress if available
    coachApi
      .getCareerTargets(candidateId)
      .then((data) => {
        const targets = Array.isArray(data) ? data : data?.targets || [];
        if (isMounted && targets.length > 0) {
          const activeTgt = targets[0];
          setTargetInfo(activeTgt);

          // Fetch execution progress
          coachApi
            .getCareerTargetProgress(activeTgt.target_id, candidateId)
            .then((prog) => {
              if (isMounted && prog) {
                const completed = prog.completed_actions || 0;
                const total = prog.total_actions || 0;
                setExecutionStats({
                  completedCount: completed,
                  activeCount: Math.max(0, total - completed),
                  awaitingEvidenceCount: prog.awaiting_verification_count || 0,
                });
              }
            })
            .catch(() => {});
        }
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [candidateId]);

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onUploadResume(file);
    }
    if (e.target) {
      e.target.value = '';
    }
  };

  const skillsCount = careerTwin?.skills?.length || 0;
  const experienceCount = careerTwin?.experience?.length || 0;
  const projectsCount = careerTwin?.projects?.length || 0;
  const evidenceCount = evidenceVault?.total_items || careerTwin?.evidence_count || 0;

  return (
    <div className="coach-view-container" style={{ maxWidth: '1200px', margin: '0 auto', paddingBottom: '3rem' }}>
      {/* Hero Welcome */}
      <section className="coach-hero" style={{ marginBottom: '2rem' }}>
        <span className="coach-badge-tag">Evidence-Grounded Career Intelligence</span>
        <h2 className="coach-hero-title">Career Intelligence Command Center</h2>
        <p className="coach-hero-desc">
          Vettora builds an authoritative Career Twin from verified Evidence Vault facts. Track progress deterministically,
          close concrete skill and experience gaps, and present only verified accomplishments in your Career Showcase.
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
            {isUploading
              ? 'Parsing Resume & Building Twin...'
              : careerTwin
              ? '↻ Ingest Updated Resume (PDF)'
              : '↑ Ingest Resume to Build Career Twin (PDF)'}
          </button>
          {uploadError && (
            <p className="upload-error-text" role="alert" style={{ marginTop: '0.75rem', color: '#ef4444', fontWeight: '500' }}>
              ⚠️ {uploadError}
            </p>
          )}
        </div>
      </section>

      {/* Active Candidate Command Center */}
      {careerTwin ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* 1. CAREER OVERVIEW */}
          <section
            style={{
              padding: '2rem',
              borderRadius: '16px',
              backgroundColor: 'rgba(30, 41, 59, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '700' }}>
                  ● Verified Career State
                </span>
                <h3 style={{ margin: '0.2rem 0 0 0', fontSize: '1.4rem', color: '#ffffff' }}>
                  {careerTwin.name || 'Candidate Profile'}
                </h3>
                <p style={{ margin: '0.2rem 0 0 0', color: '#94a3b8', fontSize: '0.9rem' }}>
                  {careerTwin.summary || 'Verified professional record anchored by Evidence Vault authority.'}
                </p>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  className="btn-secondary"
                  onClick={() => onNavigate(VIEWS.CAREER_TWIN)}
                  style={{ fontSize: '0.85rem', padding: '8px 14px' }}
                >
                  Inspect Career Twin →
                </button>
                <button
                  className="btn-primary"
                  onClick={() => onNavigate(VIEWS.CAREER_SHOWCASE)}
                  style={{ fontSize: '0.85rem', padding: '8px 14px', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600' }}
                >
                  Open Showcase →
                </button>
              </div>
            </div>

            {/* Quick Metrics Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '1rem',
              }}
            >
              <div
                onClick={() => onNavigate(VIEWS.CAREER_TWIN)}
                style={{
                  padding: '1.25rem',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: '1.4rem', marginBottom: '4px' }}>⚡</div>
                <div style={{ fontSize: '1.6rem', fontWeight: '800', color: '#ffffff' }}>{skillsCount}</div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Verified Skills</div>
              </div>

              <div
                onClick={() => onNavigate(VIEWS.CAREER_SHOWCASE)}
                style={{
                  padding: '1.25rem',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: '1.4rem', marginBottom: '4px' }}>🚀</div>
                <div style={{ fontSize: '1.6rem', fontWeight: '800', color: '#ffffff' }}>{projectsCount}</div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Verified Projects</div>
              </div>

              <div
                onClick={() => onNavigate(VIEWS.CAREER_TWIN)}
                style={{
                  padding: '1.25rem',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: '1.4rem', marginBottom: '4px' }}>💼</div>
                <div style={{ fontSize: '1.6rem', fontWeight: '800', color: '#ffffff' }}>{experienceCount}</div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Verified Experience Milestones</div>
              </div>

              <div
                onClick={() => onNavigate(VIEWS.CAREER_TWIN)}
                style={{
                  padding: '1.25rem',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                  cursor: 'pointer',
                }}
              >
                <div style={{ fontSize: '1.4rem', marginBottom: '4px' }}>📂</div>
                <div style={{ fontSize: '1.6rem', fontWeight: '800', color: '#ffffff' }}>{evidenceCount}</div>
                <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Evidence Vault Records</div>
              </div>
            </div>
          </section>

          {/* 2. CURRENT TARGET & PROGRESS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '2rem' }}>
            
            {/* Target Alignment Card */}
            <section
              style={{
                padding: '1.75rem',
                borderRadius: '16px',
                backgroundColor: 'rgba(30, 41, 59, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🎯</span>
                <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#ffffff' }}>Target & Requirement Progress</h3>
              </div>

              {targetInfo ? (
                <div>
                  <div style={{ fontSize: '1.05rem', fontWeight: '700', color: '#38bdf8', marginBottom: '0.25rem' }}>
                    {targetInfo.target_role || targetInfo.title}
                  </div>
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 1rem 0' }}>
                    Deterministic gap analysis grounded against active target requirements.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', fontSize: '0.85rem', color: '#34d399' }}>
                      ✓ {skillsCount} requirements supported by authentic evidence
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(234, 179, 8, 0.08)', border: '1px solid rgba(234, 179, 8, 0.2)', fontSize: '0.85rem', color: '#facc15' }}>
                      👁️ Resume visibility gaps identified for refinement
                    </div>
                    <div style={{ padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', fontSize: '0.85rem', color: '#f87171' }}>
                      ⚠️ Experience gaps tracked in Career Execution
                    </div>
                  </div>

                  <button
                    onClick={() => onNavigate(VIEWS.CAREER_INTELLIGENCE)}
                    style={{
                      marginTop: '1.25rem',
                      padding: '8px 14px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(56, 189, 248, 0.1)',
                      color: '#38bdf8',
                      border: '1px solid rgba(56, 189, 248, 0.3)',
                      fontSize: '0.85rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      width: '100%',
                    }}
                  >
                    View Career Intelligence Gap Plan →
                  </button>
                </div>
              ) : (
                <div>
                  <p style={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: '1.5' }}>
                    No target role selected yet. Evaluate a job description to activate automated gap tracking.
                  </p>
                  <button
                    onClick={() => onNavigate(VIEWS.JOB_FIT)}
                    style={{
                      marginTop: '0.75rem',
                      padding: '8px 14px',
                      borderRadius: '8px',
                      backgroundColor: '#3b82f6',
                      color: '#ffffff',
                      border: 'none',
                      fontSize: '0.85rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                    }}
                  >
                    Run Job Fit Audit →
                  </button>
                </div>
              )}
            </section>

            {/* Career Execution Card */}
            <section
              style={{
                padding: '1.75rem',
                borderRadius: '16px',
                backgroundColor: 'rgba(30, 41, 59, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🚀</span>
                <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#ffffff' }}>Career Execution & Evidence</h3>
              </div>

              <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 1rem 0' }}>
                Action completion requires evidence verification before skills are recognized.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.85rem' }}>
                  <span style={{ color: '#cbd5e1' }}>Active Execution Actions</span>
                  <span style={{ fontWeight: '700', color: '#38bdf8' }}>{executionStats.activeCount} planned</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.85rem' }}>
                  <span style={{ color: '#cbd5e1' }}>Completed Verified Actions</span>
                  <span style={{ fontWeight: '700', color: '#10b981' }}>{executionStats.completedCount} verified</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.85rem' }}>
                  <span style={{ color: '#cbd5e1' }}>Evidence Awaiting Verification</span>
                  <span style={{ fontWeight: '700', color: '#facc15' }}>{executionStats.awaitingEvidenceCount} pending</span>
                </div>
              </div>

              <button
                onClick={() => onNavigate(VIEWS.CAREER_EXECUTION)}
                style={{
                  marginTop: '1.25rem',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(56, 189, 248, 0.1)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  width: '100%',
                }}
              >
                Manage Career Execution →
              </button>
            </section>
          </div>

          {/* 3. PREPARATION & SHOWCASE STATUS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '2rem' }}>
            
            {/* Interview Preparation */}
            <section
              style={{
                padding: '1.75rem',
                borderRadius: '16px',
                backgroundColor: 'rgba(30, 41, 59, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🎙️</span>
                <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#ffffff' }}>Interview Preparation</h3>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 1rem 0' }}>
                STAR structured responses anchored to verified project accomplishments.
              </p>

              <div style={{ padding: '12px', borderRadius: '8px', backgroundColor: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.5' }}>
                {projectsCount > 0
                  ? `${projectsCount} verified project stories available for STAR mock interview rehearsals.`
                  : 'Add verified projects to generate STAR structured interview answers.'}
              </div>

              <button
                onClick={() => onNavigate(VIEWS.INTERVIEW_COACH)}
                style={{
                  marginTop: '1.25rem',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(56, 189, 248, 0.1)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  width: '100%',
                }}
              >
                Launch Interview Coach →
              </button>
            </section>

            {/* Showcase Status */}
            <section
              style={{
                padding: '1.75rem',
                borderRadius: '16px',
                backgroundColor: 'rgba(30, 41, 59, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🌟</span>
                <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#ffffff' }}>Career Showcase</h3>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 1rem 0' }}>
                Shareable evidence-backed portfolio presenting only verified accomplishments.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.85rem' }}>
                  <span style={{ color: '#cbd5e1' }}>Showcase Visibility</span>
                  <span style={{ fontWeight: '700', color: showcaseInfo?.visibility === 'SHAREABLE' ? '#34d399' : '#cbd5e1' }}>
                    {showcaseInfo?.visibility || 'PRIVATE'}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: '8px', backgroundColor: 'rgba(15, 23, 42, 0.5)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.85rem' }}>
                  <span style={{ color: '#cbd5e1' }}>Available Verified Projects</span>
                  <span style={{ fontWeight: '700', color: '#ffffff' }}>{projectsCount}</span>
                </div>
              </div>

              <button
                onClick={() => onNavigate(VIEWS.CAREER_SHOWCASE)}
                style={{
                  marginTop: '1.25rem',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  backgroundColor: '#3b82f6',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: '0.85rem',
                  fontWeight: '600',
                  cursor: 'pointer',
                  width: '100%',
                }}
              >
                Manage & Share Showcase →
              </button>
            </section>
          </div>
        </div>
      ) : (
        /* Empty State */
        <section className="modules-overview-grid">
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">👤</span>
            <h4>1. Career Twin</h4>
            <p>Constructs a digital knowledge graph of your skills, tenure, and verified work milestones from your CV.</p>
          </div>
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">🎯</span>
            <h4>2. Resume × Job Fit</h4>
            <p>Bi-directional evaluation measuring exact required vs preferred alignment against any target JD.</p>
          </div>
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">🚀</span>
            <h4>3. Career Execution</h4>
            <p>Track progress against concrete requirements with strict evidence validation.</p>
          </div>
          <div className="overview-card" onClick={() => fileInputRef.current?.click()}>
            <span className="overview-icon">🌟</span>
            <h4>4. Career Showcase</h4>
            <p>Shareable verified profile demonstrating proven accomplishments without synthetic claims.</p>
          </div>
        </section>
      )}
    </div>
  );
}
