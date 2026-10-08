// Thin wrapper over fetch that adds the Authorization header. It returns the raw Response,
// so callers keep handling res.ok / res.json() themselves.
export function createApi(token) {
  const auth = { Authorization: `Bearer ${token}` }
  const sendJson = (method, url, body) => fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify(body)
  })

  return {
    get: (url) => fetch(url, { headers: auth }),
    post: (url, body) => (body === undefined
      ? fetch(url, { method: 'POST', headers: auth })
      : sendJson('POST', url, body)),
    put: (url, body) => sendJson('PUT', url, body),
    delete: (url) => fetch(url, { method: 'DELETE', headers: auth }),
    // FormData: the browser sets the multipart Content-Type (with boundary) itself
    upload: (url, formData) => fetch(url, { method: 'POST', headers: auth, body: formData })
  }
}
