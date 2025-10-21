// Minimal augmentation for missing Three.js classes & methods used in hooks.
// Merges with existing module definitions provided by three.
declare module 'three' {
  class BufferAttribute { constructor(array: ArrayLike<number>, itemSize: number); array: ArrayLike<number>; needsUpdate: boolean; }
  class LineBasicMaterial { constructor(params?: any); color: { set(v:any): void; getHex?: () => number }; dispose(): void; transparent?: boolean; opacity?: number; }
  class BufferGeometry {
    setAttribute(name: string, attr: BufferAttribute): void;
    getAttribute(name: string): BufferAttribute;
    setIndex(index: number[] | Uint16Array | Uint32Array): void;
    getIndex(): { array: ArrayLike<number> } | null;
    setFromPoints(points: any[]): this;
    setDrawRange(start: number, count: number): void;
    dispose(): void;
  }
  class LineSegments extends Object3D { constructor(geom: BufferGeometry, mat: LineBasicMaterial); geometry: BufferGeometry; material: LineBasicMaterial; visible: boolean; }
  class Line extends Object3D { constructor(geom: BufferGeometry, mat: LineBasicMaterial); geometry: BufferGeometry; material: LineBasicMaterial; }
  class ConeGeometry extends BufferGeometry { constructor(radius: number, height: number, radialSegments?: number); }
  interface Color { set(v:any): void; getHex(): number; }
  interface Vector3 { copy(v: Vector3): Vector3; clone(): Vector3; }
  interface Quaternion { set(x:number,y:number,z:number,w:number): Quaternion; copy(q: Quaternion): Quaternion; }
  interface Object3D { visible: boolean; position: Vector3; quaternion: Quaternion; add(obj: Object3D): void; remove(obj: Object3D): void; }
  interface Group extends Object3D { clear?(): void; }
}
