import React, { useState, useEffect } from 'react';
import './App.css';
import { VIEWS } from './types';
import { coachApi, authApi } from './services/api';
import Navigation from './components/common/Navigation';
import Dashboard from './views/Dashboard';
import CareerTwin from './views/CareerTwin';
import JobFit from './views/JobFit';
import ResumeCoach from './views/ResumeCoach';
import ResumeBuilder from './views/ResumeBuilder';
import CareerIntelligence from './views/CareerIntelligence';
import CareerExecution from './views/CareerExecution';
import InterviewCoach from './views/InterviewCoach';
import ATSStressTest from './views/ATSStressTest';
import RecruiterPortal from './views/RecruiterPortal';
import CareerShowcase from './views/CareerShowcase';
import Auth from './views/Auth';

export default function App() {
  const getInitialPublicToken = () => {
    const hash = window.location.hash;
    if (hash && hash.startsWith('#showcase/')) {
      return hash.replace('#showcase/', '');
    }
    return null;
  };
  const [publicToken] = useState(getInitialPublicToken);
  const [currentUser, setCurrentUser] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [activeView, setActiveView] = useState(VIEWS.DASHBOARD);
  const [careerTwin, setCareerTwin] = useState(null);
  const [evidenceVault, setEvidenceVault] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [resumeCoachHandoff, setResumeCoachHandoff] = useState(null);
  const [selectedVersionId, setSelectedVersionId] = useState(null);

  const initSession = async () => {
    setIsInitializing(true);
    if (publicToken) {
      setIsInitializing(false);
      return;
    }
    try {
      const user = await authApi.getCurrentUser();
      setCurrentUser(user);
      
      try {
        const twinData = await coachApi.getCareerTwin(user.id);
        if (twinData.career_twin) {
           setCareerTwin(twinData.career_twin);
           setEvidenceVault(twinData.evidence_vault);
           setActiveView(VIEWS.CAREER_TWIN);
        }
      } catch (e) {
        // It's normal if they don't have a twin yet (404)
      }
    } catch (e) {
      // Not authenticated
      setCurrentUser(null);
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    initSession();
  }, [publicToken]);

  const handleLoginSuccess = async (user) => {
    setCurrentUser(user);
    // Fetch twin for the new user
    try {
      const twinData = await coachApi.getCareerTwin(user.id);
      if (twinData.career_twin) {
         setCareerTwin(twinData.career_twin);
         setEvidenceVault(twinData.evidence_vault);
         setActiveView(VIEWS.CAREER_TWIN);
      }
    } catch (e) {
      // 404 is fine
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('vettora_token');
    setCurrentUser(null);
    setCareerTwin(null);
    setEvidenceVault(null);
    setActiveView(VIEWS.DASHBOARD);
  };

  const handleUploadResume = async (file) => {
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      const data = await coachApi.uploadResume(file);
      setCareerTwin(data.career_twin);
      setEvidenceVault(data.evidence_vault);
      setActiveView(VIEWS.CAREER_TWIN);
    } catch (err) {
      console.error("Resume ingestion error:", err);
      const errMsg = err?.message || (typeof err === 'string' ? err : 'Resume parsing failed. Please check backend connection.');
      setUploadError(errMsg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleHandoffToResumeCoach = (payload) => {
    setResumeCoachHandoff(payload);
    setActiveView(VIEWS.RESUME_COACH);
  };

  if (isInitializing) {
    return (
      <div className="app-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div style={{ color: 'var(--text-secondary)' }}>Loading Vettora Session...</div>
      </div>
    );
  }

  if (publicToken) {
    return (
      <>
        <div className="noise-overlay" />
        <main className="app-container">
          <header className="header-nav">
            <div className="header-brand-wrap">
              <div className="brand-badge">Vettora • Verified Portfolio</div>
              <h1 className="brand-title">Candidate Career Showcase.</h1>
            </div>
          </header>
          <div className="view-content-outlet">
            <CareerShowcase publicToken={publicToken} />
          </div>
        </main>
      </>
    );
  }

  if (!currentUser) {
    return <Auth onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <>
      <div className="noise-overlay" />
      <main className="app-container">
        {/* Header / Brand Bar */}
        <header className="header-nav">
          <div className="header-brand-wrap">
            <div className="brand-badge">Vettora • AI Career & Interview Coach</div>
            <h1 className="brand-title">Career Intelligence Suite.</h1>
          </div>
          <div className="header-user-status" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {careerTwin && (
              <>
                <span className="user-avatar-small">{(careerTwin.name ? careerTwin.name[0] : 'C')}</span>
                <span className="user-name-small">{careerTwin.name || currentUser.name}</span>
              </>
            )}
            <button onClick={handleLogout} className="logout-btn" style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', padding: '4px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>
              Sign Out
            </button>
          </div>
        </header>

        {/* Global Navigation Tabs */}
        <Navigation activeView={activeView} onViewChange={setActiveView} />

        {/* Active View Router */}
        <div className="view-content-outlet">
          {activeView === VIEWS.DASHBOARD && (
            <Dashboard 
              careerTwin={careerTwin} 
              evidenceVault={evidenceVault} 
              onUploadResume={handleUploadResume}
              onNavigate={setActiveView}
              isUploading={isUploading}
              uploadError={uploadError}
            />
          )}

          {activeView === VIEWS.CAREER_TWIN && (
            <CareerTwin 
              careerTwin={careerTwin} 
              evidenceVault={evidenceVault} 
              onUploadNew={() => setActiveView(VIEWS.DASHBOARD)}
            />
          )}

          {activeView === VIEWS.JOB_FIT && (
            <JobFit 
              careerTwin={careerTwin} 
              onHandoffToResumeCoach={handleHandoffToResumeCoach}
            />
          )}

          {activeView === VIEWS.RESUME_COACH && (
            <ResumeCoach 
              careerTwin={careerTwin} 
              handoffPayload={resumeCoachHandoff}
              onClearHandoff={() => setResumeCoachHandoff(null)}
              onNavigateToBuilder={(versionId) => {
                if (versionId) setSelectedVersionId(versionId);
                setActiveView(VIEWS.RESUME_BUILDER);
              }}
            />
          )}

          {activeView === VIEWS.RESUME_BUILDER && (
            <ResumeBuilder 
              careerTwin={careerTwin}
              selectedVersionId={selectedVersionId}
              onNavigateToCoach={() => setActiveView(VIEWS.RESUME_COACH)}
              onNavigateToJobFit={() => setActiveView(VIEWS.JOB_FIT)}
            />
          )}

          {activeView === VIEWS.CAREER_INTELLIGENCE && (
            <CareerIntelligence 
              careerTwin={careerTwin}
              evidenceVault={evidenceVault}
              onHandoffToResumeCoach={handleHandoffToResumeCoach}
              onNavigateToVault={() => setActiveView(VIEWS.CAREER_TWIN)}
            />
          )}

          {activeView === VIEWS.CAREER_EXECUTION && (
            <CareerExecution 
              careerTwin={careerTwin} 
              evidenceVault={evidenceVault}
              onNavigateToTwin={() => setActiveView(VIEWS.CAREER_TWIN)}
              onNavigateToTarget={() => setActiveView(VIEWS.CAREER_INTELLIGENCE)}
            />
          )}

          {activeView === VIEWS.CAREER_SHOWCASE && (
            <CareerShowcase careerTwin={careerTwin} />
          )}

          {activeView === VIEWS.INTERVIEW_COACH && (
            <InterviewCoach 
              careerTwin={careerTwin} 
              evidenceVault={evidenceVault}
            />
          )}

          {activeView === VIEWS.ATS_STRESS_TEST && (
            <ATSStressTest 
              careerTwin={careerTwin} 
            />
          )}

          {activeView === VIEWS.RECRUITER_PORTAL && (
            <RecruiterPortal />
          )}
        </div>
      </main>
    </>
  );
}
