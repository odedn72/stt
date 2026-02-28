# Market Requirements Document: SystemSTT
**Version:** 1.0
**Date:** 2026-02-28
**Author:** Product Agent
**Status:** Approved by User

## 1. Executive Summary
SystemSTT is a system-wide speech-to-text desktop application that allows the user to dictate text into any active text field on their computer using a global keyboard shortcut. It supports both Hebrew and English with seamless mid-sentence language switching, voice commands for text editing, and a configurable STT engine (local Whisper model or cloud API). The application targets macOS first (with Windows planned for v2) and is designed for a single developer user working at a desk with a quality microphone.

## 2. Problem Statement
- Existing speech-to-text solutions are either expensive (Dragon NaturallySpeaking), limited in language support, or lack system-wide integration with voice command capabilities
- The user (a developer) wants a high-quality, low-cost dictation tool that works across all applications — not just within a single app
- Without this tool, the user must rely on manual typing for all text input, missing the productivity gains of voice dictation

## 3. Target Users
| Persona | Description | Primary Needs |
|---------|-------------|---------------|
| Developer (sole user) | Technical user, works at a desk with a good microphone, uses macOS (Intel i9) and Windows | System-wide dictation with low latency, bilingual support (Hebrew/English), voice editing commands, configurable STT engine |

## 4. Product Goals & Success Metrics
| Goal | Metric | Target |
|------|--------|--------|
| Low latency transcription | Time from speech to text appearing on screen | < 1 second for streaming; < 3 seconds for sentence completion |
| High accuracy | Word error rate for English | < 10% in controlled environment |
| Hebrew support | Usable Hebrew transcription with mixed English | Functional accuracy — user can dictate in Hebrew without manual correction for most sentences |
| Low cost | Monthly operational cost | < $10/month if using cloud API; $0 if using local model |
| Ease of use | Steps to start dictating | Single keyboard shortcut |

## 5. Functional Requirements

### 5.1 Must-Have (P0)
| ID | Requirement | Description | Acceptance Criteria |
|----|-------------|-------------|---------------------|
| FR-001 | Global keyboard shortcut | A configurable system-wide hotkey to start and stop dictation from any application | Pressing the shortcut toggles dictation on/off regardless of which app is focused |
| FR-002 | Real-time transcription | Speech is transcribed and displayed with low latency as the user speaks | Text appears in the active text field within ~1 second of being spoken |
| FR-003 | Text injection at cursor | Transcribed text is injected directly into the currently focused text field in any application | Text appears at the cursor position in browsers, editors, terminals, and other standard macOS apps |
| FR-004 | Hebrew and English support | Supports dictation in both Hebrew and English | User can dictate in either language and receive accurate transcription |
| FR-005 | Auto language detection | Automatically detects whether the user is speaking Hebrew or English, including mid-sentence switching | No manual language toggle required; mixed-language sentences are transcribed correctly (best effort) |
| FR-006 | Long-form dictation | Supports continuous dictation sessions, not just short phrases | User can dictate for 5+ minutes continuously without degradation or cutoff |
| FR-007 | Voice commands | Support voice commands for text editing actions | The following commands are recognized and executed: "delete the last sentence", "delete the last word", "undo", "new line", "new paragraph", "select all", "copy", "paste", "stop dictation" |
| FR-008 | Configurable STT engine | User can choose between a local Whisper model or a cloud API (e.g., OpenAI Whisper API) | Settings UI allows selecting the engine; switching engines does not require restart |
| FR-009 | Persistent settings | User's configuration (engine choice, hotkey, model size, etc.) is saved and restored between sessions | App remembers the last configuration on restart |
| FR-010 | macOS support | Application runs on macOS, including Intel Macs | App launches and functions correctly on macOS with Intel i9 processor |

### 5.2 Should-Have (P1)
| ID | Requirement | Description | Acceptance Criteria |
|----|-------------|-------------|---------------------|
| FR-011 | Configurable Whisper model size | User can select which Whisper model to use locally (tiny, base, small, medium, large) | Settings allow model selection with a note about speed/accuracy trade-offs |
| FR-012 | Visual dictation indicator | A small visual indicator showing when dictation is active | User can see at a glance whether dictation is on or off (e.g., menu bar icon, floating indicator) |
| FR-013 | Audio input device selection | User can select which microphone to use | Settings list available audio input devices |

