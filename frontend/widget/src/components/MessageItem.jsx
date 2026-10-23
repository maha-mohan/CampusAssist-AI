import Markdown from 'react-markdown'
import { stripCitations } from '../lib/storage'
import { IconDoc, IconDown, IconUp } from './Icons'

function Typing() {
  return (
    <span className="hd-typing" aria-label="Assistant is typing">
      <i /><i /><i />
    </span>
  )
}

export default function MessageItem({ msg, api, onRate, onRaiseTicket }) {
  if (msg.role === 'user') {
    return (
      <div className="hd-row hd-row-user">
        <p className="hd-user">{msg.content}</p>
      </div>
    )
  }
  if (msg.kind === 'ticket-success') {
    return (
      <div className="hd-row">
        <div className="hd-ticket-ok" role="status">
          <p className="hd-ticket-ok-title">Ticket created</p>
          <dl>
            <dt>Ticket ID</dt><dd><strong>{msg.ticket.ticket_code}</strong></dd>
            <dt>Category</dt><dd>{msg.ticket.category}</dd>
            {msg.ticket.department && (<><dt>Sent to</dt><dd>{msg.ticket.department}</dd></>)}
            <dt>Status</dt><dd>Open</dd>
          </dl>
          <p className="hd-muted">Save this ID. To check progress later, type it here with your email or phone number.</p>
        </div>
      </div>
    )
  }

  const text = stripCitations(msg.content)
  const canRate = msg.done && typeof msg.id === 'number' && !msg.greeting
  return (
    <div className="hd-row">
      <div className={`hd-bot ${msg.answered === false ? 'hd-bot-unsure' : ''}`}>
        {msg.pending && !text ? <Typing /> : msg.failed ? <p className="hd-muted">Not sent.</p> : <div className="hd-md"><Markdown>{text}</Markdown></div>}

        {msg.sources?.length > 0 && (
          <ul className="hd-sources" aria-label="Sources">
            {msg.sources.map((s, i) => (
              <li key={i}>
                <IconDoc />
                {s.url ? (
                  <a href={api.absolute(s.url)} target="_blank" rel="noopener noreferrer">
                    From: {s.title}{s.page ? `, page ${s.page}` : ''}
                  </a>
                ) : (
                  <span>From: {s.title}</span>
                )}
              </li>
            ))}
          </ul>
        )}

        {msg.suggestTicket && msg.done && (
          <button type="button" className="hd-btn hd-btn-accent" onClick={() => onRaiseTicket(msg.ticketPrefill)}>
            Raise a support ticket
          </button>
        )}

        {canRate && (
          <div className="hd-rate">
            <span className="hd-muted">{msg.rating ? 'Thanks for the feedback.' : 'Was this helpful?'}</span>
            <button type="button" aria-label="Helpful" aria-pressed={msg.rating === 1} className={msg.rating === 1 ? 'on' : ''} onClick={() => onRate(msg.id, 1)}><IconUp /></button>
            <button type="button" aria-label="Not helpful" aria-pressed={msg.rating === -1} className={msg.rating === -1 ? 'on' : ''} onClick={() => onRate(msg.id, -1)}><IconDown /></button>
          </div>
        )}
      </div>
    </div>
  )
}
