// Thin wrapper over fetch that adds the Authorization header. It returns the raw Response,
// so callers keep handling res.ok / res.json() themselves.
// onUnauthorized runs when the server rejects the token (expired or invalid), so the app can end the session.
export function createApi(token, onUnauthorized) {
  const auth = { Authorization: `Bearer ${token}` }
  const request = async (url, options) => {
    const res = await fetch(url, options)
    if (res.status === 401 && onUnauthorized) onUnauthorized()
    return res
  }
  const sendJson = (method, url, body) => request(url, {
    method,
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify(body)
  })

  return {
    get: (url) => request(url, { headers: auth }),
    post: (url, body) => (body === undefined
      ? request(url, { method: 'POST', headers: auth })
      : sendJson('POST', url, body)),
    put: (url, body) => sendJson('PUT', url, body),
    delete: (url) => request(url, { method: 'DELETE', headers: auth }),
    // FormData: the browser sets the multipart Content-Type (with boundary) itself
    upload: (url, formData) => request(url, { method: 'POST', headers: auth, body: formData })
  }
}
