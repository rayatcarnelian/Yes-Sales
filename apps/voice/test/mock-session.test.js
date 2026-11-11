import assert from "node:assert/strict";
import test from "node:test";
import { noteTranscript } from "../src/bridge.js";
import { buildGatewayReport, buildMockSession, liveConfigured, sessionUpdate, voiceStatus } from "../src/session.js";

test("mock voice session is explicitly labeled and does not place a call", () => {
  const session = buildMockSession({ mode: "buyer", transcript: "TEST transcript" });
  assert.equal(session.provider_mode, "mock");
  assert.equal(session.placed, false);
  assert.equal(session.transcript, "TEST transcript");
  assert.match(session.summary, /No carrier was contacted/);
});

test("live carrier stays not configured without credentials", () => {
  assert.equal(liveConfigured({}), false);
  const update = sessionUpdate("supplier");
  assert.equal(update.type, "session.update");
  assert.equal(update.session.audio.input.format.type, "audio/pcmu");
  assert.equal(update.session.audio.output.format.type, "audio/pcmu");
  assert.match(update.session.instructions, /Never agree a price/);
  assert.equal(voiceStatus({}).live_call_verified, false);
  assert.equal(voiceStatus({}).provider_mode, "mock");
});

test("a closed bridge without a model socket does not claim a live call", () => {
  const report = buildGatewayReport({ modelOpened: false, transcript: "hello" });
  assert.equal(report.provider_mode, "not_configured");
  assert.equal(report.live_call_verified, false);
  assert.match(report.summary, /No xAI realtime socket was opened/);
  const lines = [];
  noteTranscript(lines, { type: "conversation.item.input_audio_transcription.completed", transcript: "Please call me back" });
  const withText = buildGatewayReport({ modelOpened: true, transcript: lines.join("\n") });
  assert.equal(withText.provider_mode, "live");
  assert.equal(withText.live_call_verified, false);
  assert.match(withText.summary, /did not agree a price/);
});
