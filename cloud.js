/* Supabase authentication + per-user cloud conversation sync. */
(() => {
  const cfg = window.WHIZY_CONFIG || {};
  const gate = document.getElementById('authGate');
  const appShell = document.querySelector('.app-shell');
  const form = document.getElementById('authForm');
  const emailEl = document.getElementById('authEmail');
  const passEl = document.getElementById('authPassword');
  const nameEl = document.getElementById('authName');
  const titleEl = document.getElementById('authTitle');
  const subEl = document.getElementById('authSubtitle');
  const submitEl = document.getElementById('authSubmit');
  const toggleEl = document.getElementById('authToggle');
  const msgEl = document.getElementById('authMessage');
  let client = null, user = null, mode = 'signin', syncing = false, lastIds = new Set();
  const readyConfig = cfg.SUPABASE_URL && !cfg.SUPABASE_URL.includes('YOUR_PROJECT_ID') && cfg.SUPABASE_ANON_KEY && !cfg.SUPABASE_ANON_KEY.includes('YOUR_SUPABASE');
  const msg = (s, error=false) => { if(msgEl){msgEl.textContent=s;msgEl.classList.toggle('error',error);} };
  const showGate = (show) => { if(gate)gate.hidden=!show; if(appShell)appShell.style.display=show?'none':''; };
  const updateMode = () => {
    titleEl.textContent = mode === 'signup' ? 'Create your account' : 'Welcome back';
    subEl.textContent = mode === 'signup' ? 'Create a private workspace for your chats.' : 'Sign in to open your WHIZY workspace.';
    nameEl.hidden = mode !== 'signup';
    const nameLabel=document.getElementById('authNameLabel'); if(nameLabel)nameLabel.hidden=mode!=='signup';
    submitEl.textContent = mode === 'signup' ? 'Create account' : 'Sign in';
    toggleEl.textContent = mode === 'signup' ? 'Already have an account? Sign in' : 'New to WHIZY? Create account';
    msg('');
  };
  async function saveCloud(chats) {
    if(!client || !user || syncing) return;
    const list = Array.isArray(chats) ? chats : [];
    const nextIds = new Set(list.map(c=>String(c.id)));
    const removed = [...lastIds].filter(id=>!nextIds.has(id));
    if(removed.length) await client.from('conversations').delete().eq('user_id',user.id).in('conversation_id',removed);
    if(list.length) {
      const rows = list.map(c=>({user_id:user.id,conversation_id:String(c.id),title:String(c.title||'New conversation').slice(0,180),messages:Array.isArray(c.messages)?c.messages:[],updated_at:new Date(c.updated||Date.now()).toISOString()}));
      const {error} = await client.from('conversations').upsert(rows,{onConflict:'user_id,conversation_id'});
      if(error) { console.error('WHIZY cloud save failed',error); msg('Cloud sync issue: '+error.message,true); return; }
    }
    lastIds=nextIds;
  }
  async function loadCloud() {
    if(!client || !user || !window.whizyApp) return;
    syncing=true;
    const {data,error}=await client.from('conversations').select('conversation_id,title,messages,updated_at').eq('user_id',user.id).order('updated_at',{ascending:false}).limit(100);
    syncing=false;
    if(error){msg('Could not load cloud chats: '+error.message,true);return;}
    const list=(data||[]).map(r=>({id:r.conversation_id,title:r.title||'New conversation',messages:Array.isArray(r.messages)?r.messages:[],updated:Date.parse(r.updated_at)||Date.now()}));
    lastIds=new Set(list.map(c=>String(c.id)));
    window.whizyApp.setChats(list);
  }
  async function applyUser(sessionUser) {
    user=sessionUser||null;
    if(user) {
      showGate(false); document.body.classList.add('online-hosted');
      const account=document.querySelector('#openSettings small'); if(account)account.textContent=user.email||'Signed in';
      const footer=document.getElementById('footerStatus'); if(footer)footer.textContent='SECURE CLOUD WORKSPACE';
      await loadCloud();
    } else {
      showGate(true);
      if(window.whizyApp)window.whizyApp.setChats([]);
    }
  }
  async function init() {
    showGate(true);
    if(!readyConfig) {
      titleEl.textContent='WHIZY is almost ready';
      subEl.textContent='The online app needs its Supabase project settings before accounts can work.';
      form.hidden=true; toggleEl.hidden=true;
      msg('Owner setup required: add SUPABASE_URL and SUPABASE_ANON_KEY to config.js, then deploy again.',true);
      return;
    }
    if(!window.supabase || !window.supabase.createClient) {
      form.hidden=true; toggleEl.hidden=true; msg('Could not load the authentication library. Refresh when you have a stable connection.',true); return;
    }
    client=window.supabase.createClient(cfg.SUPABASE_URL,cfg.SUPABASE_ANON_KEY);
    window.whizyCloudClient=client;
    form.addEventListener('submit',async e=>{
      e.preventDefault(); const email=emailEl.value.trim(), password=passEl.value;
      if(!email || password.length<8){msg('Enter a valid email and a password with at least 8 characters.',true);return;}
      submitEl.disabled=true; msg(mode==='signup'?'Creating your account…':'Signing in…');
      try {
        let result;
        if(mode==='signup') result=await client.auth.signUp({email,password,options:{data:{display_name:nameEl.value.trim()}}});
        else result=await client.auth.signInWithPassword({email,password});
        if(result.error) throw result.error;
        if(mode==='signup' && !result.data.session) { msg('Account created. Check your email for the confirmation link, then sign in.'); }
        else if(result.data.user) { await applyUser(result.data.user); msg('Signed in successfully.'); }
      } catch(err) { msg(err.message||'Authentication failed.',true); }
      finally { submitEl.disabled=false; }
    });
    toggleEl.addEventListener('click',()=>{mode=mode==='signup'?'signin':'signup';updateMode();});
    document.getElementById('authSignOut')?.addEventListener('click',async()=>{if(client)await client.auth.signOut();});
    client.auth.onAuthStateChange((_event,session)=>{setTimeout(()=>applyUser(session?.user||null),0);});
    const {data,error}=await client.auth.getSession();
    if(error){msg(error.message,true);return;}
    await applyUser(data.session?.user||null);
  }
  window.whizyCloudSave=saveCloud;
  window.initWhizyCloud=init;
  window.whizyAuthHeaders=async()=>{if(!client)return {};const {data}=await client.auth.getSession();return data.session?.access_token?{Authorization:'Bearer '+data.session.access_token}:{};};
  // The hosted site never accepts provider credentials or arbitrary endpoints from the browser.
  const nativeFetch=window.fetch.bind(window);
  window.fetch=async(input,init={})=>{
    const url=typeof input==='string'?input:(input&&input.url)||'';
    if(url.startsWith('/api/')) {
      const headers=new Headers(init.headers||{}); const auth=await window.whizyAuthHeaders();Object.entries(auth).forEach(([k,v])=>headers.set(k,v));
      let body=init.body;
      if(typeof body==='string') { try { const obj=JSON.parse(body); ['apiKey','searchKey','endpoint','provider','imageModel'].forEach(k=>delete obj[k]); body=JSON.stringify(obj); } catch(_){} }
      init={...init,headers,body};
    }
    return nativeFetch(input,init);
  };
  updateMode();
})();
