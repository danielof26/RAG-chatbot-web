import { useState } from 'react'
import { EXPORT_FORMATS } from '../evaluation/exportFormats'

export default function DownloadDialog({ onConfirm, onCancel }) {
  const [selected, setSelected] = useState(['csv'])

  const toggle = (key) =>
    setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-lg px-6 py-5 w-72" onClick={e => e.stopPropagation()}>
        <p className="text-sm font-medium text-gray-700 mb-1">Download results</p>
        <p className="text-xs text-gray-400 mb-3">Includes the evaluation configuration (top_k, model, router...).</p>
        <div className="space-y-2 mb-4">
          {Object.entries(EXPORT_FORMATS).map(([key, { label }]) => (
            <label key={key} className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" checked={selected.includes(key)} onChange={() => toggle(key)} />
              {label}
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} className="text-sm text-gray-400 hover:text-gray-600 transition">Cancel</button>
          <button
            onClick={() => onConfirm(selected)}
            disabled={selected.length === 0}
            className="bg-orange-400 hover:bg-orange-500 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition disabled:opacity-50"
          >
            Download
          </button>
        </div>
      </div>
    </div>
  )
}
