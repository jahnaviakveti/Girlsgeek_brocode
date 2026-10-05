import os

# Patch JobFit.jsx
jobfit_path = "src/views/JobFit.jsx"
with open(jobfit_path, "r") as f:
    jobfit_content = f.read()

cta_code = """
          {/* Bulk Improve CTA */}
          <div className="bulk-improve-action" style={{marginTop: '1rem', marginBottom: '1rem', textAlign: 'center'}}>
            <button 
              className="btn-primary" 
              style={{fontSize: '1.1rem', padding: '1rem 2rem', background: 'linear-gradient(135deg, #4f46e5, #7c3aed)'}}
              onClick={() => {
                if (!onHandoffToResumeCoach || !fitData?.job_fit_analysis) return;
                
                const gaps = (fitData.job_fit_analysis.requirements || []).filter(req => 
                  req.gap_type === 'RESUME_VISIBILITY_GAP' || req.gap_type === 'EXPERIENCE_GAP' || req.gap_type === 'NOT_VERIFIABLE'
                );
                
                const payloads = gaps.map(req => {
                  const opp = fitData.job_fit_analysis.improvement_opportunities?.find(o => o.requirement_id === req.requirement_id);
                  return opp?.handoff_payload || {
                    requirement_id: req.requirement_id,
                    requirement_text: req.requirement_text,
                    target_role: fitData.job_fit_analysis.target_role || fitData.job_title || "Target Role",
                    priority: req.priority,
                    gap_type: req.gap_type,
                    can_rewrite: req.gap_type === 'RESUME_VISIBILITY_GAP',
                    evidence_ids: (req.evidence || []).map(e => e.evidence_id).filter(Boolean),
                    existing_evidence_snippets: (req.evidence || []).map(e => e.source_text),
                    missing_elements: req.missing_evidence || [],
                    action_prompt: req.candidate_action
                  };
                });

                onHandoffToResumeCoach({ bulk: true, items: payloads, target_role: fitData.job_title });
              }}
            >
              ✨ Improve My Resume for This Job
            </button>
          </div>
"""

if "✨ Improve My Resume for This Job" not in jobfit_content:
    jobfit_content = jobfit_content.replace(
        "          {/* 3. Requirement Breakdown Filter Bar */}",
        cta_code + "\n          {/* 3. Requirement Breakdown Filter Bar */}"
    )
    with open(jobfit_path, "w") as f:
        f.write(jobfit_content)

# Patch ResumeCoach.jsx
coach_path = "src/views/ResumeCoach.jsx"
with open(coach_path, "r") as f:
    coach_content = f.read()

