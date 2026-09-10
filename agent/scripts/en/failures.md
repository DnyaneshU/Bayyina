# Failure taxonomy

<!-- GENERATED from backend/src/bayyina/api/errors.py. Do not edit by
     hand: run `python scripts/render_failures.py` instead. The service
     and the script must not be able to disagree. -->

A webhook that hangs during a live call produces dead air, and the caller
hangs up. Every failure here has a status, a sentence, and a next step
decided in advance.

| Failure | Status | The agent says | Then | Escalates |
|---|---|---|---|---|
| `comparable_not_found` | 200 | I could not find enough registered contracts for a property like yours to give you a reliable average. I can still tell you what the rule says, and you can put your own figure to it. | Continue. Offer the rule without the comparison, or take a figure the caller supplies. This is the G5 script and it is not an apology. | no |
| `market_data_absent` | 503 | I cannot look up market averages at the moment. If you already know the average rent for a property like yours, I can work from that. | Continue on the caller-supplied path. Everything else still works. | no |
| `rule_evaluation_error` | 500 | Something went wrong on my side. I am not going to guess at your answer, so let me pass you to someone who can help. | Escalate immediately. Do not retry: a rule that failed will fail again. | yes |
| `timeout` | 504 | Give me one moment while I check that. | Filler line, one retry, then escalate. The filler goes out *before* the retry, not after it, or the caller hears the silence the line exists to fill. | yes |
| `dispatch_failed` | 502 | I could not text that through. I can read out the key points now, or try another number. | Offer both alternatives and take one. Never silently drop the pack: the caller was told they would receive it. | no |
| `unsupported_language` | 422 | I can talk this through with you now, but I cannot send you the written report in this language yet. | Continue the call. Do not send an English document instead - an English pack for a Malayalam reader is a failed delivery, and it is worse for being invisible. | no |
| `rate_limited` | 429 | Let me slow down a moment. | Back off and retry once. If it persists, escalate. | yes |
| `corpus_unsigned` | none - service does not start | - | Nothing. The service refuses to start, so no call is answered. A number that rings and then answers from an unverified corpus is worse than a number that does not ring (G7). | no |
