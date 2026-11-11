import express from "express";
import { createServer } from "node:http";
import { WebSocketServer } from "ws";
import { attachMediaBridge } from "./bridge.js";
import { buildMockSession, liveConfigured, voiceStatus } from "./session.js";

export function createVoiceServer(env = process.env) {
  const app = express();
  app.use(express.json());
  app.use(express.urlencoded({ extended: false }));

  app.get("/health", (_request, response) => {
    response.json(voiceStatus(env));
  });

  app.post("/sessions/mock", (request, response) => {
    response.status(201).json(buildMockSession(request.body || {}));
  });

  app.post("/twiml", (_request, response) => {
    if (!liveConfigured(env)) {
      response.status(503).type("text/plain").send("Voice carrier is not configured. No call was bridged.");
      return;
    }
    const host = env.PUBLIC_VOICE_HOST;
    response
      .type("text/xml")
      .send(
        `<?xml version="1.0" encoding="UTF-8"?><Response><Connect><Stream url="wss://${host}/media"><Parameter name="mode" value="buyer"/></Stream></Connect></Response>`,
      );
  });

  const server = createServer(app);
  const sockets = new WebSocketServer({ server, path: "/media" });
  sockets.on("connection", (socket) => attachMediaBridge(socket, env));
  return server;
}

if (process.argv[1] && process.argv[1].endsWith("server.js")) {
  const port = Number(process.env.PORT || 3001);
  createVoiceServer().listen(port, () => {
    console.log(JSON.stringify({ event: "voice.listening", port, ...voiceStatus() }));
  });
}
