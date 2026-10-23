// Embeddable entry: mounts the chat widget inside a Shadow DOM so the college
// website's CSS can't break it (and the widget can't break the website).
import { createRoot } from 'react-dom/client'
import App from './App'
import css from './styles/widget.css?inline'

const FONT_HREF = 'https://fonts.googleapis.com/css2?family=Hind+Madurai:wght@400;500;600;700&display=swap'

// Captured at load time: document.currentScript is null once DOMContentLoaded fires.
const CURRENT_SCRIPT = document.currentScript

function readConfig() {
  const script =
    CURRENT_SCRIPT ||
    document.querySelector('script[data-helpdesk], script[src*="helpdesk-widget"]')
  const ds = script?.dataset || {}
  const g = window.CollegeHelpDeskConfig || {}
  return {
    api: g.api || ds.api || `${window.location.origin}/api`,
    title: g.title || ds.title || 'College Help Desk',
    color: g.color || ds.color || '',
    accent: g.accent || ds.accent || '',
    position: (g.position || ds.position || 'right') === 'left' ? 'left' : 'right',
    maxChars: Number(g.maxChars || ds.maxChars || 1000),
  }
}

function mount() {
  if (document.getElementById('college-helpdesk-root')) return
  const config = readConfig()

  // Fonts must be declared in the main document to be usable inside the shadow root.
  if (!document.querySelector(`link[href="${FONT_HREF}"]`)) {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = FONT_HREF
    document.head.appendChild(link)
  }

  const host = document.createElement('div')
  host.id = 'college-helpdesk-root'
  document.body.appendChild(host)
  const shadow = host.attachShadow({ mode: 'open' })

  const style = document.createElement('style')
  style.textContent = css
  shadow.appendChild(style)
  if (config.color || config.accent) {
    const theme = document.createElement('style')
    theme.textContent = `:host{${config.color ? `--hd-navy:${config.color};` : ''}${config.accent ? `--hd-marigold:${config.accent};` : ''}}`
    shadow.appendChild(theme)
  }

  const container = document.createElement('div')
  shadow.appendChild(container)
  createRoot(container).render(<App config={config} />)
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount)
else mount()
