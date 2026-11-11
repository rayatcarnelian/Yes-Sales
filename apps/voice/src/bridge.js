import { WebSocket } from "ws";
import { buildGatewayReport, sessionUpdate } from "./session.js";

export function noteTranscript(lines, event) {
  if (event.type === "response.output_audio_transcript.done" && event.transcript) {
    lines.push(`Alex: ${event.transcript}`);
  }
  if (event.type === "conversation.item.input_audio_transcription.completed" && event.transcript) {
    lines.push(`Caller: ${event.transcript}`);
  }
}

export async function postGatewayReport(env, report) {
  if (!env.API_URL || !env.VOICE_GATEWAY_TOKEN) return { logged: false };
  const response = await fetch(`${String(env.API_URL).replace(/\/$/, "")}/internal/calls`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Voice-Token": env.VOICE_GATEWAY_TOKEN,
    },
    body: JSON.stringify(report),
  });
  return { logged: response.ok, status: response.status };
}

export function attachMediaBridge(twilioSocket, env = process.env) {
  let modelSocket = null;
  let streamSid = null;
  let modelOpened = false;
  let reported = false;
  let mode = "buyer";
  const lines = [];

  const report = () => {
    if (reported) return;
    reported = true;
    const payload = buildGatewayReport({
      modelOpened,
      transcript: lines.join("\n"),
      mode,
      direction: "inbound",
    });
    postGatewayReport(env, payload).catch(() => {});
  };

  const closeBoth = () => {
    if (modelSocket && modelSocket.readyState === WebSocket.OPEN) {
      modelSocket.close();
    }
    if (twilioSocket.readyState === WebSocket.OPEN) {
      twilioSocket.close();
    }
    report();
  };

  twilioSocket.on("message", (raw) => {
    let message;
    try {
      message = JSON.parse(raw.toString());
    } catch {
      return;
    }
    if (message.event === "start") {
      streamSid = message.start?.streamSid || null;
      if (!env.XAI_API_KEY) {
        closeBoth();
        return;
      }
      const url = `${env.XAI_REALTIME_URL || "wss://api.x.ai/v1/realtime"}?model=grok-voice-latest`;
      modelSocket = new WebSocket(url, { headers: { Authorization: `Bearer ${env.XAI_API_KEY}` } });
      modelSocket.on("open", () => {
        modelOpened = true;
        mode = message.start?.customParameters?.mode || "buyer";
        modelSocket.send(JSON.stringify(sessionUpdate(mode)));
      });
      modelSocket.on("message", (data) => {
        let event;
        try {
          event = JSON.parse(data.toString());
        } catch {
          return;
        }
        noteTranscript(lines, event);
        const delta = event.delta;
        if ((event.type === "response.output_audio.delta" || event.type === "response.audio.delta") && delta && streamSid) {
          twilioSocket.send(JSON.stringify({ event: "media", streamSid, media: { payload: delta } }));
        }
      });
      modelSocket.on("close", () => {
        if (twilioSocket.readyState === WebSocket.OPEN) twilioSocket.close();
      });
    }
    if (message.event === "media" && modelSocket && modelSocket.readyState === WebSocket.OPEN) {
      modelSocket.send(JSON.stringify({ type: "input_audio_buffer.append", audio: message.media.payload }));
    }
    if (message.event === "stop") {
      closeBoth();
    }
  });

  twilioSocket.on("close", () => {
    if (modelSocket && modelSocket.readyState === WebSocket.OPEN) modelSocket.close();
    report();
  });
}
