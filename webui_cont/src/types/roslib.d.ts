declare module 'roslib' {
  export interface RosOptions { url?: string; }
  export interface TopicsResponse { topics: string[]; types: string[]; }
  export class Ros {
    constructor(options?: RosOptions);
    on(event: 'connection' | 'close' | 'error' | string, cb: (...args: any[]) => void): void;
    connect(url: string): void;
    close(): void;
    getTopics(cb: (res: TopicsResponse) => void, errCb?: (err: any) => void): void;
  }
  export interface TopicOptions {
    ros: Ros; name: string; messageType: string;
    compression?: 'cbor' | 'png' | 'cbor-raw' | 'none';
    throttle_rate?: number; queue_size?: number; latch?: boolean; queue_length?: number;
  }
  export class Topic {
    constructor(options: TopicOptions);
    subscribe(cb: (msg: any) => void): void;
    unsubscribe(): void;
    publish(msg: any): void;
    advertise(): void;
    unadvertise(): void;
  }
  export class Message { constructor(values: any); }
}
