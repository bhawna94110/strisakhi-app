import { useState, useEffect, useRef } from "react";

const BASE_URL = "http://localhost:8000";
const LLAMA_URL = "http://localhost:8080";
const MAX_SESSIONS = 3;

const SAKHIS = {
  legal: {
    id: "legal", name: "Kanoon Sakhi", nameHi: "कानून सखी",
    tagline: "Your fearless legal companion", taglineHi: "डरो मत, मैं हूँ",
    quote: "Every woman deserves to know her rights. Justice is not a privilege — it's yours.",
    quoteHi: "हर महिला को अपने अधिकार जानने का हक है। न्याय कोई विशेषाधिकार नहीं — यह आपका है।",
    icon: "⚖️", color: "#1a4a6b", accent: "#2196F3",
    gradient: "linear-gradient(135deg, #1a4a6b 0%, #1565C0 60%, #0D47A1 100%)",
    usecases: [
      { icon: "🏠", en: "Eviction from home", hi: "घर से निकाला" },
      { icon: "🏛️", en: "Property rights", hi: "ज़मीन का हक़" },
      { icon: "💼", en: "Workplace harassment", hi: "काम की जगह समस्या" },
      { icon: "👊", en: "Domestic violence", hi: "घरेलू हिंसा" },
    ],
  },
  health: {
    id: "health", name: "Sehat Sakhi", nameHi: "सेहत सखी",
    tagline: "Your trusted health guardian", taglineHi: "आपकी सेहत, मेरी ज़िम्मेदारी",
    quote: "Your health is not a burden to be silenced. You deserve care, answers, and dignity.",
    quoteHi: "आपकी सेहत को चुप नहीं कराया जाना चाहिए। आप देखभाल और सम्मान की हकदार हैं।",
    icon: "🌿", color: "#1b5e20", accent: "#4CAF50",
    gradient: "linear-gradient(135deg, #1b5e20 0%, #2E7D32 60%, #388E3C 100%)",
    usecases: [
      { icon: "🤱", en: "Pregnancy care", hi: "गर्भावस्था" },
      { icon: "👶", en: "Child illness", hi: "बच्चे की बीमारी" },
      { icon: "🧠", en: "Mental health", hi: "मन की बात" },
      { icon: "💊", en: "Medicine guidance", hi: "दवाई की जानकारी" },
    ],
  },
  scheme: {
    id: "scheme", name: "Yojana Sakhi", nameHi: "योजना सखी",
    tagline: "Your guide to government benefits", taglineHi: "सरकारी मदद, आपका हक़",
    quote: "Thousands of schemes exist for women like you. You just need someone to show you the door.",
    quoteHi: "आप जैसी महिलाओं के लिए हज़ारों योजनाएं हैं। बस किसी को दरवाज़ा दिखाने की ज़रूरत है।",
    icon: "📜", color: "#7f4f00", accent: "#FF8F00",
    gradient: "linear-gradient(135deg, #7f4f00 0%, #E65100 60%, #BF360C 100%)",
    usecases: [
      { icon: "🏥", en: "Free healthcare", hi: "मुफ्त स्वास्थ्य योजनाएं" },
      { icon: "🏡", en: "Housing schemes", hi: "आवास योजना" },
      { icon: "💰", en: "Financial help", hi: "आर्थिक सहायता" },
      { icon: "📚", en: "Education schemes", hi: "शिक्षा योजना" },
    ],
  },
};

const HELPLINES = [
  { num: "181", lbl: "Women Helpline" },
  { num: "100", lbl: "Police" },
  { num: "108", lbl: "Ambulance" },
  { num: "15100", lbl: "Legal Aid (Free)" },
];

// ─── SESSION STORAGE ──────────────────────────────────────────────────────────
function getSessions() {
  try { return JSON.parse(localStorage.getItem("strisakhi_sessions") || "[]"); }
  catch { return []; }
}
function saveSessions(s) {
  localStorage.setItem("strisakhi_sessions", JSON.stringify(s.slice(-MAX_SESSIONS)));
}
function addSessionHistory(sakhiId, sessionId, preview) {
  const all = getSessions();
  const idx = all.findIndex(s => s.id === sessionId);
  if (idx >= 0) { all[idx].preview = preview.slice(0, 60); all[idx].timestamp = Date.now(); }
  else all.push({ id: sessionId, sakhiId, preview: preview.slice(0, 60), timestamp: Date.now() });
  saveSessions(all);
}
function removeSession(id) { saveSessions(getSessions().filter(s => s.id !== id)); }

// ─── API ──────────────────────────────────────────────────────────────────────
async function createSession(tab) {
  try {
    const r = await fetch(`${BASE_URL}/api/session/new`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tab_type: tab })
    });
    return (await r.json()).session_id;
  } catch { return null; }
}
async function deleteSessionAPI(id) {
  try { await fetch(`${BASE_URL}/api/session/${id}`, { method: "DELETE" }); } catch {}
}
async function loadSessionHistory(sessionId) {
  try {
    const r = await fetch(`${BASE_URL}/api/session/${sessionId}`);
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

// FIXED: correct endpoint mapping
async function streamChat(sakhiId, sessionId, message, lang, onToken, onDone, onMeta, signal) {
  const epMap = { legal: "legal", health: "medical", scheme: "scheme" };
  const ep = epMap[sakhiId] || "legal";
  try {
    const res = await fetch(`${BASE_URL}/api/${ep}/chat`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, input_type: "text", language: lang }),
      signal,
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (signal?.aborted) { reader.cancel(); break; }
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n"); buf = lines.pop() || "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.type === "token") { onToken(ev.token); await new Promise(r => setTimeout(r, 0)); }
          else if (ev.type === "done") onDone({ full_response: ev.full_response, citations: ev.citations || [], agent: ev.agent, follow_up_questions: ev.follow_up_questions || [] });
          else if (ev.type === "emergency") onMeta({ type: "emergency", data: ev.data });
          else onMeta(ev);
        } catch {}
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return;
    onMeta({ type: "error", message: err.message });
    onDone({ full_response: "Connection error. Please try again.", citations: [], agent: "error", follow_up_questions: [] });
  }
}

// ─── AUDIO ────────────────────────────────────────────────────────────────────
async function blobToWav(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  if (audioCtx.state === "suspended") await audioCtx.resume();
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
  await audioCtx.close();
  const channelData = audioBuffer.getChannelData(0);
  const numSamples = channelData.length;
  const wavBuffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(wavBuffer);
  const ws = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  ws(0, "RIFF"); view.setUint32(4, 36 + numSamples * 2, true);
  ws(8, "WAVE"); ws(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  ws(36, "data"); view.setUint32(40, numSamples * 2, true);
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, channelData[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    offset += 2;
  }
  return new Blob([wavBuffer], { type: "audio/wav" });
}

async function transcribeAudio(blob) {
  try {
    const wavBlob = await blobToWav(blob);
    const arrayBuffer = await wavBlob.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i += 8192)
      binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    const base64 = btoa(binary);
    const r = await fetch(`${LLAMA_URL}/v1/chat/completions`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "gemma4",
        messages: [{ role: "user", content: [
          { type: "input_audio", input_audio: { data: base64, format: "wav" } },
          { type: "text", text: "Transcribe exactly what this person is saying. Output only the transcription, nothing else." }
        ]}],
        stream: false, max_tokens: 300
      }),
      signal: AbortSignal.timeout(30000)
    });
    const data = await r.json();
    return data?.choices?.[0]?.message?.content?.trim() || "";
  } catch (e) { return ""; }
}

