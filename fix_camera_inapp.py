#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — in-app camera for protected projects
Run this from the same folder as your index.html:
    python3 fix_camera_inapp.py

Requires the vault scripts (VAULT_ENVELOPE in particular).

ROOT CAUSE ON RECORD
Android reclaims the browser process during the native-camera hand-off
("Unable to complete previous operation due to low memory", device-confirmed).
The file-input result is therefore never delivered: the photo dies upstream of
every line of app code, which is why hardening the write path could not reach
it. The envelope work was still necessary — it is what makes a locked capture
persistable — but it could never fix a photo that never arrives.

THE FIX
Remove the hand-off. A protected project captures through an in-app viewfinder:
getUserMedia, rear camera by default, live preview, shutter. The app never
backgrounds, so there is no window for the OS to kill it, and the shutter feeds
straight into the existing envelope pipeline — sealed and persisted within
milliseconds, locked or unlocked. Unprotected projects keep the native camera
path exactly as it was.

RESOLUTION — a sensible default plus max on demand
  * Standard: the existing 1000px ceiling, which is what everyday job
    documentation has been sized to all along. Stored in Settings.
  * Max: one tap in the viewfinder. Uses ImageCapture.takePhoto() where the
    browser has it, because that can pull full sensor resolution rather than
    whatever the preview stream happens to carry; falls back to a canvas grab
    of the live frame. The ceiling lifts; the single-blob storage model is
    untouched. The preset only governs how big that one blob is allowed to be.

LENSES
enumerateDevices() after permission, videoinput only, real labels. The picker
appears only when the device genuinely exposes more than one camera. Many
Androids expose only the main lens and some expose ultrawide/telephoto as
separate devices — whatever is actually there is what is offered. No crop is
ever presented as a lens.

FAILURE HONESTY
If getUserMedia is refused or missing, the reason is stated plainly and the
native camera is offered as an explicit choice with its known risk spelled out.
Never a silent fallback.

Backs up first, applies edits with exact-match anchors, aborts atomically
if anything doesn't match, and validates JS syntax before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "VAULT_CAMERA"
REQUIRES = ["VAULT_ENVELOPE", "VAULT_CORE"]

def fail(msg):
    print(f"\n❌ ABORTED — no changes were made.\n   Reason: {msg}\n")
    sys.exit(1)

