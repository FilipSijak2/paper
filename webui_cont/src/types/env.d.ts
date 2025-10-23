/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_ROSBRIDGE_URL?: string;
  readonly VITE_ROBOT_NAME?: string;
}
interface ImportMeta { readonly env: ImportMetaEnv; }
