'use strict';
// Transfer only. Processing is queued separately and does not depend on this page.
class JGResumableUpload {
 constructor({api,putChunk,persist,onProgress,onComplete,onPause,onExpired}){Object.assign(this,{api,putChunk,persist,onProgress,onComplete,onPause,onExpired});this.running=false;this.file=null;this.state=null;this.controller=null}
 static async fingerprint(file){const sample=new Blob([String(file.size),await file.slice(0,65536).arrayBuffer(),await file.slice(Math.max(0,file.size-65536)).arrayBuffer()]);return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await sample.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('')}
 pause(){this.controller?.abort()}
 async call(url,options={}){const timeout=setTimeout(()=>this.controller.abort(),20000);try{return await this.api(url,{...options,signal:this.controller.signal})}finally{clearTimeout(timeout)}}
 async resume(file){
  if(this.running||!this.state)return;
  this.running=true;this.controller=new AbortController();
  try{
   if(file){if(file.size!==this.state.size||await JGResumableUpload.fingerprint(file)!==this.state.fingerprint){this.onPause('Escolha o mesmo vídeo para retomar ou cancele o envio anterior.',false);return}this.file=file}
   if(!this.state.id&&!this.file){this.onPause('Selecione novamente o mesmo vídeo e toque em Retomar envio.',false);return}
   if(!this.state.id){const d=await this.call('/api/uploads?'+this.state.params,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:this.state.client_id,name:this.state.name,size:this.state.size,fingerprint:this.state.fingerprint})});this.state.id=d.id;this.persist(this.state)}
   const info=await this.call('/api/jobs/'+this.state.id);
   if(info.status!=='uploading'){if(['cancelled','cancelling'].includes(info.status))throw Object.assign(Error('Envio cancelado.'),{status:404});this.onComplete(this.state.id);return}
   if(info.upload_fingerprint!==this.state.fingerprint||info.upload_total!==this.state.size)throw Error('O vídeo não corresponde ao envio pendente.');
   if(!this.file){this.onPause('Selecione novamente o mesmo vídeo e toque em Retomar envio. Os trechos recebidos estão guardados.',false);return}
   let offset=info.upload_received;
   while(offset<this.file.size){
    if(this.controller.signal.aborted)throw new DOMException('Envio pausado.','AbortError');
    const end=Math.min(offset+4*1024*1024,this.file.size),ack=await this.putChunk('/api/uploads/'+this.state.id+'?offset='+offset,this.file.slice(offset,end),this.controller.signal,n=>this.onProgress(offset+n,this.file.size));
    if(ack.upload_received!==end)throw Error('Não foi possível confirmar o trecho. Vou consultar o servidor para retomar.');offset=end;this.onProgress(offset,this.file.size);
   }
   await this.call('/api/uploads/'+this.state.id+'/complete',{method:'POST'});this.onComplete(this.state.id);
  }catch(e){if(e.status===404)this.onExpired();else this.onPause(e.name==='AbortError'?'Envio pausado. Retomaremos do último trecho confirmado.':e.message,!e.status||[408,409,429,500,502,503,504].includes(e.status))}
  finally{this.running=false;this.controller=null}
 }
}
window.JGResumableUpload=JGResumableUpload;
