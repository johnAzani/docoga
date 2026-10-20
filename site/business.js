/* DocOga — business.js (20 Oct 2026)
 * The Business tier: waitlist, team sign-in, configurator + checkout, renewal, the team portal
 * (licence, branding, seats, invoices). Loaded by index.html's bizLoad() only when a team is
 * signed in or a Business form is used — retail readers never download it (≈9 KB gzipped).
 * Everything here uses index.html's globals (team, WORKER_URL, $, esc, ngn, toast, store,
 * trackEvent, teamSignInForm, teamSignOut, renderAll). Same rules as the page: no build step,
 * no framework, no personal data in URLs. Tests: tools/tests/domtest.mjs (inlined + lazy-load).
 */
async function bizWaitlistSubmit(e){
  e.preventDefault();
  const msg=$('biz-waitlist-msg');
  const email=$('biz-email').value.trim();
  if(!email){ msg.textContent='Please enter your work email.'; return false; }
  msg.textContent='Sending…';
  try{
    const r=await fetch(WORKER_URL+'/business/waitlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,company:$('biz-company').value.trim(),segment:$('biz-seg').value})});
    const j=await r.json();
    if(j.ok){
      $('biz-email').value='';$('biz-company').value='';$('biz-seg').value='';
      msg.textContent=j.alreadyOnList?'You\u2019re already on the list \u2014 we\u2019ll email you at launch.':'You\u2019re on the list \u2014 we\u2019ll email you when your team can sign up.';
    } else { msg.textContent=j.error||'Something went wrong \u2014 please try again.'; }
  }catch(err){ msg.textContent='Could not reach the server \u2014 please try again in a moment.'; }
  return false;
}

async function bizLoginSubmit(e){
  e.preventDefault();
  const form=e.target;
  const msg=$('biz-login-msg')||$('tp-login-msg');
  const input=form&&form.querySelector('input[type=email]');
  if(!msg||!input) return false;
  const email=input.value.trim();
  if(!email){ msg.textContent='Enter the email your team owner added for you.'; return false; }
  msg.textContent='Sending your sign-in link…';
  try{
    const r=await fetch(WORKER_URL+'/business/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
    const j=await r.json();
    if(j.ok){ input.value=''; msg.textContent='✅ Check your inbox — a sign-in link is on its way (works once, 10 minutes).'; }
    else { msg.textContent=j.error||'Something went wrong — please try again.'; }
  }catch(err){ msg.textContent='Could not reach the server — please try again in a moment.'; }
  return false;
}
function teamUIRender(){
  const box=$('biz-team-box'); if(!box) return;
  if(teamActive()){
    box.innerHTML='<div class="team-chip"><span>🏢 <b>'+esc(team.team.name)+'</b> · signed in as '+esc(team.email)+(team.role==='owner'?'':'')+'</span><a class="link-btn" href="#team">Team dashboard →</a><button class="link-btn" onclick="teamSignOut()">Sign out</button></div>';
  } else if(team && team.team && (team.team.status==='grace' || team.team.status==='free')){
    const gtxt=team.team.status==='grace'?'licence expired — 14-day grace, renew to keep branding':'licence expired — free tier, renew to restore branding';
    box.innerHTML='<div class="team-chip" style="align-items:flex-start;flex-direction:column;gap:6px"><span>🏢 <b>'+esc(team.team.name)+'</b> — '+gtxt+'</span>'+
      '<div style="display:flex;gap:12px;margin-top:4px"><a class="link-btn" href="#team">Renew in the team dashboard →</a><button class="link-btn" onclick="teamSignOut()">Sign out</button></div></div>';
  } else if(team && team.token && team.team && team.team.status==='unpaid'){
    const q=team.quote||{};
    box.innerHTML='<div class="team-chip" style="align-items:flex-start;flex-direction:column;gap:6px"><span>🏢 <b>'+esc(team.team.name)+'</b> — activated: pay <b>'+ngn(q.total)+'</b>/yr (incl. VAT) and your team switches on automatically</span>'+
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px">'+
      '<button class="btn primary" style="justify-content:center" onclick="bizCharge(\'transfer\')">Pay by bank transfer</button>'+
      '<button class="btn ghost" style="justify-content:center" onclick="bizCharge(\'card\')">Pay by card / USSD</button>'+
      '</div>'+
      '<div id="biz-va-panel" style="width:100%;margin-top:8px"></div>'+
      '<div style="display:flex;gap:12px;margin-top:6px"><a class="link-btn" href="#team">Team dashboard →</a><button class="link-btn" onclick="teamSignOut()">Sign out</button></div></div>';
  } else {
    box.innerHTML=teamSignInForm('biz-login-email','biz-login-msg','Magic link, no password, no WhatsApp.','');
  }
  try{ teamPortalRender(); }catch(e){}
}


/* ================= Business configurator + checkout (Phase 2, 11 Oct 2026 — C3/C5) =================
   The published formula (dossier §6.1 — PROPOSED bands, config not code):
   the price is computed from the buyer's own inputs. The worker recomputes
   the SAME formula server-side, so the display and the invoice agree on the
   rules; the owner changes numbers in exactly one place (the worker). */
const BIZ_TIER_TABLE=[{key:'starter',base:96000,seats:3,docs:100,brands:1},{key:'standard',base:240000,seats:8,docs:300,brands:1},{key:'growth',base:480000,seats:20,docs:1000,brands:2}];
const BIZ_SEAT_UNIT=48000, BIZ_DOC_BLOCK_UNIT=18000, BIZ_VAT=0.075;
const BIZ_SEGMENTS={'estate-agent':[3,300],'property-manager':[8,300],'landlord':[3,100],'hr-team':[8,100]};
let bizSeg='';
function bizQuote(seats,docs){
  const nseats=Math.max(1,Math.min(500,Math.floor(Number(seats)||1)));
  const ndocs=Math.max(100,Math.min(100000,Math.floor(Number(docs)||100)));
  const tier=BIZ_TIER_TABLE.find(t=>nseats<=t.seats)||BIZ_TIER_TABLE[BIZ_TIER_TABLE.length-1];
  const extraSeats=Math.max(0,nseats-tier.seats);
  const extraBlocks=Math.max(0,Math.ceil((ndocs-tier.docs)/100));
  const price=tier.base+extraSeats*BIZ_SEAT_UNIT+extraBlocks*BIZ_DOC_BLOCK_UNIT;
  const vat=Math.round(price*BIZ_VAT);
  return {tier:tier.key,seats:nseats,docs:ndocs,extraSeats,extraBlocks,price,vat,total:price+vat};
}
function bizUpdateQuote(){
  const el=$('biz-cfg-quote'); if(!el) return;
  const q=bizQuote($('biz-cfg-seats').value,$('biz-cfg-docs').value);
  const t=BIZ_TIER_TABLE.find(x=>x.key===q.tier);
  let h='<div style="display:flex;justify-content:space-between;font-size:14px;margin:4px 0"><span>'+t.key.charAt(0).toUpperCase()+t.key.slice(1)+' — base ('+t.seats+' seats, '+t.docs+' docs/mo)</span><b>'+ngn(t.base)+'</b></div>';
  if(q.extraSeats) h+='<div style="display:flex;justify-content:space-between;font-size:14px;margin:4px 0"><span>+'+q.extraSeats+' seat'+(q.extraSeats>1?'s':'')+' × '+ngn(BIZ_SEAT_UNIT)+'</span><b>'+ngn(q.extraSeats*BIZ_SEAT_UNIT)+'</b></div>';
  if(q.extraBlocks) h+='<div style="display:flex;justify-content:space-between;font-size:14px;margin:4px 0"><span>+'+q.extraBlocks+' block'+(q.extraBlocks>1?'s':'')+' of 100 docs/mo × '+ngn(BIZ_DOC_BLOCK_UNIT)+'</span><b>'+ngn(q.extraBlocks*BIZ_DOC_BLOCK_UNIT)+'</b></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:14px;margin:4px 0"><span>VAT (7.5%)</span><b>'+ngn(q.vat)+'</b></div>';
  h+='<div style="display:flex;justify-content:space-between;font-size:17px;border-top:1px solid #cdd6e4;margin-top:8px;padding-top:8px"><b>Total / year</b><b>'+ngn(q.total)+'</b></div>';
  el.innerHTML=h;
}
function bizSetSegment(seg){
  const p=BIZ_SEGMENTS[seg]; if(!p) return;
  bizSeg=seg;
  $('biz-cfg-seats').value=String(p[0]);
  $('biz-cfg-docs').value=String(p[1]);
  document.querySelectorAll('[id^="biz-seg-"]').forEach(b=>b.classList.toggle('active',b.id==='biz-seg-'+seg));
  bizUpdateQuote();
}
async function bizCreateTeam(){
  const msg=$('biz-cfg-msg');
  const email=$('biz-cfg-email').value.trim(), name=$('biz-cfg-name').value.trim();
  if(!name){ msg.textContent='Please enter your firm name.'; return; }
  if(!email){ msg.textContent='Please enter your work email.'; return; }
  msg.textContent='Creating your team…';
  try{
    const r=await fetch(WORKER_URL+'/business/teams',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,name,seats:$('biz-cfg-seats').value,docs:$('biz-cfg-docs').value,segment:bizSeg})});
    const j=await r.json();
    if(j.ok){ trackEvent('business_team_created',{team_id:j.team.id, value:j.quote.total}); msg.textContent='✅ Team created — a sign-in link is on its way to '+email+'. Click it, pay by card or transfer, and your team activates automatically.'; $('biz-cfg-email').value=''; $('biz-cfg-name').value=''; }
    else { msg.textContent=j.error||'Something went wrong — please try again.'; }
  }catch(e){ msg.textContent='Could not reach the server — please try again in a moment.'; }
}
async function bizCharge(method){
  const panel=$('biz-va-panel'); if(!panel) return;
  panel.innerHTML='<div style="font-size:13px;color:#33415C">Creating your payment…</div>';
  try{
    const r=await fetch(WORKER_URL+'/business/team/charge',{method:'POST',headers:{Authorization:'Bearer '+team.token,'Content-Type':'application/json'},body:JSON.stringify({method})});
    const j=await r.json();
    if(!j.ok){ panel.innerHTML='<div style="font-size:13px;color:#b91c1c">'+esc(j.error||'Payment setup failed — please try again.')+'</div>'; return; }
    trackEvent('business_charge_started',{method:method, value:j.invoice.total, reused:!!j.reused});
    if(method==='card' && j.pay_url){
      window.open(j.pay_url,'_blank');
      panel.innerHTML='<div style="font-size:13px;color:#33415C">We opened the secure Flutterwave checkout. Your team activates automatically once payment lands — refresh this page if it does not update.</div>';
      return;
    }
    if(j.va){
      const va=j.va;
      const expTxt=va.expires?new Date(va.expires).toLocaleString():'';
      panel.innerHTML='<div style="background:#fff;border:1px solid #0B1B3F;border-radius:10px;padding:12px;font-size:13px;line-height:1.7">'+
        '<b>Transfer exactly '+ngn(j.invoice.total)+' NGN</b> to:<br>'+
        'Bank: <b>'+esc(va.bank)+'</b><br>Account: <b>'+esc(va.account)+'</b><br>'+
        (expTxt?'Valid until: <b>'+expTxt+'</b><br>':'')+
        'Your team activates the moment the exact amount lands — automatically.<br>'+
        '<button class="link-btn" style="margin-top:4px" onclick="bizCharge(\'transfer\')">Link expired? Get a new one →</button>'+
        '<span id="biz-va-status" style="font-size:12px;color:#33415C"></span></div>';
      bizPollActivation();
    }
  }catch(e){ panel.innerHTML='<div style="font-size:13px;color:#b91c1c">Could not reach the server — please try again in a moment.</div>'; }
}
/* Phase 4 (C9): renewal — same machinery as first purchase, price at purchase.
   The worker owns the window rules (T-90/grace/free) and the re-pricing is
   server-side; the panel mirrors the checkout VA panel. */
