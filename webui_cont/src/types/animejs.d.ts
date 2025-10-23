// Expanded anime.js type declarations to support timeline, rotate, and compound value arrays.
declare module 'animejs' {
  interface ValueKeyframe { value: number | string; duration?: number; easing?: string; }
  // Allow raw string values (e.g. '20px', '200vmax') directly.
  type NumericValue = number | number[] | string | ValueKeyframe[];

  interface AnimeParams {
    targets: any;
    opacity?: NumericValue;
    translateY?: NumericValue;
    translateX?: NumericValue;
    rotate?: NumericValue; // degrees
    scale?: NumericValue;
    width?: NumericValue;
    height?: NumericValue;
    borderRadius?: NumericValue;
    top?: NumericValue;
    easing?: string;
    duration?: number;
    delay?: number;
    loop?: boolean | number;
    direction?: 'normal' | 'reverse' | 'alternate';
    complete?: () => void;
    autoplay?: boolean;
    offset?: string | number; // for timeline chaining
  }

  interface AnimeInstance {
    add?: (params: AnimeParams, offset?: string | number) => AnimeInstance;
    pause?: () => void;
    play?: () => void;
  }

  interface AnimeTimelineInstance extends AnimeInstance { add(params: AnimeParams): AnimeTimelineInstance; pause(): void; }

  // Primary function
  function anime(params: AnimeParams): AnimeInstance;

  // Namespace augmentation for anime.timeline usage.
  namespace anime {
    function timeline(params?: Omit<AnimeParams, 'targets'>): AnimeTimelineInstance;
  }
  export = anime;
}
