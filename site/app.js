"use strict";
const $=id=>document.getElementById(id);
const siteState={config:null,entries:[],active:null,mode:"learner",details:new Map(),approvedPhotos:{}};
const hub="https://crking92.github.io/Hays-County-Botany/";
function setText(node,text){node.textContent=String(text??"");return node}
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)setText(n,text);if(cls)n.className=cls;return n}
function clear(node){node.replaceChildren()}
function statusMessage(title,body){const d=$("detail");clear(d);d.append(el("h3",title),el("p",body))}
function renderList(){
 const result=$("results");clear(result);
 const q=$("search").value.trim().toLocaleLowerCase();
 const list=siteState.entries.filter(x=>(String(x.scientific_name||"")+" "+String(x.common_name||"")).toLocaleLowerCase().includes(q));
 if(!siteState.entries.length){result.append(el("p","No species in this collection release. Open the legacy Hays Botany learner for older records.","muted"));return}
 if(!list.length){result.append(el("p","No matching plants in this collection.","muted"));return}
 for(const s of list){
   const b=el("button");b.type="button";b.append(el("strong",s.common_name||s.scientific_name),el("em",s.scientific_name));
   if(s.id===siteState.active)b.setAttribute("aria-current","true");
   b.addEventListener("click",()=>select(s.id,true));result.append(b);
 }
}
async function select(id,push){
 const r=siteState.entries.find(x=>x.id===id);
 if(!r){statusMessage("Plant not available","That species has not been imported or verified in this family collection.");return}
 siteState.active=id;renderList();
 if(push){const url=new URL(location.href);url.searchParams.set("species",id);history.pushState({species:id},"",url)}
 const d=$("detail");clear(d);d.append(el("p",r.family+" · "+r.genus,"sectionnum"),el("h3",r.common_name||r.scientific_name),el("p",r.scientific_name,"latin"));
 try{
   if(!siteState.details.has(id)){
     const resp=await fetch("data/species/"+encodeURIComponent(id)+".json");
     if(!resp.ok)throw Error("Verified teaching summary is not available yet");
     siteState.details.set(id,await resp.json());
   }
   if(siteState.active!==id)return;
   const card=siteState.details.get(id);
   const photos=siteState.approvedPhotos[id]||[];
   d.append(el("p",photos.length?`${photos.length} individually credited historical photograph${photos.length===1?"":"s"} released from an exact-source CC license review. Other images remain held.`:"Field-identification text from the existing Hays Botany scientific record. Photographs for this species remain withheld pending source-specific reuse review.","muted"));
   if(card.look_here_first){
     d.append(el("h3","LOOK HERE FIRST"));
     d.append(el("p",card.look_here_first));
   }
   if(siteState.mode==="learner" && Array.isArray(card.key_traits)&&card.key_traits.length){
     d.append(el("h3","Anatomy and field recognition"));
     const list=el("ul");
     for(const trait of card.key_traits.slice(0,10)){
       const li=el("li");li.append(el("strong",trait.label+": "),document.createTextNode(trait.text));list.append(li);
     }
     d.append(list);
   }
   if(card.lookalikes){
     d.append(el("h3","Look-alikes"));
     if(card.lookalikes.names?.length)d.append(el("p","Compare with: "+card.lookalikes.names.join(", ")));
     if(card.lookalikes.differences)d.append(el("p",card.lookalikes.differences));
   }
   if(photos.length){
     const heading=el("h3","Real species photographs");d.append(heading);
     d.append(el("p","Scroll sideways to compare the photographed structures. Image rights vary by photograph; review each caption. Anatomy arrows have not yet been individually certified.","muted"));
     const strip=el("div",undefined,"gallery-strip");
     for(const photo of photos){
       const fig=el("figure",undefined,"gallery-photo");
       const link=document.createElement("a");link.href=photo.src;link.target="_blank";link.rel="noopener noreferrer";link.setAttribute("aria-label","Open original-size preview of "+(photo.role||card.scientific_name));
       const image=document.createElement("img");image.src=photo.src;image.loading="lazy";image.alt=card.scientific_name+": "+(photo.role||"verified species photograph");
       link.append(image);fig.append(link);
       const cap=el("figcaption");cap.append(el("strong",photo.role||"Species photograph"),el("small","Photo: "+photo.creator+" · "+photo.license+". Resized for this learner, source credited."));
       if(photo.noncommercial_only)cap.append(el("small","NONCOMMERCIAL-ONLY reuse. No commercial use or redistribution outside license terms.","photo-nc"));
       if(photo.private_rights_review_only)cap.append(el("small",photo.rights_note||"Private review: public license verification still required.","photo-review"));
       const sources=el("div",undefined,"source-links");
       for(const [label,url] of [[photo.source_page_is_exact===false?"Related iNaturalist reference (exact photo page pending)":"Photo source",photo.source_page],["License",photo.license_url]]){
         if(!url||!url.startsWith("https://"))continue;
         const a=el("a",label);a.href=url;a.target="_blank";a.rel="noopener noreferrer";sources.append(a);
       }
       cap.append(sources);fig.append(cap);strip.append(fig);
     }
     d.append(strip);
   }else d.append(el("p","Photographs for this species are held for source-rights or visual review. Its text lesson is available; see the current main learner for any existing images.","muted"));

 }catch(error){
   if(siteState.active===id)d.append(el("p","Teaching summary pending: "+error.message,"muted"));
 }
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
   const [confResp,indexResp,photosResp]=await Promise.all([fetch("data/collection-meta.json"),fetch("data/collection-index.json"),fetch("data/reviewed-external-photo-manifest.json")]);
   if(!confResp.ok||!indexResp.ok||!photosResp.ok)throw Error("collection or approved photo manifest missing");
   siteState.config=await confResp.json();const doc=await indexResp.json();const photoDoc=await photosResp.json();
   if(photoDoc.schema_version!==1||!photoDoc.species||typeof photoDoc.species!=="object")throw Error("approved photo manifest invalid");
   siteState.approvedPhotos=photoDoc.species;
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
