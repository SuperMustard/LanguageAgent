import { PipecatClient, RTVIEvent } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';

const BOT_START_URL = 'http://127.0.0.1:7860/start';

export class VoiceSession {
  constructor(callbacks = {}) {
    this.callbacks = callbacks;
    this.client = null;
  }

  async connect(scenario) {
    const transport = new SmallWebRTCTransport();
    this.client = new PipecatClient({
      transport,
      enableMic: true,
      enableCam: false,
      callbacks: {
        onConnected: () => this.callbacks.onConnected?.(),
        onDisconnected: () => this.callbacks.onDisconnected?.(),
        onBotReady: () => this.callbacks.onBotReady?.(),
        onUserTranscript: (data) => {
          if (data.final) this.callbacks.onUserTranscript?.(data.text);
        },
        onBotTranscript: (data) => this.callbacks.onBotTranscript?.(data.text),
        onError: (error) => this.callbacks.onError?.(error?.message || String(error)),
      },
    });

    // 播放 bot 的音频轨道——SmallWebRTC 的音频不会自动挂到页面上，需要手动接一个 <audio>
    this.client.on(RTVIEvent.TrackStarted, (track, participant) => {
      if (!participant?.local && track.kind === 'audio') {
        const audio = document.createElement('audio');
        audio.autoplay = true;
        audio.srcObject = new MediaStream([track]);
        document.body.appendChild(audio);
      }
    });

    await this.client.startBotAndConnect({
      endpoint: BOT_START_URL,
      requestData: {
        transport: 'webrtc',
        createDailyRoom: false,
        enableDefaultIceServers: true,
        // 自定义数据必须包在 "body" 里，Pipecat runner 的 /start 只把这里的东西转成
        // runner_args.body 传给 bot()；塞在顶层（跟 transport 平级）会被直接丢弃。
        body: { scenario },
      },
    });
  }

  /** 发 "结束演练" 信号，等 bot 端跑完 Debrief + 存库，拿到诊断结果。 */
  async endSession() {
    if (!this.client) return null;
    return this.client.sendClientRequest('end_session', {}, 30000);
  }

  async disconnect() {
    if (this.client) {
      await this.client.disconnect();
      this.client = null;
    }
  }
}

window.LangPracticeVoice = { VoiceSession };
