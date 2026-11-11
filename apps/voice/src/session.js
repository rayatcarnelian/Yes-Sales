export function liveConfigured(env = process.env) {
  return Boolean(env.XAI_API_KEY && env.TWILIO_AUTH_TOKEN && env.TWILIO_PHONE_NUMBER && env.PUBLIC_VOICE_HOST);
}

export function voiceStatus(env = process.env) {
  const configured = liveConfigured(env);
  return {
    status: "ok",
    service: "yes-sales-voice",
    provider_mode: configured ? "configured_unverified" : "mock",
    carrier: configured ? "configured_unverified" : "not_configured",
    live_call_verified: false,
  };
}

export function buildMockSession(input = {}) {
  const mode = input.mode === "supplier" ? "supplier" : "buyer";
  return {
    provider_mode: "mock",
    status: "completed",
    mode,
    direction: "inbound",
    placed: false,
    transcript: input.transcript || "TEST mock voice transcript",
    summary: "Mock voice session. No carrier was contacted and no recording was made.",
    request_callback: Boolean(input.request_callback),
    live_call_verified: false,
    logged_to_api: false,
  };
}

export function buildGatewayReport({ modelOpened = false, transcript = "", mode = "buyer", direction = "inbound" } = {}) {
  const text = String(transcript || "").trim();
  const normalizedMode = mode === "supplier" ? "supplier" : "buyer";
  if (!modelOpened) {
    return {
      provider_mode: "not_configured",
      status: "blocked",
      direction,
      mode: normalizedMode,
      transcript: text || null,
      summary: "No xAI realtime socket was opened. No audio was forwarded and no call outcome was inferred.",
      model_socket_opened: false,
      consent_checked: false,
      live_call_verified: false,
    };
  }
  return {
    provider_mode: "live",
    status: "completed",
    direction,
    mode: normalizedMode,
    transcript: text || null,
    summary: text
      ? "Realtime session closed with a stored transcript. The gateway did not agree a price, commission, or contract."
      : "Realtime socket closed. No transcript events arrived, so no call outcome was inferred.",
    model_socket_opened: true,
    consent_checked: direction === "outbound",
    live_call_verified: false,
  };
}

export function sessionUpdate(mode) {
  const supplier = mode === "supplier";
  return {
    type: "session.update",
    session: {
      voice: "eve",
      instructions: supplier
        ? "You are Alex at YES SALES, speaking with a supplier. Collect capacity, MOQ, lead time, certifications, and public contact details. Never agree a price, commission, contract, or payment. If the caller asks for a person, say a human will follow up. Do not place a call."
        : "You are Alex at YES SALES, speaking with a buyer. Collect product, quantity, destination, certifications, and lead time. Never promise a price, landed cost, delivery date, or contract. If the caller asks for a person, say a human will follow up. Do not place a call.",
      turn_detection: { type: "server_vad" },
      audio: {
        input: { format: { type: "audio/pcmu" } },
        output: { format: { type: "audio/pcmu" } },
      },
    },
  };
}