# I am replacing the component body to handle `bulk: true` inside `handoffPayload`
if "handoffPayload?.bulk" not in coach_content:
    replacement = """
  const isBulk = handoffPayload?.bulk;
  const bulkItems = isBulk ? handoffPayload.items : (handoffPayload ? [handoffPayload] : []);

  const [bulkResults, setBulkResults] = useState({});
  const [bulkAccepted, setBulkAccepted] = useState({});
  
  const handleGenerateRewrite = async (payloadOverride) => {
    const item = payloadOverride || handoffPayload;
    if (!item) return;
    setLoading(true);
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
      if (isBulk) {
        setBulkResults(prev => ({...prev, [item.requirement_id]: data}));
        setBulkAccepted(prev => ({...prev, [item.requirement_id]: data.status === 'ACCEPTED'}));
      } else {
        setRewriteResult(data);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to generate resume rewrite.');
    } finally {
      setLoading(false);
    }
  };

  const handleBulkGenerateAll = async () => {
    for (const item of bulkItems) {
      if (item.gap_type === 'RESUME_VISIBILITY_GAP') {
        await handleGenerateRewrite(item);
      }
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
      
      const itemsToApply = Object.values(bulkResults).filter(r => bulkAccepted[r.requirement_id] && r.status === 'ACCEPTED');
      for (const sug of itemsToApply) {
        targetVersion = await coachApi.applySuggestionToVersion(targetVersion.version_id, sug, false);
      }
      
      onNavigateToBuilder(targetVersion.version_id);
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message);
    } finally {
      setApplyingToDraft(false);
    }
  };
"""

    # Simple insertion right after state initialization
    insert_idx = coach_content.find("  const [prevReqId, setPrevReqId] = useState")
    coach_content = coach_content[:insert_idx] + replacement + coach_content[insert_idx:]
    
    # Render bulk list
    bulk_ui = """
      {isBulk && bulkItems.length > 0 && (
        <div className="bulk-coach-container">
          <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: '1rem'}}>
             <h3>Bulk Improvements</h3>
             <button className="btn-coach-generate" onClick={handleBulkGenerateAll}>
                ✨ Generate All AI Improvements
             </button>
          </div>
          
          {bulkItems.map((item, idx) => {
             const result = bulkResults[item.requirement_id];
             const isExpGap = item.gap_type === 'EXPERIENCE_GAP';
             
             return (
               <div key={idx} className="rewrite-result-card" style={{marginBottom: '1rem'}}>
                 <div className="opt-card-header">
                    <div>
                      <span className={`gap-badge ${isExpGap ? 'badge-exp-gap' : 'badge-vis-gap'}`}>
                        {item.gap_type}
                      </span>
                      <h4>Target Requirement: "{item.requirement_text}"</h4>
                    </div>
                 </div>
                 
                 {isExpGap ? (
                    <div className="experience-gap-alert-box">
                       <p>You do not currently have verified evidence for this requirement. Learn Skill / Build Project / Gain Experience.</p>
                    </div>
                 ) : (
                    <div>
                       {!result ? (
                         <button onClick={() => handleGenerateRewrite(item)} className="btn-secondary">Generate AI Improvement</button>
                       ) : (
                         <div className="suggestion-details">
                            <div className="compare-block">
                               <div className="before">
                                 <strong>BEFORE:</strong> {result.original_text}
                               </div>
                               <div className="after" style={{color: '#047857'}}>
                                 <strong>AFTER:</strong> {result.suggested_text}
                               </div>
                            </div>
                            <div className="meta-info">
                               <strong>WHY THIS HELPS:</strong> {result.explanation}<br/>
                               <strong>STATUS:</strong> {result.status}<br/>
                               <strong>EVIDENCE CITATIONS:</strong> {result.evidence_used?.map(e => e.evidence_id).join(', ')}
                            </div>
                            
                            <div style={{marginTop: '1rem', display: 'flex', gap: '0.5rem'}}>
                               <label>
                                 <input type="checkbox" checked={!!bulkAccepted[item.requirement_id]} onChange={(e) => setBulkAccepted(prev => ({...prev, [item.requirement_id]: e.target.checked}))} />
                                 <strong>Accept Suggestion</strong>
                               </label>
                               <button onClick={() => handleGenerateRewrite(item)}>Regenerate</button>
                               <button onClick={() => setBulkAccepted(prev => ({...prev, [item.requirement_id]: false}))}>Keep Original</button>
                            </div>
                         </div>
                       )}
                    </div>
                 )}
               </div>
             );
          })}
          
          <button className="btn-primary" onClick={handleCreateTailoredVersion} disabled={applyingToDraft} style={{marginTop: '2rem', width: '100%', padding: '1rem'}}>
             {applyingToDraft ? "Applying..." : "Create Tailored Resume Version"}
          </button>
        </div>
      )}
"""
    # Insert ui right before target requirement card
    ui_insert = coach_content.find("{/* Target Requirement Optimization Card from Job Fit */}")
    coach_content = coach_content[:ui_insert] + bulk_ui + "\n      {!isBulk && handoffPayload && (" + coach_content[ui_insert:].replace("{handoffPayload && (", "")
    coach_content = coach_content.replace("{/* Target Requirement Optimization Card from Job Fit */}", "{/* Target Requirement Optimization Card from Job Fit */}\n")
    
    with open(coach_path, "w") as f:
        f.write(coach_content)