async function bizRenew(method){
  const panel=$('biz-renew-panel'); if(!panel) return;
  panel.innerHTML='<div style="font-size:13px;color:#33415C">Creating your renewal payment…</div>';
  try{
    const r=await fetch(WORKER_URL+'/business/team/renew',{method:'POST',headers:{Authorization:'Bearer '+team.token,'Content-Type':'application/json'},body:JSON.stringify({method})});
    const j=await r.json();
    if(!j.ok){ panel.innerHTML='<div style="font-size:13px;color:#b91c1c">'+esc(j.error||'Renewal setup failed — please try again.')+'</div>'; return; }
    trackEvent('business_renewal_started',{method:method, value:j.invoice.total});
    if(method==='card' && j.pay_url){
      window.open(j.pay_url,'_blank');
      panel.innerHTML='<div style="font-size:13px;color:#33415C">We opened the secure Flutterwave checkout. Your licence renews automatically once payment lands — refresh this page if it does not update.</div>';
      return;
    }
    if(j.va){
      const va=j.va;
      const expTxt=va.expires?new Date(va.expires).toLocaleString():'';
      panel.innerHTML='<div style="background:#fff;border:1px solid #0B1B3F;border-radius:10px;padding:12px;font-size:13px;line-height:1.7">'+
        '<b>Transfer exactly '+ngn(j.invoice.total)+' NGN</b> to:<br>'+
        'Bank: <b>'+esc(va.bank)+'</b><br>Account: <b>'+esc(va.account)+'</b><br>'+
        (expTxt?'Valid until: <b>'+expTxt+'</b><br>':'')+
        'Your licence renews the moment the exact amount lands — automatically.<br>'+
        '<button class="link-btn" style="margin-top:4px" onclick="bizRenew(\'transfer\')">Link expired? Get a new one →</button>'+
        '<span id="biz-renew-status" style="font-size:12px;color:#33415C"></span></div>';
      bizPollActivation();
    }
  }catch(e){ panel.innerHTML='<div style="font-size:13px;color:#b91c1c">Could not reach the server — please try again in a moment.</div>'; }
}
async function bizPollActivation(){
  for(let i=0;i<8;i++){
    await new Promise(res=>setTimeout(res,15000));
    try{
      const r=await fetch(WORKER_URL+'/business/team',{headers:{Authorization:'Bearer '+(team&&team.token)}});
      const j=await r.json();
      if(j.ok && j.team.status==='active'){
        team.team=j.team; team.brand=j.brand||{}; team.role=j.role; team.renewal=j.renewal; team.usage=j.usage;
        updateTeamUI(); renderAll();
        trackEvent('business_team_activated',{value:team.quote?team.quote.total:undefined});
        toast('✅ Payment received — your team is live. Invite your team members by email.');
        return;
      }
    }catch(e){ break; }
  }
  const st=$('biz-va-status'); if(st) st.innerHTML='If you already transferred, it usually confirms within a few minutes — just refresh this page.';
}

