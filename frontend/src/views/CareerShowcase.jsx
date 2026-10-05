import React, { useState, useEffect, useCallback } from 'react';
import { coachApi } from '../services/api';

const SCOPE_BADGE_STYLES = {
  'LEVEL 1 — TECHNOLOGY PRESENCE': { bg: 'rgba(148, 163, 184, 0.15)', text: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)', label: 'Level 1: Presence' },
  'LEVEL 2 — USAGE': { bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)', label: 'Level 2: Usage' },
  'LEVEL 3 — IMPLEMENTATION': { bg: 'rgba(74, 222, 128, 0.15)', text: '#4ade80', border: 'rgba(74, 222, 128, 0.3)', label: 'Level 3: Implementation' },
  'LEVEL 4 — OPERATIONAL / PRODUCTION': { bg: 'rgba(168, 85, 247, 0.15)', text: '#c084fc', border: 'rgba(168, 85, 247, 0.3)', label: 'Level 4: Production' },
  'LEVEL 5 — SPECIFIC SCOPE': { bg: 'rgba(251, 146, 60, 0.15)', text: '#fb923c', border: 'rgba(251, 146, 60, 0.3)', label: 'Level 5: Specialized Scope' },
};

export default function CareerShowcase({ careerTwin, publicToken = null }) {
  const isPublic = Boolean(publicToken);
  const candidateId = careerTwin?.candidate_id || 'cand_jane';

  const [showcase, setShowcase] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Edit profile state
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [headlineInput, setHeadlineInput] = useState('');
  const [bioInput, setBioInput] = useState('');

  // Target alignment selection
  const [targets, setTargets] = useState([]);
  const [selectedTargetId, setSelectedTargetId] = useState('');

  // Provenance inspect modal
  const [selectedProvenance, setSelectedProvenance] = useState(null);

  // Story accordion states (track open project stories)
  const [openStories, setOpenStories] = useState({});

  // Share state
  const [shareUrl, setShareUrl] = useState('');
  const [copiedLink, setCopiedLink] = useState(false);

  const fetchShowcase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isPublic) {
        const pubData = await coachApi.getPublicShowcase(publicToken);
        setShowcase(pubData);
      } else {
        const data = await coachApi.getShowcase(candidateId);
        setShowcase(data);
        setHeadlineInput(data.headline || '');
        setBioInput(data.bio || data.professional_summary || '');
        setSelectedTargetId(data.selected_target_id || '');

        try {
          const twinData = await coachApi.getCareerTwin(candidateId);
          if (twinData?.targets) {
            setTargets(twinData.targets);
          }
        } catch {
          // Non-critical if targets list is unavailable
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load Career Showcase.');
    } finally {
      setLoading(false);
    }
  }, [candidateId, isPublic, publicToken]);

  useEffect(() => {
    let ignore = false;
    async function loadInitial() {
      try {
        if (isPublic) {
          const pubData = await coachApi.getPublicShowcase(publicToken);
          if (!ignore) setShowcase(pubData);
        } else {
          const data = await coachApi.getShowcase(candidateId);
          if (!ignore) {
            setShowcase(data);
            setHeadlineInput(data.headline || '');
            setBioInput(data.bio || data.professional_summary || '');
            setSelectedTargetId(data.selected_target_id || '');
          }
          try {
            const twinData = await coachApi.getCareerTwin(candidateId);
            if (!ignore && twinData?.targets) {
              setTargets(twinData.targets);
            }
          } catch {
            // Non-critical
          }
        }
      } catch (err) {
        if (!ignore) setError(err.message || 'Failed to load Career Showcase.');
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    loadInitial();
    return () => {
      ignore = true;
    };
  }, [candidateId, isPublic, publicToken]);

  const handleSaveProfile = async () => {
    try {
      setError(null);
      const updated = await coachApi.updateShowcase(candidateId, {
        candidate_id: candidateId,
        headline: headlineInput,
        bio: bioInput,
      });
      setShowcase(updated);
      setIsEditingProfile(false);
      setSuccessMsg('Showcase profile updated successfully.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to update profile.');
    }
  };

  const handleTargetChange = async (targetId) => {
    setSelectedTargetId(targetId);
    try {
      setError(null);
      const updated = await coachApi.updateShowcase(candidateId, {
        candidate_id: candidateId,
        selected_target_id: targetId || null,
        show_target_alignment: Boolean(targetId),
      });
      setShowcase(updated);
    } catch (err) {
      setError(err.message || 'Failed to update target alignment focus.');
    }
  };

  const handleGenerateShareLink = async () => {
    try {
      setError(null);
      const res = await coachApi.generateShareToken(candidateId);
      const fullUrl = `${window.location.origin}/#showcase/${res.share_token}`;
      setShareUrl(fullUrl);
      setShowcase((prev) => (prev ? { ...prev, visibility: 'SHAREABLE', share_token: res.share_token } : null));
      setSuccessMsg('Shareable link generated! Anyone with this link can view your verified showcase.');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.message || 'Failed to generate share link.');
    }
  };

  const handleRevokeShareLink = async () => {
    if (!window.confirm('Are you sure you want to revoke this public link? Existing links will immediately become private.')) {
      return;
    }
    try {
      setError(null);
      await coachApi.revokeShareToken(candidateId);
      setShareUrl('');
      setShowcase((prev) => (prev ? { ...prev, visibility: 'PRIVATE', share_token: null } : null));
      setSuccessMsg('Public link successfully revoked. Showcase is now private.');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      setError(err.message || 'Failed to revoke link.');
    }
  };

  const handleCopyLink = () => {
    if (!shareUrl) return;
    navigator.clipboard.writeText(shareUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  const handleExport = async () => {
    try {
      setError(null);
      const data = await coachApi.exportShowcase(candidateId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Vettora_Verified_Showcase_${candidateId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setSuccessMsg('Verified portfolio exported successfully.');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      setError(err.message || 'Failed to export showcase.');
    }
  };

  const toggleStory = (projId) => {
    setOpenStories((prev) => ({
      ...prev,
      [projId]: !prev[projId],
    }));
  };

  const renderScopeBadge = (scope) => {
    const style = SCOPE_BADGE_STYLES[scope] || SCOPE_BADGE_STYLES['LEVEL 1 — TECHNOLOGY PRESENCE'];
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '2px 8px',
          borderRadius: '999px',
          fontSize: '0.75rem',
          fontWeight: '600',
          backgroundColor: style.bg,
          color: style.text,
          border: `1px solid ${style.border}`,
          whiteSpace: 'nowrap',
        }}
      >
        {style.label}
      </span>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>
        <div style={{ fontSize: '2rem', marginBottom: '1rem', animation: 'spin 1s infinite linear' }}>🌟</div>
        <p style={{ fontSize: '1.1rem', fontWeight: '500' }}>Loading Evidence-Grounded Career Showcase...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '2.5rem', maxWidth: '800px', margin: '0 auto' }}>
        <div
          style={{
            padding: '1.5rem',
            borderRadius: '12px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#f87171',
          }}
        >
          <h3 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>⚠️</span> Unable to display Showcase
          </h3>
          <p style={{ margin: 0 }}>{error}</p>
          <button
            onClick={fetchShowcase}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              backgroundColor: '#ef4444',
              color: '#ffffff',
              border: 'none',
              cursor: 'pointer',
              fontWeight: '600',
            }}
          >
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  if (!showcase) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>
        <p>No verified showcase data available. Upload a resume to create your evidence vault.</p>
      </div>
    );
  }

  const skills = showcase.skills || showcase.verified_skills || [];
  const experience = showcase.experience || showcase.verified_experience || [];
  const projects = showcase.projects || showcase.verified_projects || [];
  const education = showcase.education || showcase.verified_education || [];
  const certifications = showcase.certifications || showcase.verified_certifications || [];
  const targetAlignment = showcase.target_alignment;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1.5rem 4rem 1.5rem', color: '#e2e8f0' }}>
      {/* Toast Notification */}
      {successMsg && (
        <div
          style={{
            position: 'fixed',
            top: '20px',
            right: '20px',
            zIndex: 1000,
            padding: '12px 20px',
            borderRadius: '10px',
            backgroundColor: '#10b981',
            color: '#ffffff',
            boxShadow: '0 10px 25px -5px rgba(16, 185, 129, 0.4)',
            fontWeight: '600',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>✓</span> {successMsg}
        </div>
      )}

      {/* Top Banner / Privacy & Sharing Toolbar (Candidate Only) */}
      {!isPublic && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
            padding: '1rem 1.5rem',
            marginBottom: '2rem',
            borderRadius: '14px',
            backgroundColor: 'rgba(30, 41, 59, 0.7)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            backdropFilter: 'blur(10px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.2rem' }}>🔒</span>
            <div>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Visibility Status
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span
                  style={{
                    padding: '2px 10px',
                    borderRadius: '6px',
                    fontSize: '0.8rem',
                    fontWeight: '700',
                    backgroundColor:
                      showcase.visibility === 'SHAREABLE' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(148, 163, 184, 0.2)',
                    color: showcase.visibility === 'SHAREABLE' ? '#34d399' : '#cbd5e1',
                    border:
                      showcase.visibility === 'SHAREABLE'
                        ? '1px solid rgba(16, 185, 129, 0.4)'
                        : '1px solid rgba(148, 163, 184, 0.4)',
                  }}
                >
                  {showcase.visibility}
                </span>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                  {showcase.visibility === 'SHAREABLE'
                    ? 'Active link accessible only to viewers with secret token'
                    : 'Showcase is strictly private to your account'}
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {showcase.visibility === 'SHAREABLE' ? (
              <>
                <button
                  onClick={handleCopyLink}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    color: '#38bdf8',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '0.85rem',
                  }}
                >
                  {copiedLink ? '✓ Copied URL' : '🔗 Copy Share Link'}
                </button>
                <button
                  onClick={handleRevokeShareLink}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    color: '#f87171',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '0.85rem',
                  }}
                >
                  Revoke Link
                </button>
              </>
            ) : (
              <button
                onClick={handleGenerateShareLink}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  backgroundColor: '#3b82f6',
                  color: '#ffffff',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontSize: '0.85rem',
                  boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)',
                }}
              >
                🌐 Create Shareable Link
              </button>
            )}

            <button
              onClick={handleExport}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                color: '#e2e8f0',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '0.85rem',
              }}
            >
              📥 Export JSON
            </button>
          </div>
        </div>
      )}

      {/* Main Profile Header Card */}
      <div
        style={{
          padding: '2.5rem',
          borderRadius: '18px',
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.5)',
          marginBottom: '2rem',
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
              <h1 style={{ fontSize: '2.2rem', fontWeight: '800', margin: 0, color: '#ffffff', letterSpacing: '-0.02em' }}>
                {showcase.name || 'Verified Candidate'}
              </h1>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  borderRadius: '20px',
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                <span>🛡️</span> EVIDENCE-VERIFIED
              </span>
            </div>

            <p style={{ fontSize: '1.15rem', color: '#94a3b8', margin: '0 0 1rem 0', fontWeight: '500' }}>
              {showcase.headline || 'Software Engineering Professional'}
            </p>

            {(showcase.bio || showcase.professional_summary) && (
              <p style={{ fontSize: '0.95rem', color: '#cbd5e1', lineHeight: '1.6', maxWidth: '850px', margin: 0 }}>
                {showcase.bio || showcase.professional_summary}
              </p>
            )}
          </div>

          {!isPublic && !isEditingProfile && (
            <button
              onClick={() => setIsEditingProfile(true)}
              style={{
                padding: '8px 14px',
                borderRadius: '8px',
                backgroundColor: 'rgba(255, 255, 255, 0.08)',
                color: '#cbd5e1',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                cursor: 'pointer',
                fontSize: '0.85rem',
                fontWeight: '600',
              }}
            >
              ✏️ Edit Headline & Bio
            </button>
          )}
        </div>

        {/* Profile Inline Editor */}
        {!isPublic && isEditingProfile && (
          <div
            style={{
              marginTop: '1.5rem',
              padding: '1.5rem',
              borderRadius: '12px',
              backgroundColor: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <h4 style={{ margin: '0 0 1rem 0', fontSize: '1rem', color: '#38bdf8' }}>Edit Showcase Presentation</h4>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.4rem' }}>
                Headline
              </label>
              <input
                type="text"
                value={headlineInput}
                onChange={(e) => setHeadlineInput(e.target.value)}
                placeholder="e.g. Senior Backend Engineer | Python, Flask, Docker"
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(30, 41, 59, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#ffffff',
                  fontSize: '0.9rem',
                }}
              />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.4rem' }}>
                Professional Summary / Bio
              </label>
              <textarea
                value={bioInput}
                onChange={(e) => setBioInput(e.target.value)}
                rows={3}
                placeholder="Summarize your verified background..."
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(30, 41, 59, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#ffffff',
                  fontSize: '0.9rem',
                  resize: 'vertical',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                onClick={handleSaveProfile}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  backgroundColor: '#10b981',
                  color: '#ffffff',
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontSize: '0.85rem',
                }}
              >
                Save Changes
              </button>
              <button
                onClick={() => setIsEditingProfile(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  backgroundColor: 'transparent',
                  color: '#94a3b8',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Target Alignment Focus Bar */}
      {!isPublic && targets && targets.length > 0 && (
        <div
          style={{
            padding: '1.25rem 1.5rem',
            marginBottom: '2rem',
            borderRadius: '14px',
            backgroundColor: 'rgba(30, 41, 59, 0.6)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.2rem' }}>🎯</span>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Career Target Focus
              </span>
              <div style={{ fontSize: '0.9rem', color: '#cbd5e1', fontWeight: '500' }}>
                Filter strengths and transparently display verified readiness
              </div>
            </div>
          </div>
          <select
            value={selectedTargetId}
            onChange={(e) => handleTargetChange(e.target.value)}
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              backgroundColor: 'rgba(15, 23, 42, 0.8)',
              color: '#ffffff',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              fontSize: '0.9rem',
              cursor: 'pointer',
            }}
          >
            <option value="">No Target Selected (Show Full Profile)</option>
            {targets.map((tgt) => (
              <option key={tgt.target_id} value={tgt.target_id}>
                {tgt.target_role || tgt.title}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Target Alignment Card (if active) */}
      {targetAlignment && (
        <div
          style={{
            padding: '1.75rem',
            borderRadius: '16px',
            backgroundColor: 'rgba(30, 41, 59, 0.8)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            marginBottom: '2rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '700' }}>
                Target Alignment
              </span>
              <h3 style={{ margin: '0.2rem 0 0 0', fontSize: '1.3rem', color: '#ffffff' }}>
                {targetAlignment.target_role}
              </h3>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#38bdf8' }}>
                {targetAlignment.evidence_coverage}%
              </div>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Verified Evidence Coverage</span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>
            {/* Verified Strengths */}
            <div style={{ padding: '1rem', borderRadius: '10px', backgroundColor: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', color: '#34d399', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>✓</span> Verified Strengths ({targetAlignment.verified_strengths?.length || 0})
              </h4>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#cbd5e1', fontSize: '0.85rem' }}>
                {(targetAlignment.verified_strengths || []).map((s, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>
                    {s.requirement_text || s.title || s}
                  </li>
                ))}
              </ul>
            </div>

            {/* Visibility Gaps */}
            <div style={{ padding: '1rem', borderRadius: '10px', backgroundColor: 'rgba(234, 179, 8, 0.05)', border: '1px solid rgba(234, 179, 8, 0.2)' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', color: '#facc15', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>👁️</span> Visibility Gaps ({targetAlignment.visibility_gaps?.length || 0})
              </h4>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#cbd5e1', fontSize: '0.85rem' }}>
                {(targetAlignment.visibility_gaps || []).map((g, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>
                    {g.requirement_text || g.title || g}
                  </li>
                ))}
              </ul>
            </div>

            {/* Experience Gaps */}
            <div style={{ padding: '1rem', borderRadius: '10px', backgroundColor: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', color: '#f87171', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>⚠️</span> Experience Gaps ({targetAlignment.experience_gaps?.length || 0})
              </h4>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#cbd5e1', fontSize: '0.85rem' }}>
                {(targetAlignment.experience_gaps || []).map((eg, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>
                    {eg.requirement_text || eg.title || eg}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Grid Layout: Left Column (Experience & Projects) / Right Column (Skills & Credentials) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '2rem' }}>
        
        {/* Left Column: Experience & Projects */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Section: Verified Experience */}
          <section
            style={{
              padding: '1.75rem',
              borderRadius: '16px',
              backgroundColor: 'rgba(30, 41, 59, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '1.3rem' }}>💼</span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', margin: 0, color: '#ffffff' }}>
                Verified Experience
              </h2>
            </div>

            {experience.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No verified work experience recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {experience.map((exp, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '1.25rem',
                      borderRadius: '12px',
                      backgroundColor: 'rgba(15, 23, 42, 0.5)',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <div>
                        <h3 style={{ margin: '0 0 0.2rem 0', fontSize: '1.05rem', color: '#ffffff', fontWeight: '700' }}>
                          {exp.title || exp.role}
                        </h3>
                        <div style={{ fontSize: '0.9rem', color: '#38bdf8', fontWeight: '600' }}>
                          {exp.company || exp.organization}
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                        {(exp.start_date || exp.end_date) && (
                          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                            {exp.start_date} — {exp.end_date || 'Present'}
                          </span>
                        )}
                        {renderScopeBadge(exp.claim_scope)}
                      </div>
                    </div>

                    {exp.verified_responsibilities && exp.verified_responsibilities.length > 0 && (
                      <ul style={{ margin: '0.75rem 0 0 0', paddingLeft: '1.2rem', color: '#cbd5e1', fontSize: '0.88rem', lineHeight: '1.5' }}>
                        {exp.verified_responsibilities.map((r, rIdx) => (
                          <li key={rIdx} style={{ marginBottom: '4px' }}>
                            {r}
                          </li>
                        ))}
                      </ul>
                    )}

                    {exp.evidence_claims && exp.evidence_claims.length > 0 && (
                      <div style={{ marginTop: '0.75rem' }}>
                        <button
                          onClick={() => setSelectedProvenance({ title: `${exp.title} at ${exp.company}`, claims: exp.evidence_claims })}
                          style={{
                            padding: '3px 8px',
                            borderRadius: '6px',
                            backgroundColor: 'rgba(56, 189, 248, 0.1)',
                            color: '#38bdf8',
                            border: '1px solid rgba(56, 189, 248, 0.25)',
                            fontSize: '0.75rem',
                            cursor: 'pointer',
                          }}
                        >
                          🔍 Inspect Provenance ({exp.evidence_claims.length} claims)
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Section: Verified Projects */}
          <section
            style={{
              padding: '1.75rem',
              borderRadius: '16px',
              backgroundColor: 'rgba(30, 41, 59, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '1.3rem' }}>🚀</span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', margin: 0, color: '#ffffff' }}>
                Verified Projects & Stories
              </h2>
            </div>

            {projects.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No verified projects recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {projects.map((proj, idx) => {
                  const projId = proj.project_id || `proj_${idx}`;
                  const isStoryOpen = Boolean(openStories[projId]);
                  const story = proj.project_story;

                  return (
                    <div
                      key={projId}
                      style={{
                        padding: '1.25rem',
                        borderRadius: '12px',
                        backgroundColor: 'rgba(15, 23, 42, 0.5)',
                        border: '1px solid rgba(255, 255, 255, 0.05)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <div>
                          <h3 style={{ margin: '0 0 0.2rem 0', fontSize: '1.05rem', color: '#ffffff', fontWeight: '700' }}>
                            {proj.name}
                          </h3>
                          <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                            {proj.role || 'Contributor'}
                          </div>
                        </div>
                        {renderScopeBadge(proj.claim_scope)}
                      </div>

                      {proj.description && (
                        <p style={{ margin: '0.6rem 0', color: '#cbd5e1', fontSize: '0.88rem', lineHeight: '1.5' }}>
                          {proj.description}
                        </p>
                      )}

                      {proj.technologies && proj.technologies.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', margin: '0.75rem 0' }}>
                          {proj.technologies.map((t, tIdx) => (
                            <span
                              key={tIdx}
                              style={{
                                padding: '2px 8px',
                                borderRadius: '4px',
                                backgroundColor: 'rgba(255, 255, 255, 0.06)',
                                color: '#e2e8f0',
                                fontSize: '0.75rem',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                              }}
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Project Story Accordion */}
                      {story && (
                        <div style={{ marginTop: '0.75rem' }}>
                          <button
                            onClick={() => toggleStory(projId)}
                            style={{
                              padding: '5px 10px',
                              borderRadius: '6px',
                              backgroundColor: isStoryOpen ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                              color: isStoryOpen ? '#38bdf8' : '#cbd5e1',
                              border: '1px solid rgba(255, 255, 255, 0.1)',
                              fontSize: '0.8rem',
                              fontWeight: '600',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                            }}
                          >
                            <span>{isStoryOpen ? '▲' : '▼'}</span> Project Story (STAR/CAR)
                          </button>

                          {isStoryOpen && (
                            <div
                              style={{
                                marginTop: '0.75rem',
                                padding: '1rem',
                                borderRadius: '8px',
                                backgroundColor: 'rgba(30, 41, 59, 0.8)',
                                border: '1px solid rgba(56, 189, 248, 0.2)',
                                fontSize: '0.85rem',
                                lineHeight: '1.6',
                              }}
                            >
                              <div style={{ marginBottom: '8px' }}>
                                <strong style={{ color: '#38bdf8' }}>Context:</strong> {story.context}
                              </div>
                              <div style={{ marginBottom: '8px' }}>
                                <strong style={{ color: '#facc15' }}>Problem:</strong> {story.problem}
                              </div>
                              <div style={{ marginBottom: '8px' }}>
                                <strong style={{ color: '#c084fc' }}>Approach:</strong> {story.approach}
                              </div>
                              <div style={{ marginBottom: '8px' }}>
                                <strong style={{ color: '#4ade80' }}>Implementation:</strong> {story.implementation}
                              </div>
                              {story.result && (
                                <div style={{ marginBottom: '8px' }}>
                                  <strong style={{ color: '#10b981' }}>Honest Result:</strong> {story.result}
                                </div>
                              )}
                              {story.learning && (
                                <div>
                                  <strong style={{ color: '#94a3b8' }}>Key Learning:</strong> {story.learning}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {proj.evidence_claims && proj.evidence_claims.length > 0 && (
                        <div style={{ marginTop: '0.75rem' }}>
                          <button
                            onClick={() => setSelectedProvenance({ title: `Project: ${proj.name}`, claims: proj.evidence_claims })}
                            style={{
                              padding: '3px 8px',
                              borderRadius: '6px',
                              backgroundColor: 'rgba(56, 189, 248, 0.1)',
                              color: '#38bdf8',
                              border: '1px solid rgba(56, 189, 248, 0.25)',
                              fontSize: '0.75rem',
                              cursor: 'pointer',
                            }}
                          >
                            🔍 Inspect Provenance ({proj.evidence_claims.length} claims)
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Verified Skills, Education, Certifications */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Section: Verified Skills */}
          <section
            style={{
              padding: '1.75rem',
              borderRadius: '16px',
              backgroundColor: 'rgba(30, 41, 59, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '1.3rem' }}>⚡</span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', margin: 0, color: '#ffffff' }}>
                Verified Skills
              </h2>
            </div>

            {skills.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No verified skills recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                {skills.map((s, idx) => (
                  <div
                    key={idx}
                    onClick={() => s.evidence_claims && setSelectedProvenance({ title: `Skill: ${s.name}`, claims: s.evidence_claims })}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      cursor: 'pointer',
                      transition: 'transform 0.15s ease',
                    }}
                    title="Click to view supporting evidence in vault"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                      <span style={{ fontWeight: '600', color: '#ffffff', fontSize: '0.9rem' }}>{s.name}</span>
                      <span style={{ fontSize: '0.75rem', color: '#38bdf8' }}>({s.evidence_claims?.length || s.evidence_count || 1})</span>
                    </div>
                    {renderScopeBadge(s.claim_scope)}
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Section: Verified Education */}
          <section
            style={{
              padding: '1.75rem',
              borderRadius: '16px',
              backgroundColor: 'rgba(30, 41, 59, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '1.3rem' }}>🎓</span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', margin: 0, color: '#ffffff' }}>
                Verified Education
              </h2>
            </div>

            {education.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No verified education recorded.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {education.map((edu, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '1rem',
                      borderRadius: '10px',
                      backgroundColor: 'rgba(15, 23, 42, 0.5)',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                    }}
                  >
                    <h3 style={{ margin: '0 0 4px 0', fontSize: '1rem', color: '#ffffff', fontWeight: '600' }}>
                      {edu.degree}
                    </h3>
                    <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                      {edu.institution} {edu.year ? `(${edu.year})` : ''}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Section: Verified Certifications */}
          <section
            style={{
              padding: '1.75rem',
              borderRadius: '16px',
              backgroundColor: 'rgba(30, 41, 59, 0.65)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '1.3rem' }}>📜</span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', margin: 0, color: '#ffffff' }}>
                Verified Certifications
              </h2>
            </div>

            {certifications.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>No verified certifications recorded.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {certifications.map((c, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '1rem',
                      borderRadius: '10px',
                      backgroundColor: 'rgba(15, 23, 42, 0.5)',
                      border: '1px solid rgba(255, 255, 255, 0.05)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <h3 style={{ margin: '0 0 4px 0', fontSize: '0.95rem', color: '#ffffff', fontWeight: '600' }}>
                        {c.name}
                      </h3>
                      <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                        {c.issuer} {c.date ? `• ${c.date}` : ''}
                      </div>
                    </div>
                    {renderScopeBadge(c.claim_scope || 'LEVEL 2 — USAGE')}
                  </div>
                ))}
              </div>
            )}
          </section>

        </div>
      </div>

      {/* Provenance Inspection Modal */}
      {selectedProvenance && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
          onClick={() => setSelectedProvenance(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '650px',
              maxHeight: '80vh',
              overflowY: 'auto',
              borderRadius: '16px',
              backgroundColor: '#1e293b',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              padding: '2rem',
              color: '#e2e8f0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: '700' }}>
                  Evidence Vault Provenance
                </span>
                <h3 style={{ margin: '0.2rem 0 0 0', fontSize: '1.2rem', color: '#ffffff' }}>
                  {selectedProvenance.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedProvenance(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: '1.4rem',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '1rem' }}>
              Every claim displayed in Vettora must be traceable to an authoritative Evidence Vault entry. Below are the verified source excerpts backing this claim:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {selectedProvenance.claims.map((c, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '1rem',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(15, 23, 42, 0.7)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#38bdf8' }}>
                      {c.evidence_id}
                    </span>
                    {renderScopeBadge(c.claim_scope)}
                  </div>
                  <blockquote
                    style={{
                      margin: '0.5rem 0',
                      paddingLeft: '0.75rem',
                      borderLeft: '2px solid #38bdf8',
                      color: '#f1f5f9',
                      fontSize: '0.85rem',
                      fontStyle: 'italic',
                    }}
                  >
                    "{c.claim_text}"
                  </blockquote>
                  <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: '#94a3b8', marginTop: '6px' }}>
                    {c.source_section && <span>Section: {c.source_section}</span>}
                    {c.confidence && <span>Confidence: {(c.confidence * 100).toFixed(0)}%</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
