import { useState, useEffect, useRef, useCallback } from "react";

const MOCK_LEGAL_RESPONSES = [
  { agent:"intake", text:"Main samajh sakti hoon. Aap kaun se state mein rehti hain?\nI understand. Which state do you live in?", citations:[], phase:"intake", confidence:4 },
  { agent:"intake", text:"Aur aapka dharm kya hai? (Hindu, Muslim, Christian?)\nAnd what is your religion?", citations:[], phase:"intake", confidence:8 },
  { agent:"expert", text:"Aapki baat sunkar dil dukha. Aap akeli nahi hain.\n\n**Aapke Adhikar / Your Rights:**\n→ Aapko ghar mein rehne ka poora adhikar hai.\n[Source: Gharelu Hinsa Adhiniyam 2005, Dhara 17]\n\n→ Pati aapko ghar se nahi nikaala sakta.\n[Source: DV Act 2005, Section 17]\n\n**Aaj Ye Karein / Do This Today:**\n1. Nearest Magistrate Court mein jaayein\n2. Dhara 12 ke tahet application dein — court fee NAHI lagti\n3. Court 3 din mein sunwai karegi\n\n**FREE Madad / Free Help:**\n• Mahila Helpline: 181\n• NALSA Legal Aid: 15100", citations:[{source:"Gharelu Hinsa Adhiniyam 2005",section:"Dhara 17"},{source:"DV Act 2005",section:"Section 12"}], phase:"expert", confidence:18 },
];
const MOCK_MEDICAL_RESPONSES = [
  { agent:"intake", text:"Samajh gayi. Mujhe batayein — ye problem kitne din se hai?\nI understand. How many days has this been going on?", citations:[], phase:"intake", confidence:4 },
  { agent:"expert", text:"Ye sunkar chinta hoti hai. Aapki sehat sabse zaroori hai.\n\n**Zaruri Jaankari / Important Info:**\nPair mein sujan + tez sir dard pregnancy mein — ye SERIOUS symptoms hain.\n[Source: WHO Antenatal Care Guidelines 2016]\n\n**Abhi Ye Karein / Do This Now:**\n1. TURANT hospital jaayein — aaj hi\n2. Free ambulance ke liye 102 pe call karein\n3. Janani Suraksha Yojana ke tahet delivery FREE hai\n[Source: JSY Scheme, NHM India]\n\n**Emergency Numbers:**\n• Ambulance: 108\n• Maternity Ambulance: 102\n• Health Helpline: 104", citations:[{source:"WHO ANC Guidelines 2016",section:"Pre-eclampsia Protocol"},{source:"Janani Suraksha Yojana",section:"NHM India"}], phase:"expert", confidence:16 },
];
const LEGAL_UC = [
  {icon:"🏠",hi:"घर का अधिकार",en:"Home Rights",dhi:"Pati ne ghar se nikaala",den:"Husband evicted me"},
  {icon:"🏛️",hi:"ज़मीन का हक़",en:"Property Rights",dhi:"Pitaji ki zameen mein hissa",den:"Share in father's land"},
  {icon:"💼",hi:"काम की जगह",en:"Workplace Issue",dhi:"Kaam par pareshan kiya",den:"Harassment at work"},
];
const MEDICAL_UC = [
  {icon:"🤱",hi:"गर्भावस्था",en:"Pregnancy",dhi:"Pregnancy mein takleef",den:"Pregnancy problem"},
  {icon:"👶",hi:"बच्चे की बीमारी",en:"Child Illness",dhi:"Bachche ko bukhar",den:"Child has fever"},
  {icon:"🧠",hi:"मन की बात",en:"Mental Health",dhi:"Bahut udaasi hai",den:"Feeling very sad"},
];

let mockIdx = {legal:0,medical:0};
async function mockChat(tab,msg,onToken,onDone,onMeta){
  const pool = tab==="legal"?MOCK_LEGAL_RESPONSES:MOCK_MEDICAL_RESPONSES;
  const r = pool[Math.min(mockIdx[tab],pool.length-1)];
  mockIdx[tab]=Math.min(mockIdx[tab]+1,pool.length-1);
  await new Promise(x=>setTimeout(x,350));
  onMeta({type:"routing",model:r.agent==="intake"?"gemma3n:e2b":"gemma3n:e4b",decision:r.agent});
  onMeta({type:"metrics",ram_used_gb:4.2,ram_percent:52,model:r.agent==="intake"?"gemma3n:e2b":"gemma3n:e4b"});
  if(r.phase==="expert"&&mockIdx[tab]>1){
    await new Promise(x=>setTimeout(x,250));
    onMeta({type:"phase_change",from:"intake",to:"expert"});
    onMeta({type:"citations",citations:r.citations});
  }
  await new Promise(x=>setTimeout(x,500));
  for(const w of r.text.split(" ")){onToken(w+" ");await new Promise(x=>setTimeout(x,30+Math.random()*25));}
  onDone({full_response:r.text,citations:r.citations,agent:r.agent,response_ms:1180});
}

