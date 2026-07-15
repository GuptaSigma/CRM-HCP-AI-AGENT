import { useState } from 'react';
import { createInteraction, getAssistantDraft, type ApiStatus, type Sentiment } from '../api/client';

type ChatMessage = { role: 'assistant' | 'user'; text: string };
const suggestedFollowUps = ['Schedule follow-up meeting in 2 weeks', 'Send CardioBest Phase III PDF', 'Add Dr. Sharma to advisory board invite list'];

export function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: 'Log interaction details here (e.g., “Met Dr. Smith, discussed Product X efficacy, positive sentiment”) or ask for help.' }]);
  const [chatText, setChatText] = useState('');
  const [hcpName, setHcpName] = useState('');
  const [interactionType, setInteractionType] = useState('Meeting');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [time, setTime] = useState(new Date().toTimeString().slice(0, 5));
  const [attendees, setAttendees] = useState('');
  const [topics, setTopics] = useState('');
  const [outcomes, setOutcomes] = useState('');
  const [followUpText, setFollowUpText] = useState('');
  const [sentiment, setSentiment] = useState<Sentiment>('neutral');
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [materials, setMaterials] = useState<string[]>([]);
  const [samples, setSamples] = useState<string[]>([]);
  const [apiStatus, setApiStatus] = useState<ApiStatus>('idle');
  const [notice, setNotice] = useState('');

  const [activeId, setActiveId] = useState<string | null>(null);

  async function submitChat(event: React.FormEvent) {
    event.preventDefault();
    const message = chatText.trim();
    if (!message) return;
    setMessages((items) => [...items, { role: 'user', text: message }]);
    setApiStatus('loading');
    try {
      const result = await getAssistantDraft(message, activeId, {
        hcp_name: hcpName,
        interaction_type: interactionType,
        topics_discussed: topics,
        sentiment: sentiment,
        outcomes: outcomes
      });
      
      // Auto-populate all form fields, preserving existing values if not provided in the draft
      if (result.draft.hcp_name) {
        setHcpName(result.draft.hcp_name);
      }
      if (result.draft.interaction_type && result.draft.interaction_type !== 'Meeting') {
        setInteractionType(result.draft.interaction_type);
      }
      if (result.draft.topics_discussed) {
        setTopics(result.draft.topics_discussed);
      }
      if (result.draft.sentiment) {
        setSentiment(result.draft.sentiment);
      }
      if (result.draft.outcomes) {
        setOutcomes(result.draft.outcomes);
      }
      if (result.draft.attendees && result.draft.attendees.length > 0) {
        setAttendees(result.draft.attendees.join(', '));
      }
      if (result.draft.materials && result.draft.materials.length > 0) {
        setMaterials(result.draft.materials);
      }
      if (result.draft.samples && result.draft.samples.length > 0) {
        setSamples(result.draft.samples);
      }
      if (result.draft.follow_ups && result.draft.follow_ups.length > 0) {
        setFollowUpText(result.draft.follow_ups.join('\n'));
      }
      if (result.draft.occurred_at && result.draft.hcp_name) {
        const dateObj = new Date(result.draft.occurred_at);
        if (!isNaN(dateObj.getTime())) {
          setDate(dateObj.toISOString().slice(0, 10));
          setTime(dateObj.toTimeString().slice(0, 5));
        }
      }

      // Sync activeId if parsed from message
      const idMatch = result.message.match(/Interaction ID:\s*([a-f0-9-]+)/i);
      if (idMatch && idMatch[1]) {
        setActiveId(idMatch[1]);
      }

      setMessages((items) => [...items, { role: 'assistant', text: result.message }]);
      setApiStatus('success');
    } catch (error) {
      setMessages((items) => [...items, { role: 'assistant', text: error instanceof Error ? error.message : 'Assistant is unavailable.' }]);
      setApiStatus('error');
    }
    setChatText('');
  }

  async function saveInteraction(event: React.FormEvent) {
    event.preventDefault();
    if (!hcpName.trim()) { setNotice('Please enter an HCP name before saving.'); return; }
    setApiStatus('loading'); setNotice('');
    try {
      const result = await createInteraction({
        hcp_name: hcpName.trim(), interaction_type: interactionType, occurred_at: new Date(`${date}T${time}:00`).toISOString(),
        attendees: attendees.split(',').map((item) => item.trim()).filter(Boolean), topics_discussed: topics,
        sentiment, outcomes, materials: materials.map((name) => ({ name, quantity: 1 })), samples: samples.map((name) => ({ name, quantity: 1 })),
        follow_ups: followUpText.split('\n').map((task) => task.trim()).filter(Boolean).map((task) => ({ task })),
      });
      if (result && result.id) {
        setActiveId(result.id);
      }
      setApiStatus('success'); setNotice('Interaction saved successfully.');
    } catch (error) { setApiStatus('error'); setNotice(error instanceof Error ? error.message : 'Could not save interaction.'); }
  }

  return <main className="interaction-page">
    <h1>Log HCP Interaction</h1>
    <div className="interaction-layout">
      <section className="interaction-card" aria-labelledby="details-heading">
        <div className="card-titlebar"><h2 id="details-heading">Interaction Details</h2></div>
        <form className="interaction-form" onSubmit={saveInteraction}>
          <div className="two-column-fields">
            <label className="field"><span>HCP Name</span><input value={hcpName} onChange={(e) => setHcpName(e.target.value)} placeholder="Search or select HCP..." /></label>
            <label className="field select-field"><span>Interaction Type</span><select value={interactionType} onChange={(e) => setInteractionType(e.target.value)}><option>Meeting</option><option>In-person meeting</option><option>Virtual meeting</option><option>Phone call</option></select></label>
            <label className="field"><span>Date</span><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
            <label className="field"><span>Time</span><input type="time" value={time} onChange={(e) => setTime(e.target.value)} /></label>
          </div>
          <label className="field"><span>Attendees</span><input value={attendees} onChange={(e) => setAttendees(e.target.value)} placeholder="Enter names, separated by commas..." /></label>
          <label className="field"><span>Topics Discussed</span><textarea value={topics} onChange={(e) => setTopics(e.target.value)} placeholder="Enter key discussion points..." rows={3} /></label>
          <label className="voice-note"><input type="checkbox" checked={voiceEnabled} onChange={(e) => setVoiceEnabled(e.target.checked)} /><span>Summarize from Voice Note (Requires Consent)</span></label>
          <section className="distribution-section"><h3>Materials / Samples Distributed</h3><div className="distribution-box"><div className="distribution-heading"><strong>Materials Shared</strong><button type="button" onClick={() => setMaterials((items) => [...items, 'CardioBest Product Brochure'])}>Search/Add</button></div><p>{materials.length ? materials.join(', ') : 'No materials added'}</p></div><div className="distribution-box"><div className="distribution-heading"><strong>Samples Distributed</strong><button type="button" onClick={() => setSamples((items) => [...items, 'CardioBest 10mg sample'])}>Add Sample</button></div><p>{samples.length ? samples.join(', ') : 'No samples added'}</p></div></section>
          <fieldset className="sentiment-field"><legend>Observed/Inferred HCP Sentiment</legend>{(['positive', 'neutral', 'negative'] as Sentiment[]).map((value) => <label key={value}><input type="radio" name="sentiment" value={value} checked={sentiment === value} onChange={() => setSentiment(value)} /> {value[0].toUpperCase() + value.slice(1)}</label>)}</fieldset>
          <label className="field"><span>Outcomes</span><textarea value={outcomes} onChange={(e) => setOutcomes(e.target.value)} placeholder="Key outcomes or agreements..." rows={3} /></label>
          <label className="field"><span>Follow-up Actions</span><textarea value={followUpText} onChange={(e) => setFollowUpText(e.target.value)} placeholder="Enter one next step per line..." rows={3} /></label>
          <div className="followups"><strong>AI Suggested Follow-ups:</strong>{suggestedFollowUps.map((item) => <button type="button" key={item} onClick={() => setFollowUpText((text) => text ? `${text}\n${item}` : item)}>+ {item}</button>)}</div>
          <div className="save-row"><span className={`api-status ${apiStatus}`}>{notice}</span><button className="save-button" type="submit" disabled={apiStatus === 'loading'}>{apiStatus === 'loading' ? 'Saving...' : 'Save Interaction'}</button></div>
        </form>
      </section>
      <aside className="assistant-card" aria-labelledby="assistant-heading"><div className="assistant-header"><div><span className="bot-icon">✦</span><div><h2 id="assistant-heading">AI Assistant</h2><p>Log interaction via chat</p></div></div></div><div className="chat-history">{messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}>{message.text}</div>)}</div><form className="chat-input" onSubmit={submitChat}><input value={chatText} onChange={(e) => setChatText(e.target.value)} placeholder="Describe interaction..." /><button type="submit" disabled={apiStatus === 'loading'}>Log</button></form></aside>
    </div>
  </main>;
}