/* ================= Team portal (Phase 3, 11 Oct 2026) =================
   Self-serve dashboard for team members: licence state, firm branding
   (owner edits), seats (owner invites/revokes), invoices (C10 — each opens
   a printable page, print → Save as PDF) and support (FAQ + business@).
   No WhatsApp anywhere: every action is a worker call or an email. */
function teamChip(status,label){
  const map={paid:['#dcfce7','#166534'],open:['#fef9c3','#854d0e'],wrong:['#fee2e2','#991b1b'],active:['#dcfce7','#166534'],expired:['#fee2e2','#991b1b']};
  const c=map[status]||map.open;
  return '<span style="background:'+c[0]+';color:'+c[1]+';padding:4px 10px;border-radius:999px;font-size:12px;font-weight:bold;white-space:nowrap">'+label+'</span>';
}
function teamPortalRender(){
  const el=$('team-portal'); if(!el) return;
  if(!team || !team.team){
    el.innerHTML=teamSignInForm('tp-login-email','tp-login-msg','Magic link, no password — sent to the email your team owner added for you.',
      '<p style="text-align:center;margin-top:12px"><a class="link-btn" href="#business-setup">Setting up your first team? →</a></p>',true);
    return;
  }
  const t=team.team, q=team.quote||{}, b=team.brand||{}, isOwner=team.role==='owner';
  const exp=t.expiry?new Date(t.expiry).toLocaleDateString('en-NG',{day:'numeric',month:'long',year:'numeric'}):'—';
  const card='<div style="background:#fff;border:1px solid #cdd6e4;border-radius:12px;padding:16px 18px;margin-bottom:14px">';
  let h='';
  /* 1 — licence */
  const renewBtns=isOwner?'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px"><button class="btn primary" style="justify-content:center" onclick="bizRenew(\'transfer\')">Renew by bank transfer</button><button class="btn ghost" style="justify-content:center" onclick="bizRenew(\'card\')">Renew by card / USSD</button></div><div id="biz-renew-panel" style="margin-top:8px"></div>':'';
  h+=card+'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px"><div style="font-size:16px;font-weight:bold">🏢 '+esc(t.name)+'</div>';
  if(t.status==='unpaid'){
    h+=teamChip('open','UNPAID — pay '+ngn(q.total||0)+' to activate');
    h+='<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary" style="justify-content:center" onclick="bizCharge(\'transfer\')">Pay by bank transfer</button><button class="btn ghost" style="justify-content:center" onclick="bizCharge(\'card\')">Pay by card / USSD</button></div>';
  } else if(t.status==='active'){
    h+=teamChip('active','ACTIVE · until '+exp);
  } else if(t.status==='grace'){
    h+=teamChip('expired','EXPIRED · 14-day grace — branding paused');
  } else if(t.status==='free'){
    h+=teamChip('expired','EXPIRED · free tier — data kept 90 days');
  } else {
    h+=teamChip('expired','LICENCE PROBLEM · email business@docoga.com.ng');
  }
  h+='</div><div style="margin-top:8px;font-size:13px;color:#475569">'+(q.tier?q.tier.charAt(0).toUpperCase()+q.tier.slice(1)+' licence':'Business licence')+' · '+(q.seats||'—')+' seats · '+(q.docs||'—')+' docs/month · '+(q.total?ngn(q.total)+' billed yearly, incl. VAT':'')+' · signed in as '+esc(team.email)+(isOwner?' (owner)':'')+'</div>';
  /* Phase 4 (C9): renewal is self-serve — owner renews at the price at purchase */
  if(isOwner && t.status==='grace'){
    h+='<div style="margin-top:10px;font-size:13px;color:#33415C;line-height:1.6">Your licence expired on '+(t.expiry||'the last day')+'. Nothing is lost — renew below and branding comes straight back (the next 12 months start now). Data is kept 90 days after the grace period ends.</div>'+renewBtns;
  } else if(isOwner && t.status==='free'){
    h+='<div style="margin-top:10px;font-size:13px;color:#33415C;line-height:1.6">Your team is on the free tier — documents show the DocOga banner. Seats, branding and invoices are kept for 90 days; renew below to restore everything at the price you paid.</div>'+renewBtns;
  } else if(isOwner && t.status==='active' && t.expiry && (new Date(t.expiry+'T23:59:59Z').getTime()-Date.now()) <= 90*864e5){
    const price=(team.renewal&&team.renewal.total)?' '+ngn(team.renewal.total)+' incl. VAT':'';
    h+='<div style="margin-top:10px;font-size:13px;color:#33415C;line-height:1.6">Renews <b>'+exp+'</b> — same price you paid'+price+'. Renew any time below; early renewal stacks on your remaining days (none lost).</div>'+renewBtns;
  }
  /* Phase 4 (C8): monthly allowance line (soft limit — stated honestly) */
  if(team.usage && team.usage.band && t.status==='active'){
    const pct=Math.round(team.usage.used/team.usage.band*100);
    h+='<div style="margin-top:10px;padding:9px 12px;background:'+(pct>=100?'#fef9c3':'#f8fafc')+';border:1px solid '+(pct>=100?'#fde68a':'#e2e8f0')+';border-radius:10px;font-size:13px;color:#33415C">Documents this month: <b>'+team.usage.used+' / '+team.usage.band+'</b> ('+pct+'%)'+(pct>=100?' — you\'re over the band. The limit is soft: nothing stops, in-progress documents are never interrupted — but if this is the new normal, email <a href="mailto:business@docoga.com.ng">business@docoga.com.ng</a> and we\'ll right-size the plan by email.':'')+'</div>';
  }
  h+='</div>';
  /* 2 — firm branding */
  h+=card+'<div style="font-size:15px;font-weight:bold;margin-bottom:10px">Firm branding</div>'+
    '<div style="display:flex;align-items:center;gap:12px;padding:10px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px">'+
    ((b.logo||team._logo)?'<img src="'+esc(b.logo||team._logo)+'" alt="" style="height:40px;max-width:160px;object-fit:contain">':'<div style="width:48px;height:40px;border:1px dashed #94a3b8;border-radius:6px"></div>')+
    '<div><div style="font-weight:bold">'+esc(b.name||t.name)+'</div>'+(b.address?'<div style="font-size:12px;color:#64748b">'+esc(b.address)+'</div>':'')+(b.footer?'<div style="font-size:12px;color:#64748b">'+esc(b.footer)+'</div>':'')+'</div></div>';
  if(isOwner){
    h+='<div style="margin-top:12px;display:grid;gap:8px">'+
      '<input id="tp-brand-name" type="text" value="'+esc(b.name||t.name)+'" placeholder="Firm or company name" aria-label="Firm name" style="width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #cdd6e4;border-radius:10px;font-size:15px">'+
      '<input id="tp-brand-tagline" type="text" value="'+esc(b.tagline||'')+'" placeholder="Tagline (optional)" aria-label="Tagline" style="width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #cdd6e4;border-radius:10px;font-size:15px">'+
      '<input id="tp-brand-address" type="text" value="'+esc(b.address||'')+'" placeholder="Address / contact line (optional)" aria-label="Address" style="width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #cdd6e4;border-radius:10px;font-size:15px">'+
      '<input id="tp-brand-footer" type="text" value="'+esc(b.footer||'')+'" placeholder="Document footer line (optional)" aria-label="Footer" style="width:100%;box-sizing:border-box;padding:11px 13px;border:1px solid #cdd6e4;border-radius:10px;font-size:15px">'+
      '<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">'+
      '<label style="font-size:14px;font-weight:600;cursor:pointer" for="tp-brand-logo">Logo (PNG/JPG/SVG ≤ 25KB)</label>'+
      '<input id="tp-brand-logo" type="file" accept="image/png,image/jpeg,image/svg+xml" aria-label="Logo file" style="font-size:13px" onchange="teamBrandLogoChange()">'+
      '<img id="tp-brand-logo-preview" alt="" style="height:32px;max-width:120px;object-fit:contain;display:'+(team._logo?'block':'none')+'">'+
      '</div>'+
      '<div><button class="btn primary" style="justify-content:center" onclick="teamBrandSave()">Save branding</button> <span id="tp-brand-msg" style="font-size:13px;color:#33415C;display:inline-block;margin-left:8px"></span></div>'+
      '</div>';
  } else {
    h+='<p class="guarantee" style="margin-top:10px">Your owner manages firm branding — changes appear on every document the team produces.</p>';
  }
  h+='</div>';
  /* 3 — seats */
  const seats=team.seats||[];
  h+=card+'<div style="font-size:15px;font-weight:bold">Team seats'+(q.seats?' <span style="font-weight:normal;color:#64748b;font-size:13px">('+seats.length+' of '+q.seats+' used)</span>':'')+'</div>';
  if(seats.length){
    h+=seats.map(s=>'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #eef2f7;font-size:14px"><div><b>'+esc(s.name||'')+'</b> '+esc(s.email)+(s.role==='owner'?' <span style="font-size:11px;color:#64748b">(owner)</span>':'')+'</div>'+((isOwner&&s.role!=='owner')?'<button class="link-btn" style="color:#b91c1c" onclick="teamRevoke(\''+esc(s.email)+'\')">Remove</button>':'')+'</div>').join('');
  } else {
    h+='<p class="guarantee" style="margin-top:6px">No seats added yet.</p>';
  }
  if(isOwner){
    h+='<div style="display:flex;gap:8px;margin-top:12px"><input id="tp-invite-email" type="email" placeholder="colleague@firm.com" aria-label="Invite email" style="flex:1;min-width:0;padding:11px 13px;border:1px solid #cdd6e4;border-radius:10px;font-size:15px"><button class="btn ghost" style="white-space:nowrap" onclick="teamInvite()">Invite →</button></div>'+
      '<p id="tp-invite-msg" style="font-size:13px;color:#33415C;margin-top:8px"></p>'+
      '<p class="guarantee" style="margin-top:4px">They get a sign-in link by email the moment you invite — magic link, no password. Need <b>more seats</b> this year? Email <a href="mailto:business@docoga.com.ng">business@docoga.com.ng</a> and a human confirms the addition.</p>';
  }
  h+='</div>';
  /* 4 — invoices */
  h+=card+'<div style="font-size:15px;font-weight:bold">Invoices &amp; payments</div>'+
    '<div id="tp-invoices" style="margin-top:8px"><div style="font-size:13px;color:#33415C">Loading invoices…</div></div>'+
    '<p class="guarantee" style="margin-top:10px">Each invoice opens as a printable page — use the print button on it (or your browser’s Print → Save as PDF). Invoices stay available for 12 months.</p></div>';
  /* 5 — support */
  h+=card+'<div style="font-size:15px;font-weight:bold">Support</div>'+
    '<div style="font-size:14px;line-height:1.9;margin-top:8px">'+
    '<a class="link-btn" href="support.html" style="display:inline-block;margin-bottom:6px">Read the Business FAQ →</a><br>'+
'Email <a href="mailto:business@docoga.com.ng">business@docoga.com.ng</a> — an automated inbox with self-serve answers; the Business FAQ is one tap above.<br>'+
'<span style="color:#64748b;font-size:13px">Every message is kept on record. Renewals and invoicing are self-serve in this dashboard; mid-year seat changes come with your next renewal.</span></div></div>';
  el.innerHTML=h;
  try{ teamInvoicesLoad(); }catch(e){}
}
async function teamInvite(){
  const input=$('tp-invite-email'), msg=$('tp-invite-msg');
  const email=input&&input.value.trim();
  if(!email){ msg.textContent='Enter your colleague’s work email.'; return; }
  msg.textContent='Inviting '+email+'…';
  try{
    const r=await fetch(WORKER_URL+'/business/team/seats',{method:'POST',headers:{Authorization:'Bearer '+team.token,'Content-Type':'application/json'},body:JSON.stringify({action:'invite',email})});
    const j=await r.json();
    if(j.ok){ input.value=''; msg.textContent='✅ '+email+' will receive a sign-in link by email.'; team.seats=j.seats||team.seats; }
    else { msg.textContent=j.error||'Could not invite — please try again.'; }
  }catch(e){ msg.textContent='Could not reach the server — please try again in a moment.'; }
}
async function teamRevoke(email){
  if(!confirm('Remove '+email+' from the team? Their documents stay as they are; they simply lose the team banner.')) return;
  try{
    const r=await fetch(WORKER_URL+'/business/team/seats',{method:'POST',headers:{Authorization:'Bearer '+team.token,'Content-Type':'application/json'},body:JSON.stringify({action:'revoke',email})});
    const j=await r.json();
    if(j.ok){ team.seats=(j.seats||[]); teamPortalRender(); toast('Removed '+email+'.'); }
    else toast('⚠️ '+(j.error||'Could not remove — please try again.'));
  }catch(e){ toast('Could not reach the server — please try again in a moment.'); }
}
async function teamBrandSave(){
  const msg=$('tp-brand-msg');
  const brand={name:($('tp-brand-name')||{}).value, tagline:($('tp-brand-tagline')||{}).value, address:($('tp-brand-address')||{}).value, footer:($('tp-brand-footer')||{}).value};
  brand.name=(brand.name||'').trim(); brand.tagline=(brand.tagline||'').trim(); brand.address=(brand.address||'').trim(); brand.footer=(brand.footer||'').trim();
  if(team._logo) brand.logo=team._logo; else if(team.brand&&team.brand.logo) brand.logo=team.brand.logo;
  msg.textContent='Saving…';
  try{
    const r=await fetch(WORKER_URL+'/business/team/brand',{method:'PUT',headers:{Authorization:'Bearer '+team.token,'Content-Type':'application/json'},body:JSON.stringify(brand)});
    const j=await r.json();
    if(j.ok){ team.brand=j.brand||brand; delete team._logo; msg.textContent='✅ Saved — your firm name now appears on every document instead of DocOga.'; updateTeamUI(); }
    else { msg.textContent=j.error||'Could not save — please try again.'; }
  }catch(e){ msg.textContent='Could not reach the server — please try again in a moment.'; }
}
function teamBrandLogoChange(){
  const inp=$('tp-brand-logo'), msg=$('tp-brand-msg'), f=inp&&inp.files&&inp.files[0];
  if(!f) return;
  if(!/^image\/(png|jpe?g|svg\+xml)$/.test(f.type)){ msg.textContent='Logo must be a PNG, JPG or SVG image.'; inp.value=''; return; }
  if(f.size>25*1024){ msg.textContent='Logo must be ≤ 25KB — please export a smaller image.'; inp.value=''; return; }
  const rd=new FileReader();
  rd.onload=function(){ team._logo=String(rd.result); const pv=$('tp-brand-logo-preview'); if(pv){ pv.src=team._logo; pv.style.display='block'; } msg.textContent='Logo attached — press “Save branding” to apply.'; };
  rd.readAsDataURL(f);
}
async function teamInvoicesLoad(){
  const box=$('tp-invoices'); if(!box) return;
  box.innerHTML='<div style="font-size:13px;color:#33415C">Loading invoices…</div>';
  try{
    const r=await fetch(WORKER_URL+'/business/team/invoices',{headers:{Authorization:'Bearer '+team.token}});
    const j=await r.json();
    if(!j.ok){ box.innerHTML='<div style="font-size:13px;color:#33415C">Could not load invoices — refresh the page.</div>'; return; }
    const list=j.invoices||[];
    if(!list.length){ box.innerHTML='<div style="font-size:13px;color:#33415C">No invoices yet — they appear here as soon as you pay.</div>'; return; }
    box.innerHTML=list.map(function(x){
      const d=x.created?new Date(x.created).toLocaleDateString('en-NG'):'—';
      const chip=x.status==='paid'?teamChip('paid','PAID'):(x.status==='wrong_amount'?teamChip('wrong','WRONG AMOUNT'):teamChip('open','OPEN'));
      return '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid #eef2f7;font-size:14px"><div><b>'+esc(x.id)+'</b><br><span style="color:#64748b;font-size:12px">'+d+' · '+ngn(x.total)+' incl. VAT</span></div><div style="display:flex;align-items:center;gap:10px">'+chip+'<a class="link-btn" style="white-space:nowrap" href="'+WORKER_URL+'/business/invoice/'+encodeURIComponent(x.id)+'" target="_blank" rel="noopener">Open / Save PDF →</a></div></div>';
    }).join('');
  }catch(e){ box.innerHTML='<div style="font-size:13px;color:#33415C">Could not load invoices — check your connection and refresh.</div>'; }
}