const css = `
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --sky:#E8F6FF;--sky-mid:#C8E8FA;--sky-deep:#B0D8F0;
  --teal:#0EA5B0;--teal-dark:#0B8A94;--teal-light:#E0F7FA;
  --mint:#43D9A2;--coral:#FF6B6B;--coral-dark:#E55555;
  --cream:#FAFCFF;--text-dark:#1A2B3C;--text-mid:#4A6274;--text-light:#8BA5B8;
  --white:#FFFFFF;--r:20px;--r-sm:12px;--r-full:999px;
  --font:'Baloo 2','Noto Sans Devanagari',sans-serif;
}
html,body,#root{height:100%;width:100%;overflow:hidden}
body{font-family:var(--font);background:var(--sky);color:var(--text-dark);-webkit-font-smoothing:antialiased}

/* SPLASH */
.splash{position:fixed;inset:0;z-index:100;background:linear-gradient(150deg,#0EA5B0 0%,#0B7A83 45%,#064F56 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;animation:sFade .5s ease forwards;animation-delay:3.1s}
@keyframes sFade{to{opacity:0;pointer-events:none}}
.s-logo{width:100px;height:100px;background:rgba(255,255,255,.15);border-radius:28px;display:flex;align-items:center;justify-content:center;font-size:50px;border:2px solid rgba(255,255,255,.25);animation:sFloat 2s ease-in-out infinite;box-shadow:0 0 50px rgba(255,255,255,.12)}
@keyframes sFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.s-title{text-align:center;animation:sUp .8s cubic-bezier(.22,1,.36,1) .3s both}
@keyframes sUp{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
.s-title h1{font-size:36px;font-weight:800;color:#fff;line-height:1.1}
.s-title .dev{font-size:26px;font-weight:600;color:rgba(255,255,255,.78);margin-top:2px}
.s-tag{font-size:13px;color:rgba(255,255,255,.60);text-align:center;line-height:1.6;animation:sUp .8s cubic-bezier(.22,1,.36,1) .6s both;max-width:250px}
.s-dots{display:flex;gap:7px;animation:sUp .8s cubic-bezier(.22,1,.36,1) .9s both}
.s-dot{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.35);animation:dPulse 1.4s ease-in-out infinite}
.s-dot:nth-child(2){animation-delay:.2s}.s-dot:nth-child(3){animation-delay:.4s}
@keyframes dPulse{0%,100%{background:rgba(255,255,255,.3);transform:scale(1)}50%{background:rgba(255,255,255,.9);transform:scale(1.35)}}

/* APP */
.app{height:100%;display:flex;flex-direction:column;background:var(--sky);opacity:0;animation:aReveal .6s ease 3.3s forwards}
@keyframes aReveal{to{opacity:1}}

/* HEADER */
.hdr{padding:14px 18px 10px;display:flex;align-items:center;justify-content:space-between;background:#fff;box-shadow:0 2px 16px rgba(14,165,176,.08);flex-shrink:0;position:relative;z-index:10}
.hdr-brand{display:flex;align-items:center;gap:9px}
.hdr-icon{width:38px;height:38px;border-radius:11px;background:linear-gradient(135deg,var(--teal),var(--teal-dark));display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 4px 12px rgba(14,165,176,.28)}
.hdr-nm .en{font-size:16px;font-weight:800;color:var(--text-dark);line-height:1.2}
.hdr-nm .hi{font-size:12px;font-weight:500;color:var(--teal)}
.lang-tgl{display:flex;background:var(--sky);border-radius:var(--r-full);padding:3px;gap:2px;border:1.5px solid var(--sky-mid)}
.l-btn{padding:5px 12px;border-radius:var(--r-full);font-size:12px;font-weight:700;cursor:pointer;border:none;transition:all .22s ease;background:transparent;color:var(--text-light);font-family:var(--font)}
.l-btn.on{background:var(--teal);color:#fff;box-shadow:0 2px 8px rgba(14,165,176,.35)}

/* SCROLL */
.scroll{flex:1;overflow-y:auto;overflow-x:hidden;padding:18px 14px 100px;scroll-behavior:smooth}
.scroll::-webkit-scrollbar{width:0}

/* GREETING */
.greet{margin-bottom:18px;animation:slideD .6s cubic-bezier(.22,1,.36,1) 3.5s both}
@keyframes slideD{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
.greet h2{font-size:21px;font-weight:800;color:var(--text-dark);line-height:1.2}
.greet p{font-size:13px;color:var(--text-mid);margin-top:4px;line-height:1.5}

/* CARDS */
.cards{display:flex;flex-direction:column;gap:14px}
.card{border-radius:var(--r);overflow:hidden;box-shadow:0 8px 32px rgba(14,165,176,.13);cursor:pointer;transition:transform .2s ease,box-shadow .2s ease;position:relative;animation:cReveal .7s cubic-bezier(.22,1,.36,1) both}
.card:nth-child(1){animation-delay:3.6s}.card:nth-child(2){animation-delay:3.85s}
@keyframes cReveal{from{opacity:0;transform:translateY(22px) scale(.97)}to{opacity:1;transform:translateY(0) scale(1)}}
.card:active{transform:scale(.985);box-shadow:0 4px 16px rgba(14,165,176,.10)}
.card.legal{background:linear-gradient(148deg,#0EA5B0 0%,#0891B2 55%,#0369A1 100%)}
.card.medical{background:linear-gradient(148deg,#10B981 0%,#059669 55%,#047857 100%)}
.c-in{padding:22px 18px 18px;position:relative;z-index:1}
.c-circ{position:absolute;border-radius:50%;background:rgba(255,255,255,.07);pointer-events:none}
.cc1{width:150px;height:150px;right:-35px;top:-35px}
.cc2{width:80px;height:80px;right:55px;bottom:-18px}
.cc3{width:44px;height:44px;left:18px;bottom:8px}
.c-top{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.c-ico{width:60px;height:60px;border-radius:16px;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-size:30px;flex-shrink:0;border:2px solid rgba(255,255,255,.22)}
.c-ttl .main{font-size:21px;font-weight:800;color:#fff;line-height:1.1}
.c-ttl .sub{font-size:13px;font-weight:500;color:rgba(255,255,255,.78);margin-top:2px}
.c-ttl .badge{display:inline-block;margin-top:5px;background:rgba(255,255,255,.18);border-radius:99px;padding:2px 10px;font-size:11px;font-weight:600;color:rgba(255,255,255,.88);border:1px solid rgba(255,255,255,.22)}
.c-chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{display:flex;align-items:center;gap:5px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.18);border-radius:99px;padding:6px 11px;color:#fff;font-size:12px;font-weight:500;font-family:var(--font)}
.c-cta{margin-top:14px;display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.11);border-radius:11px;padding:11px 14px;border:1px solid rgba(255,255,255,.18)}
.cta-t{color:#fff;font-size:13px;font-weight:600}
.cta-arr{width:30px;height:30px;border-radius:50%;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px}

/* INFO STRIP */
.info{margin-top:14px;display:flex;gap:9px;animation:slideD .7s cubic-bezier(.22,1,.36,1) 4s both}
.pill{flex:1;background:#fff;border-radius:13px;padding:11px;text-align:center;box-shadow:0 4px 16px rgba(14,165,176,.09);border:1.5px solid var(--sky-mid)}
.pi{font-size:20px;margin-bottom:3px}
.pv{font-size:12px;font-weight:800;color:var(--teal)}
.pl{font-size:10px;font-weight:600;color:var(--text-mid);line-height:1.3}

/* CHAT OVERLAY */
.ov{position:fixed;inset:0;z-index:50;background:rgba(14,165,176,.14);backdrop-filter:blur(4px);opacity:0;pointer-events:none;transition:opacity .3s ease}
.ov.on{opacity:1;pointer-events:all}
.cpanel{position:fixed;bottom:0;left:0;right:0;z-index:51;background:var(--cream);border-radius:26px 26px 0 0;box-shadow:0 -6px 36px rgba(14,165,176,.18);transform:translateY(100%);transition:transform .4s cubic-bezier(.22,1,.36,1);display:flex;flex-direction:column;max-height:92vh}
.cpanel.on{transform:translateY(0)}
.handle{width:42px;height:4px;border-radius:2px;background:var(--sky-mid);margin:11px auto 0;flex-shrink:0}

/* CHAT HEADER */
.chdr{padding:14px 18px 10px;display:flex;align-items:center;justify-content:space-between;border-bottom:1.5px solid var(--sky-mid);flex-shrink:0}
.chdr-info{display:flex;align-items:center;gap:10px}
.chdr-ico{width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;font-size:21px}
.chdr-ico.legal{background:var(--teal-light)}.chdr-ico.medical{background:#D1FAE5}
.chdr-t{font-size:16px;font-weight:800;color:var(--text-dark)}
.chdr-s{font-size:11px;color:var(--teal);font-weight:600}
.c-acts{display:flex;gap:7px;align-items:center}
.ns-btn{font-size:11px;font-weight:700;color:var(--teal);background:none;border:none;cursor:pointer;padding:4px 7px;font-family:var(--font);display:flex;align-items:center;gap:3px}
.x-btn{width:34px;height:34px;border-radius:50%;background:var(--sky);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;color:var(--text-mid);transition:background .2s;font-family:var(--font)}
.x-btn:hover{background:var(--sky-mid)}

/* PHASE BAR */
.pbar{padding:7px 18px;display:flex;align-items:center;gap:9px;background:var(--sky);flex-shrink:0}
.p-lbl{font-size:10px;font-weight:700;color:var(--text-mid);text-transform:uppercase;letter-spacing:.5px}
.p-dots{display:flex;gap:4px}
.p-dot{height:6px;border-radius:3px;background:var(--sky-mid);transition:all .35s ease}
.p-dot.active{background:var(--teal);width:20px}
.p-dot.done{background:var(--mint)}
.conf{font-size:10px;font-weight:700;color:var(--teal);margin-left:auto}

/* METRICS */
.mbar{padding:5px 16px;display:flex;gap:11px;align-items:center;background:var(--sky);flex-shrink:0;border-bottom:1px solid var(--sky-mid);overflow-x:auto}
.mbar::-webkit-scrollbar{display:none}
.mi{display:flex;align-items:center;gap:4px;flex-shrink:0}
.mdot{width:6px;height:6px;border-radius:50%;background:var(--mint)}
.mt{font-size:10px;font-weight:600;color:var(--text-light)}
.mv{font-size:10px;font-weight:800;color:var(--text-mid)}

/* QUICK PICKS */
.qpicks{padding:8px 14px 4px;flex-shrink:0;display:flex;gap:7px;overflow-x:auto}
.qpicks::-webkit-scrollbar{display:none}
.qchip{display:flex;align-items:center;gap:5px;background:#fff;border:1.5px solid var(--sky-mid);border-radius:99px;padding:6px 13px;font-size:12px;font-weight:600;color:var(--text-mid);white-space:nowrap;cursor:pointer;flex-shrink:0;transition:all .2s;font-family:var(--font)}
.qchip:hover{background:var(--teal-light);border-color:var(--teal);color:var(--teal)}

/* MESSAGES */
.msgs{flex:1;overflow-y:auto;padding:14px 14px 8px;display:flex;flex-direction:column;gap:11px}
.msgs::-webkit-scrollbar{width:0}
.msg{display:flex;gap:8px;animation:mPop .3s cubic-bezier(.22,1,.36,1)}
@keyframes mPop{from{opacity:0;transform:translateY(9px) scale(.97)}to{opacity:1;transform:translateY(0) scale(1)}}
.msg.usr{flex-direction:row-reverse}
.mav{width:32px;height:32px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700}
.mav.ai{background:linear-gradient(135deg,var(--teal),var(--teal-dark));color:#fff}
.mav.usr{background:var(--sky-mid);color:var(--teal)}
.mbub{max-width:82%;border-radius:18px;padding:11px 14px;font-size:14px;line-height:1.6;position:relative}
.mbub.ai{background:#fff;color:var(--text-dark);border:1.5px solid var(--sky-mid);box-shadow:0 4px 16px rgba(14,165,176,.09);border-bottom-left-radius:5px}
.mbub.usr{background:linear-gradient(135deg,var(--teal),var(--teal-dark));color:#fff;border-bottom-right-radius:5px}
.mtext{white-space:pre-wrap;word-break:break-word}
.mtext strong{font-weight:700}
.ctags{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
.ctag{font-size:10px;font-weight:600;background:var(--teal-light);color:var(--teal-dark);border-radius:99px;padding:3px 8px;border:1px solid rgba(14,165,176,.18)}
.abadge{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px;color:var(--text-light)}
.abadge.exp{color:var(--teal)}
.typing{display:flex;align-items:center;gap:9px;padding:0 3px}
.tdots{display:flex;gap:4px}
.td{width:7px;height:7px;border-radius:50%;background:var(--teal);opacity:.5;animation:tBounce 1.2s ease-in-out infinite}
.td:nth-child(2){animation-delay:.2s}.td:nth-child(3){animation-delay:.4s}
@keyframes tBounce{0%,100%{transform:translateY(0);opacity:.4}50%{transform:translateY(-5px);opacity:1}}
.ttxt{font-size:12px;color:var(--text-light);font-style:italic}

/* INPUT BAR */
.ibar{padding:11px 14px 18px;flex-shrink:0;border-top:1.5px solid var(--sky-mid);background:#fff}
.irow{display:flex;gap:9px;align-items:flex-end}
.tin{flex:1;border:1.5px solid var(--sky-mid);border-radius:14px;padding:10px 13px;font-size:14px;font-family:var(--font);color:var(--text-dark);background:var(--sky);resize:none;outline:none;max-height:90px;transition:border-color .2s;line-height:1.4}
.tin:focus{border-color:var(--teal);background:#fff}
.tin::placeholder{color:var(--text-light)}
.mic{width:46px;height:46px;border-radius:50%;background:linear-gradient(135deg,var(--teal),var(--teal-dark));border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:19px;flex-shrink:0;box-shadow:0 4px 14px rgba(14,165,176,.38);transition:all .2s}
.mic:active{transform:scale(.93)}
.mic.rec{background:linear-gradient(135deg,var(--coral),var(--coral-dark));box-shadow:0 4px 18px rgba(255,107,107,.42);animation:mPulse 1s ease-in-out infinite}
@keyframes mPulse{0%,100%{box-shadow:0 4px 18px rgba(255,107,107,.42)}50%{box-shadow:0 4px 28px rgba(255,107,107,.68);transform:scale(1.05)}}
.snd{width:46px;height:46px;border-radius:50%;background:var(--teal);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;box-shadow:0 4px 14px rgba(14,165,176,.33);transition:all .2s;color:#fff;font-family:var(--font)}
.snd:disabled{opacity:.40;cursor:not-allowed}
.snd:not(:disabled):active{transform:scale(.93)}

/* EMERGENCY FAB */
.efab{position:fixed;bottom:22px;right:18px;z-index:60;display:flex;flex-direction:column;align-items:flex-end;gap:9px}
.eopts{display:flex;flex-direction:column;gap:7px;transform:scale(.88) translateY(8px);transform-origin:bottom right;opacity:0;pointer-events:none;transition:all .3s cubic-bezier(.22,1,.36,1)}
.eopts.vis{transform:scale(1) translateY(0);opacity:1;pointer-events:all}
.eopt{display:flex;align-items:center;gap:9px;background:#fff;border-radius:13px;padding:9px 13px;cursor:pointer;box-shadow:0 4px 18px rgba(255,107,107,.18);border:1.5px solid rgba(255,107,107,.13);transition:all .2s;text-decoration:none;white-space:nowrap}
.eopt:active{transform:scale(.97)}
.enum{font-size:15px;font-weight:800;color:var(--coral)}
.elbl{font-size:11px;font-weight:600;color:var(--text-mid)}
.eico{font-size:17px}
.fab{width:54px;height:54px;border-radius:50%;background:linear-gradient(135deg,var(--coral),var(--coral-dark));border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:22px;color:#fff;box-shadow:0 6px 22px rgba(255,107,107,.42);transition:all .3s ease;position:relative}
.fab::before{content:'';position:absolute;inset:-4px;border-radius:50%;border:2px solid rgba(255,107,107,.28);animation:fRing 2s ease-in-out infinite}
@keyframes fRing{0%,100%{transform:scale(1);opacity:.6}50%{transform:scale(1.18);opacity:0}}
.fab.open{transform:rotate(45deg);background:linear-gradient(135deg,var(--text-mid),var(--text-dark))}
.fab.open::before{display:none}
`;

