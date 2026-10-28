"use strict";
const $=id=>document.getElementById(id);
const siteState={config:null,entries:[],active:null,mode:"learner"};
const hub="https://crking92.github.io/Hays-County-Botany/";
function setText(node,text){node.textContent=String(text??"");return node}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)setText(n,text);if(cls)n.className=cls;return n}
function clear(node){node.replaceChildren()}
function statusMessage(title,body){const d=$("detail");clear(d);d.append(el("h3",title),el("p",body))}
function renderList(){
 const result=$("results");clear(result);
 const q=$("search").value.trim().toLocaleLowerCase();
 const list=siteState.entries.filter(x=>(String(x.scientific_name||"")+" "+String(x.common_name||"")).toLocaleLowerCase().includes(q));
 if(!siteState.entries.length){result.append(el("p","No species imported yet. The existing main Hays Botany learner still contains the authoritative cards.","muted"));return}
 if(!list.length){result.append(el("p","No matching plants in this collection.","muted"));return}
 for(const s of list){
   const b=el("button");b.type="button";b.append(el("strong",s.common_name||s.scientific_name),el("em",s.scientific_name));
   if(s.id===siteState.active)b.setAttribute("aria-current","true");
   b.addEventListener("click",()=>select(s.id,true));result.append(b);
 }
}
function select(id,push){
 const r=siteState.entries.find(x=>x.id===id);
 if(!r){statusMessage("Plant not available","That species has not been imported or verified in this family collection.");return}
 siteState.active=id;renderList();
 const d=$("detail");clear(d);d.append(el("p",r.family+" · "+r.genus,"sectionnum"),el("h3",r.common_name||r.scientific_name),el("p",r.scientific_name,"latin"));
 d.append(el("p","A verified "+(siteState.mode==="learner"?"visual lesson":"field-identification tile")+" will be displayed here after source data, photos, and anatomy annotations have passed the migration and publication reviews.","muted"));
 if(push){const url=new URL(location.href);url.searchParams.set("species",id);history.pushState({species:id},"",url)}
}
function setMode(mode){
 siteState.mode=mode;
 for(const b of document.querySelectorAll("[data-mode]"))b.setAttribute("aria-pressed",String(b.dataset.mode===mode));
 $("nav-learner").setAttribute("aria-current",mode==="learner"?"page":"false");
 $("nav-field").setAttribute("aria-current",mode==="field"?"page":"false");
 if(siteState.active)select(siteState.active,false);
 else statusMessage(mode==="learner"?"Choose a species to begin":"Field ID tiles","This is a preview shell. Species lessons will appear only after the first verified import.");
}
async function boot(){
 try{
   const [confResp,indexResp]=await Promise.all([fetch("data/collection-meta.json"),fetch("data/collection-index.json")]);
   if(!confResp.ok||!indexResp.ok)throw Error("collection metadata missing");
   siteState.config=await confResp.json();const doc=await indexResp.json();
   if(!Array.isArray(doc.entries))throw Error("invalid collection index");
   siteState.entries=doc.entries;
   const label=siteState.config.repository_full_name.split("/")[1].replace("Hays-Botany-","").replaceAll("-"," ");
   $("collection-title").textContent=label+" Visual Learner";
   $("family-count").textContent=siteState.config.family_assignments.length;
   $("species-count").textContent=siteState.entries.length;
   for(const b of document.querySelectorAll("[data-mode]"))b.addEventListener("click",()=>setMode(b.dataset.mode));
   $("nav-learner").addEventListener("click",()=>setMode("learner"));
   $("nav-field").addEventListener("click",()=>setMode("field"));
   $("search").addEventListener("input",renderList);
   window.addEventListener("popstate",()=>{const id=new URLSearchParams(location.search).get("species");if(id)select(id,false);else{siteState.active=null;renderList();statusMessage("Choose a species to begin","Select a verified plant from the collection.")}});
   renderList();
   const wanted=new URLSearchParams(location.search).get("species");
   if(wanted)select(wanted,false);else setMode("learner");
 }catch(e){statusMessage("Preview could not load",e.message)}
}
boot();
