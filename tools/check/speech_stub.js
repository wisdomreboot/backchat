/* A scripted stand-in for the browser's speech engine, used by tools/check/check.py.
   Installed before the page loads, it speaks by the clock, fires word boundaries as Safari does or none
   as Chrome's online voices do, and can imitate faults seen in real engines: an utterance that goes
   silent with no end (Chrome), a voice that always fails, and a speak() lost right after cancel().
   It also records the screen wake lock. Everything it does is logged on window.__speech. */
(function(){
  var F = window.__speech = {
    mode: "boundary",      // "boundary": word boundary events; "none": no boundary events
    cps: 120,              // characters per second at rate 1
    log: [],               // every utterance spoken: {text, t, rate, voice, ended, error}
    events: [],
    stallAfterMs: 0,       // >0: an utterance goes silent after this long, with no end (Chrome's 15 s bug)
    failAll: false,        // every utterance errors at once ("synthesis-failed")
    swallowAfterCancelMs: 0, // a speak() this soon after cancel() is silently dropped (Chrome)
    cancels: 0, lastCancelAt: 0,
    cur: null, queue: [], paused: false
  };
  function Utt(text){ this.text = String(text||""); this.rate = 1; this.pitch = 1; this.volume = 1; this.voice = null; this.lang = "";
    this.onstart = this.onend = this.onerror = this.onboundary = this.onpause = this.onresume = null; }
  Utt.prototype.addEventListener = function(t, fn){ this["on"+t] = fn; };
  function fire(u, type, extra){ var e = Object.assign({ type:type, utterance:u, charIndex:0, elapsedTime:0, name:"word" }, extra||{}); try{ if(u["on"+type]) u["on"+type](e); }catch(err){ F.events.push("handler error "+err); } }
  function runNext(){
    if(F.cur || !F.queue.length) return;
    var u = F.queue.shift(), rec = { text:u.text, t:Date.now(), rate:u.rate, voice:u.voice && u.voice.name, ended:false, error:null };
    F.log.push(rec); F.cur = { u:u, rec:rec, timers:[] };
    if(F.failAll){ F.cur = null; rec.error = "synthesis-failed"; setTimeout(function(){ fire(u, "error", { error:"synthesis-failed" }); runNext(); }, 5); return; }
    fire(u, "start");
    var words = [], re = /\S+/g, m; while((m = re.exec(u.text))) words.push(m.index);
    var msPerChar = 1000 / (F.cps * (u.rate || 1)), cur = F.cur;
    words.forEach(function(ci){
      var at = ci * msPerChar;
      if(F.stallAfterMs && at > F.stallAfterMs) return;
      cur.timers.push(setTimeout(function(){ if(F.cur !== cur || F.paused) return; rec.lastWord = ci; if(F.mode === "boundary") fire(u, "boundary", { charIndex:ci, name:"word" }); }, at));
    });
    var endAt = u.text.length * msPerChar + 30;
    if(!(F.stallAfterMs && endAt > F.stallAfterMs)){
      cur.timers.push(setTimeout(function(){ if(F.cur !== cur) return; F.cur = null; rec.ended = true; fire(u, "end"); runNext(); }, endAt));
    }
  }
  var synth = {
    get speaking(){ return !!F.cur; }, get pending(){ return F.queue.length > 0; }, get paused(){ return F.paused; },
    onvoiceschanged: null,
    getVoices: function(){ return [
      { name:"Test Natural Voice", voiceURI:"test-natural", lang:"en-US", localService:false, default:true },
      { name:"Test Local Voice", voiceURI:"test-local", lang:"en-GB", localService:true, default:false } ]; },
    speak: function(u){
      if(F.swallowAfterCancelMs && Date.now() - F.lastCancelAt < F.swallowAfterCancelMs){ F.log.push({ text:u.text, t:Date.now(), swallowed:true }); return; }
      F.queue.push(u); runNext();
    },
    cancel: function(){
      F.cancels++; F.lastCancelAt = Date.now();
      var q = F.queue; F.queue = [];
      q.forEach(function(u){ fire(u, "error", { error:"canceled" }); });
      if(F.cur){ var c = F.cur; F.cur = null; c.timers.forEach(clearTimeout); c.rec.error = "interrupted"; fire(c.u, "error", { error:"interrupted" }); }
    },
    pause: function(){ F.paused = true; }, resume: function(){ F.paused = false; },
    addEventListener: function(){}, removeEventListener: function(){}
  };
  Object.defineProperty(window, "speechSynthesis", { value:synth, configurable:true, writable:true });
  window.SpeechSynthesisUtterance = Utt;
  // Screen wake lock, recorded.
  F.wake = { held:false, requests:0, releases:0 };
  try{ Object.defineProperty(navigator, "wakeLock", { configurable:true, value:{ request:function(){ F.wake.requests++; F.wake.held = true;
    var l = { released:false, _h:[], addEventListener:function(t, fn){ this._h.push(fn); }, release:function(){ if(this.released) return Promise.resolve(); this.released = true; F.wake.releases++; F.wake.held = false; this._h.forEach(function(fn){ try{ fn(); }catch(e){} }); return Promise.resolve(); } };
    return Promise.resolve(l); } } }); }catch(e){}
})();
