import re
with open('frontend/src/services/api.js', 'r') as f:
    content = f.read()

# Fix `if (!res.ok, { headers:  }) {`
content = content.replace('if (!res.ok, { headers:  }) {', 'if (!res.ok) {')
content = content.replace(', { headers:  }', '')

with open('frontend/src/services/api.js', 'w') as f:
    f.write(content)
