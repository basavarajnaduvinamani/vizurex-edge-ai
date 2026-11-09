export const $=id=>document.getElementById(id);
export function el(tag,attrs={},...children){
  const node=document.createElement(tag);for(const [key,value]of Object.entries(attrs)){
    if(key.startsWith('on')&&typeof value==='function')node.addEventListener(key.slice(2),value);
    else if(key==='class')node.className=value;else if(value!==false&&value!==null)node.setAttribute(key,value===true?'':String(value));
  }
  for(const child of children.flat())if(child!==null&&child!==undefined)node.append(typeof child==='string'?document.createTextNode(child):child);
  return node;
}
export function button(text,action,attrs={}){return el('button',{type:'button',onclick:action,...attrs},text);}
export function option(value,text=value){return el('option',{value},text);}
export function field(label,id,data,{type='text',options=null,readonly=false}={}){
  const input=options?el('select',{id,name:id},...options.map(item=>typeof item==='string'?option(item):option(item.value,item.label))):el(type==='textarea'?'textarea':'input',{id,name:id,...(type==='textarea'?{rows:3}:{type}),...(readonly?{readonly:true}:{})});
  input.value=data.value??'';
  const hint=el('span',{class:'provenance'},`${data.source}${data.confirmed?' / confirmed':' / suggestion, confirm or edit'}`);
  const wrapper=el('label',{class:!data.confirmed?'suggested':'',for:id},label,input,hint);
  if(!readonly)input.addEventListener('input',()=>{data.source='human';data.confirmed=true;wrapper.classList.remove('suggested');hint.textContent='human / confirmed';});
  return wrapper;
}
export function download(name,text,type='text/plain'){
  const blob=new Blob([text],{type}),url=URL.createObjectURL(blob),a=el('a',{href:url,download:name});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function notify(text,error=false){const message=$('platform-message');message.textContent=text;message.setAttribute('role',error?'alert':'status');message.classList.toggle('error',error);}
export function safe(action){return async(...args)=>{try{await action(...args);}catch(error){console.error('Platform operation failed:',error.message);notify(error.message,true);}};}
export const roleName=role=>({inspector:'Inspector',qa_lead:'QA lead',plant_manager:'Plant manager'}[role]||role);
