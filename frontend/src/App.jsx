import React, { useState } from 'react';
import './App.css';
import { VIEWS } from './types';
import { coachApi } from './services/api';
import Navigation from './components/common/Navigation';
import Dashboard from './views/Dashboard';
import CareerTwin from './views/CareerTwin';
import JobFit from './views/JobFit';
import ResumeCoach from './views/ResumeCoach';
import ResumeBuilder from './views/ResumeBuilder';
import CareerIntelligence from './views/CareerIntelligence';
import InterviewCoach from './views/InterviewCoach';
import ATSStressTest from './views/ATSStressTest';
import RecruiterPortal from './views/RecruiterPortal';

export default function App() {
  const [activeView, setActiveView] = useState(VIEWS.DASHBOARD);
  const [careerTwin, setCareerTwin] = useState(null);
  const [evidenceVault, setEvidenceVault] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [resumeCoachHandoff, setResumeCoachHandoff] = useState(null);
  const [selectedVersionId, setSelectedVersionId] = useState(null);

  const handleUploadResume = async (file) => {
    setIsUploading(true);
    setUploadError(null);
    try {
      const data = await coachApi.uploadResume(file);
      setCareerTwin(data.career_twin);
      setEvidenceVault(data.evidence_vault);
      setActiveView(VIEWS.CAREER_TWIN);
    } catch (err) {
      console.error("Resume ingestion error:", err);
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleHandoffToResumeCoach = (payload) => {
    setResumeCoachHandoff(payload);
    setActiveView(VIEWS.RESUME_COACH);
  };

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
          {careerTwin && (
            <div className="header-user-status">
              <span className="user-avatar-small">{(careerTwin.name ? careerTwin.name[0] : 'C')}</span>
              <span className="user-name-small">{careerTwin.name || "Candidate"}</span>
            </div>
          )}
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