function Splash(){
  return(
    <div className="splash">
      <div className="s-logo">⚖️</div>
      <div className="s-title">
        <h1>Nyay Vani</h1>
        <div className="dev">न्याय वाणी</div>
      </div>
      <div className="s-tag">Your voice. Your rights. Your language.<br/><span style={{opacity:.75}}>आपकी आवाज़। आपके अधिकार।</span></div>
      <div className="s-dots"><div className="s-dot"/><div className="s-dot"/><div className="s-dot"/></div>
    </div>
  );
}

function Header({lang,setLang}){
  return(
    <div className="hdr">
      <div className="hdr-brand">
        <div className="hdr-icon">⚖️</div>
        <div className="hdr-nm">
          <div className="en">Nyay Vani</div>
          <div className="hi">न्याय वाणी</div>
        </div>
      </div>
      <div className="lang-tgl">
        <button className={`l-btn ${lang==="en"?"on":""}`} onClick={()=>setLang("en")}>EN</button>
        <button className={`l-btn ${lang==="hi"?"on":""}`} onClick={()=>setLang("hi")}>हि</button>
      </div>
    </div>
  );
}

function SectionCard({type,lang,onOpen}){
  const isL=type==="legal";
  const uc=isL?LEGAL_UC:MEDICAL_UC;
  const T={
    legal:{en:"Kanoon Sahayak",hi:"कानून सहायक",sub:"Legal Assistant",subhi:"क़ानूनी मदद"},
    medical:{en:"Swasthya Sahayak",hi:"स्वास्थ्य सहायक",sub:"Health Assistant",subhi:"स्वास्थ्य मदद"},
  }[type];
  const cta=isL?(lang==="hi"?"अपने अधिकार जानें →":"Know your legal rights →"):(lang==="hi"?"स्वास्थ्य सलाह लें →":"Get health guidance →");
  return(
    <div className={`card ${type}`} onClick={onOpen}>
      <div className="c-circ cc1"/><div className="c-circ cc2"/><div className="c-circ cc3"/>
      <div className="c-in">
        <div className="c-top">
          <div className="c-ico">{isL?"⚖️":"🏥"}</div>
          <div className="c-ttl">
            <div className="main">{lang==="hi"?T.hi:T.en}</div>
            <div className="sub">{lang==="hi"?T.subhi:T.sub}</div>
            <span className="badge">{isL?"🔒 Private • Free":"❤️ Free • Confidential"}</span>
          </div>
        </div>
        <div className="c-chips">
          {uc.map((u,i)=>(
            <div key={i} className="chip" onClick={e=>e.stopPropagation()}>
              <span>{u.icon}</span>
              <span>{lang==="hi"?u.hi:u.en}</span>
            </div>
          ))}
        </div>
        <div className="c-cta">
          <span className="cta-t">{cta}</span>
          <div className="cta-arr">→</div>
        </div>
      </div>
    </div>
  );
}

