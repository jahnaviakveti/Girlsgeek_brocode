import re

with open('frontend/src/views/CareerIntelligence.jsx', 'r') as f:
    content = f.read()

# Replace the old modal and add the new layout

# Find the start of `{/* Empty State when no targets exist */}`
empty_state_start = content.find('{/* Empty State when no targets exist */}')

# Find the end of `{/* Action Plan Section */}` div
action_plan_end = content.find('{/* Create Target Modal */}')

if empty_state_start == -1 or action_plan_end == -1:
    print("Could not find markers")
    exit(1)

# Extract the existing empty state and intelligence dashboard
existing_dashboard = content[empty_state_start:action_plan_end]

# Define the new structure
new_structure = """      {showCreateModal ? (
        <div className="ci-create-target-card">
          <div className="ci-create-left">
            <div className="ci-create-icon">🎯</div>
            <h3 className="ci-create-title">{targets.length === 0 ? "No Career Target Defined" : "Create your career target"}</h3>
            <p className="ci-create-desc">
              Set a target role and Vettora will analyze your verified evidence against its requirements.
            </p>
            <ul className="ci-create-benefits">
              <li>✓ Evidence alignment</li>
              <li>✓ Gap analysis</li>
              <li>✓ Career action planning</li>
            </ul>
          </div>
          <div className="ci-create-right">
            <div className="ci-create-right-header">
              <h4>Create New Career Target</h4>
            </div>
            <form onSubmit={handleCreateTarget} className="ci-create-form">
              <div className="form-group">
                <label className="form-label" htmlFor="role-input">Target Role Title *</label>
                <input
                  id="role-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Senior Backend Engineer"
                  value={targetRoleInput}
                  onChange={e => setTargetRoleInput(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="company-input">Target Company (Optional)</label>
                <input
                  id="company-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Stripe, OpenAI, Datadog"
                  value={targetCompanyInput}
                  onChange={e => setTargetCompanyInput(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="jd-text-input">Job Description / Requirements</label>
                <textarea
                  id="jd-text-input"
                  className="form-textarea"
                  rows={6}
                  placeholder={`Paste target job requirements here, for example:\n\nRequirements:\n- Python microservices\n- PostgreSQL database\n- Kubernetes cluster orchestration\n\nPreferred:\n- Rust experience`}
                  value={targetJdTextInput}
                  onChange={e => setTargetJdTextInput(e.target.value)}
                />
                <span className="form-hint">
                  Requirements are deterministically analyzed using the existing Job Fit engine.
                </span>
              </div>

              <div className="ci-create-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={createSubmitting || !targetRoleInput.trim()}
                >
                  {createSubmitting ? 'Creating...' : 'Create Career Target'}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : (
        <>
"""

existing_dashboard = existing_dashboard.replace('      {/* Empty State when no targets exist */}', '          {/* Empty State when no targets exist */}')

# Now we need to remove the old Create Target Modal
old_modal_start = content.find('{/* Create Target Modal */}')
evidence_modal_start = content.find('{/* Evidence Provenance Modal / Drawer */}')

before_old_content = content[:empty_state_start]
after_old_content = content[evidence_modal_start:]

final_content = before_old_content + new_structure + existing_dashboard + "        </>\n      )}\n\n      " + after_old_content

with open('frontend/src/views/CareerIntelligence.jsx', 'w') as f:
    f.write(final_content)

print("Updated CareerIntelligence.jsx successfully.")
