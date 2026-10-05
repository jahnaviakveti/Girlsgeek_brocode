import re

with open('backend/app/api/routes/coach.py', 'r') as f:
    content = f.read()

# Replace the part in upload_resume
old_code = """        # 2. Extract CandidateProfile
        profile = _resume_analyzer.analyze(doc)
        cid = profile.candidate_id"""

new_code = """        # 2. Extract CandidateProfile
        profile = _resume_analyzer.analyze(doc)
        profile.candidate_id = current_user.id  # Force ownership
        cid = current_user.id"""

content = content.replace(old_code, new_code)

with open('backend/app/api/routes/coach.py', 'w') as f:
    f.write(content)
print("upload_resume patched")