function InfoStrip({lang}){
  const items=[
    {icon:"🔒",v:lang==="hi"?"100% निजी":"100% Private",l:lang==="hi"?"डेटा सुरक्षित":"Data Secure"},
    {icon:"🌐",v:lang==="hi"?"9 भाषाएं":"9 Languages",l:lang==="hi"?"हिंदी, तमिल...":"Hindi, Tamil..."},
    {icon:"⚡",v:lang==="hi"?"तुरंत":"Instant",l:lang==="hi"?"AI सहायक":"AI Response"},
  ];
  return(
    <div className="info">
      {items.map((it,i)=>(
        <div key={i} className="pill">
          <div className="pi">{it.icon}</div>
          <div className="pv">{it.v}</div>
          <div className="pl">{it.l}</div>
        </div>
      ))}
    </div>
  );
}

function MetricsBar({m}){
  if(!m)return null;
  return(
    <div className="mbar">
      <div className="mi"><div className="mdot"/><span className="mt">Model:</span><span className="mv">{m.model}</span></div>
      <div className="mi"><span className="mt">RAM:</span><span className="mv">{m.ram_used_gb}GB ({m.ram_percent}%)</span></div>
      <div className="mi"><span className="mt">Device:</span><span className="mv">Apple M2 — Offline</span></div>
    </div>
  );
}