// ─── LIFELIKE SAKHI CHARACTER ─────────────────────────────────────────────────
function SakhiCharacter({ state = "idle", type = "legal", size = 110 }) {
  const colors = {
    legal:  { primary: "#1565C0", secondary: "#2196F3", accent: "#FFD700", aura: "rgba(33,150,243,0.18)" },
    health: { primary: "#2E7D32", secondary: "#4CAF50", accent: "#FF8A65", aura: "rgba(76,175,80,0.18)" },
    scheme: { primary: "#E65100", secondary: "#FF8F00", accent: "#FFD54F", aura: "rgba(255,143,0,0.18)" },
  };
  const c = colors[type] || colors.legal;

  return (
    <svg width={size} height={size * 1.3} viewBox="0 0 120 156" style={{ overflow: "visible" }}>
      <defs>
        <radialGradient id={`aura_${type}`} cx="50%" cy="60%" r="50%">
          <stop offset="0%" stopColor={c.aura} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <radialGradient id="skin" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#D4956A" />
          <stop offset="100%" stopColor="#B5723A" />
        </radialGradient>
        <filter id="softglow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* Ambient aura */}
      <ellipse cx="60" cy="95" rx="52" ry="50" fill={`url(#aura_${type})`}
        style={{ animation: "auraPulse 3s ease-in-out infinite" }} />

      {/* Shadow under feet */}
      <ellipse cx="60" cy="152" rx="22" ry="4" fill="rgba(0,0,0,0.08)"
        style={{ animation: "shadowBreath 3s ease-in-out infinite" }} />

      {/* Body group — floats up/down */}
      <g style={{ animation: `bodyFloat_${state} 3s ease-in-out infinite`, transformOrigin: "60px 156px" }}>

        {/* HAIR — back layer */}
        <path d="M28,52 Q26,20 60,16 Q94,20 92,52 Q95,68 88,76 L32,76 Q25,68 28,52"
          fill="#1a1a1a" />

        {/* BUN */}
        <circle cx="87" cy="32" r="12" fill="#1a1a1a" />
        {type === "scheme" && <>
          <circle cx="94" cy="27" r="4" fill="white" opacity="0.9" />
          <circle cx="98" cy="32" r="3.5" fill="white" opacity="0.85" />
          <circle cx="93" cy="36" r="3" fill="white" opacity="0.8" />
          <circle cx="87" cy="24" r="3" fill="white" opacity="0.75" />
        </>}

        {/* CLOTHES */}
        {type === "legal" && (
          <g>
            {/* Advocate coat */}
            <path d="M32,156 L24,98 Q22,78 42,68 L78,68 Q98,78 96,98 L88,156 Z" fill="#0d1b2a" />
            {/* White bands */}
            <path d="M42,68 Q60,82 78,68 L74,76 Q60,90 46,76 Z" fill="white" />
            <line x1="44" y1="68" x2="40" y2="140" stroke="#1a4a6b" strokeWidth="1.5" opacity="0.5" />
            <line x1="76" y1="68" x2="80" y2="140" stroke="#1a4a6b" strokeWidth="1.5" opacity="0.5" />
            {/* Scales of justice — right hand */}
            <g style={{ animation: "scalesSway 2s ease-in-out infinite", transformOrigin: "97px 108px" }}>
              <line x1="97" y1="90" x2="97" y2="108" stroke={c.accent} strokeWidth="2" />
              <line x1="84" y1="98" x2="110" y2="98" stroke={c.accent} strokeWidth="1.8" />
              <line x1="84" y1="98" x2="81" y2="110" stroke={c.accent} strokeWidth="1.5" />
              <line x1="110" y1="98" x2="113" y2="110" stroke={c.accent} strokeWidth="1.5" />
              <ellipse cx="81" cy="112" rx="5" ry="3" fill={c.accent} opacity="0.9" />
              <ellipse cx="113" cy="112" rx="5" ry="3" fill={c.accent} opacity="0.9" />
            </g>
          </g>
        )}
        {type === "health" && (
          <g>
            {/* White doctor coat */}
            <path d="M32,156 L24,98 Q22,78 42,68 L78,68 Q98,78 96,98 L88,156 Z" fill="white" />
            <path d="M34,156 L30,110 Q44,122 60,118 Q76,122 90,110 L86,156 Z" fill="#1b5e20" opacity="0.85" />
            {/* Stethoscope */}
            <path d="M36,70 Q26,90 40,102 Q54,114 76,102 Q90,90 84,70"
              stroke="#b0b0b0" strokeWidth="2.5" fill="none"
              style={{ animation: "stethSway 3s ease-in-out infinite", transformOrigin: "60px 80px" }} />
            <circle cx="60" cy="114" r="5" fill="#909090" />
            {/* Medical cross */}
            <rect x="53" y="82" width="14" height="18" rx="2" fill="#ef4444" />
            <rect x="56" y="84" width="8" height="14" fill="white" />
            <rect x="53" y="88" width="14" height="6" fill="white" />
          </g>
        )}
        {type === "scheme" && (
          <g>
            {/* Saree */}
            <path d="M32,156 L24,98 Q22,78 42,68 L78,68 Q98,78 96,98 L88,156 Z" fill={c.primary} />
            <path d="M42,68 L36,118 Q52,132 68,118 L62,68 Z" fill={c.secondary} opacity="0.9" />
            <path d="M22,100 Q60,116 98,100" stroke="white" strokeWidth="1.5" fill="none" opacity="0.5" />
            {/* Document */}
            <g style={{ animation: "docBob 2.5s ease-in-out infinite", transformOrigin: "96px 108px" }}>
              <rect x="88" y="94" width="16" height="22" rx="2" fill="white" stroke="#ddd" strokeWidth="0.8" />
              <line x1="91" y1="100" x2="101" y2="100" stroke="#999" strokeWidth="1" />
              <line x1="91" y1="104" x2="101" y2="104" stroke="#999" strokeWidth="1" />
              <line x1="91" y1="108" x2="98" y2="108" stroke="#999" strokeWidth="1" />
              <circle cx="96" cy="114" r="3" fill="#4CAF50" />
            </g>
          </g>
        )}

        {/* EARRINGS */}
        <circle cx="27" cy="54" r="3.5" fill={c.accent} filter="url(#softglow)" />
        <line x1="27" y1="57" x2="27" y2="64" stroke={c.accent} strokeWidth="1.5" />
        <circle cx="27" cy="65" r="2.5" fill={c.accent} />
        <circle cx="93" cy="54" r="3.5" fill={c.accent} filter="url(#softglow)" />
        <line x1="93" y1="57" x2="93" y2="64" stroke={c.accent} strokeWidth="1.5" />
        <circle cx="93" cy="65" r="2.5" fill={c.accent} />

        {/* NECK */}
        <rect x="52" y="64" width="16" height="10" rx="3" fill="url(#skin)" />

        {/* HEAD */}
        <ellipse cx="60" cy="46" rx="28" ry="30" fill="url(#skin)" />

        {/* BINDI */}
        <circle cx="60" cy="30" r="2.5" fill="#dc2626" filter="url(#softglow)" />
        <circle cx="60" cy="30" r="1" fill="#ff6b6b" />

        {/* EYEBROWS */}
        <path d="M44,38 Q51,35 56,38" stroke="#2d1a0e" strokeWidth="2" fill="none" strokeLinecap="round"
          style={{ animation: state === "thinking" ? "browThink 2s ease-in-out infinite" : "none", transformOrigin: "50px 38px" }} />
        <path d="M64,38 Q69,35 76,38" stroke="#2d1a0e" strokeWidth="2" fill="none" strokeLinecap="round"
          style={{ animation: state === "thinking" ? "browThink 2s ease-in-out infinite" : "none", transformOrigin: "70px 38px" }} />

        {/* EYES */}
        <g style={{ animation: "blink 5s ease-in-out infinite" }}>
          <ellipse cx="50" cy="46" rx="6" ry="7"
            fill="#1a1a1a"
            style={{ transform: state === "thinking" ? "translateY(-2px)" : state === "listening" ? "scaleY(1.15)" : "none" }} />
          <ellipse cx="70" cy="46" rx="6" ry="7"
            fill="#1a1a1a"
            style={{ transform: state === "thinking" ? "translateY(-2px)" : state === "listening" ? "scaleY(1.15)" : "none" }} />
          {/* Iris highlights */}
          <circle cx="52" cy="44" r="2" fill="white" opacity="0.9" />
          <circle cx="72" cy="44" r="2" fill="white" opacity="0.9" />
          {/* Tiny sparkle */}
          <circle cx="53" cy="43" r="0.8" fill="white" opacity="0.7" />
          <circle cx="73" cy="43" r="0.8" fill="white" opacity="0.7" />
        </g>

        {/* NOSE */}
        <path d="M58,52 Q60,55 62,52" stroke="#a0522d" strokeWidth="1.2" fill="none" strokeLinecap="round" />

        {/* MOUTH — animated by state */}
        {state === "idle" && (
          <path d="M53,62 Q60,68 67,62" stroke="#8B4513" strokeWidth="2.2" fill="none" strokeLinecap="round" />
        )}
        {state === "listening" && (
          <path d="M54,63 Q60,67 66,63" stroke="#8B4513" strokeWidth="2" fill="none" strokeLinecap="round" />
        )}
        {state === "speaking" && (
          <g style={{ animation: "lipSync 0.35s ease-in-out infinite" }}>
            <ellipse cx="60" cy="64" rx="6" ry="4" fill="#8B4513" />
            <ellipse cx="60" cy="63" rx="4.5" ry="2.5" fill="#c0654a" />
          </g>
        )}
        {state === "thinking" && (
          <path d="M55,63 Q60,65 65,63" stroke="#8B4513" strokeWidth="2" fill="none" strokeLinecap="round" />
        )}

        {/* BLUSH */}
        <ellipse cx="40" cy="54" rx="7" ry="4" fill="#ff8a80" opacity="0.25"
          style={{ opacity: state === "speaking" ? 0.4 : 0.2, transition: "opacity 0.3s" }} />
        <ellipse cx="80" cy="54" rx="7" ry="4" fill="#ff8a80" opacity="0.25"
          style={{ opacity: state === "speaking" ? 0.4 : 0.2, transition: "opacity 0.3s" }} />

        {/* THINKING DOTS */}
        {state === "thinking" && (
          <g>
            <circle cx="78" cy="28" r="3" fill={c.secondary} style={{ animation: "thinkDot 1s ease-in-out infinite" }} />
            <circle cx="86" cy="22" r="2.5" fill={c.secondary} style={{ animation: "thinkDot 1s ease-in-out infinite 0.2s" }} />
            <circle cx="92" cy="15" r="2" fill={c.secondary} style={{ animation: "thinkDot 1s ease-in-out infinite 0.4s" }} />
          </g>
        )}

        {/* LISTENING SOUND WAVES */}
        {state === "listening" && (
          <g>
            <path d="M10,42 Q6,46 10,50" stroke={c.secondary} strokeWidth="2" fill="none" strokeLinecap="round"
              style={{ animation: "wavePulse 0.8s ease-in-out infinite" }} />
            <path d="M6,38 Q0,46 6,54" stroke={c.secondary} strokeWidth="1.5" fill="none" strokeLinecap="round"
              style={{ animation: "wavePulse 0.8s ease-in-out infinite 0.15s" }} />
            <path d="M2,34 Q-6,46 2,58" stroke={c.secondary} strokeWidth="1" fill="none" strokeLinecap="round"
              style={{ animation: "wavePulse 0.8s ease-in-out infinite 0.3s" }} />
          </g>
        )}

        {/* SPEAKING SOUND WAVES */}
        {state === "speaking" && (
          <g>
            <path d="M110,42 Q114,46 110,50" stroke={c.accent} strokeWidth="2" fill="none" strokeLinecap="round"
              style={{ animation: "wavePulse 0.5s ease-in-out infinite" }} />
            <path d="M114,38 Q120,46 114,54" stroke={c.accent} strokeWidth="1.5" fill="none" strokeLinecap="round"
              style={{ animation: "wavePulse 0.5s ease-in-out infinite 0.1s" }} />
            <path d="M118,34 Q126,46 118,58" stroke={c.accent} strokeWidth="1" fill="none" strokeLinecap="round"
              style={{ animation: "wavePulse 0.5s ease-in-out infinite 0.2s" }} />
          </g>
        )}
      </g>

      <style>{`
        @keyframes auraPulse {
          0%,100% { opacity:0.7; transform:scale(1); }
          50% { opacity:1; transform:scale(1.06); }
        }
        @keyframes shadowBreath {
          0%,100% { transform:scaleX(1); opacity:0.08; }
          50% { transform:scaleX(0.85); opacity:0.04; }
        }
        @keyframes bodyFloat_idle {
          0%,100% { transform:translateY(0px) rotate(-0.5deg); }
          50% { transform:translateY(-5px) rotate(0.5deg); }
        }
        @keyframes bodyFloat_listening {
          0%,100% { transform:translateY(0px) rotate(-1.5deg) scale(1); }
          50% { transform:translateY(-6px) rotate(1.5deg) scale(1.01); }
        }
        @keyframes bodyFloat_speaking {
          0%,100% { transform:translateY(0px) scale(1) rotate(0); }
          25% { transform:translateY(-3px) scale(1.015) rotate(-0.8deg); }
          75% { transform:translateY(-2px) scale(1.01) rotate(0.8deg); }
        }
        @keyframes bodyFloat_thinking {
          0%,100% { transform:translateY(0) rotate(-0.5deg); }
          30% { transform:translateY(-3px) translateX(1px) rotate(1deg); }
          60% { transform:translateY(-5px) rotate(-0.5deg); }
        }
        @keyframes blink {
          0%,94%,100% { transform:scaleY(1); }
          97% { transform:scaleY(0.08); }
        }
        @keyframes lipSync {
          0%,100% { transform:scaleY(0.7) scaleX(0.9); }
          50% { transform:scaleY(1.1) scaleX(1.05); }
        }
        @keyframes thinkDot {
          0%,100% { opacity:0.3; transform:scale(0.8); }
          50% { opacity:1; transform:scale(1.2); }
        }
        @keyframes wavePulse {
          0%,100% { opacity:0.3; transform:scaleX(0.8); }
          50% { opacity:1; transform:scaleX(1); }
        }
        @keyframes scalesSway {
          0%,100% { transform:rotate(-5deg); }
          50% { transform:rotate(5deg); }
        }
        @keyframes stethSway {
          0%,100% { transform:rotate(-2deg); }
          50% { transform:rotate(2deg); }
        }
        @keyframes docBob {
          0%,100% { transform:translateY(0) rotate(0deg); }
          50% { transform:translateY(-3px) rotate(2deg); }
        }
        @keyframes browThink {
          0%,100% { transform:translateY(0); }
          50% { transform:translateY(-2px); }
        }
      `}</style>
    </svg>
  );
}

