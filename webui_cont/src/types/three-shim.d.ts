declare module 'three' {
  export class Vector2 { constructor(x?:number,y?:number); x:number; y:number; set(x:number,y:number):this; subVectors(a:Vector2,b:Vector2):this; copy(v:Vector2):this; }
  export class Vector3 { constructor(x?:number,y?:number,z?:number); x:number; y:number; z:number; set(x:number,y:number,z:number):this; add(v:Vector3):this; sub(v:Vector3):this; subVectors(a:Vector3,b:Vector3):this; multiplyScalar(s:number):this; clone():Vector3; normalize():Vector3; distanceTo(v:Vector3):number; applyQuaternion(q:Quaternion):this; }
  export class Euler { constructor(x?:number,y?:number,z?:number,order?:string); x:number; y:number; z:number; }
  export class Quaternion { constructor(x?:number,y?:number,z?:number,w?:number); x:number; y:number; z:number; w:number; setFromAxisAngle(axis:Vector3,angle:number):this; multiply(q:Quaternion):this; invert():this; inverse():this; clone():Quaternion; }
  export class Color { constructor(hex?:number|string); setRGB(r:number,g:number,b:number):void; }
  export class BufferGeometry { dispose():void; setAttribute(name:string, attr:any):void; setFromPoints(points:Vector3[]):BufferGeometry; setDrawRange(start:number,count:number):void; getAttribute(name:string):any; }
  export class PointsMaterial { constructor(params?:any); size:number; color:Color; needsUpdate:boolean; }
  export class MeshLambertMaterial { constructor(params?:any); dispose():void; }
  export class Material { dispose():void; }
  export class Mesh { constructor(geometry?:BufferGeometry, material?:any); geometry:BufferGeometry; material:any; scale:Vector3; position:Vector3; rotation:Euler; quaternion:Quaternion; traverse(cb:(obj:any)=>void):void; }
  export class Group { constructor(); add(o:any):void; remove(o:any):void; position:Vector3; rotation:Euler; quaternion:Quaternion; updateMatrix():void; matrixWorldNeedsUpdate:boolean; }
  export class Object3D { add(o:any):void; remove(o:any):void; position:Vector3; rotation:Euler; quaternion:Quaternion; visible:boolean; updateMatrix():void; matrixWorldNeedsUpdate:boolean; traverse(cb:(obj:any)=>void):void; }
  export class Scene extends Object3D { background:Color; }
  export class PerspectiveCamera extends Object3D { constructor(fov:number,aspect:number,near:number,far:number); aspect:number; up:Vector3; lookAt(x:number,y:number,z:number):void; updateProjectionMatrix():void; }
  export class WebGLRenderer { constructor(params?:any); setSize(w:number,h:number):void; render(scene:Scene,camera:PerspectiveCamera):void; domElement:HTMLElement; }
  export class AmbientLight extends Object3D { constructor(color:number,intensity?:number); }
  export class DirectionalLight extends Object3D { constructor(color:number,intensity?:number); }
  export class AxesHelper extends Object3D { constructor(size?:number); geometry:BufferGeometry; material:Material; }
  export class GridHelper extends Object3D { constructor(size:number,divisions:number, c1?:number, c2?:number); geometry:BufferGeometry; material:Material; rotation:Euler; }
  export class Points extends Object3D { constructor(geometry:BufferGeometry, material:any); geometry:BufferGeometry; material:any; frustumCulled:boolean; }
  export class SphereGeometry extends BufferGeometry { constructor(r:number, w?:number, h?:number); }
  export class CylinderGeometry extends BufferGeometry { constructor(rt:number, rb:number, h:number, seg?:number); }
  export class BoxGeometry extends BufferGeometry { constructor(x:number,y:number,z:number); }
  export class TextureLoader { load(path:string):any; }
  export class Spherical { setFromVector3(v:Vector3):void; }
}
