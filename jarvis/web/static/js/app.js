/**
 * M.I.N.E. Core Frontend Application Controller
 */

class MineHUDApp {
  constructor() {
    this.visualizer = new AudioWaveformVisualizer('audioVisualizer');
    this.ws = null;
    this.state = 'idle'; // idle | listening | processing | speaking
    this.speechEnabled = true;
    this.recognition = null;
    this.isListening = false;
    this.selectedVoice = null;

    this.initElements();
    this.initWebSocket();
    this.initSpeechRecognition();
    this.initSpeechSynthesis();
    this.bindEvents();
    this.loadState();
    
    // Auto refresh telemetry every 5s
    setInterval(() => this.loadState(), 5000);
  }

  initElements() {
    this.arcReactor = document.getElementById('arcReactor');
    this.reactorStatus = document.getElementById('reactorStatus');
    this.cmdInput = document.getElementById('cmdInput');
    this.sendBtn = document.getElementById('sendBtn');
    this.micBtn = document.getElementById('micBtn');
    this.audioToggleBtn = document.getElementById('audioToggleBtn');
    this.settingsBtn = document.getElementById('settingsBtn');
    this.chatStream = document.getElementById('chatStream');

    // Modals
    this.hazardModal = document.getElementById('hazardModal');
    this.hazardMessage = document.getElementById('hazardMessage');
    this.btnAuthorize = document.getElementById('btnAuthorize');
    this.btnAbort = document.getElementById('btnAbort');

    this.settingsModal = document.getElementById('settingsModal');
    this.closeSettingsBtn = document.getElementById('closeSettingsBtn');
    this.saveSettingsBtn = document.getElementById('saveSettingsBtn');
    this.providerSelect = document.getElementById('providerSelect');
    this.ollamaModelInput = document.getElementById('ollamaModelInput');
    this.ollamaUrlInput = document.getElementById('ollamaUrlInput');
    this.apiKeyInput = document.getElementById('apiKeyInput');

    // Widgets
    this.cpuVal = document.getElementById('cpuVal');
    this.cpuBar = document.getElementById('cpuBar');
    this.ramVal = document.getElementById('ramVal');
    this.ramBar = document.getElementById('ramBar');
    this.batteryVal = document.getElementById('batteryVal');
    this.batteryBar = document.getElementById('batteryBar');

    this.remindersList = document.getElementById('remindersList');
    this.calendarList = document.getElementById('calendarList');
    this.memoryList = document.getElementById('memoryList');
    this.docsList = document.getElementById('docsList');
  }

  setVisualState(newState) {
    this.state = newState;
    this.visualizer.setState(newState);

    this.arcReactor.className = `arc-reactor-wrapper ${newState}`;
    const labels = {
      idle: 'SYSTEM ONLINE',
      listening: 'LISTENING...',
      processing: 'ANALYZING...',
      speaking: 'TRANSMITTING...'
    };
    this.reactorStatus.textContent = labels[newState] || 'STANDBY';
  }

  initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('[M.I.N.E] WebSocket Uplink Established.');
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.handleSocketEvent(payload);
        } catch (e) {
          console.error('[M.I.N.E] WS parse error:', e);
        }
      };

      this.ws.onclose = () => {
        console.warn('[M.I.N.E] WebSocket Disconnected. Reconnecting in 3s...');
        setTimeout(() => this.initWebSocket(), 3000);
      };
    } catch (e) {
      console.error('[M.I.N.E] WS init error:', e);
    }
  }

  handleSocketEvent(payload) {
    const event = payload.event;
    const data = payload.data;

    if (event === 'initial_state') {
      this.renderState(data);
    } else if (event === 'reminder_triggered') {
      this.notifyReminder(data);
      this.loadState();
    } else if (event === 'system_voice_start') {
      this.onSystemVoiceStart(data.text);
    } else if (event === 'system_voice_end') {
      this.onSystemVoiceEnd();
    } else if (event === 'tts_speech' && this.speechEnabled) {
      if (!data.server_audio_active) {
        this.speakText(data.text);
      } else {
        // Server SAPI is already speaking out loud, update visual state without double-speaking
        this.onSystemVoiceStart(data.text);
      }
    } else if (event === 'action_confirmed' || event === 'action_cancelled') {
      this.hideHazardModal();
      this.loadState();
    }
  }

  onSystemVoiceStart(text) {
    this.isSystemSpeaking = true;
    if (text) {
      if (!this.recentSystemSpeech) this.recentSystemSpeech = [];
      this.recentSystemSpeech.push({ text: text.toLowerCase().trim(), time: Date.now() });
      if (this.recentSystemSpeech.length > 20) {
        this.recentSystemSpeech.shift();
      }
    }
    this.setVisualState('speaking');

    // Pause browser speech recognition during System Voice playback to prevent acoustic feedback
    if (this.recognition && this.isListening) {
      console.log('[M.I.N.E] Pausing microphone recognition during System Voice output.');
      try {
        this.recognition.abort();
      } catch (e) {}
      this.isListening = false;
      this.micBtn.classList.remove('active');
    }
  }

  onSystemVoiceEnd() {
    this.isSystemSpeaking = false;
    setTimeout(() => {
      if (this.state === 'speaking' && !this.isSystemSpeaking) {
        this.setVisualState('idle');
      }
    }, 450);
  }

  isSystemVoiceEcho(transcript) {
    if (!transcript) return false;
    const clean = transcript.toLowerCase().trim();
    if (!clean) return false;

    if (this.isSystemSpeaking || this.state === 'speaking') {
      return true;
    }

    const now = Date.now();
    if (this.recentSystemSpeech) {
      for (const item of this.recentSystemSpeech) {
        if (now - item.time > 15000) continue;
        const sys = item.text;
        if (clean === sys) return true;
        if (sys.includes(clean) && (clean.length > 3 || clean.split(' ').length > 1)) return true;
        if (clean.includes(sys) && sys.length > 4) return true;
      }
    }
    return false;
  }

  notifyReminder(reminder) {
    const text = `Reminder: ${reminder.title}!`;
    this.addChatMessage('mine', `⏰ ALERT: ${text}`);
    if (this.speechEnabled) {
      this.speakText(`Sir, reminder: ${reminder.title}`);
    }
    // Browser notification if permitted
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('M.I.N.E Reminder', { body: reminder.title });
    }
  }

  initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('[M.I.N.E] Web SpeechRecognition API not supported in this browser.');
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = false;
    this.recognition.lang = 'en-US';

    this.recognition.onstart = () => {
      this.isListening = true;
      this.setVisualState('listening');
      this.micBtn.classList.add('active');
    };

    this.recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      console.log('[M.I.N.E] Heard speech:', transcript);

      // Differentiate system voice reflection from microphone voice
      if (this.isSystemVoiceEcho(transcript)) {
        console.warn('[M.I.N.E] Differentiated system voice reflection in browser mic (suppressed):', transcript);
        this.stopListening();
        return;
      }

      this.cmdInput.value = transcript;
      this.sendMessage(transcript);
    };

    this.recognition.onerror = (event) => {
      console.warn('[M.I.N.E] STT error:', event.error);
      this.stopListening();
    };

    this.recognition.onend = () => {
      this.stopListening();
    };
  }

  toggleListening() {
    if (!this.recognition) {
      // Fallback: trigger backend microphone listening turn
      this.triggerServerMic();
      return;
    }

    if (this.isListening) {
      this.recognition.stop();
    } else {
      try {
        this.recognition.start();
      } catch (e) {
        console.warn('Recognition start failed:', e);
      }
    }
  }

  stopListening() {
    this.isListening = false;
    this.micBtn.classList.remove('active');
    if (this.state === 'listening') {
      this.setVisualState('idle');
    }
  }

  async triggerServerMic() {
    this.setVisualState('listening');
    try {
      const res = await fetch('/api/voice/listen', { method: 'POST' });
      const data = await res.json();
      if (data.result && data.result.text) {
        this.addChatMessage('mine', data.result.text, data.result.tool_called);
      }
      this.renderState(data.state);
    } catch (e) {
      console.error(e);
    } finally {
      this.setVisualState('idle');
    }
  }

  initSpeechSynthesis() {
    if (!('speechSynthesis' in window)) return;
    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      // Prefer British or natural English voice for JARVIS feel
      this.selectedVoice = voices.find(v => v.name.includes('Daniel') || v.name.includes('George') || v.name.includes('Natural') || (v.lang === 'en-GB')) || voices.find(v => v.lang.startsWith('en')) || voices[0];
    };
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  speakText(text) {
    if (!('speechSynthesis' in window) || !this.speechEnabled || !text) return;
    window.speechSynthesis.cancel();

    this.onSystemVoiceStart(text);

    const utterance = new SpeechSynthesisUtterance(text);
    if (this.selectedVoice) {
      utterance.voice = this.selectedVoice;
    }
    utterance.rate = 1.05;
    utterance.pitch = 0.95;

    utterance.onstart = () => {
      this.setVisualState('speaking');
    };

    utterance.onend = () => {
      this.onSystemVoiceEnd();
    };

    utterance.onerror = () => {
      this.onSystemVoiceEnd();
    };

    window.speechSynthesis.speak(utterance);
  }

  bindEvents() {
    // Arc Reactor Click
    this.arcReactor.addEventListener('click', () => this.toggleListening());

    // Mic button
    this.micBtn.addEventListener('click', () => this.toggleListening());

    // Send button & Enter key
    this.sendBtn.addEventListener('click', () => {
      const text = this.cmdInput.value.trim();
      if (text) {
        this.sendMessage(text);
        this.cmdInput.value = '';
      }
    });

    this.cmdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const text = this.cmdInput.value.trim();
        if (text) {
          this.sendMessage(text);
          this.cmdInput.value = '';
        }
      }
    });

    // Quick prompt chips
    document.querySelectorAll('.prompt-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.getAttribute('data-prompt');
        this.cmdInput.value = prompt;
        this.sendMessage(prompt);
      });
    });

    // Audio Toggle
    this.audioToggleBtn.addEventListener('click', () => {
      this.speechEnabled = !this.speechEnabled;
      this.audioToggleBtn.textContent = this.speechEnabled ? '🔊 AUDIO: ON' : '🔇 AUDIO: MUTED';
      this.audioToggleBtn.classList.toggle('active', this.speechEnabled);
      if (!this.speechEnabled && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    });

    // Settings Modal
    this.settingsBtn.addEventListener('click', () => {
      this.settingsModal.classList.add('active');
    });

    this.closeSettingsBtn.addEventListener('click', () => {
      this.settingsModal.classList.remove('active');
    });

    this.saveSettingsBtn.addEventListener('click', async () => {
      const provider = this.providerSelect ? this.providerSelect.value : 'ollama';
      const ollamaModel = this.ollamaModelInput ? this.ollamaModelInput.value.trim() : 'llama3.2';
      const ollamaUrl = this.ollamaUrlInput ? this.ollamaUrlInput.value.trim() : 'http://localhost:11434';
      const key = this.apiKeyInput ? this.apiKeyInput.value.trim() : '';

      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: provider,
          ollama_model: ollamaModel,
          ollama_url: ollamaUrl,
          gemini_api_key: key
        })
      });
      this.settingsModal.classList.remove('active');
      this.loadState();
    });

    // Hazard Modal actions
    this.btnAuthorize.addEventListener('click', async () => {
      await fetch('/api/action/confirm', { method: 'POST' });
      this.hideHazardModal();
      this.loadState();
    });

    this.btnAbort.addEventListener('click', async () => {
      await fetch('/api/action/cancel', { method: 'POST' });
      this.hideHazardModal();
      this.loadState();
    });

    // Notification permission request
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }

  async sendMessage(text) {
    this.addChatMessage('user', text);
    this.setVisualState('processing');

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, speak: false })
      });
      const data = await res.json();
      const reply = data.result.text;
      const tool = data.result.tool_called;

      this.addChatMessage('mine', reply, tool);

      // Check for confirmation required
      if (data.result.requires_confirmation && data.state.pending_confirmation) {
        this.showHazardModal(data.state.pending_confirmation);
      } else {
        this.hideHazardModal();
      }

      if (this.speechEnabled && reply) {
        this.speakText(reply);
      } else {
        this.setVisualState('idle');
      }

      this.renderState(data.state);
    } catch (e) {
      console.error(e);
      this.addChatMessage('mine', 'Connection error occurred while processing command.');
      this.setVisualState('idle');
    }
  }

  addChatMessage(sender, text, tool = null) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;

    let html = `<div>${this.escapeHtml(text)}</div>`;
    if (tool) {
      html += `<div class="tool-badge">⚙️ TOOL: ${this.escapeHtml(tool)}</div>`;
    }
    bubble.innerHTML = html;

    this.chatStream.appendChild(bubble);
    this.chatStream.scrollTop = this.chatStream.scrollHeight;
  }

  showHazardModal(pending) {
    this.hazardMessage.textContent = pending.prompt_message;
    this.hazardModal.classList.add('active');
  }

  hideHazardModal() {
    this.hazardModal.classList.remove('active');
  }

  async loadState() {
    try {
      const res = await fetch('/api/state');
      const data = await res.json();
      this.renderState(data);
    } catch (e) {
      console.warn('State load error:', e);
    }
  }

  renderState(state) {
    if (!state) return;

    // AI Status Indicator
    const aiIndicator = document.getElementById('aiIndicator');
    if (aiIndicator) {
      const label = state.active_label || 'LOCAL INTENT ENGINE';
      aiIndicator.textContent = label;
      if (label.includes('OLLAMA') && !label.includes('OFFLINE')) {
        aiIndicator.style.color = '#00f3ff';
      } else if (label.includes('GEMINI')) {
        aiIndicator.style.color = '#0088ff';
      } else if (label.includes('OFFLINE')) {
        aiIndicator.style.color = '#ffb700';
      } else {
        aiIndicator.style.color = '#00ffaa';
      }
    }

    // Sync input values when settings modal is opened
    if (state.llm_info && this.settingsModal && !this.settingsModal.classList.contains('active')) {
      if (this.providerSelect) this.providerSelect.value = state.llm_info.provider || 'ollama';
      if (this.ollamaModelInput && state.llm_info.ollama_model) this.ollamaModelInput.value = state.llm_info.ollama_model;
      if (this.ollamaUrlInput && state.llm_info.ollama_url) this.ollamaUrlInput.value = state.llm_info.ollama_url;
    }

    // Telemetry
    if (state.system_status) {
      const s = state.system_status;
      const cpu = s.cpu_usage_percent || 0;
      const ram = s.ram_usage_percent || 0;

      this.cpuVal.textContent = `${cpu}%`;
      this.cpuBar.style.width = `${cpu}%`;

      this.ramVal.textContent = `${ram}%`;
      this.ramBar.style.width = `${ram}%`;

      if (s.battery) {
        this.batteryVal.textContent = `${s.battery.percent}%`;
        this.batteryBar.style.width = `${s.battery.percent}%`;
      } else {
        this.batteryVal.textContent = 'PLUGGED IN';
        this.batteryBar.style.width = '100%';
      }
    }

    // Pending confirmation modal sync
    if (state.pending_confirmation) {
      this.showHazardModal(state.pending_confirmation);
    } else {
      this.hideHazardModal();
    }

    // Reminders
    this.renderReminders(state.reminders || []);

    // Calendar
    this.renderCalendar(state.calendar_events || []);

    // Memories
    this.renderMemories(state.memories || []);

    // Documents
    this.renderDocs(state.documents || []);
  }

  renderReminders(reminders) {
    if (!this.remindersList) return;
    this.remindersList.innerHTML = '';
    if (reminders.length === 0) {
      this.remindersList.innerHTML = '<div style="color:var(--text-dim);font-size:0.75rem;padding:6px;">No active reminders</div>';
      return;
    }
    reminders.forEach(r => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <div class="item-info">
          <span class="item-title">${this.escapeHtml(r.title)}</span>
          <span class="item-sub">⏰ ${this.escapeHtml(r.due_human || r.due_at || '')}</span>
        </div>
        <button class="item-delete-btn" title="Delete reminder" data-id="${r.id}">✕</button>
      `;
      card.querySelector('.item-delete-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/api/reminders/${r.id}`, { method: 'DELETE' });
        this.loadState();
      });
      this.remindersList.appendChild(card);
    });
  }

  renderCalendar(events) {
    if (!this.calendarList) return;
    this.calendarList.innerHTML = '';
    if (events.length === 0) {
      this.calendarList.innerHTML = '<div style="color:var(--text-dim);font-size:0.75rem;padding:6px;">No scheduled events</div>';
      return;
    }
    events.forEach(ev => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <div class="item-info">
          <span class="item-title">${this.escapeHtml(ev.title)}</span>
          <span class="item-sub">📅 ${this.escapeHtml(ev.date)} at ${this.escapeHtml(ev.time)}</span>
        </div>
        <button class="item-delete-btn" title="Cancel event" data-id="${ev.id}">✕</button>
      `;
      card.querySelector('.item-delete-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/api/calendar/${ev.id}`, { method: 'DELETE' });
        this.loadState();
      });
      this.calendarList.appendChild(card);
    });
  }

  renderMemories(memories) {
    if (!this.memoryList) return;
    this.memoryList.innerHTML = '';
    if (memories.length === 0) {
      this.memoryList.innerHTML = '<div style="color:var(--text-dim);font-size:0.75rem;padding:6px;">Memory is empty</div>';
      return;
    }
    memories.forEach(m => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <div class="item-info">
          <span class="item-title">${this.escapeHtml(m.topic)}: ${this.escapeHtml(m.value)}</span>
          <span class="item-sub">🧠 ${this.escapeHtml(m.category)}</span>
        </div>
        <button class="item-delete-btn" title="Forget" data-key="${m.key}">✕</button>
      `;
      card.querySelector('.item-delete-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/api/memory/${m.key}`, { method: 'DELETE' });
        this.loadState();
      });
      this.memoryList.appendChild(card);
    });
  }

  renderDocs(docs) {
    if (!this.docsList) return;
    this.docsList.innerHTML = '';
    if (docs.length === 0) {
      this.docsList.innerHTML = '<div style="color:var(--text-dim);font-size:0.75rem;padding:6px;">No documents in library</div>';
      return;
    }
    docs.forEach(d => {
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <div class="item-info">
          <span class="item-title">📄 ${this.escapeHtml(d.name)}</span>
          <span class="item-sub">${d.size_bytes ? d.size_bytes + ' bytes' : 'File'}</span>
        </div>
      `;
      card.addEventListener('click', async () => {
        const res = await fetch(`/api/documents/${d.name}`);
        const data = await res.json();
        if (data.content) {
          alert(`Document Content (${d.name}):\n\n${data.content.slice(0, 500)}`);
        }
      });
      this.docsList.appendChild(card);
    });
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.mineApp = new MineHUDApp();
  window.jarvisApp = window.mineApp;
});