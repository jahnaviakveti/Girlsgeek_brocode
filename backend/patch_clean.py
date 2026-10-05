import re
with open('app/api/routes/coach.py', 'r') as f:
    content = f.read()

# The original content ended at `get_project_stories`.
# Let's find the end of `get_project_stories` and truncate there.

match = re.search(r'def get_project_stories.*?(?=\n\n\n|\Z)', content, re.DOTALL)
if match:
    # Actually, the function ends around `return readiness.project_stories`.
    # Let's find `return readiness.project_stories`
    end_idx = content.find('return readiness.project_stories')
    if end_idx != -1:
        # include the return statement
        end_idx += len('return readiness.project_stories')
        clean_content = content[:end_idx] + "\n\n"
        with open('app/api/routes/coach.py', 'w') as f:
            f.write(clean_content)
        print("Cleaned!")
    else:
        print("Could not find end of get_project_stories")
