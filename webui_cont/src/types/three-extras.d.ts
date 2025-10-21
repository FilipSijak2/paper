declare module 'three/examples/jsm/loaders/ColladaLoader.js' {
  import { Object3D } from 'three';
  export class ColladaLoader { load(path:string, onLoad:(collada:{ scene: Object3D })=>void, onProgress?:(e:any)=>void, onError?:(e:any)=>void): void; }
}
declare module 'three/examples/jsm/loaders/STLLoader.js' {
  import { BufferGeometry } from 'three';
  export class STLLoader { load(path:string, onLoad:(geometry: BufferGeometry)=>void, onProgress?:(e:any)=>void, onError?:(e:any)=>void): void; }
}