// ─── CSS ──────────────────────────────────────────────────────────────────────
const css = `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,700&family=DM+Sans:wght@300;400;500;600&family=Noto+Sans+Devanagari:wght@400;500;600&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f5f3ef;--bg2:#ede9e3;--wh:#fff;
  --ink:#1a1a1a;--ink2:#444;--ink3:#888;--border:#ddd8d0;
  --fd:'Playfair Display',serif;--fb:'DM Sans','Noto Sans Devanagari',sans-serif;
  --r:16px;--rsm:10px;--sh:0 4px 24px rgba(0,0,0,.08);--shl:0 12px 48px rgba(0,0,0,.14);
}
html,body,#root{height:100%;font-family:var(--fb);background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
.app{display:flex;flex-direction:column;height:100%;overflow:hidden}
.page{flex:1;overflow-y:auto;overflow-x:hidden}
.page::-webkit-scrollbar{width:6px}
.page::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.hdr{background:var(--wh);border-bottom:1px solid var(--border);padding:13px 18px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;position:sticky;top:0;z-index:100}
.brand{display:flex;align-items:center;gap:10px}
.brand-logo{width:38px;height:38px;background:linear-gradient(135deg,#1a4a6b,#E65100);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:17px}
.brand-name{font-family:var(--fd);font-size:20px;font-weight:700;letter-spacing:-.5px}
.brand-name span{color:#E65100}
.brand-sub{font-size:10px;color:var(--ink3);margin-top:1px;letter-spacing:.4px}
.hdr-right{display:flex;align-items:center;gap:8px}
.sos-wrap{position:relative}
.sos-pill{display:flex;align-items:center;gap:5px;background:#fee2e2;border:1px solid #fca5a5;border-radius:99px;padding:6px 11px;cursor:pointer;user-select:none}
.sos-pill span{font-size:11px;font-weight:700;color:#dc2626;letter-spacing:.5px}
.sos-drop{position:absolute;top:calc(100% + 6px);right:0;background:var(--wh);border:1px solid var(--border);border-radius:var(--rsm);box-shadow:var(--shl);min-width:190px;overflow:hidden;z-index:300}
.sos-it{display:flex;align-items:center;gap:10px;padding:10px 13px;transition:background .15s}
.sos-it:hover{background:var(--bg)}
.sos-num{font-size:14px;font-weight:800;color:#dc2626}
.sos-lbl{font-size:12px;color:var(--ink2)}
.lang-pill{display:flex;background:var(--bg);border:1px solid var(--border);border-radius:99px;padding:3px;gap:2px}
.l-btn{padding:5px 12px;border-radius:99px;font-size:11px;font-weight:600;border:none;cursor:pointer;background:transparent;color:var(--ink3);font-family:var(--fb);transition:all .2s}
.l-btn.on{background:var(--ink);color:var(--wh)}
.home{padding:26px 18px 100px;max-width:660px;margin:0 auto}
.hero{margin-bottom:32px;text-align:center}
.hero-eye{font-size:10px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--ink3);margin-bottom:9px}
.hero-title{font-family:var(--fd);font-size:clamp(24px,5vw,34px);font-weight:800;line-height:1.15;margin-bottom:9px}
.hero-title em{font-style:italic;color:#E65100}
.hero-sub{font-size:13px;color:var(--ink2);line-height:1.65;max-width:380px;margin:0 auto}
.sakhi-grid{display:flex;flex-direction:column;gap:13px;margin-bottom:26px}
.s-card{border-radius:var(--r);overflow:hidden;cursor:pointer;transition:transform .2s,box-shadow .2s;position:relative;box-shadow:var(--sh);min-height:170px}
.s-card:hover{transform:translateY(-2px);box-shadow:var(--shl)}
.s-card:active{transform:scale(.99)}
.c-body{padding:20px 18px 16px;color:white;position:relative;z-index:1;height:100%;display:flex;flex-direction:column}
.c-blob{position:absolute;border-radius:50%;background:rgba(255,255,255,.07);pointer-events:none}
.cb1{width:160px;height:160px;right:-42px;top:-42px}
.cb2{width:85px;height:85px;right:70px;bottom:-25px}
.c-top{display:flex;align-items:flex-start;gap:13px;margin-bottom:11px}
.c-ico{width:58px;height:58px;background:rgba(255,255,255,.2);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:26px;flex-shrink:0;border:1.5px solid rgba(255,255,255,.25)}
.c-name{font-family:var(--fd);font-size:20px;font-weight:700;line-height:1.15}
.c-tag{font-size:12px;opacity:.9;margin-top:3px}
.c-quote{font-size:12px;opacity:.75;line-height:1.7;font-style:italic;margin-bottom:11px;border-left:2px solid rgba(255,255,255,.35);padding-left:9px}
.c-chips{display:flex;gap:5px;flex-wrap:wrap;margin-top:auto}
.c-chip{display:flex;align-items:center;gap:4px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.2);border-radius:99px;padding:5px 11px;font-size:12px;font-weight:500}
.c-cta{margin-top:11px;display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.11);border-radius:10px;padding:10px 14px;border:1px solid rgba(255,255,255,.18);font-size:13px;font-weight:600}
.hist{margin-top:4px}
.sec-lbl{font-size:10px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--ink3);margin-bottom:9px}
.sess-list{display:flex;flex-direction:column;gap:7px}
.sess-item{display:flex;align-items:center;gap:10px;background:var(--wh);border:1px solid var(--border);border-radius:var(--rsm);padding:13px 14px;cursor:pointer;transition:all .2s}
.sess-item:hover{border-color:#aaa}
.sess-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sess-info{flex:1;min-width:0}
.sess-prev{font-size:13px;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sess-meta{font-size:11px;color:var(--ink3);margin-top:2px}
.sess-del{width:26px;height:26px;border-radius:50%;border:none;background:transparent;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:13px;color:var(--ink3);transition:all .2s;font-family:var(--fb)}
.sess-del:hover{background:#fee2e2;color:#dc2626}
.chat-pg{display:flex;flex-direction:column;height:100%;overflow:hidden;position:relative}
.chat-hdr{padding:12px 16px;display:flex;align-items:center;gap:11px;border-bottom:1px solid var(--border);background:var(--wh);flex-shrink:0;position:relative;z-index:10}
.back{width:34px;height:34px;border-radius:50%;border:1px solid var(--border);background:var(--wh);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:15px;color:var(--ink2);font-family:var(--fb);transition:all .2s}
.back:hover{background:var(--bg)}
.ch-ico{width:37px;height:37px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.ch-name{font-family:var(--fd);font-size:16px;font-weight:700}
.ch-st{font-size:11px;color:var(--ink3);margin-top:1px}
.new-btn{font-size:11px;font-weight:600;color:var(--ink2);background:var(--bg);border:1px solid var(--border);border-radius:99px;padding:5px 11px;cursor:pointer;font-family:var(--fb);transition:all .2s;margin-left:auto;flex-shrink:0}
.new-btn:hover{background:var(--bg2)}
.as-toggle{font-size:11px;font-weight:600;color:var(--ink2);background:var(--bg);border:1px solid var(--border);border-radius:99px;padding:5px 10px;cursor:pointer;font-family:var(--fb);transition:all .2s;flex-shrink:0}
.as-toggle.on{background:var(--ink);color:white;border-color:var(--ink)}
.pbar{padding:6px 16px;display:flex;align-items:center;gap:7px;background:var(--bg);border-bottom:1px solid var(--border);flex-shrink:0;position:relative;z-index:10}
.p-lbl{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--ink3)}
.p-dots{display:flex;gap:4px}
.p-dot{height:4px;border-radius:2px;background:var(--border);transition:all .3s}
.p-dot.done{background:#4CAF50}
.p-dot.active{background:var(--ink);width:18px!important}
.p-info{margin-left:auto;font-size:9px;color:var(--ink3);font-weight:600}
.msgs{flex:1;overflow-y:auto;padding:16px 16px 8px;display:flex;flex-direction:column;gap:12px;position:relative;z-index:1}
.msgs::-webkit-scrollbar{width:0}
.msg{display:flex;gap:8px;animation:mIn .25s ease}
@keyframes mIn{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
.msg.usr{flex-direction:row-reverse}
.mav{width:30px;height:30px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700}
.mbub{max-width:82%;border-radius:15px;padding:10px 13px;font-size:14px;line-height:1.65}
.mbub.ai{background:var(--wh);color:var(--ink);border:1px solid var(--border);border-bottom-left-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.05)}
.mbub.usr{background:var(--ink);color:white;border-bottom-right-radius:4px}
.mtext{white-space:pre-wrap;word-break:break-word}
.mtext strong{font-weight:600}
.mbadge{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px;opacity:.55}
.ctags{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
.ctag{font-size:10px;padding:3px 7px;border-radius:99px;border:1px solid var(--border);background:var(--bg);color:var(--ink2)}
.listen-btn{display:inline-flex;align-items:center;gap:4px;background:var(--bg);border:1px solid var(--border);border-radius:99px;padding:4px 10px;font-size:11px;font-weight:600;color:var(--ink2);cursor:pointer;font-family:var(--fb);transition:all .2s;margin-top:7px}
.listen-btn:hover{background:var(--ink);color:white;border-color:var(--ink)}
.listen-btn:disabled{opacity:.4;cursor:not-allowed}
.listen-btn.playing{background:var(--ink);color:white}
.audio-msg{display:flex;flex-direction:column;gap:4px}
.audio-wrap audio{display:block;width:180px;height:30px;opacity:.85}
.audio-sub{font-size:11px;opacity:.7;font-style:italic;margin-top:2px;line-height:1.4}
.lang-picker{flex:1;overflow-y:auto;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 20px;gap:20px}
.lp-title{font-family:var(--fd);font-size:20px;font-weight:700;text-align:center}
.lp-sub{font-size:13px;color:var(--ink2);text-align:center;line-height:1.6;max-width:300px}
.lp-options{display:flex;flex-direction:column;gap:10px;width:100%;max-width:320px}
.lp-btn{display:flex;align-items:center;gap:14px;background:var(--wh);border:1.5px solid var(--border);border-radius:14px;padding:14px 18px;cursor:pointer;font-family:var(--fb);transition:all .2s;text-align:left;width:100%}
.lp-btn:hover{border-color:var(--ink2);background:var(--bg)}
.lp-btn:active{transform:scale(.98)}
.lp-ico{font-size:24px;flex-shrink:0}
.lp-name{font-size:15px;font-weight:700;display:block}
.lp-desc{font-size:11px;color:var(--ink3);display:block;margin-top:2px}
.lp-soon{opacity:.4;cursor:not-allowed}
.lp-soon:hover{border-color:var(--border);background:var(--wh)}
.lp-badge{font-size:9px;font-weight:700;background:var(--bg2);color:var(--ink3);border-radius:99px;padding:2px 7px;margin-left:auto;flex-shrink:0}
.lang-tag{font-size:10px;font-weight:700;background:var(--bg2);border:1px solid var(--border);border-radius:99px;padding:3px 9px;color:var(--ink2)}
.typ-wrap{display:flex;align-items:center;gap:8px}
.typ-dots{display:flex;gap:4px}
.typ-dot{width:6px;height:6px;border-radius:50%;background:var(--ink3);opacity:.5;animation:tB 1.2s ease infinite}
.typ-dot:nth-child(2){animation-delay:.2s}.typ-dot:nth-child(3){animation-delay:.4s}
@keyframes tB{0%,100%{transform:translateY(0);opacity:.4}50%{transform:translateY(-4px);opacity:1}}
.typ-lbl{font-size:12px;color:var(--ink3);font-style:italic}
.thinking-wrap{display:flex;flex-direction:column;gap:6px}
.thinking-bar{display:flex;align-items:center;gap:8px}
.thinking-ico{font-size:14px;animation:tSpin 2s linear infinite}
@keyframes tSpin{0%{opacity:1}50%{opacity:.3}100%{opacity:1}}
.thinking-lbl{font-size:12px;font-weight:600;color:var(--ink2)}
.thinking-sub{font-size:11px;color:var(--ink3);font-style:italic}
.thinking-progress{height:3px;background:var(--border);border-radius:2px;overflow:hidden;margin-top:2px}
.thinking-fill{height:100%;border-radius:2px;background:linear-gradient(90deg,#1a4a6b,#2196F3);animation:tFill 15s linear forwards}
@keyframes tFill{from{width:0%}to{width:100%}}
.wait-note{font-size:10px;color:var(--ink3);margin-top:4px;font-style:italic}
.qpicks{padding:6px 16px 3px;display:flex;gap:6px;overflow-x:auto;flex-shrink:0;position:relative;z-index:10}
.qpicks::-webkit-scrollbar{display:none}
.qchip{display:flex;align-items:center;gap:4px;background:var(--wh);border:1px solid var(--border);border-radius:99px;padding:6px 11px;font-size:11px;font-weight:500;white-space:nowrap;cursor:pointer;flex-shrink:0;color:var(--ink2);font-family:var(--fb);transition:all .2s}
.qchip:hover{border-color:var(--ink3);color:var(--ink)}
.followup-row{padding:8px 16px 4px;flex-shrink:0;position:relative;z-index:10}
.followup-lbl{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--ink3);margin-bottom:6px}
.followup-chips{display:flex;gap:6px;overflow-x:auto;padding-bottom:2px}
.followup-chips::-webkit-scrollbar{display:none}
.fchip{display:flex;align-items:center;background:var(--bg);border:1.5px solid var(--border);border-radius:99px;padding:6px 12px;font-size:11px;font-weight:600;white-space:nowrap;cursor:pointer;flex-shrink:0;color:var(--ink);font-family:var(--fb);transition:all .2s;gap:4px}
.fchip:hover{background:var(--ink);color:white;border-color:var(--ink)}
.fchip:active{transform:scale(.97)}
.emergency-overlay{position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px;backdrop-filter:blur(4px)}
.emergency-box{background:var(--wh);border-radius:20px;padding:24px 20px;max-width:360px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.3)}
.emergency-title{font-size:20px;font-weight:800;color:#dc2626;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.emergency-msg{font-size:13px;color:var(--ink2);margin-bottom:18px;line-height:1.5}
.emergency-lines{display:flex;flex-direction:column;gap:10px;margin-bottom:20px}
.eline{display:flex;align-items:center;gap:12px;background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:12px 14px}
.eline-num{font-size:20px;font-weight:800;color:#dc2626;font-family:var(--fb)}
.eline-lbl{font-size:12px;color:var(--ink2);font-weight:500}
.emergency-continue{width:100%;padding:14px;border-radius:12px;border:none;background:var(--ink);color:white;font-size:14px;font-weight:700;cursor:pointer;font-family:var(--fb);transition:all .2s}
.ibar{padding:10px 14px 16px;border-top:1px solid var(--border);background:var(--wh);flex-shrink:0;position:relative;z-index:10}
.irow{display:flex;gap:8px;align-items:flex-end}
.tin{flex:1;border:1.5px solid var(--border);border-radius:12px;padding:10px 12px;font-size:14px;font-family:var(--fb);color:var(--ink);background:var(--bg);resize:none;outline:none;max-height:90px;line-height:1.4;transition:border-color .2s}
.tin:focus{border-color:var(--ink2);background:var(--wh)}
.tin::placeholder{color:var(--ink3)}
.mic{width:48px;height:48px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;transition:all .2s;background:var(--ink);color:white;box-shadow:0 3px 10px rgba(0,0,0,.2)}
.mic:active{transform:scale(.93)}
.mic.rec{background:#dc2626;animation:micRec 1.2s ease infinite}
.mic.proc{background:#f59e0b;cursor:not-allowed}
@keyframes micRec{0%,100%{box-shadow:0 3px 12px rgba(220,38,38,.35)}50%{box-shadow:0 3px 24px rgba(220,38,38,.6);transform:scale(1.08)}}
.snd{width:48px;height:48px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;transition:all .2s;background:var(--ink);color:white;box-shadow:0 3px 10px rgba(0,0,0,.2);font-family:var(--fb)}
.snd:disabled{opacity:.35;cursor:not-allowed}
.snd:not(:disabled):active{transform:scale(.93)}
.fade{animation:fade .35s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
/* Character floater */
.char-floater{position:fixed;bottom:80px;right:8px;z-index:50;display:flex;flex-direction:column;align-items:center;gap:4px;pointer-events:none}
.char-bubble{background:var(--wh);border:1px solid var(--border);border-radius:12px 12px 0 12px;padding:5px 11px;font-size:11px;font-weight:700;color:var(--ink);box-shadow:var(--sh);white-space:nowrap;animation:bubblePop .3s cubic-bezier(.34,1.56,.64,1)}
@keyframes bubblePop{from{opacity:0;transform:scale(.7) translateY(4px)}to{opacity:1;transform:scale(1) translateY(0)}}
/* Voice wave */
.vwave{display:flex;align-items:center;gap:3px;height:24px;margin:4px 0}
.vbar{width:3.5px;background:linear-gradient(180deg,#dc2626,#f59e0b);border-radius:2px;animation:vWave 1s ease-in-out infinite}
@keyframes vWave{0%,100%{transform:scaleY(.4)}50%{transform:scaleY(1.1)}}
`;