### 5.3 Nice-to-Have (P2)
| ID | Requirement | Description | Acceptance Criteria |
|----|-------------|-------------|---------------------|
| FR-020 | Windows support | Application runs on Windows | App launches and functions correctly on Windows with equivalent features |
| FR-021 | Custom voice commands | User can define their own voice commands | Settings allow mapping custom phrases to keyboard shortcuts or actions |
| FR-022 | Transcription history | Log of past dictation sessions | User can review what was dictated in previous sessions |

## 6. Non-Functional Requirements
| ID | Category | Requirement | Target |
|----|----------|-------------|--------|
| NFR-001 | Performance | Transcription latency (local model, small/medium) | < 2 seconds |
| NFR-002 | Performance | Transcription latency (cloud API) | < 1 second |
| NFR-003 | Performance | Memory usage | < 2 GB RAM (local model loaded) |
| NFR-004 | Performance | CPU usage during idle (not dictating) | Negligible (< 1%) |
| NFR-005 | Reliability | Application stability | No crashes during normal use; graceful error handling for API failures or model errors |
| NFR-006 | Security | API key storage | Cloud API keys stored securely (OS keychain or encrypted config) |
| NFR-007 | Usability | Setup complexity | App should work with minimal configuration out of the box (sensible defaults) |
| NFR-008 | Portability | Cross-platform architecture | Core logic separated from platform-specific code to ease future Windows port |

## 7. Technical Constraints & Preferences
- **Preferred stack:** No preference — architect to decide based on requirements. Python is a natural fit for ML/audio; native frameworks may be needed for system integration (accessibility APIs, global hotkeys)
- **STT engine:** OpenAI Whisper (local) as primary; OpenAI Whisper API as cloud option
- **Hardware (Mac):** 2.4 GHz 8-Core Intel Core i9 — no Apple Silicon, no dedicated GPU. Local large model will be too slow; small/medium models or cloud API recommended as defaults
- **Hardware (Windows, future):** Powerful machine — local large model should be viable
- **Deployment:** Local application, not a web app. No Docker needed for v1
- **Audio environment:** Desk setup with quality microphone — no need for advanced noise suppression
- **Data privacy:** Audio is processed locally (when using local model) or sent to cloud API (when using cloud). No persistent audio storage required

## 8. Out of Scope
- Multi-user support or user accounts
- Mobile platforms (iOS, Android)
- Noise cancellation or noisy environment optimization
- Windows support (deferred to v2 — see FR-020)
- Real-time translation (Hebrew to English or vice versa)
- Custom model training or fine-tuning
- Voice authentication or speaker identification

## 9. Open Questions & Risks
| Risk/Question | Impact | Mitigation |
|---------------|--------|------------|
| Mixed Hebrew/English mid-sentence detection accuracy | Core feature may have noticeable errors | Use Whisper large model via cloud API for best multilingual accuracy; allow user to correct and continue |
| Intel Mac performance for local Whisper | Local model may be too slow for real-time on Intel | Default to cloud API on Intel Macs; offer smaller models as local option with accuracy warning |
| Accessibility API permissions on macOS | App needs Accessibility permissions to inject text into other apps | Guide user through granting permissions on first launch; handle gracefully if denied |
| Voice command recognition in Hebrew | Voice commands may need to work in both languages | Start with English-only voice commands for v1; add Hebrew commands later |
| Text injection compatibility across apps | Some apps may not accept injected text via accessibility APIs | Test with common apps (browsers, VS Code, Terminal, Notes); document known limitations |

## 10. Appendix
### User Interview Notes
- User is a developer building this for personal use
- Primary motivation: experiment with building a better, cheaper STT tool
- Uses both Mac (Intel i9) and Windows (powerful machine)
- Works at desk with good microphone — controlled audio environment
- Needs Hebrew and English with frequent mid-sentence switching
- Wants voice commands for editing (delete, undo, navigation)
- Prefers configurable architecture: local model vs. cloud API, user's choice
- Settings should persist between sessions
- Mac is the priority platform for v1
