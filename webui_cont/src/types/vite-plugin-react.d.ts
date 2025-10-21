declare module '@vitejs/plugin-react' {
  import { PluginOption } from 'vite';
  interface ReactPluginOptions {
    jsxRuntime?: 'classic' | 'automatic';
    jsxImportSource?: string;
    babel?: any;
    include?: string | RegExp | (string | RegExp)[];
    exclude?: string | RegExp | (string | RegExp)[];
    fastRefresh?: boolean;
    tsDecorators?: boolean;
  }
  export default function react(options?: ReactPluginOptions): PluginOption;
}