def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found in this folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ Already applied — nothing to do.")
        return
    for req in REQUIRES:
        if req not in text:
            fail(f"{req} not found — run the vault scripts first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: CSS for the viewfinder
    # ---------------------------------------------------------------
    old = r"""  .hidden{display:none!important}"""
    new = r"""  /* VAULT_CAMERA — in-app viewfinder */
  #camera{
    position:fixed;inset:0;z-index:115;background:#05070a;
    display:flex;flex-direction:column;
  }
  #camera .cam-top{
    display:flex;align-items:center;justify-content:space-between;gap:10px;
    padding:calc(var(--safe-t) + 10px) 12px 8px;flex:none;
  }
  #camera .cam-title{font-family:var(--serif);font-size:16px;color:var(--paper)}
  #camera .icon-btn{background:rgba(255,255,255,.09)}
  #camera .cam-stage{
    flex:1;position:relative;overflow:hidden;background:#000;
    display:flex;align-items:center;justify-content:center;
  }
  #camera video,#camera .cam-still{
    max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;background:#000;
  }
  #camera .cam-controls{flex:none;padding:10px 12px calc(var(--safe-b) + 14px)}
  #camera .cam-row{display:flex;align-items:center;gap:8px;overflow-x:auto;padding-bottom:8px}
  .cam-chip{
    font-family:var(--mono);font-size:11px;letter-spacing:.06em;padding:7px 13px;border-radius:999px;
    border:1px solid var(--line);background:rgba(255,255,255,.06);color:var(--paper-dim);
    white-space:nowrap;flex:none;
  }
  .cam-chip.on{background:var(--brass);border-color:var(--brass);color:#231a07}
  #camera .cam-shutter-row{display:flex;align-items:center;justify-content:center;gap:22px;margin-top:4px}
  .cam-shutter{
    width:70px;height:70px;border-radius:50%;background:#fff;border:4px solid rgba(255,255,255,.35);
    flex:none;box-shadow:0 4px 18px rgba(0,0,0,.5);
  }
  .cam-shutter:active{transform:scale(.94)}
  #camera .cam-msg{
    padding:26px 22px;color:var(--paper-dim);font-size:14px;line-height:1.65;
    max-width:560px;margin:0 auto;
  }
  #camera .cam-msg b{color:var(--paper);display:block;font-family:var(--serif);font-size:18px;margin-bottom:8px}
  #camera .cam-warn{
    border-left:2px solid var(--danger);padding-left:12px;margin:14px 0;color:var(--paper-dim);font-size:13px;
  }
  #camera .cam-hint{
    text-align:center;font-family:var(--mono);font-size:10px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--paper-faint);padding-top:8px;
  }

  .hidden{display:none!important}"""
    edits.append((old, new, "CSS: viewfinder"))

    # ---------------------------------------------------------------
    # Edit 2: the overlay element
    # ---------------------------------------------------------------
    old = r"""<div id="vault" class="hidden"></div>"""
    new = r"""<div id="vault" class="hidden"></div>
<div id="camera" class="hidden"></div>"""
    edits.append((old, new, "add #camera overlay element"))

    # ---------------------------------------------------------------
    # Edit 3: presets + a downscale that takes a ceiling
    # ---------------------------------------------------------------
    old = r"""function downscale(file){
  return new Promise((res,rej)=>{
    const img=new Image(); const url=URL.createObjectURL(file);
    img.onload=()=>{
      const max=1000; let {width:w,height:h}=img;
      if(w>max||h>max){ const s=max/Math.max(w,h); w=Math.round(w*s); h=Math.round(h*s); }
      const c=document.createElement('canvas'); c.width=w; c.height=h;
      c.getContext('2d').drawImage(img,0,0,w,h);
      c.toBlob(b=>{ URL.revokeObjectURL(url); b?res(b):rej(new Error('encode failed')); },'image/jpeg',0.8);
    };
    img.onerror=()=>{ URL.revokeObjectURL(url); rej(new Error('bad image')); };
    img.src=url;
  });
}"""
    new = r"""/* VAULT_CAMERA — capture presets. The preset governs only how big the single
   stored blob is allowed to be; the storage model is unchanged. Standard is
   the ceiling this app has always used. */
const PHOTO_PRESETS = {
  standard:{ label:'Standard', maxEdge:1000,     quality:0.8,
             hint:'Everyday job documentation. Small files, quick backups.' },
  max:     { label:'Max',      maxEdge:Infinity, quality:0.92,
             hint:'The most the device will give. Much larger files.' }
};
function photoPresetKey(){ return PHOTO_PRESETS[settings.photoPreset] ? settings.photoPreset : 'standard'; }

/* maxEdge/quality default to the original hardcoded values, so every existing
   caller behaves exactly as before. */
function downscale(file, maxEdge, quality){
  const cap = maxEdge || 1000;
  const q   = quality || 0.8;
  return new Promise((res,rej)=>{
    const img=new Image(); const url=URL.createObjectURL(file);
    img.onload=()=>{
      let {width:w,height:h}=img;
      if(w>cap||h>cap){ const s=cap/Math.max(w,h); w=Math.round(w*s); h=Math.round(h*s); }
      const c=document.createElement('canvas'); c.width=w; c.height=h;
      c.getContext('2d').drawImage(img,0,0,w,h);
      c.toBlob(b=>{ URL.revokeObjectURL(url); b?res(b):rej(new Error('encode failed')); },'image/jpeg',q);
    };
    img.onerror=()=>{ URL.revokeObjectURL(url); rej(new Error('bad image')); };
    img.src=url;
  });
}

/* One place that decides how a captured or imported image is sized before it
   goes down the write path. alreadyJpeg is true for our own canvas/ImageCapture
   output, which at Max is passed through untouched rather than re-encoded. */
async function preparePhotoBlob(src, presetKey, alreadyJpeg){
  const p = PHOTO_PRESETS[presetKey] || PHOTO_PRESETS.standard;
  if(p.maxEdge===Infinity && alreadyJpeg) return src;
  return downscale(src, p.maxEdge, p.quality);
}"""
    edits.append((old, new, "photo presets + parameterised downscale"))

    # ---------------------------------------------------------------
    # Edit 4: the viewfinder itself
    # ---------------------------------------------------------------
    old = r"""/* ===== SORTED ENGINE START ====="""
    new = r"""/* ============================================================
   VAULT_CAMERA — in-app viewfinder
   ------------------------------------------------------------
   Android reclaims the browser process during the native-camera hand-off, so
   the file-input result never arrives and the photo is lost before any app
   code sees it. The cure is not to hand off: we never leave the app, so there
   is no window for the OS to kill. The shutter feeds the same envelope write
   path everything else uses.
   ============================================================ */
const $camera=document.getElementById('camera');
let cam={ open:false, houseId:null, stream:null, imageCapture:null,
          devices:[], deviceId:null, presetKey:'standard', shot:null, error:null };

function camStop(){
  /* Complete teardown: tracks stopped, srcObject cleared, references dropped.
     A live indicator light after leaving the viewfinder is not acceptable. */
  try{ if(cam.stream) cam.stream.getTracks().forEach(t=>{ try{ t.stop(); }catch(e){} }); }catch(e){}
  cam.stream=null; cam.imageCapture=null;
  const v=document.getElementById('cam-video');
  if(v){ try{ v.pause(); }catch(e){} try{ v.srcObject=null; }catch(e){} }
}
function camClose(){
  camStop();
  if(cam.shot && cam.shot.url){ try{ URL.revokeObjectURL(cam.shot.url); }catch(e){} }
  cam={ open:false, houseId:null, stream:null, imageCapture:null,
        devices:[], deviceId:null, presetKey:'standard', shot:null, error:null };
  $camera.classList.add('hidden'); $camera.innerHTML='';
  document.body.style.overflow='';
  render();
}

async function openCamera(houseId){
  const h=houseById(houseId); if(!h) return;
  cam={ open:true, houseId, stream:null, imageCapture:null, devices:[], deviceId:null,
        presetKey:photoPresetKey(), shot:null, error:null };
  document.body.style.overflow='hidden';
  $camera.classList.remove('hidden');
  if(!settings.camIntroSeen){ camDrawIntro(); return; }
  camDrawLoading();
  await camStart();
}

function camDrawIntro(){
  $camera.innerHTML='<div class="cam-top">'
    +'<button class="icon-btn" data-cam-close aria-label="Cancel">'+I.x+'</button>'
    +'<span class="cam-title">Camera</span><span style="width:46px"></span></div>'
    +'<div class="cam-stage" style="align-items:flex-start"><div class="cam-msg">'
    +'<b>Notebuilt needs the camera</b>'
    +'For a protected project the photo is taken inside the app rather than by handing you '
    +'to the phone\'s camera app. That hand-off is where photos have been getting lost: '
    +'Android can reclaim Notebuilt while the camera app is in front, and the picture never '
    +'comes back. Taking it here means it is encrypted and saved within milliseconds, and '
    +'there is no moment where it can go missing.<br><br>'
    +'Your phone will ask for permission next. The camera runs only while this screen is '
    +'open, and nothing leaves the device.'
    +'</div></div>'
    +'<div class="cam-controls">'
    +'<button class="btn primary block" data-cam-allow>Continue</button>'
    +'<button class="btn block" data-cam-close style="margin-top:8px">Not now</button></div>';
  camBind();
}
function camDrawLoading(){
  $camera.innerHTML='<div class="cam-top">'
    +'<button class="icon-btn" data-cam-close aria-label="Close">'+I.x+'</button>'
    +'<span class="cam-title">Camera</span><span style="width:46px"></span></div>'
    +'<div class="cam-stage"><div class="cam-msg" style="text-align:center">Starting the camera…</div></div>'
    +'<div class="cam-controls"></div>';
  camBind();
}

/* Say what went wrong and offer the native path as an explicit choice, with the
   risk stated. Never a silent fallback. */
function camDrawError(err){
  const name=(err&&err.name)||'';
  let why;
  if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia)
    why='This browser does not offer in-app camera access.';
  else if(name==='NotAllowedError'||name==='SecurityError')
    why='Camera permission was refused, so the viewfinder cannot open. You can change that in your browser\'s site settings for this app.';
  else if(name==='NotFoundError'||name==='OverconstrainedError')
    why='No camera was found on this device.';
  else if(name==='NotReadableError')
    why='The camera is in use by another app, or the system would not release it.';
  else
    why='The camera could not be started'+(name?' ('+name+')':'')+'.';
  $camera.innerHTML='<div class="cam-top">'
    +'<button class="icon-btn" data-cam-close aria-label="Close">'+I.x+'</button>'
    +'<span class="cam-title">Camera unavailable</span><span style="width:46px"></span></div>'
    +'<div class="cam-stage" style="align-items:flex-start"><div class="cam-msg">'
    +'<b>The in-app camera did not open</b>'+esc(why)
    +'<div class="cam-warn">You can still use the phone\'s own camera app, but be aware of '
    +'what that risks: Android can reclaim Notebuilt while the camera app is in front, and '
    +'when that happens the photo is lost before it ever reaches this app. That is the exact '
    +'failure the in-app camera exists to avoid.</div>'
    +'</div></div>'
    +'<div class="cam-controls">'
    +'<label class="btn block" style="display:flex;align-items:center;justify-content:center;gap:8px">'
    +I.camera+' Use the phone camera anyway'
    +'<input type="file" accept="image/*" capture="environment" hidden data-cam-native></label>'
    +'<button class="btn block" data-cam-close style="margin-top:8px">Cancel</button></div>';
  camBind();
}

async function camStart(deviceId){
  camStop();
  const base={ width:{ideal:4096}, height:{ideal:4096} };
  const video = deviceId ? Object.assign({deviceId:{exact:deviceId}}, base)
                         : Object.assign({facingMode:{ideal:'environment'}}, base);
  try{
    if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error('unsupported');
    cam.stream=await navigator.mediaDevices.getUserMedia({video, audio:false});
  }catch(err){
    /* an exact deviceId that the phone will not honour: fall back to any camera
       rather than dead-ending on a lens choice */
    if(deviceId){ return camStart(null); }
    cam.error=err; camDrawError(err); return;
  }
  settings.camIntroSeen=true; persist.settings();
  const track=cam.stream.getVideoTracks()[0];
  cam.deviceId = track && track.getSettings ? (track.getSettings().deviceId||null) : null;
  /* ImageCapture can pull full sensor resolution, past whatever the preview
     stream carries. Only worth it at Max. */
  cam.imageCapture=null;
  try{ if(window.ImageCapture && track) cam.imageCapture=new ImageCapture(track); }catch(e){}
  await camListDevices();
  camDrawLive();
}

/* Only what the device genuinely exposes. Labels are blank until permission has
   been granted, which is why this runs after getUserMedia. */
async function camListDevices(){
  cam.devices=[];
  try{
    const all=await navigator.mediaDevices.enumerateDevices();
    cam.devices=all.filter(d=>d.kind==='videoinput');
  }catch(e){}
}

function camDrawLive(){
  const multi=cam.devices.length>1;
  const lensRow = multi
    ? '<div class="cam-row">'+cam.devices.map((d,i)=>
        '<button class="cam-chip'+(d.deviceId===cam.deviceId?' on':'')+'" data-cam-lens="'+esc(d.deviceId)+'">'
        +esc(d.label||('Camera '+(i+1)))+'</button>').join('')+'</div>'
    : '';
  const presetRow='<div class="cam-row">'
    +Object.keys(PHOTO_PRESETS).map(k=>
      '<button class="cam-chip'+(k===cam.presetKey?' on':'')+'" data-cam-preset="'+k+'">'
      +esc(PHOTO_PRESETS[k].label)+'</button>').join('')
    +'<span class="cam-chip" style="border:none;background:none;color:var(--paper-faint)">'
    +esc(PHOTO_PRESETS[cam.presetKey].hint)+'</span></div>';
  $camera.innerHTML='<div class="cam-top">'
    +'<button class="icon-btn" data-cam-close aria-label="Close">'+I.x+'</button>'
    +'<span class="cam-title">'+esc((houseById(cam.houseId)||{}).name||'Camera')+'</span>'
    +'<span style="width:46px"></span></div>'
    +'<div class="cam-stage"><video id="cam-video" playsinline autoplay muted></video></div>'
    +'<div class="cam-controls">'+lensRow+presetRow
    +'<div class="cam-shutter-row"><button class="cam-shutter" data-cam-shoot aria-label="Take photo"></button></div>'
    +'<div class="cam-hint">'+(multi?'Pick a lens · ':'')+'Tap Max for full resolution</div>'
    +'</div>';
  const v=document.getElementById('cam-video');
  if(v && cam.stream){ v.srcObject=cam.stream; v.play().catch(()=>{}); }
  camBind();
}

function camDrawReview(){
  $camera.innerHTML='<div class="cam-top">'
    +'<button class="icon-btn" data-cam-close aria-label="Close">'+I.x+'</button>'
    +'<span class="cam-title">Keep this one?</span><span style="width:46px"></span></div>'
    +'<div class="cam-stage"><img class="cam-still" src="'+cam.shot.url+'" alt="Captured photo"></div>'
    +'<div class="cam-controls">'
    +'<div class="cam-hint" style="padding-bottom:10px">'
    +esc(cam.shot.w+' × '+cam.shot.h+' · '+PHOTO_PRESETS[cam.presetKey].label)+'</div>'
    +'<div class="row" style="gap:10px">'
    +'<button class="btn" style="flex:1" data-cam-retake>Retake</button>'
    +'<button class="btn primary" style="flex:1" data-cam-keep>Keep</button></div></div>';
  camBind();
}

async function camGrabFrame(){
  const v=document.getElementById('cam-video'); if(!v) return null;
  const w=v.videoWidth, h=v.videoHeight; if(!w||!h) return null;
  const c=document.createElement('canvas'); c.width=w; c.height=h;
  c.getContext('2d').drawImage(v,0,0,w,h);
  return new Promise(res=>c.toBlob(b=>res(b),'image/jpeg',PHOTO_PRESETS[cam.presetKey].quality));
}

async function camShoot(){
  const btn=$camera.querySelector('[data-cam-shoot]'); if(btn) btn.setAttribute('disabled','');
  let blob=null;
  if(cam.presetKey==='max' && cam.imageCapture){
    /* full sensor resolution where the browser offers it */
    try{ blob=await cam.imageCapture.takePhoto(); }catch(e){ blob=null; }
  }
  if(!blob) blob=await camGrabFrame();
  if(!blob){ if(btn) btn.removeAttribute('disabled'); toast('Could not capture that frame'); return; }
  const url=URL.createObjectURL(blob);
  const dims=await new Promise(res=>{ const im=new Image();
    im.onload=()=>res({w:im.naturalWidth,h:im.naturalHeight}); im.onerror=()=>res({w:0,h:0}); im.src=url; });
  cam.shot={ blob, url, w:dims.w, h:dims.h };
  camDrawReview();
}

function camRetake(){
  if(cam.shot && cam.shot.url){ try{ URL.revokeObjectURL(cam.shot.url); }catch(e){} }
  cam.shot=null;
  camDrawLive();
}

/* The captured frame goes down the SAME write path as everything else:
   photoPutFor() seals it symmetrically when unlocked and envelopes it when
   not, and the list is persisted immediately after. */
async function camKeep(){
  if(!cam.shot) return;
  const houseId=cam.houseId, h=houseById(houseId);
  if(!h){ camClose(); return; }
  const keepBtn=$camera.querySelector('[data-cam-keep]');
  if(keepBtn){ keepBtn.setAttribute('disabled',''); keepBtn.textContent='Saving…'; }
  try{
    const blob=await preparePhotoBlob(cam.shot.blob, cam.presetKey, true);
    const id=uid();
    await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
    h.photos=h.photos||[]; h.photos.push(id);
    if(!h.cover) h.cover=id;
    h.updatedAt=now(); persist.houses();
    if(cam.shot.url){ try{ URL.revokeObjectURL(cam.shot.url); }catch(e){} }
    cam.shot=null;
    toast('Photo saved');
    camDrawLive();                       /* straight back to the viewfinder */
  }catch(err){
    if(keepBtn){ keepBtn.removeAttribute('disabled'); keepBtn.textContent='Keep'; }
    toast(String(err&&err.message)==='no capture key'
      ? 'Unlock the vault once to turn on locked capture'
      : 'Could not save that photo');
  }
}

function camBind(){
  $camera.querySelectorAll('[data-cam-close]').forEach(b=>b.onclick=camClose);
  const allow=$camera.querySelector('[data-cam-allow]');
  if(allow) allow.onclick=async()=>{ camDrawLoading(); await camStart(); };
  const shoot=$camera.querySelector('[data-cam-shoot]'); if(shoot) shoot.onclick=camShoot;
  const retake=$camera.querySelector('[data-cam-retake]'); if(retake) retake.onclick=camRetake;
  const keep=$camera.querySelector('[data-cam-keep]'); if(keep) keep.onclick=camKeep;
  $camera.querySelectorAll('[data-cam-lens]').forEach(b=>b.onclick=async()=>{
    camDrawLoading(); await camStart(b.getAttribute('data-cam-lens'));
  });
  $camera.querySelectorAll('[data-cam-preset]').forEach(b=>b.onclick=()=>{
    cam.presetKey=b.getAttribute('data-cam-preset'); camDrawLive();
  });
  const native=$camera.querySelector('[data-cam-native]');
  if(native) native.onchange=async e=>{
    const hid=cam.houseId;
    camClose();
    captureBegin();                      /* the hand-off risk, now chosen knowingly */
    await handlePhoto(e,hid);
  };
}

/* Release the camera if the app goes out of sight, and pick it back up on
   return. Leaving a live stream running behind a hidden page is not on. */
document.addEventListener('visibilitychange',()=>{
  if(!cam.open) return;
  if(document.visibilityState==='hidden') camStop();
  else if(!cam.stream && !cam.shot && !cam.error) camStart(cam.deviceId);
});
window.addEventListener('pagehide',()=>{ if(cam.open) camStop(); });

/* ===== SORTED ENGINE START ====="""
    edits.append((old, new, "the in-app viewfinder"))

    # ---------------------------------------------------------------
    # Edit 5: protected projects get the viewfinder, others keep the native path
    # ---------------------------------------------------------------
    old = r"""      <label class="photo-add" aria-label="Take photo">${I.camera}<span>Camera</span><input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>"""
    new = r"""      ${h.protected
        ? `<button class="photo-add" data-open-camera="${h.id}" aria-label="Take photo">${I.camera}<span>Camera</span></button>`
        : `<label class="photo-add" aria-label="Take photo">${I.camera}<span>Camera</span><input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>`}"""
    edits.append((old, new, "renderHouse: viewfinder for protected projects"))

    # ---------------------------------------------------------------
    # Edit 6: wire it
    # ---------------------------------------------------------------
    old = r"""  $app.querySelectorAll('[data-add-photo]').forEach(el=>{
    el.onclick=()=>captureBegin();
    el.onchange=e=>handlePhoto(e,view.param);
  });"""
    new = r"""  $app.querySelectorAll('[data-add-photo]').forEach(el=>{
    el.onclick=()=>captureBegin();
    el.onchange=e=>handlePhoto(e,view.param);
  });
  /* VAULT_CAMERA — a protected project never hands off to the camera app. */
  $app.querySelectorAll('[data-open-camera]').forEach(b=>b.onclick=()=>openCamera(b.dataset.openCamera));"""
    edits.append((old, new, "bind(): open the viewfinder"))

    # ---------------------------------------------------------------
    # Edit 7: handlePhoto honours the preset too
    # ---------------------------------------------------------------
    old = r"""    try{ blob=await downscale(file); }catch(err){ failed++; continue; }"""
    new = r"""    try{ blob=await preparePhotoBlob(file, photoPresetKey(), false); }catch(err){ failed++; continue; }"""
    edits.append((old, new, "handlePhoto(): honour the preset"))

    # ---------------------------------------------------------------
    # Edit 8: Settings — the default preset
    # ---------------------------------------------------------------
    old = r"""    <div class="sec-head"><span class="label">About</span><span class="rule"></span></div>"""
    new = r"""    <div class="sec-head"><span class="label">Photos</span><span class="rule"></span></div>
    <div class="card row"><div class="grow"><div>Capture size</div><div class="muted" style="font-size:13px">${esc(PHOTO_PRESETS[photoPresetKey()].hint)} You can switch to Max for a single shot from the viewfinder.</div></div>
      <div class="unit-toggle">${Object.keys(PHOTO_PRESETS).map(k=>`<button class="${k===photoPresetKey()?'on':''}" data-photo-preset="${k}">${esc(PHOTO_PRESETS[k].label)}</button>`).join('')}</div></div>

    <div class="sec-head"><span class="label">About</span><span class="rule"></span></div>"""
    edits.append((old, new, "Settings: capture size preset"))

    old = r"""  $app.querySelectorAll('[data-units-set]').forEach(b=>b.onclick=()=>{ settings.units=b.dataset.unitsSet; persist.settings(); render(); });"""
    new = r"""  $app.querySelectorAll('[data-units-set]').forEach(b=>b.onclick=()=>{ settings.units=b.dataset.unitsSet; persist.settings(); render(); });
  $app.querySelectorAll('[data-photo-preset]').forEach(b=>b.onclick=()=>{ settings.photoPreset=b.dataset.photoPreset; persist.settings(); render(); toast('Capture size: '+PHOTO_PRESETS[photoPresetKey()].label); });"""
    edits.append((old, new, "bind(): preset toggle"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # A protected project must not be able to reach a capture=environment input.
    m = re.search(r"\$\{h\.protected\s*\n\s*\?\s*`<button class=\"photo-add\" data-open-camera", working)
    if not m:
        fail("protected-project camera branch not found after edit.")
    print("✅ assertion: protected projects route to the in-app viewfinder")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit; restored from backup.")
    js_path = Path("/tmp/_notebuilt_camera_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ In-app camera applied: protected projects never hand off to the camera app.")

if __name__ == "__main__":
    main()
