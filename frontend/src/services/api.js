const API_BASE_URL = 'http://localhost:8000/api';

export const coachApi = {
  /**
   * Health check for coach layer
   */
  async checkHealth() {
    const res = await fetch(`${API_BASE_URL}/coach/health`);
    if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
    return res.json();
  },

  /**
   * Ingest a single candidate resume PDF
   * @param {File} resumeFile
   */
  async uploadResume(resumeFile) {
    const formData = new FormData();
    formData.append('resume_file', resumeFile);
    const res = await fetch(`${API_BASE_URL}/coach/resume`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed with status ${res.status}`);
    }
    return res.json();
  },

  /**
   * Evaluate Job Fit between candidate and target JD
   * @param {string} candidateId
   * @param {File|null} jdFile
   * @param {string|null} jdText
   */
  async evaluateJobFit(candidateId, jdFile = null, jdText = null) {
    const formData = new FormData();
    formData.append('candidate_id', candidateId);
    if (jdFile) {
      formData.append('jd_file', jdFile);
    }
    if (jdText) {
      formData.append('jd_text', jdText);
    }
    const res = await fetch(`${API_BASE_URL}/coach/job-fit`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Fit analysis failed with status ${res.status}`);
    }
    return res.json();
  },

  /**
   * Query Career Twin by candidateId
   * @param {string} candidateId
   */
  async getCareerTwin(candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/career-twin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candidateId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Query failed with status ${res.status}`);
    }
    return res.json();
  },

  /**
   * Query Evidence Vault with optional filtering
   * @param {string} candidateId
   * @param {Object} filters
   */
  async getEvidence(candidateId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.section) params.append('section', filters.section);
    if (filters.type) params.append('type', filters.type);
    if (filters.skill) params.append('skill', filters.skill);
    if (filters.project) params.append('project', filters.project);
    if (filters.experience) params.append('experience', filters.experience);

    const queryStr = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE_URL}/coach/evidence/${encodeURIComponent(candidateId)}${queryStr}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Evidence query failed with status ${res.status}`);
    }
    return res.json();
  },

  /**
   * Ground a candidate factual claim against the Evidence Vault
   * @param {string} candidateId
   * @param {string} claim
   */
  async validateClaim(candidateId, claim) {
    const res = await fetch(`${API_BASE_URL}/coach/evidence/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candidateId, claim }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Validation failed with status ${res.status}`);
    }
    return res.json();
  },

  /**
   * Resume Versions & Builder API (Phase 5)
   */
  async getResumeVersions(candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(candidateId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch resume versions: ${res.status}`);
    }
    return res.json();
  },

  async getResumeVersionDetail(candidateId, versionId) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(candidateId)}/${encodeURIComponent(versionId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch resume version: ${res.status}`);
    }
    return res.json();
  },

  async createResumeVersion(candidateId, title, targetRole = null, parentVersionId = null) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: candidateId,
        title,
        target_role: targetRole,
        parent_version_id: parentVersionId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create resume version: ${res.status}`);
    }
    return res.json();
  },

  async applySuggestionToVersion(versionId, suggestion, createNewVersion = false, title = null) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(versionId)}/apply-suggestion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        suggestion,
        create_new_version: createNewVersion,
        new_version_title: title,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to apply suggestion: ${res.status}`);
    }
    return res.json();
  },

  async recheckJobFit(versionId, jobText, targetRole = null, company = null, previousCoverage = null) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(versionId)}/recheck-job-fit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_text: jobText,
        target_role: targetRole,
        company,
        previous_coverage: previousCoverage,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to re-check job fit: ${res.status}`);
    }
    return res.json();
  },

  async cloneResumeVersion(versionId, title = null) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(versionId)}/clone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to clone resume version: ${res.status}`);
    }
    return res.json();
  },

  async getVersionDiff(versionId) {
    const res = await fetch(`${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(versionId)}/diff`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch diff: ${res.status}`);
    }
    return res.json();
  },

  getExportPdfUrl(versionId) {
    return `${API_BASE_URL}/coach/resume-versions/${encodeURIComponent(versionId)}/export`;
  },

  /**
   * Career Targets & Intelligence API (Phase 6)
   */
  async createCareerTarget(data) {
    const res = await fetch(`${API_BASE_URL}/coach/career-targets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create career target: ${res.status}`);
    }
    return res.json();
  },

  async getCareerTargets(candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/career-targets/${encodeURIComponent(candidateId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch career targets: ${res.status}`);
    }
    return res.json();
  },

  async getCareerTargetDetail(candidateId, targetId) {
    const res = await fetch(`${API_BASE_URL}/coach/career-targets/${encodeURIComponent(candidateId)}/${encodeURIComponent(targetId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch career target: ${res.status}`);
    }
    return res.json();
  },

  async getCareerIntelligence(candidateId, targetId, previousCoverage = null) {
    let url = `${API_BASE_URL}/coach/career-intelligence/${encodeURIComponent(candidateId)}/${encodeURIComponent(targetId)}`;
    if (previousCoverage !== null && previousCoverage !== undefined) {
      url += `?previous_coverage=${encodeURIComponent(previousCoverage)}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch career intelligence: ${res.status}`);
    }
    return res.json();
  },

  async refreshCareerIntelligence(targetId, candidateId, previousCoverage = null) {
    let url = `${API_BASE_URL}/coach/career-intelligence/${encodeURIComponent(targetId)}/refresh?candidate_id=${encodeURIComponent(candidateId)}`;
    if (previousCoverage !== null && previousCoverage !== undefined) {
      url += `&previous_coverage=${encodeURIComponent(previousCoverage)}`;
    }
    const res = await fetch(url, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to refresh career intelligence: ${res.status}`);
    }
    return res.json();
  },

  async createCareerAction(data) {
    const res = await fetch(`${API_BASE_URL}/coach/career-actions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create career action: ${res.status}`);
    }
    return res.json();
  },

  async getCareerActions(candidateId, targetId = null) {
    let url = `${API_BASE_URL}/coach/career-actions/${encodeURIComponent(candidateId)}`;
    if (targetId) {
      url += `?target_id=${encodeURIComponent(targetId)}`;
    }
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch career actions: ${res.status}`);
    }
    return res.json();
  },

  async completeCareerAction(actionId, candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/career-actions/${encodeURIComponent(actionId)}/complete?candidate_id=${encodeURIComponent(candidateId)}`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to complete career action: ${res.status}`);
    }
    return res.json();
  },

  async dismissCareerAction(actionId, candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/career-actions/${encodeURIComponent(actionId)}/dismiss?candidate_id=${encodeURIComponent(candidateId)}`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to dismiss career action: ${res.status}`);
    }
    return res.json();
  },

  // ==========================================
  // PHASE 7: INTERVIEW & APPLICATION READINESS
  // ==========================================

  async createInterviewTarget(candidateId, targetRole, company = null, jobDescriptionText = null, targetId = null) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-targets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: candidateId,
        target_role: targetRole,
        company,
        job_description_text: jobDescriptionText,
        target_id: targetId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create interview target: ${res.status}`);
    }
    return res.json();
  },

  async getInterviewTargets(candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-targets/${encodeURIComponent(candidateId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch interview targets: ${res.status}`);
    }
    return res.json();
  },

  async getInterviewTargetDetail(candidateId, targetId) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-targets/${encodeURIComponent(candidateId)}/${encodeURIComponent(targetId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch interview target: ${res.status}`);
    }
    return res.json();
  },

  async getInterviewReadiness(candidateId, targetId) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-readiness/${encodeURIComponent(candidateId)}/${encodeURIComponent(targetId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch interview readiness: ${res.status}`);
    }
    return res.json();
  },

  async refreshInterviewReadiness(targetId, candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-readiness/${encodeURIComponent(targetId)}/refresh?candidate_id=${encodeURIComponent(candidateId)}`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to refresh interview readiness: ${res.status}`);
    }
    return res.json();
  },

  async getInterviewQuestions(targetId, candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-questions/${encodeURIComponent(targetId)}?candidate_id=${encodeURIComponent(candidateId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch questions: ${res.status}`);
    }
    return res.json();
  },

  async validateInterviewAnswer(candidateId, questionId, answerText, requirementId = null, targetId = null) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-answers/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: candidateId,
        question_id: questionId,
        answer_text: answerText,
        requirement_id: requirementId,
        target_id: targetId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to validate answer: ${res.status}`);
    }
    return res.json();
  },

  async createInterviewSession(candidateId, interviewTargetId) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: candidateId,
        interview_target_id: interviewTargetId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to create interview session: ${res.status}`);
    }
    return res.json();
  },

  async submitSessionAnswer(sessionId, candidateId, questionId, answerText) {
    const res = await fetch(`${API_BASE_URL}/coach/interview-sessions/${encodeURIComponent(sessionId)}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: candidateId,
        question_id: questionId,
        answer_text: answerText,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to submit session answer: ${res.status}`);
    }
    return res.json();
  },

  async getProjectStories(candidateId) {
    const res = await fetch(`${API_BASE_URL}/coach/project-stories/${encodeURIComponent(candidateId)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to fetch project stories: ${res.status}`);
    }
    return res.json();
  },

  /**
   * Legacy recruiter batch candidate analysis
   * @param {File} jdFile
   * @param {File[]} resumeFiles
   */
  async analyzeRecruiterBatch(jdFile, resumeFiles) {
    const formData = new FormData();
    formData.append('jd_file', jdFile);
    resumeFiles.forEach((file) => {
      formData.append('resume_files', file);
    });
    const res = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Recruiter analysis failed: ${res.status}`);
    }
    return res.json();
  },
};
