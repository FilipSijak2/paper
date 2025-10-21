declare module 'roslib' {
  export interface RosOptions { url: string; }
  export interface TopicsResponse { topics: string[]; types: string[]; }
  export class Ros {
    constructor(options: RosOptions);
    on(event: string, cb: (...args: any[]) => void): void;
    connect(url: string): void;
    close(): void;
    getTopics(cb: (res: TopicsResponse) => void, errCb?: (err: any) => void): void; // Added for topic discovery
  }
  export interface TopicOptions {
    ros: Ros; name: string; messageType: string;
    compression?: string; throttle_rate?: number; queue_size?: number; latch?: boolean;
  }
  export class Topic {
    constructor(options: TopicOptions);
    subscribe(cb: (msg: any) => void): void;
    unsubscribe(): void;
    publish(msg: any): void;
    unadvertise(): void; // Added cleanup method
    advertise(): void; // Added advertise method for publisher creation
  }
  export class Message { constructor(values: any); } // Minimal message wrapper
}
