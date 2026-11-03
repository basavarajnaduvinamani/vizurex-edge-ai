const STORES=['walks','findings','ncrs','actions','audit','meta'];
let opening;
export function openStore(){
  if(!opening)opening=new Promise((resolve,reject)=>{
    const request=indexedDB.open('visurex-platform-v1',1);
    request.onupgradeneeded=()=>STORES.forEach(name=>request.result.createObjectStore(name,{keyPath:'id'}));
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });return opening;
}
export async function all(store){const db=await openStore();return new Promise((resolve,reject)=>{
  const request=db.transaction(store).objectStore(store).getAll();request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
});}
export async function saveMany(entries){
  const db=await openStore(),names=[...new Set(entries.map(e=>e.store))];
  return new Promise((resolve,reject)=>{
    const tx=db.transaction(names,'readwrite');tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Storage transaction aborted'));
    for(const {store,record,addOnly=false} of entries){
      const object=tx.objectStore(store);
      if(store==='audit'||addOnly)object.add(record);else object.put(record);
    }
  });
}
export async function snapshot(){const rows=await Promise.all(STORES.slice(0,5).map(all));return Object.fromEntries(STORES.slice(0,5).map((name,i)=>[name,rows[i]]));}
export async function updateNcr(next,event,additional=[]){
  const db=await openStore();return new Promise((resolve,reject)=>{
    const tx=db.transaction([...new Set(['ncrs','audit',...additional.map(e=>e.store)])],'readwrite'),object=tx.objectStore('ncrs'),request=object.get(next.id);
    request.onsuccess=()=>{if(request.result&&next.revision!==request.result.revision+1){tx.abort();return;}
      object.put(next);tx.objectStore('audit').add(event);for(const entry of additional)tx.objectStore(entry.store).add(entry.record);};
    tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(Error('Record changed or duplicate audit ID; reload and retry'));
  });
}
