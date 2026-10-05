/**
 * Navigation views and module identifiers for Vettora AI Career Coach
 */
export const VIEWS = {
  DASHBOARD: 'dashboard',
  CAREER_TWIN: 'career_twin',
  JOB_FIT: 'job_fit',
  RESUME_COACH: 'resume_coach',
  RESUME_BUILDER: 'resume_builder',
  CAREER_INTELLIGENCE: 'career_intelligence',
  CAREER_EXECUTION: 'career_execution',
  CAREER_SHOWCASE: 'career_showcase',
  INTERVIEW_COACH: 'interview_coach',
  ATS_STRESS_TEST: 'ats_stress_test',
  RECRUITER_PORTAL: 'recruiter_portal', // Legacy recruiter batch shortlisting
};

export const NAV_ITEMS = [
  { id: VIEWS.DASHBOARD, label: 'Dashboard', icon: '📊' },
  { id: VIEWS.CAREER_TWIN, label: 'Career Twin', icon: '👤' },
  { id: VIEWS.JOB_FIT, label: 'Resume × Job Fit', icon: '🎯' },
  { id: VIEWS.RESUME_COACH, label: 'Resume Coach', icon: '📝' },
  { id: VIEWS.RESUME_BUILDER, label: 'Resume Versions', icon: '📄' },
  { id: VIEWS.CAREER_INTELLIGENCE, label: 'Career Intelligence', icon: '🧭' },
  { id: VIEWS.CAREER_EXECUTION, label: 'Career Execution', icon: '🚀' },
  { id: VIEWS.CAREER_SHOWCASE, label: 'Career Showcase', icon: '🌟' },
  { id: VIEWS.INTERVIEW_COACH, label: 'Interview Coach', icon: '🎙️' },
  { id: VIEWS.ATS_STRESS_TEST, label: 'ATS Stress Test', icon: '🛡️' },
  { id: VIEWS.RECRUITER_PORTAL, label: 'Recruiter Vetting', icon: '⚡' },
];