// ─── SOS ─────────────────────────────────────────────────────────────────────
function SosButton() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div ref={ref} className="sos-wrap">
      <div className="sos-pill" onClick={() => setOpen(o => !o)}>
        <span>🆘</span><span>SOS</span>
      </div>
      {open && (
        <div className="sos-drop">
          {HELPLINES.map((h, i) => (
            <div key={i} className="sos-it">
              <span className="sos-num">{h.num}</span>
              <span className="sos-lbl">{h.lbl}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── HOME ─────────────────────────────────────────────────────────────────────
function HomePage({ lang, onSelectSakhi, onResumeSession }) {
  const [sessions, setSessions] = useState(getSessions());
  const hi = lang === "hi";
  const handleDelete = (e, id) => {
    e.stopPropagation(); removeSession(id); deleteSessionAPI(id); setSessions(getSessions());
  };
  const timeAgo = ts => {
    const m = Math.floor((Date.now() - ts) / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  };
  return (
    <div className="home fade">
      <div className="hero">
        <div className="hero-eye">{hi ? "आपकी तीन सखियाँ" : "Your three companions"}</div>
        <h1 className="hero-title">
          {hi ? <>स्त्री<em>सखी</em> — हमेशा आपके साथ</> : <>Stri<em>Sakhi</em> — Always by your side</>}
        </h1>
        <p className="hero-sub">
          {hi ? "कानून, स्वास्थ्य और सरकारी योजनाओं में मदद के लिए तीन AI सखियाँ। निजी, मुफ्त, ऑफलाइन।"
               : "Three AI companions for legal rights, health guidance, and government schemes. Private, free, and offline."}
        </p>
      </div>
      <div className="sakhi-grid">
        {Object.values(SAKHIS).map(s => (
          <div key={s.id} className="s-card" style={{ background: s.gradient }} onClick={() => onSelectSakhi(s.id)}>
            <div className="c-blob cb1"/><div className="c-blob cb2"/>
            <div className="c-body">
              <div className="c-top">
                <div className="c-ico">{s.icon}</div>
                <div>
                  <div className="c-name">{hi ? s.nameHi : s.name}</div>
                  <div className="c-tag">{hi ? s.taglineHi : s.tagline}</div>
                </div>
              </div>
              <div className="c-quote">"{hi ? s.quoteHi : s.quote}"</div>
              <div className="c-chips">
                {s.usecases.map((u, i) => (
                  <div key={i} className="c-chip"><span>{u.icon}</span><span>{hi ? u.hi : u.en}</span></div>
                ))}
              </div>
              <div className="c-cta">
                <span>{hi ? `${s.nameHi} से बात करें` : `Talk to ${s.name}`} →</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      {sessions.length > 0 && (
        <div className="hist">
          <div className="sec-lbl">{hi ? "हालिया बातचीत" : "Recent conversations"}</div>
          <div className="sess-list">
            {[...sessions].reverse().map(s => {
              const sk = SAKHIS[s.sakhiId];
              return (
                <div key={s.id} className="sess-item" onClick={() => onResumeSession(s)}>
                  <div className="sess-dot" style={{ background: sk?.accent || "#888" }}/>
                  <div className="sess-info">
                    <div className="sess-prev">{s.preview || "Conversation"}</div>
                    <div className="sess-meta">{hi ? sk?.nameHi : sk?.name} · {timeAgo(s.timestamp)}</div>
                  </div>
                  <button className="sess-del" onClick={e => handleDelete(e, s.id)}>✕</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── CHAT ─────────────────────────────────────────────────────────────────────
function ChatPage({ sakhiId, resumeSessionId, lang, onBack }) {
  const sk = SAKHIS[sakhiId];
  const hi = lang === "hi";

  const [sessionLang, setSessionLang] = useState(null);
  const [langPicked, setLangPicked] = useState(false);
  const [sessionId, setSessionId] = useState(resumeSessionId || null);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [phase, setPhase] = useState("intake");
  const [showWait, setShowWait] = useState(false);
  const [showQuicks, setShowQuicks] = useState(true);
  const [ttsLoading, setTtsLoading] = useState(null);
  const audioRef = useRef(null);
  const [playingIdx, setPlayingIdx] = useState(null);
  const abortRef = useRef(null);
  const lastSpokenRef = useRef(null);
  const [followUpQuestions, setFollowUpQuestions] = useState([]);
  const [emergency, setEmergency] = useState(null);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingSeconds, setThinkingSeconds] = useState(0);
  const thinkingTimerRef = useRef(null);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [charState, setCharState] = useState("idle");
  const [recState, setRecState] = useState("idle");
  const bot = useRef(null);
  const waitRef = useRef(null);
  const mrRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const isTypingRef = useRef(false);
  const sessionIdRef = useRef(sessionId);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);

  const EMERGENCY_HELPLINES = {
    legal: {
      hi: { message: "आप सुरक्षित रहें। अभी मदद लें:", helplines: [{num:"181",lbl:"महिला हेल्पलाइन (FREE)"},{num:"100",lbl:"पुलिस"},{num:"15100",lbl:"मुफ्त वकील"}] },
      en: { message: "Stay safe. Get help RIGHT NOW:", helplines: [{num:"181",lbl:"Women Helpline (FREE)"},{num:"100",lbl:"Police"},{num:"15100",lbl:"Free Legal Aid"}] },
      bn: { message: "নিরাপদ থাকুন:", helplines: [{num:"181",lbl:"মহিলা হেল্পলাইন"},{num:"100",lbl:"পুলিশ"}] },
    },
    health: {
      hi: { message: "यह EMERGENCY है। तुरंत कॉल करें:", helplines: [{num:"108",lbl:"Ambulance (FREE)"},{num:"102",lbl:"Maternity"},{num:"104",lbl:"Health Helpline"}] },
      en: { message: "MEDICAL EMERGENCY. Call immediately:", helplines: [{num:"108",lbl:"Ambulance (FREE)"},{num:"102",lbl:"Maternity Emergency"},{num:"104",lbl:"Health Helpline"}] },
      bn: { message: "জরুরি:", helplines: [{num:"108",lbl:"অ্যাম্বুলেন্স"},{num:"102",lbl:"মাতৃত্ব জরুরি"}] },
    },
    scheme: {
      hi: { message: "तुरंत मदद लें:", helplines: [{num:"181",lbl:"Women Helpline (FREE)"},{num:"1098",lbl:"CHILDLINE"}] },
      en: { message: "Immediate help:", helplines: [{num:"181",lbl:"Women Helpline (FREE)"}] },
      bn: { message: "সাহায্য:", helplines: [{num:"181",lbl:"মহিলা হেল্পলাইন"}] },
    },
  };

  const showEmergencyOverlay = () => {
    const sakhiKey = sakhiId === "health" ? "health" : sakhiId === "scheme" ? "scheme" : "legal";
    const langData = EMERGENCY_HELPLINES[sakhiKey]?.[sessionLang || "hi"] || EMERGENCY_HELPLINES[sakhiKey]?.["en"];
    setEmergency(langData);
  };

  const getTtsLang = () => (sessionLang === "hi" ? "hi" : sessionLang === "en" ? "en" : null);

  const handleListen = async (text, idx) => {
    if (audioRef.current) {
      audioRef.current.pause(); audioRef.current = null;
      if (playingIdx === idx) { setPlayingIdx(null); setCharState("idle"); return; }
    }
    setTtsLoading(idx);
    try {
      const ttsLang = getTtsLang();
      if (!ttsLang) return;
      const res = await fetch(`${BASE_URL}/api/voice/tts`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, lang: ttsLang })
      });
      if (!res.ok || res.status === 204) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      setPlayingIdx(idx);
      setCharState("speaking");
      audio.onended = () => { setPlayingIdx(null); audioRef.current = null; setCharState("idle"); };
      audio.play();
    } catch (e) { console.error("TTS error:", e); }
    finally { setTtsLoading(null); }
  };

  const GREETINGS = {
    hi: `नमस्ते! मैं ${sk.nameHi} हूँ\n${sk.taglineHi}\n\nआज मैं आपकी कैसे मदद कर सकती हूँ?`,
    en: `Hello! I'm ${sk.name}\n${sk.tagline}\n\nHow can I help you today?`,
    bn: `নমস্কার! আমি ${sk.name}\n\nআজ আমি আপনাকে কীভাবে সাহায্য করতে পারি?`,
  };

  const startChat = async (chosenLang) => {
    setSessionLang(chosenLang);
    setLangPicked(true);
    // FIXED: correct tab_type mapping
    const tabMap = { legal: "legal", health: "medical", scheme: "scheme" };
    const id = await createSession(tabMap[sakhiId] || sakhiId);
    setSessionId(id);
    sessionIdRef.current = id;
    setMsgs([{ role: "assistant", content: GREETINGS[chosenLang] || GREETINGS.en, agent: "intake", citations: [] }]);
  };

  useEffect(() => {
    if (resumeSessionId) {
      const init = async () => {
        setSessionLang("hi"); setLangPicked(true);
        setSessionId(resumeSessionId); sessionIdRef.current = resumeSessionId;
        const sessionData = await loadSessionHistory(resumeSessionId);
        if (sessionData?.messages?.length > 0) {
          setMsgs(sessionData.messages.map(m => ({
            role: m.role, content: m.content,
            agent: m.agent_used || (m.role === "assistant" ? "intake" : null),
            citations: m.citations || [],
          })));
          if (sessionData.agent_phase === "expert") setPhase("expert");
          setShowQuicks(false);
        } else {
          setMsgs([{ role: "assistant", content: GREETINGS.hi, agent: "intake", citations: [] }]);
        }
      };
      init();
    }
    return () => { clearTimeout(waitRef.current); clearTimeout(timerRef.current); };
  }, []);

  useEffect(() => { bot.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, isTyping]);

  // Character state machine
  useEffect(() => {
    if (recState === "recording") setCharState("listening");
    else if (isThinking) setCharState("thinking");
    else if (isTyping) setCharState("thinking");
    else if (playingIdx !== null) setCharState("speaking");
    else setCharState("idle");
  }, [recState, isThinking, isTyping, playingIdx]);

  // Auto-speak new assistant messages
  useEffect(() => {
    if (!autoSpeak || !getTtsLang() || isTyping) return;
    const lastMsg = msgs[msgs.length - 1];
    if (!lastMsg || lastMsg.role !== "assistant" || !lastMsg.content || lastMsg.type) return;
    if (lastMsg.agent === "..." || !lastMsg.agent) return;
    const key = lastMsg.id ?? msgs.length - 1;
    if (lastSpokenRef.current === key) return;
    if (playingIdx !== null) return;
    lastSpokenRef.current = key;
    setTimeout(() => handleListen(lastMsg.content, msgs.length - 1), 500);
  }, [msgs, isTyping, autoSpeak]);

  const sendMessage = async (txt) => {
    if (!txt || !sessionIdRef.current) return;
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setShowQuicks(false);
    setIsTyping(true); isTypingRef.current = true;
    setShowWait(false); setIsThinking(false); setThinkingSeconds(0);
    clearTimeout(waitRef.current);
    waitRef.current = setTimeout(() => setShowWait(true), 8000);

    if (phase === "expert") {
      setIsThinking(true);
      thinkingTimerRef.current = setInterval(() => {
        setThinkingSeconds(s => { if (s >= 15) { clearInterval(thinkingTimerRef.current); setIsThinking(false); } return s + 1; });
      }, 1000);
    }

    const msgId = Date.now();
    setMsgs(p => [...p, { role: "assistant", content: "", agent: "...", citations: [], id: msgId }]);

    let ai = "";
    // FIXED: pass sakhiId directly — streamChat handles mapping internally
    await streamChat(
      sakhiId,
      sessionIdRef.current,
      txt,
      sessionLang || "hi",
      tok => {
        clearTimeout(waitRef.current); setShowWait(false);
        ai += tok;
        setMsgs(p => p.map(m => m.id === msgId ? { ...m, content: ai } : m));
      },
      done => {
        clearTimeout(waitRef.current); clearInterval(thinkingTimerRef.current);
        setShowWait(false); setIsTyping(false); setIsThinking(false); setThinkingSeconds(0);
        isTypingRef.current = false;
        const full = done.full_response || ai;
        if (full) setMsgs(p => p.map(m => m.id === msgId ? { ...m, content: full, agent: done.agent, citations: done.citations || [] } : m));
        if (done.follow_up_questions?.length > 0 &&
            ["expert","emergency","sehat","yojana"].includes(done.agent)) {
          setFollowUpQuestions(done.follow_up_questions);
        }
        if (full) addSessionHistory(sakhiId, sessionIdRef.current, txt);
      },
      meta => {
        if (meta.type === "phase_change") {
          setPhase("expert"); setIsThinking(true); setThinkingSeconds(0);
          clearInterval(thinkingTimerRef.current);
          thinkingTimerRef.current = setInterval(() => {
            setThinkingSeconds(s => { if (s >= 15) { clearInterval(thinkingTimerRef.current); setIsThinking(false); } return s + 1; });
          }, 1000);
        }
        if (meta.type === "emergency") {
          showEmergencyOverlay();
          clearTimeout(waitRef.current); clearInterval(thinkingTimerRef.current);
          setShowWait(false); setIsTyping(false); setIsThinking(false); isTypingRef.current = false;
          const emMsg = sessionLang === "hi"
            ? "🆘 आपकी स्थिति गंभीर लग रही है। कृपया अभी 181 पर call करें।"
            : "🆘 Your situation sounds serious. Please call 181 RIGHT NOW.";
          setMsgs(p => p.map(m => m.id === msgId ? { ...m, content: emMsg, agent: "emergency", citations: [] } : m));
        }
      },
      controller.signal
    );
  };

  const sendFromInput = () => {
    const txt = input.trim();
    if (!txt || isTypingRef.current) return;
    setInput("");
    setMsgs(p => [...p, { role: "user", content: txt, citations: [] }]);
    sendMessage(txt);
  };

  const stopRecording = () => { clearTimeout(timerRef.current); if (mrRef.current?.state === "recording") mrRef.current.stop(); };

  const startRecording = async () => {
    if (recState !== "idle") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ["audio/webm;codecs=opus","audio/webm","audio/ogg","audio/mp4"].find(m => MediaRecorder.isTypeSupported(m)) || "";
      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      mrRef.current = mr; chunksRef.current = [];
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        setRecState("processing");
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
        const audioUrl = URL.createObjectURL(blob);
        const audioMsgId = Date.now();
        setMsgs(p => [...p, { role: "user", type: "audio", audioUrl, transcript: null, transcribing: true, id: audioMsgId, citations: [] }]);
        const transcript = await transcribeAudio(blob);
        setMsgs(p => p.map(m => m.id === audioMsgId ? { ...m, transcript: transcript || "(no transcription)", transcribing: false } : m));
        setRecState("idle");
        if (transcript.trim()) await sendMessage(transcript.trim());
      };
      mr.start(250); setRecState("recording");
      timerRef.current = setTimeout(stopRecording, 25000);
    } catch (e) { setRecState("idle"); }
  };

  const toggleMic = () => { if (recState === "recording") stopRecording(); else if (recState === "idle") startRecording(); };

  const reset = async () => {
    clearTimeout(waitRef.current);
    if (sessionIdRef.current) deleteSessionAPI(sessionIdRef.current);
    setSessionId(null); sessionIdRef.current = null;
    setMsgs([]); setPhase("intake"); setIsTyping(false); isTypingRef.current = false;
    setShowWait(false); setShowQuicks(true); setInput("");
    setFollowUpQuestions([]); setEmergency(null);
    clearInterval(thinkingTimerRef.current); if (abortRef.current) abortRef.current.abort();
    setIsThinking(false); setThinkingSeconds(0); lastSpokenRef.current = null;
    setSessionLang(null); setLangPicked(false);
  };

  const fmt = t => t
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[Source:([^\]]+)\]/g, '<span style="font-size:10px;color:#7c9cbf;font-style:italic;">[Source: $1]</span>')
    .split("\n").join("<br/>");

  const pIdx = phase === "expert" ? 2 : 1;

  const charBubble = {
    idle:      { hi: "मैं यहाँ हूँ 🌸", en: "Here for you 🌸", bn: "এখানে আছি 🌸" },
    listening: { hi: "बोलिए... 🎤", en: "Listening... 🎤", bn: "বলুন... 🎤" },
    speaking:  { hi: "सुनिए... 🔊", en: "Playing... 🔊", bn: "শুনুন... 🔊" },
    thinking:  { hi: "सोच रही हूँ... 🧠", en: "Thinking... 🧠", bn: "ভাবছি... 🧠" },
  };

  const LANG_OPTIONS = [
    { code: "hi", name: "हिंदी", eng: "Hindi", desc: "Devanagari · Hindi voice", tts: true },
    { code: "en", name: "English", eng: "English", desc: "Roman script · English voice", tts: true },
    { code: "bn", name: "বাংলা", eng: "Bengali", desc: "Bengali script · text only", tts: false },
  ];
  const COMING_SOON = ["தமிழ் Tamil", "తెలుగు Telugu", "मराठी Marathi"];

  if (!langPicked) {
    return (
      <div className="chat-pg fade">
        <div className="chat-hdr">
          <button className="back" onClick={onBack}>←</button>
          <div className="ch-ico" style={{ background: sk.gradient }}>{sk.icon}</div>
          <div style={{ flex: 1 }}>
            <div className="ch-name" style={{ color: sk.color }}>{sk.name}</div>
            <div className="ch-st">Choose your language</div>
          </div>
        </div>
        <div className="lang-picker">
          <div className="lp-title">Choose your language</div>
          <div className="lp-sub">This will be used for the entire conversation.</div>
          <div className="lp-options">
            {LANG_OPTIONS.map(l => (
              <button key={l.code} className="lp-btn" onClick={() => startChat(l.code)}>
                <span className="lp-ico">{l.tts ? "🔊" : "📝"}</span>
                <span><span className="lp-name">{l.name} · {l.eng}</span><span className="lp-desc">{l.desc}</span></span>
              </button>
            ))}
            {COMING_SOON.map(l => (
              <button key={l} className="lp-btn lp-soon" disabled>
                <span className="lp-ico">🔜</span>
                <span><span className="lp-name">{l}</span><span className="lp-desc">Coming soon</span></span>
                <span className="lp-badge">Soon</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-pg fade">
      {emergency && (
        <div className="emergency-overlay">
          <div className="emergency-box">
            <div className="emergency-title">🆘 {sessionLang === "hi" ? "आपातकाल सहायता" : "Emergency Help"}</div>
            <div className="emergency-msg">{emergency.message}</div>
            <div className="emergency-lines">
              {emergency.helplines.map((h, i) => (
                <div key={i} className="eline"><div className="eline-num">{h.num}</div><div className="eline-lbl">{h.lbl}</div></div>
              ))}
            </div>
            <button className="emergency-continue" onClick={() => setEmergency(null)}>
              {sessionLang === "hi" ? "मैं सुरक्षित हूँ — जारी रखें" : "I am safe — continue"}
            </button>
          </div>
        </div>
      )}

      {/* Floating character */}
      <div className="char-floater">
        <div className="char-bubble" key={charState}>
          {charBubble[charState]?.[sessionLang || "en"] || charBubble[charState]?.en}
        </div>
        <SakhiCharacter state={charState} type={sakhiId} size={100} />
      </div>

      <div className="chat-hdr">
        <button className="back" onClick={onBack}>←</button>
        <div className="ch-ico" style={{ background: sk.gradient }}>{sk.icon}</div>
        <div style={{ flex: 1 }}>
          <div className="ch-name" style={{ color: sk.color }}>{sk.name}</div>
          <div className="ch-st" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {phase === "expert" ? "✓ Expert mode"
              : sakhiId === "health" ? (hi ? "✓ सेहत मोड" : "✓ Health mode")
              : sakhiId === "scheme" ? (hi ? "✓ योजना मोड" : "✓ Scheme mode")
              : "Listening..."}
            <span className="lang-tag">
              {sessionLang === "hi" ? "हिंदी" : sessionLang === "en" ? "English" : sessionLang === "bn" ? "বাংলা" : sessionLang}
            </span>
          </div>
        </div>
        <button className={`as-toggle ${autoSpeak ? "on" : ""}`} onClick={() => setAutoSpeak(s => !s)}>
          {autoSpeak ? "🔊" : "🔇"}
        </button>
        <button className="new-btn" onClick={reset}>New ↺</button>
      </div>

      <div className="pbar">
        <span className="p-lbl">Phase</span>
        <div className="p-dots">
          {[0,1,2].map(i => (
            <div key={i} className={`p-dot ${i < pIdx ? "done" : i === pIdx ? "active" : ""}`} style={{ width: i === pIdx ? 18 : 9 }}/>
          ))}
        </div>
        <span className="p-info">{phase === "expert" ? "Solution" : "Intake"}</span>
      </div>

      <div className="msgs">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "usr" : ""}`}>
            <div className="mav" style={m.role === "assistant" ? { background: sk.gradient, color: "white" } : {}}>
              {m.role === "assistant" ? sk.icon : "👤"}
            </div>
            <div className={`mbub ${m.role === "assistant" ? "ai" : "usr"}`}>
              {m.role === "assistant" && m.agent && m.agent !== "..." && (
                <div className="mbadge">
                  {m.agent === "expert" ? `⚡ ${hi ? "विशेषज्ञ" : "Expert"}`
                    : m.agent === "sehat" ? `🌿 ${hi ? "सेहत सखी" : "Sehat Sakhi"}`
                    : m.agent === "yojana" ? `📜 ${hi ? "योजना सखी" : "Yojana Sakhi"}`
                    : `🔍 ${hi ? "सुन रही हूँ" : "Listening"}`}
                </div>
              )}
              {m.type === "audio" ? (
                <div className="audio-msg">
                  <div className="audio-wrap"><audio controls src={m.audioUrl}/></div>
                  <div className="audio-sub">
                    {m.transcribing ? `⏳ ${hi ? "समझ रही हूँ..." : "Transcribing..."}`
                      : m.transcript ? `"${m.transcript}"` : ""}
                  </div>
                </div>
              ) : (
                <div className="mtext" dangerouslySetInnerHTML={{ __html: fmt(m.content || "") }}/>
              )}
              {m.citations?.length > 0 && (
                <div className="ctags">
                  {m.citations.map((c, ci) => (
                    <span key={ci} className="ctag">📖 {c.source}{c.section ? `, ${c.section}` : ""}</span>
                  ))}
                </div>
              )}
              {m.role === "assistant" && m.content && !m.streaming && getTtsLang() && (
                <button className={`listen-btn ${playingIdx === i ? "playing" : ""}`}
                  onClick={() => handleListen(m.content, i)} disabled={ttsLoading === i}>
                  {ttsLoading === i ? "⏳" : playingIdx === i ? "⏹ Stop" : "🔊 Listen"}
                </button>
              )}
            </div>
          </div>
        ))}

        {recState === "recording" && (
          <div className="msg">
            <div className="mav" style={{ background: sk.gradient, color: "white" }}>{sk.icon}</div>
            <div className="mbub ai" style={{ background: "#fef2f2", borderColor: "#fecaca" }}>
              <div className="vwave">
                {[...Array(7)].map((_, idx) => (
                  <div key={idx} className="vbar" style={{ height: `${8 + Math.sin(idx * 0.8) * 8 + 8}px`, animationDelay: `${idx * 0.08}s` }} />
                ))}
              </div>
              <div style={{ fontSize: 11, color: "#dc2626", fontWeight: 700, marginTop: 4 }}>
                {sessionLang === "hi" ? "बोलिए..." : "Listening..."}
              </div>
            </div>
          </div>
        )}

        {isTyping && (
          <div className="msg">
            <div className="mav" style={{ background: sk.gradient, color: "white" }}>{sk.icon}</div>
            <div className="mbub ai">
              {isThinking ? (
                <div className="thinking-wrap">
                  <div className="thinking-bar">
                    <span className="thinking-ico">🧠</span>
                    <span className="thinking-lbl">{sessionLang === "hi" ? "गहराई से सोच रही हूँ..." : "Reasoning deeply..."}</span>
                    <span style={{ fontSize: 10, color: "var(--ink3)", marginLeft: "auto" }}>{thinkingSeconds}s</span>
                  </div>
                  <div className="thinking-sub">{sessionLang === "hi" ? "आपके मामले का विश्लेषण हो रहा है" : "Analyzing your case"}</div>
                  <div className="thinking-progress"><div className="thinking-fill" key={thinkingSeconds}/></div>
                </div>
              ) : (
                <div className="typ-wrap">
                  <div className="typ-dots"><div className="typ-dot"/><div className="typ-dot"/><div className="typ-dot"/></div>
                  <span className="typ-lbl">{sessionLang === "hi" ? "सुन रही हूँ..." : "Listening..."}</span>
                </div>
              )}
              {showWait && !isThinking && <div className="wait-note">{sessionLang === "hi" ? "थोड़ा इंतज़ार करें..." : "Please wait..."}</div>}
            </div>
          </div>
        )}
        <div ref={bot}/>
      </div>

      {showQuicks && (
        <div className="qpicks">
          {sk.usecases.map((u, i) => (
            <button key={i} className="qchip" onClick={() => {
              setShowQuicks(false);
              setMsgs(p => [...p, { role: "user", content: hi ? u.hi : u.en, citations: [] }]);
              sendMessage(hi ? u.hi : u.en);
            }}>{u.icon} {hi ? u.hi : u.en}</button>
          ))}
        </div>
      )}

      {followUpQuestions.length > 0 && !isTyping && (
        <div className="followup-row">
          <div className="followup-lbl">{sessionLang === "hi" ? "आगे पूछें:" : "Ask more:"}</div>
          <div className="followup-chips">
            {followUpQuestions.map((q, i) => (
              <button key={i} className="fchip" onClick={() => {
                setFollowUpQuestions([]);
                setMsgs(p => [...p, { role: "user", content: q, citations: [] }]);
                sendMessage(q);
              }}>💬 {q}</button>
            ))}
          </div>
        </div>
      )}

      <div className="ibar">
        <div className="irow">
          <button className={`mic ${recState === "recording" ? "rec" : recState === "processing" ? "proc" : ""}`}
            onClick={toggleMic} disabled={recState === "processing"}>
            {recState === "processing" ? "⏳" : recState === "recording" ? "⏹️" : "🎤"}
          </button>
          <textarea className="tin" rows={1}
            placeholder={recState === "processing" ? (hi ? "ऑडियो process हो रहा है..." : "Processing...")
              : recState === "recording" ? (hi ? "बोल रहे हैं... रोकने के लिए दबाएं" : "Recording... tap to stop")
              : (hi ? "यहाँ लिखें या माइक दबाएं..." : "Type here or press mic...")}
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendFromInput(); } }} />
          <button className="snd" onClick={sendFromInput} disabled={!input.trim() || isTyping}>➤</button>
        </div>
      </div>
    </div>
  );
}

// ─── ADMIN ────────────────────────────────────────────────────────────────────
const ADMIN_PIN = "1234";
const adminCss = `*{box-sizing:border-box;margin:0;padding:0}.adm{display:flex;flex-direction:column;height:100vh;overflow:hidden;background:#0f1117;color:#e8eaf6;font-family:'DM Sans',sans-serif}.adm-hdr{padding:13px 22px;background:#1a1d27;border-bottom:1px solid #2e3347;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}.adm-brand{display:flex;align-items:center;gap:9px}.adm-logo{width:32px;height:32px;background:linear-gradient(135deg,#06b6d4,#3b82f6);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:15px}.adm-ttl{font-size:16px;font-weight:700}.adm-sub{font-size:10px;color:#5f6688;margin-top:1px}.spill{display:flex;align-items:center;gap:6px;background:#1a1d27;border:1px solid #2e3347;border-radius:99px;padding:4px 11px;font-size:11px;font-weight:700}.sdot{width:7px;height:7px;border-radius:50%}.lout{font-size:12px;color:#5f6688;background:none;border:none;cursor:pointer;padding:4px 8px;border-radius:6px;transition:all .2s}.lout:hover{color:#e8eaf6;background:#2e3347}.body{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.scard{background:#1a1d27;border:1px solid #2e3347;border-radius:12px;padding:16px}.slbl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#5f6688;margin-bottom:7px}.sval{font-size:26px;font-weight:700;line-height:1}.ssub{font-size:11px;color:#5f6688;margin-top:3px}.sbar{height:4px;background:#242838;border-radius:2px;margin-top:9px;overflow:hidden}.sfill{height:100%;border-radius:2px;transition:width .5s}.sec{background:#1a1d27;border:1px solid #2e3347;border-radius:12px;overflow:hidden}.shdr{padding:12px 16px;border-bottom:1px solid #2e3347;display:flex;align-items:center;gap:7px;font-size:13px;font-weight:700}.sbody{padding:14px 16px;display:flex;flex-direction:column;gap:8px}.row{display:flex;align-items:center;justify-content:space-between;padding:9px 11px;background:#242838;border-radius:9px;border:1px solid #2e3347}.rlbl{font-size:12px;font-weight:600}.rsub{font-size:10px;color:#5f6688;margin-top:2px;font-family:monospace}.bdg{font-size:10px;font-weight:700;padding:3px 8px;border-radius:99px;white-space:nowrap}.bdg-ok{background:rgba(34,197,94,.15);color:#22c55e;border:1px solid rgba(34,197,94,.25)}.bdg-err{background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.25)}.bdg-warn{background:rgba(245,158,11,.15);color:#f59e0b;border:1px solid rgba(245,158,11,.25)}.flow{display:flex;align-items:center;flex-wrap:wrap;gap:2px;padding:14px 16px}.fstep{display:flex;flex-direction:column;align-items:center;gap:5px;min-width:72px}.fico{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;border:1.5px solid #2e3347;background:#242838}.flbl{font-size:9px;font-weight:600;text-align:center;color:#5f6688;line-height:1.3}.farr{font-size:14px;color:#3d4460;margin-bottom:18px}.fstep.act .fico{border-color:#06b6d4;background:rgba(6,182,212,.1)}.fstep.act .flbl{color:#06b6d4}.rbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}.lupd{font-size:11px;color:#5f6688}.rbtn{display:flex;align-items:center;gap:5px;background:#242838;border:1px solid #2e3347;border-radius:7px;padding:6px 12px;font-size:11px;font-weight:600;color:#9ca3c9;cursor:pointer;font-family:inherit;transition:all .2s}.rbtn:hover{background:#2e3347;color:#e8eaf6}.spin{animation:spin 1s linear infinite;display:inline-block}@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}.login-wrap{height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1117}.lbox{background:#1a1d27;border:1px solid #2e3347;border-radius:16px;padding:36px;width:320px;text-align:center}.lico{font-size:36px;margin-bottom:14px}.lttl{font-size:20px;font-weight:700;margin-bottom:5px}.lsub{font-size:12px;color:#5f6688;margin-bottom:24px}.pins{display:flex;gap:9px;justify-content:center;margin-bottom:18px}.pd{width:44px;height:44px;border-radius:11px;background:#242838;border:2px solid #2e3347;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;transition:all .2s;color:#06b6d4}.pd.f{border-color:#06b6d4;background:rgba(6,182,212,.1)}.pd.e{border-color:#ef4444;background:rgba(239,68,68,.1)}.npad{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.nb{padding:13px;border-radius:9px;border:1px solid #2e3347;background:#242838;color:#e8eaf6;font-size:17px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .2s}.nb:hover{background:#2e3347}.nb:active{transform:scale(.95)}.errmsg{font-size:12px;color:#ef4444;margin-top:9px;height:16px}.preblock{font-family:monospace;font-size:10px;color:#9ca3c9;white-space:pre-wrap;word-break:break-word;line-height:1.6;padding:14px 16px}`;

function AdminBadge({ status }) {
  const ok = ["connected","ok","loaded","ready","found"].includes(status);
  const err = ["error","NOT FOUND","missing","not loaded"].includes(status);
  return <span className={`bdg ${ok?"bdg-ok":err?"bdg-err":"bdg-warn"}`}>{ok?"● OK":err?"● Error":"● "+status}</span>;
}

function AdminLogin({ onLogin }) {
  const [pin, setPin] = useState(""); const [err, setErr] = useState(""); const [shake, setShake] = useState(false);
  const press = d => {
    if (pin.length >= 4) return;
    const np = pin + d; setPin(np); setErr("");
    if (np.length === 4) setTimeout(() => {
      if (np === ADMIN_PIN) { onLogin(); }
      else { setShake(true); setErr("Wrong PIN"); setTimeout(() => { setPin(""); setShake(false); }, 700); }
    }, 100);
  };
  return (
    <div className="login-wrap">
      <div className="lbox">
        <div className="lico">🔐</div>
        <div className="lttl">StriSakhi Admin</div>
        <div className="lsub">Enter PIN to continue</div>
        <div className="pins">
          {[0,1,2,3].map(i => <div key={i} className={`pd ${i<pin.length?(shake?"e":"f"):""}`}>{i<pin.length?"●":""}</div>)}
        </div>
        <div className="npad">
          {[1,2,3,4,5,6,7,8,9].map(n => <button key={n} className="nb" onClick={() => press(String(n))}>{n}</button>)}
          <button className="nb" onClick={() => setPin(p=>p.slice(0,-1))} style={{color:"#ef4444"}}>⌫</button>
          <button className="nb" onClick={() => press("0")}>0</button>
          <button className="nb" onClick={() => setPin("")} style={{color:"#9ca3c9"}}>C</button>
        </div>
        <div className="errmsg">{err}</div>
      </div>
    </div>
  );
}

function AdminDashboard({ onLogout }) {
  const [data, setData] = useState(null); const [loading, setLoading] = useState(true);
  const [lastUpd, setLastUpd] = useState(null); const [fetchErr, setFetchErr] = useState(null);
  const load = async () => {
    setLoading(true);
    try { const r = await fetch(`${BASE_URL}/api/health`); setData(await r.json()); setLastUpd(new Date()); setFetchErr(null); }
    catch(e) { setFetchErr("Cannot reach backend"); }
    setLoading(false);
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);
  const sys=data?.system||{}; const svc=data?.services||{};
  const llm=svc.llamacpp||{}; const db=svc.database||{};
  const chroma=svc.chromadb||{}; const tts=data?.tts||{};
  const overall=data?.status||"unknown";
  return (
    <div className="adm">
      <style>{adminCss}</style>
      <div className="adm-hdr">
        <div className="adm-brand"><div className="adm-logo">⚡</div><div><div className="adm-ttl">StriSakhi Admin</div><div className="adm-sub">System Dashboard</div></div></div>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div className="spill">
            <div className="sdot" style={{background:overall==="ok"?"#22c55e":overall==="degraded"?"#f59e0b":"#ef4444"}}/>
            <span style={{color:overall==="ok"?"#22c55e":overall==="degraded"?"#f59e0b":"#ef4444",fontSize:11,fontWeight:700}}>
              {overall==="ok"?"All Systems OK":overall==="degraded"?"Degraded":"Unknown"}
            </span>
          </div>
          <button className="lout" onClick={onLogout}>Logout</button>
        </div>
      </div>
      <div className="body">
        <div className="rbar">
          <span className="lupd">{lastUpd?`Updated: ${lastUpd.toLocaleTimeString()}`:"Loading..."}</span>
          <button className="rbtn" onClick={load} disabled={loading}><span className={loading?"spin":""}>↻</span> Refresh</button>
        </div>
        {fetchErr && <div style={{color:"#ef4444",fontSize:13,padding:"10px 0"}}>⚠️ {fetchErr}</div>}
        <div className="grid">
          <div className="scard"><div className="slbl">CPU</div><div className="sval" style={{color:sys.cpu_percent>80?"#ef4444":"#22c55e"}}>{sys.cpu_percent??"-"}%</div><div className="ssub">Container</div><div className="sbar"><div className="sfill" style={{width:`${sys.cpu_percent||0}%`,background:sys.cpu_percent>80?"#ef4444":"#22c55e"}}/></div></div>
          <div className="scard"><div className="slbl">RAM</div><div className="sval" style={{color:"#06b6d4"}}>{sys.ram_used_gb??"-"}GB</div><div className="ssub">of {sys.ram_total_gb??"-"}GB</div><div className="sbar"><div className="sfill" style={{width:`${sys.ram_percent||0}%`,background:"#06b6d4"}}/></div></div>
          <div className="scard"><div className="slbl">Sessions</div><div className="sval" style={{color:"#f59e0b"}}>{db.total_sessions??"-"}</div><div className="ssub">All time</div></div>
          <div className="scard"><div className="slbl">Messages</div><div className="sval" style={{color:"#a855f7"}}>{db.total_messages??"-"}</div><div className="ssub">All time</div></div>
        </div>
        <div className="sec">
          <div className="shdr"><span>🧠</span> AI Flow</div>
          <div className="flow">
            {[{ico:"🎤",lbl:"Voice\nInput",act:true},{arr:true},{ico:"⚡",lbl:"Gemma4\nSTT",act:llm.status==="connected"},{arr:true},{ico:"🧩",lbl:"Intake\nAgent",act:true},{arr:true},{ico:"📚",lbl:"RAG\nChromaDB",act:chroma.status==="connected"},{arr:true},{ico:"⚖️",lbl:"Expert\nAgent",act:true},{arr:true},{ico:"🔊",lbl:"Piper\nTTS",act:tts.binary==="found"}].map((s,i) =>
              s.arr ? <span key={i} className="farr">→</span>
              : <div key={i} className={`fstep ${s.act?"act":""}`}><div className="fico">{s.ico}</div><div className="flbl">{s.lbl}</div></div>
            )}
          </div>
        </div>
        <div className="sec"><div className="shdr"><span>🤖</span> Models</div><div className="sbody">
          {[{lbl:"Gemma 4 E2B (Q4_K_M)",sub:"3.2GB · Metal GPU · thinking disabled",st:llm.status==="connected"?"loaded":"not loaded"},{lbl:"mmproj-gemma4-e2b",sub:"557MB · audio projector",st:llm.status==="connected"?"loaded":"not loaded"},{lbl:"Piper hi_IN-priyamvada",sub:`${tts.voices?.hindi?.size_mb||0}MB · Hindi TTS`,st:tts.voices?.hindi?.status||"missing"},{lbl:"Piper en_US-amy",sub:`${tts.voices?.english?.size_mb||0}MB · English TTS`,st:tts.voices?.english?.status||"missing"}].map((m,i) =>
            <div key={i} className="row"><div><div className="rlbl">{m.lbl}</div><div className="rsub">{m.sub}</div></div><AdminBadge status={m.st}/></div>
          )}
        </div></div>
        <div className="sec"><div className="shdr"><span>🔌</span> Services</div><div className="sbody">
          {[{lbl:"llama.cpp Server",sub:llm.url||"host.docker.internal:8080",st:llm.status||"error"},{lbl:"ChromaDB",sub:`${Object.values(chroma.document_counts||{}).reduce((a,b)=>a+b,0)} docs`,st:chroma.status||"error"},{lbl:"SQLite",sub:`${db.total_sessions||0} sessions`,st:db.status||"error"},{lbl:"Piper TTS",sub:"/usr/local/piper",st:tts.binary||"NOT FOUND"}].map((s,i) =>
            <div key={i} className="row"><div><div className="rlbl">{s.lbl}</div><div className="rsub">{s.sub}</div></div><AdminBadge status={s.st}/></div>
          )}
        </div></div>
        <div className="sec"><div className="shdr"><span>🌸</span> Three Sakhis</div><div className="sbody">
          {[{ico:"⚖️",name:"Kanoon Sakhi",desc:"/api/legal"},{ico:"🌿",name:"Sehat Sakhi",desc:"/api/medical"},{ico:"📜",name:"Yojana Sakhi",desc:"/api/scheme"}].map((s,i) =>
            <div key={i} className="row"><div><div className="rlbl">{s.ico} {s.name}</div><div className="rsub">{s.desc}</div></div><AdminBadge status={llm.status==="connected"?"ok":"error"}/></div>
          )}
        </div></div>
        {chroma.document_counts && Object.keys(chroma.document_counts).length > 0 && (
          <div className="sec"><div className="shdr"><span>📚</span> RAG Knowledge Base</div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:10,padding:"14px 16px"}}>
              {Object.entries(chroma.document_counts).map(([n,c]) => (
                <div key={n} style={{background:"#242838",border:"1px solid #2e3347",borderRadius:10,padding:"12px",textAlign:"center"}}>
                  <div style={{fontSize:22,fontWeight:700,color:"#06b6d4"}}>{c}</div>
                  <div style={{fontSize:11,color:"#5f6688",marginTop:3}}>{n}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="sec"><div className="shdr"><span>📋</span> Health JSON</div>
          <pre className="preblock">{data ? JSON.stringify(data,null,2) : "Loading..."}</pre>
        </div>
      </div>
    </div>
  );
}

function AdminPage() {
  const [auth, setAuth] = useState(() => sessionStorage.getItem("ss_admin") === "1");
  const login = () => { sessionStorage.setItem("ss_admin","1"); setAuth(true); };
  const logout = () => { sessionStorage.removeItem("ss_admin"); setAuth(false); };
  return auth ? <AdminDashboard onLogout={logout}/> : <AdminLogin onLogin={login}/>;
}

// ─── ROOT ─────────────────────────────────────────────────────────────────────
export default function App() {
  const [lang, setLang] = useState("en");
  const [view, setView] = useState("home");
  const [activeSakhi, setActiveSakhi] = useState(null);
  const [resumeSession, setResumeSession] = useState(null);
  if (window.location.pathname === "/admin") return <AdminPage />;
  return (
    <>
      <style>{css}</style>
      <div className="app">
        <header className="hdr">
          <div className="brand">
            <div className="brand-logo">🌸</div>
            <div>
              <div className="brand-name">Stri<span>Sakhi</span></div>
              <div className="brand-sub">{lang === "hi" ? "तीन सखियाँ — हमेशा आपके साथ" : "Three companions — always with you"}</div>
            </div>
          </div>
          <div className="hdr-right">
            <SosButton/>
            <div className="lang-pill">
              <button className={`l-btn ${lang === "en" ? "on" : ""}`} onClick={() => setLang("en")}>EN</button>
              <button className={`l-btn ${lang === "hi" ? "on" : ""}`} onClick={() => setLang("hi")}>हि</button>
            </div>
          </div>
        </header>
        <div className="page">
          {view === "home" ? (
            <HomePage lang={lang}
              onSelectSakhi={id => { setActiveSakhi(id); setResumeSession(null); setView("chat"); }}
              onResumeSession={s => { setActiveSakhi(s.sakhiId); setResumeSession(s.id); setView("chat"); }}
            />
          ) : (
            <ChatPage sakhiId={activeSakhi} resumeSessionId={resumeSession} lang={lang}
              onBack={() => { setView("home"); setActiveSakhi(null); setResumeSession(null); }}
            />
          )}
        </div>
      </div>
    </>
  );
}