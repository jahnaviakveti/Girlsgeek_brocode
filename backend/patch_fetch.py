import re

with open('../frontend/src/services/api.js', 'r') as f:
    content = f.read()

# I will replace `await fetch(` with `await fetchWithAuth(`
# But authApi should still use `fetch` or `fetchWithAuth` without infinite loop.
# Let's define `fetchWithAuth` at the top of the file.

wrapper = """
async function fetchWithAuth(url, options = {}) {
  const token = localStorage.getItem('vettora_token');
  const headers = { ...options.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return fetch(url, { ...options, headers });
}
"""

# Remove the old getAuthHeaders
content = re.sub(r'function getAuthHeaders.*?\n}\n', wrapper, content, flags=re.DOTALL)

# Now, we need to replace `await fetch(` with `await fetchWithAuth(`
# except we don't want to double replace if it's already fetchWithAuth.
# And authApi's register/login don't need auth, but it's safe to send it.
# We also need to remove any calls to getAuthHeaders() that we previously added.

# Remove getAuthHeaders wrapping
content = re.sub(r'headers:\s*getAuthHeaders\((.*?)\)', r'headers: \1', content)
content = re.sub(r'headers:\s*getAuthHeaders\(\)', '', content)

# Replace fetch with fetchWithAuth
content = re.sub(r'\bawait fetch\(', 'await fetchWithAuth(', content)

with open('../frontend/src/services/api.js', 'w') as f:
    f.write(content)

print("api.js patched with fetchWithAuth")
