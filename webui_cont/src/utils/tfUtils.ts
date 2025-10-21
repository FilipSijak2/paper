/* Migrated tfUtils */
import * as THREE from 'three';
import { Ros } from 'roslib';

export interface TransformStore { [childFrame: string]: { parentFrame: string; transform: { translation: THREE.Vector3; rotation: THREE.Quaternion; }; isStatic: boolean; }; }
export type StoredTransform = { translation: THREE.Vector3; rotation: THREE.Quaternion; };
export const IDENTITY_TRANSFORM: StoredTransform = { translation: new THREE.Vector3(0,0,0), rotation: new THREE.Quaternion(0,0,0,1) };

export function invertTransform(transform: StoredTransform): StoredTransform {
  let invQ: THREE.Quaternion;
  if (typeof transform.rotation.invert === 'function') invQ = transform.rotation.clone().invert();
  else if (typeof transform.rotation.inverse === 'function') invQ = transform.rotation.clone().inverse();
  else {
    invQ = new THREE.Quaternion(-transform.rotation.x, -transform.rotation.y, -transform.rotation.z, transform.rotation.w);
    const len = Math.sqrt(invQ.x*invQ.x + invQ.y*invQ.y + invQ.z*invQ.z + invQ.w*invQ.w);
    if (len>0){ invQ.x/=len; invQ.y/=len; invQ.z/=len; invQ.w/=len; }
  }
  const invT = transform.translation.clone().negate(); invT.applyQuaternion(invQ);
  return { translation: invT, rotation: invQ };
}

export function multiplyTransforms(a: StoredTransform, b: StoredTransform): StoredTransform {
  return { translation: a.translation.clone().add(b.translation.clone().applyQuaternion(a.rotation)), rotation: a.rotation.clone().multiply(b.rotation) };
}

export function findTransformPath(targetFrame: string, sourceFrame: string, transforms: TransformStore): { frame: string; transform: StoredTransform; isStatic: boolean }[] | null {
  if (targetFrame === sourceFrame) return [];
  const queue: { frame: string; path: { frame: string; transform: StoredTransform; isStatic: boolean }[] }[] = [{ frame: sourceFrame, path: [] }];
  const visited = new Set<string>([sourceFrame]);
  while (queue.length) {
    const current = queue.shift(); if (!current) continue; const cf = current.frame;
    for (const child in transforms) {
      const data = transforms[child];
      if (data.parentFrame === cf && !visited.has(child)) {
        const newPath = [...current.path, { frame: child, transform: data.transform, isStatic: data.isStatic }];
        if (child === targetFrame) return newPath;
        visited.add(child); queue.push({ frame: child, path: newPath });
      }
    }
    const parentData = transforms[cf];
    if (parentData && !visited.has(parentData.parentFrame)) {
      const inv = invertTransform(parentData.transform);
      const newPath = [...current.path, { frame: parentData.parentFrame, transform: inv, isStatic: parentData.isStatic }];
      if (parentData.parentFrame === targetFrame) return newPath;
      visited.add(parentData.parentFrame); queue.push({ frame: parentData.parentFrame, path: newPath });
    }
  }
  return null;
}

export function lookupTransform(targetFrame: string, sourceFrame: string, transforms: TransformStore): StoredTransform | null {
  const t = targetFrame.startsWith('/')? targetFrame.substring(1): targetFrame;
  const s = sourceFrame.startsWith('/')? sourceFrame.substring(1): sourceFrame;
  const startTime = performance.now();
  try {
    if (t === s) return IDENTITY_TRANSFORM;
    if (transforms[s]?.parentFrame === t) return invertTransform(transforms[s].transform);
    if (transforms[t]?.parentFrame === s) return transforms[t].transform;
    const path = findTransformPath(t, s, transforms); if (!path) return null;
    if (path.length===0) return IDENTITY_TRANSFORM; if (path.length===1) return path[0].transform;
    let ft = path[0].transform; for (let i=1;i<path.length;i++) ft = multiplyTransforms(ft, path[i].transform); return ft;
  } catch { return null; } finally { const d = performance.now()-startTime; if (d>10) console.warn(`[TF] Slow lookup ${s}->${t}: ${d.toFixed(1)}ms`); }
}

export class CustomTFProvider {
  fixedFrame: string; private transforms: TransformStore; private callbacks: Map<string, Set<(t:any|null)=>void>>;
  constructor(fixedFrame: string, initialTransforms: TransformStore) { this.fixedFrame = fixedFrame.startsWith('/')? fixedFrame.substring(1): fixedFrame; this.transforms = initialTransforms; this.callbacks = new Map(); }
  updateTransforms(newTransforms: TransformStore) { this.transforms = newTransforms; this.callbacks.forEach((_, frameId) => { const tf = this.lookupTransform(this.fixedFrame, frameId); const obj = tf? { translation:{x:tf.translation.x,y:tf.translation.y,z:tf.translation.z}, rotation:{x:tf.rotation.x,y:tf.rotation.y,z:tf.rotation.z,w:tf.rotation.w} } : null; this.callbacks.get(frameId)?.forEach(cb => { try { cb(obj); } catch(e){ console.error('TF callback error', e);} }); }); }
  updateFixedFrame(newFrame: string) { const nf = newFrame.startsWith('/')? newFrame.substring(1): newFrame; if (this.fixedFrame===nf) return; this.fixedFrame = nf; this.callbacks.forEach((_, frameId)=>{ const tf = this.lookupTransform(this.fixedFrame, frameId); const obj = tf? { translation:{x:tf.translation.x,y:tf.translation.y,z:tf.translation.z}, rotation:{x:tf.rotation.x,y:tf.rotation.y,z:tf.rotation.z,w:tf.rotation.w} } : null; this.callbacks.get(frameId)?.forEach(cb=>{ try{ cb(obj);}catch(e){ cb(null);} }); }); }
  subscribe(frameId: string, callback: (transform:any|null)=>void){ const f = frameId.startsWith('/')? frameId.substring(1): frameId; if(!this.callbacks.has(f)) this.callbacks.set(f,new Set()); this.callbacks.get(f)!.add(callback); const tf = this.lookupTransform(this.fixedFrame, f); const obj = tf? { translation:{x:tf.translation.x,y:tf.translation.y,z:tf.translation.z}, rotation:{x:tf.rotation.x,y:tf.rotation.y,z:tf.rotation.z,w:tf.rotation.w} } : null; try { callback(obj); } catch(e){ console.error('Initial TF cb error', e);} }
  unsubscribe(frameId: string, callback?: (transform:any|null)=>void){ const f = frameId.startsWith('/')? frameId.substring(1): frameId; const set = this.callbacks.get(f); if(!set) return; if (callback) set.delete(callback); else set.clear(); if (set.size===0) this.callbacks.delete(f); }
  lookupTransform(targetFrame: string, sourceFrame: string): StoredTransform | null { const t = targetFrame.startsWith('/')? targetFrame.substring(1): targetFrame; const s = sourceFrame.startsWith('/')? sourceFrame.substring(1): sourceFrame; return lookupTransform(s, t, this.transforms); }
  dispose(){ this.transforms = {}; this.callbacks.clear(); }
}
export interface ITFProvider extends CustomTFProvider {}
