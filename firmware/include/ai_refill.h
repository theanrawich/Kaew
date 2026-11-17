#pragma once
#include <cstddef>
#include <cstring>
#include "dispensing.h"

constexpr uint32_t AI_REQUEST_MS = 2000, AI_ADVICE_MAX_AGE_MS = 120000;
constexpr size_t AI_RESPONSE_BYTES = 512;
struct AdviceQuery {
  uint32_t bootSession = 0, requestId = 0, cupSession = 0, nonce = 0, issuedAtMs = 0;
};
struct AdviceProposal {
  uint32_t version = 0, bootSession = 0, requestId = 0, cupSession = 0, nonce = 0;
  uint32_t adviceId = 0, ageMs = 0, suggestedMl = 0;
  bool modelBacked = false, actuationAllowed = false;
};

// Restricted, flat JSON v1 decoder. Exact keys/types, no duplicates, strings,
// escaping, exponent/fractional numbers, unknown fields or trailing documents.
// This schema is a small projection of /api/advice, not general JSON parsing.
inline bool parseAdvice(const char *body, size_t length, AdviceProposal &out) {
  if (!body || !length || length > AI_RESPONSE_BYTES) return false;
  const char *p = body, *end = body + length;
  auto space = [&]() { while (p != end && (*p == ' ' || *p == '\n' || *p == '\r' || *p == '\t')) ++p; };
  const char *keys[] = {"version", "boot_session", "request_id", "cup_session", "nonce",
                        "advice_id", "age_ms", "suggested_ml", "model_backed", "actuation_allowed"};
  uint32_t values[10]{}; unsigned seen = 0;
  space(); if (p == end || *p++ != '{') return false;
  for (unsigned n=0; n<10; ++n) {
    space(); if (p == end || *p++ != '"') return false;
    const char *start = p;
    while (p != end && ((*p >= 'a' && *p <= 'z') || *p == '_')) ++p;
    if (p == end || *p != '"') return false;
    unsigned key = 0;
    for (; key < 10; ++key) if (std::strlen(keys[key]) == size_t(p-start) && !std::memcmp(start, keys[key], p-start)) break;
    if (key == 10 || (seen & (1u << key))) return false;
    seen |= 1u << key; ++p; space(); if (p == end || *p++ != ':') return false;
    space();
    if (key >= 8) {
      if (size_t(end-p) >= 5 && !std::memcmp(p, "false", 5)) { p += 5; values[key] = 0; }
      else if (size_t(end-p) >= 4 && !std::memcmp(p, "true", 4)) { p += 4; values[key] = 1; }
      else return false;
    } else {
      if (p == end || *p < '0' || *p > '9') return false;
      bool zero = *p == '0'; unsigned digits = 0; uint64_t value = 0;
      while (p != end && *p >= '0' && *p <= '9') {
        if (++digits > 10 || (zero && digits > 1)) return false;
        value = value*10 + unsigned(*p++-'0'); if (value > UINT32_MAX) return false;
      }
      values[key] = static_cast<uint32_t>(value);
    }
    space(); if (p == end || *p++ != (n == 9 ? '}' : ',')) return false;
  }
  space(); if (p != end || seen != 1023) return false;
  AdviceProposal next;
  next.version=values[0]; next.bootSession=values[1]; next.requestId=values[2]; next.cupSession=values[3]; next.nonce=values[4];
  next.adviceId=values[5]; next.ageMs=values[6]; next.suggestedMl=values[7]; next.modelBacked=values[8]; next.actuationAllowed=values[9];
  out = next; return true;
}

enum class AiResult { Armed, NotArmed, Disabled, Unsafe, Busy, WrongContext, Expired, InvalidAdvice, DuplicateAdvice, Rejected, Started };

class AiRefillBridge {
  GatewayDispenser &gateway_;
  AdviceQuery pending_{};
  bool armed_ = false;
  uint32_t issuedId_ = 0, lastAdviceId_ = 0;
  RefillResult refillResult_ = RefillResult::Disabled;
public:
  explicit AiRefillBridge(GatewayDispenser &gateway) : gateway_(gateway) {}
  bool pending() const { return armed_; }
  void cancel() { armed_ = false; }
  void fail(const AdviceQuery &query) {
    if (query.bootSession == pending_.bootSession && query.requestId == pending_.requestId &&
        query.cupSession == pending_.cupSession && query.nonce == pending_.nonce) cancel();
  }
  RefillResult refillResult() const { return refillResult_; }
  AiResult arm(const Inputs &i, const CupTare &tare, uint32_t cupSession, uint32_t nonce, AdviceQuery &query) {
    gateway_.update(i);
    if (!gateway_.aiEnabled_) return AiResult::Disabled;
    if (armed_ || gateway_.safety().state() != DispenseState::Idle) return AiResult::Busy;
    float volume = 0;
    if (!gateway_.boot_ || !cupSession || !nonce || !gateway_.safety().ready(i) || !tare.volume(i.cupPresent, i.weightG, volume)) return AiResult::Unsafe;
    if (issuedId_ < gateway_.lastRequest_) issuedId_ = gateway_.lastRequest_;
    if (issuedId_ == UINT32_MAX) return AiResult::Disabled; // Never wrap IDs.
    pending_.bootSession=gateway_.boot_; pending_.requestId=++issuedId_; pending_.cupSession=cupSession;
    pending_.nonce=nonce; pending_.issuedAtMs=i.nowMs; armed_=true; query=pending_; return AiResult::Armed;
  }
  void update(const Inputs &i, const CupTare &tare, uint32_t cupSession) {
    if (!armed_) return;
    float volume = 0;
    if (uint32_t(i.nowMs-pending_.issuedAtMs) >= AI_REQUEST_MS || cupSession != pending_.cupSession ||
        !gateway_.safety().ready(i) || !tare.volume(i.cupPresent, i.weightG, volume)) cancel();
  }
  AiResult deliver(const AdviceProposal &a, const Inputs &i, const CupTare &tare, uint32_t cupSession) {
    refillResult_=RefillResult::Disabled; // Diagnostics describe this reply, not an older start.
    gateway_.update(i);
    if (!armed_) return AiResult::NotArmed;
    if (a.bootSession != pending_.bootSession || a.requestId != pending_.requestId ||
        a.cupSession != pending_.cupSession || a.nonce != pending_.nonce) return AiResult::WrongContext;
    const uint32_t elapsed = uint32_t(i.nowMs-pending_.issuedAtMs);
    armed_=false; // Matching replies consume local consent, even when rejected.
    if (elapsed >= AI_REQUEST_MS) return AiResult::Expired;
    if (cupSession != pending_.cupSession || !gateway_.safety().ready(i)) return AiResult::Unsafe;
    if (a.version != 1 || !a.adviceId || a.actuationAllowed || !a.modelBacked || a.ageMs >= AI_ADVICE_MAX_AGE_MS ||
        uint64_t(a.ageMs)+elapsed >= AI_ADVICE_MAX_AGE_MS) return AiResult::InvalidAdvice;
    if (a.adviceId <= lastAdviceId_) return AiResult::DuplicateAdvice;
    lastAdviceId_=a.adviceId;
    RefillRequest request{1,pending_.bootSession,pending_.requestId,pending_.issuedAtMs,float(a.suggestedMl)};
    refillResult_=gateway_.boundedRequest(request,i,tare,gateway_.aiEnabled_);
    return refillResult_ == RefillResult::Started ? AiResult::Started : AiResult::Rejected;
  }
};