function ChatPanel({tab,lang,open,onClose}){
  const [msgs,setMsgs]=useState([]);
  const [input,setInput]=useState("");
  const [typing,setTyping]=useState(false);
  const [phase,setPhase]=useState("intake");
  const [conf,setConf]=useState(0);
  const [metrics,setMetrics]=useState(null);
  const [rec,setRec]=useState(false);
  const bot=useRef(null);
  const isL=tab==="legal";
  const uc=isL?LEGAL_UC:MEDICAL_UC;

  useEffect(()=>{
    if(open&&msgs.length===0){
      const g=isL
        ?(lang==="hi"?"Namaste 🙏 Main Nyay Vani hoon. Aapki kya mushkil hai? Bata sakti hain — main yahaan hoon.\n\nआप क्या जानना चाहती हैं?":"Namaste 🙏 I'm Nyay Vani. What is your problem? You can tell me — I am here to help.")
        :(lang==="hi"?"Namaste 🙏 Main Nyay Vani hoon. Koi tabiyat theek nahi? Mujhe batayein.\n\nकौन सी तकलीफ है?":"Namaste 🙏 I'm Nyay Vani. Is someone unwell? Please tell me what's happening.");
      setMsgs([{role:"assistant",content:g,agent:"intake",citations:[]}]);
    }
  },[open]);

  useEffect(()=>{bot.current?.scrollIntoView({behavior:"smooth"})},[msgs,typing]);

  const send=useCallback(async(txt)=>{
    if(!txt.trim()||typing)return;
    setInput("");
    setMsgs(p=>[...p,{role:"user",content:txt,agent:null,citations:[]}]);
    setTyping(true);
    let ai="";const id=Date.now();
    setMsgs(p=>[...p,{role:"assistant",content:"",agent:"...",citations:[],streaming:true,id}]);
    await mockChat(tab,txt,
      (tok)=>{ai+=tok;setMsgs(p=>p.map(m=>m.id===id?{...m,content:ai}:m));},
      (done)=>{setTyping(false);setMsgs(p=>p.map(m=>m.id===id?{...m,content:done.full_response,agent:done.agent,citations:done.citations||[],streaming:false}:m));},
      (meta)=>{
        if(meta.type==="phase_change")setPhase("expert");
        if(meta.type==="metrics")setMetrics(meta);
        if(meta.type==="metadata_update")setConf(meta.confidence_score||0);
      }
    );
  },[tab,typing]);

  const reset=()=>{
    setMsgs([]);setPhase("intake");setConf(0);setMetrics(null);
    mockIdx[tab]=0;
    setTimeout(()=>{
      const g=isL?(lang==="hi"?"Namaste 🙏 Nayi baat shuru karte hain. Kya mushkil hai?":"Namaste 🙏 Let's start fresh. What is your problem?"):(lang==="hi"?"Namaste 🙏 Nayi baat. Kya takleef hai?":"Namaste 🙏 Fresh start. What's the health concern?");
      setMsgs([{role:"assistant",content:g,agent:"intake",citations:[]}]);
    },100);
  };

  const fmt=(t)=>t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\[Source:[^\]]+\]/g,'').split('\n').join('<br/>');
  const pIdx=phase==="expert"?2:1;

  return(
    <>
      <div className={`ov ${open?"on":""}`} onClick={onClose}/>
      <div className={`cpanel ${open?"on":""}`}>
        <div className="handle"/>
        <div className="chdr">
          <div className="chdr-info">
            <div className={`chdr-ico ${tab}`}>{isL?"⚖️":"🏥"}</div>
            <div>
              <div className="chdr-t">{isL?(lang==="hi"?"कानून सहायक":"Kanoon Sahayak"):(lang==="hi"?"स्वास्थ्य सहायक":"Swasthya Sahayak")}</div>
              <div className="chdr-s">{phase==="expert"?(lang==="hi"?"✓ विशेषज्ञ मोड":"✓ Expert Mode — E4B"):(lang==="hi"?"जानकारी ले रहे हैं... E2B":"Gathering info... E2B")}</div>
            </div>
          </div>
          <div className="c-acts">
            <button className="ns-btn" onClick={reset}>↺ {lang==="hi"?"नया":"New"}</button>
            <button className="x-btn" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="pbar">
          <span className="p-lbl">{lang==="hi"?"चरण":"Phase"}</span>
          <div className="p-dots">
            {[0,1,2].map(i=>(
              <div key={i} className={`p-dot ${i<pIdx?"done":i===pIdx?"active":""}`} style={{width:i===pIdx?20:10}}/>
            ))}
          </div>
          <span className="conf">{conf}/24 {lang==="hi"?"जानकारी":"info"}</span>
        </div>

        <MetricsBar m={metrics}/>

        {msgs.length<=1&&(
          <div className="qpicks">
            {uc.map((u,i)=>(
              <button key={i} className="qchip" onClick={()=>send(lang==="hi"?u.dhi:u.den)}>
                {u.icon} {lang==="hi"?u.hi:u.en}
              </button>
            ))}
          </div>
        )}

        <div className="msgs">
          {msgs.map((m,i)=>(
            <div key={i} className={`msg ${m.role==="user"?"usr":""}`}>
              <div className={`mav ${m.role==="assistant"?"ai":"usr"}`}>{m.role==="assistant"?"NV":"👤"}</div>
              <div className={`mbub ${m.role==="assistant"?"ai":"usr"}`}>
                {m.role==="assistant"&&m.agent&&(
                  <div className={`abadge ${m.agent==="expert"?"exp":""}`}>
                    {m.agent==="expert"?"⚡ Expert Agent (E4B)":m.agent==="intake"?"🔍 Intake Agent (E2B)":"..."}
                  </div>
                )}
                <div className="mtext" dangerouslySetInnerHTML={{__html:fmt(m.content)}}/>
                {m.citations&&m.citations.length>0&&(
                  <div className="ctags">
                    {m.citations.map((c,ci)=>(
                      <span key={ci} className="ctag">📖 {c.source}{c.section?`, ${c.section}`:""}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {typing&&(
            <div className="msg">
              <div className="mav ai">NV</div>
              <div className="mbub ai">
                <div className="typing">
                  <div className="tdots"><div className="td"/><div className="td"/><div className="td"/></div>
                  <span className="ttxt">{lang==="hi"?"सोच रही हूँ...":"Thinking..."}</span>
                </div>
              </div>
            </div>
          )}
          <div ref={bot}/>
        </div>

        <div className="ibar">
          <div className="irow">
            <button className={`mic ${rec?"rec":""}`} onClick={()=>{if(rec){setRec(false);send(lang==="hi"?"Mere pati ne mujhe ghar se nikaala hai":"My husband has evicted me from home");}else setRec(true);}}>
              {rec?"⏹️":"🎤"}
            </button>
            <textarea className="tin" rows={1}
              placeholder={lang==="hi"?"यहाँ लिखें या माइक दबाएं...":"Type here or press mic..."}
              value={input} onChange={e=>setInput(e.target.value)}
              onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send(input);}}}
            />
            <button className="snd" onClick={()=>send(input)} disabled={!input.trim()||typing}>➤</button>
          </div>
        </div>
      </div>
    </>
  );
}

function EmergencyFAB({lang}){
  const [open,setOpen]=useState(false);
  const opts=[
    {ico:"👮",num:"100",lbl:lang==="hi"?"Police":"Police"},
    {ico:"👩",num:"181",lbl:lang==="hi"?"महिला हेल्पलाइन":"Women Helpline"},
    {ico:"🚑",num:"108",lbl:lang==="hi"?"एम्बुलेंस":"Ambulance"},
    {ico:"⚖️",num:"15100",lbl:lang==="hi"?"Legal Aid (FREE)":"Legal Aid (FREE)"},
  ];
  return(
    <div className="efab">
      <div className={`eopts ${open?"vis":""}`}>
        {opts.map((o,i)=>(
          <div key={i} className="eopt">
            <span className="eico">{o.ico}</span>
            <div><div className="enum">{o.num}</div><div className="elbl">{o.lbl}</div></div>
          </div>
        ))}
      </div>
      <button className={`fab ${open?"open":""}`} onClick={()=>setOpen(x=>!x)}>{open?"✕":"🆘"}</button>
    </div>
  );
}

export default function App(){
  const [lang,setLang]=useState("hi");
  const [tab,setTab]=useState(null);
  const G={
    en:{main:"How can we help you today?",sub:"Select a service below — private and free."},
    hi:{main:"आज हम आपकी कैसे मदद करें?",sub:"नीचे एक सेवा चुनें — बिल्कुल निजी और मुफ़्त।"},
  };
  return(
    <>
      <style>{css}</style>
      <Splash/>
      <div className="app">
        <Header lang={lang} setLang={setLang}/>
        <div className="scroll">
          <div className="greet">
            <h2>{G[lang].main}</h2>
            <p>{G[lang].sub}</p>
          </div>
          <div className="cards">
            <SectionCard type="legal" lang={lang} onOpen={()=>setTab("legal")}/>
            <SectionCard type="medical" lang={lang} onOpen={()=>setTab("medical")}/>
          </div>
          <InfoStrip lang={lang}/>
        </div>
        <ChatPanel tab={tab} lang={lang} open={!!tab} onClose={()=>setTab(null)}/>
        <EmergencyFAB lang={lang}/>
      </div>
    </>
  );
}
