# Design Specification: SystemSTT
**Version:** 1.0
**Date:** 2026-02-28
**Author:** Design Agent
**Status:** Approved by User
**References:** [MRD v1.0](../mrd/mrd.md)

---

## 1. Overview

This document defines the user interface and visual design for SystemSTT, a system-wide speech-to-text application for macOS (with Windows planned for v2). SystemSTT is a background utility that lives in the menu bar and provides real-time dictation with bilingual support (Hebrew and English), voice commands, and configurable STT engines.

The UI surface is intentionally small -- menu bar icon, floating status pill, compact settings window, and system notifications. Every design decision prioritizes clarity of state ("is dictation active?", "what language?", "which engine?") while staying out of the user's way.

### 1.1 Design Principles

1. **State clarity above all** -- The user must always know at a glance whether dictation is active, what language is detected, and which engine is in use.
2. **Stay out of the way** -- UI appears when needed and recedes when not. No dock icon by default. Minimal screen real estate.
3. **Cross-platform consistency** -- All UI uses a custom visual language that will translate identically to Windows in v2. No reliance on platform-native widgets for visual identity.
4. **Developer-friendly density** -- Settings are compact and scannable. No wizard flows, no hand-holding. Every setting on one page with tabs.

### 1.2 Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Menu bar presence | Icon + language label | At-a-glance language awareness for bilingual dictation |
| Dictation indicator | Menu bar change + floating pill | Dual feedback: passive (menu bar) and active (pill) |
| Floating pill content | Status pill + toggleable live preview | Layered information: essential info always, detail on demand |
| Pill positioning | Draggable, remembers position | Avoids overlap with varying app layouts |
| Settings layout | Compact single-page with tabs | Quick to scan, quick to build, bounded setting count |
| Error/notification strategy | Hybrid: pill inline + macOS notifications | Feedback appears where attention already is |
| Visual aesthetic | Custom/branded, dark-only, translucent | Cross-platform consistency; premium developer tool feel |
| Accent color | Purple/violet (#8B5CF6) | Distinctive, high contrast on dark, not overused in utilities |
| Dock presence | Hidden by default, toggleable | Menu bar app; no dock clutter |

---

## 2. Color System

### 2.1 Core Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `--bg-solid` | `#1A1A2E` | Settings window background, opaque surfaces |
| `--bg-translucent` | `#1A1A2E` at 70% opacity | Floating pill, dropdown menu (with backdrop blur) |
| `--bg-elevated` | `#252540` | Cards, tab content areas, input field backgrounds |
| `--bg-hover` | `#2E2E4A` | Hover state for interactive elements |
| `--bg-active` | `#3A3A5C` | Active/pressed state for interactive elements |
| `--text-primary` | `#F0F0F5` | Primary text, labels |
| `--text-secondary` | `#9999B0` | Secondary text, descriptions, dimmed labels |
| `--text-disabled` | `#55556A` | Disabled text, inactive elements |
| `--accent` | `#8B5CF6` | Primary accent: active states, recording indicator, buttons, toggles |
| `--accent-hover` | `#7C4FE0` | Accent hover state |
| `--accent-glow` | `#8B5CF6` at 40% opacity | Glow effect behind active recording indicator |
| `--error` | `#EF4444` | Error states, critical alerts |
| `--error-bg` | `#EF4444` at 15% opacity | Error state backgrounds |
| `--warning` | `#F59E0B` | Warning states, caution indicators |
| `--success` | `#10B981` | Success confirmations, healthy status |
| `--border` | `#2E2E4A` | Subtle borders and dividers |

### 2.2 Backdrop Blur

All translucent surfaces (floating pill, dropdown menu) use a backdrop blur of **20px** to achieve the frosted glass effect. This creates visual depth and allows the underlying content to subtly show through without being readable.

On Windows (v2), this maps to the Acrylic/Mica material system. On macOS, this uses `NSVisualEffectView` or equivalent rendering.

### 2.3 Dark-Only Rationale

SystemSTT ships with a single dark theme. No light mode. Rationale:
- Reduces design and development surface by 50%
- Developer tools overwhelmingly use dark themes
- The floating pill is less visually intrusive on dark backgrounds
- Translucent effects look more premium on dark surfaces
- Consistent across platforms without needing to match each OS's light/dark conventions

---

## 3. Typography

### 3.1 Font Stack

| Platform | Font | Fallback |
|----------|------|----------|
| macOS | SF Pro | -apple-system, Helvetica Neue |
| Windows (v2) | Segoe UI | sans-serif |

Using system fonts for readability and sharp rendering, but with custom sizing and spacing to maintain the branded feel.

### 3.2 Type Scale

| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| `--text-xs` | 10px | 400 | Pill secondary info (engine, elapsed time) |
| `--text-sm` | 12px | 400 | Settings descriptions, secondary labels |
| `--text-base` | 13px | 400 | Settings labels, dropdown items, body text |
| `--text-md` | 14px | 500 | Tab labels, section headers |
| `--text-lg` | 16px | 600 | Window titles, pill language label |
| `--text-xl` | 20px | 600 | Onboarding headings (if needed) |

### 3.3 Monospace (for transcription preview)

| Platform | Font | Fallback |
|----------|------|----------|
| macOS | SF Mono | Menlo, monospace |
| Windows (v2) | Cascadia Code | Consolas, monospace |

Used only in the live transcription preview area of the floating pill, to give a clear "raw output" feel.

---

## 4. Menu Bar Icon and Dropdown

### 4.1 Menu Bar States

The menu bar element consists of a microphone icon and a language label. It has three states:

**Idle (not dictating):**
```
┌──────────┐
│  ○ EN    │
└──────────┘
  ^  ^
  |  └── Language label in --text-secondary (#9999B0)
  └── Outlined mic icon in --text-secondary (#9999B0)
```
- Mic icon: outlined/stroke style, 16x16px
- Language label: dimmed, shows last-detected language (defaults to "EN")

**Active (dictating):**
```
┌──────────┐
│  ● HE    │
└──────────┘
  ^  ^
  |  └── Language label in --text-primary (#F0F0F5), updates in real time
  └── Filled mic icon in --accent (#8B5CF6)
```
- Mic icon: filled style, colored with `--accent`
- Language label: bright, updates as language detection changes
- Subtle glow behind the icon using `--accent-glow` (optional, if macOS menu bar supports it)

**Error (dictation failed or engine unavailable):**
```
┌──────────┐
│  ⚠ EN    │
└──────────┘
  ^
  └── Warning icon in --warning (#F59E0B), replaces mic temporarily
```
- Warning icon replaces mic icon for 5 seconds, then reverts to idle state
- Used only for critical errors (engine crash, mic disconnected)

### 4.2 Menu Bar Icon Specifications

| Property | Value |
|----------|-------|
| Icon size | 16x16px (standard macOS menu bar) |
| Icon style | Line/outlined (idle), filled (active) |
| Padding between icon and label | 4px |
| Label font | `--text-sm` (12px), medium weight |
| Total menu bar item width | ~44px ("● HE") to ~46px ("● EN") |

### 4.3 Dropdown Menu

Clicking the menu bar item opens a compact dropdown menu. This uses the custom dark translucent style (not a native NSMenu).

```
╭──────────────────────────────╮
│  SystemSTT                   │
│──────────────────────────────│
│  ● Dictation Active          │  <-- status line (green/purple when active, dim when idle)
│    Language: Hebrew           │  <-- --text-secondary
│    Engine:   Cloud API        │  <-- --text-secondary
│──────────────────────────────│
│  Start Dictation     ⌥Space  │  <-- or "Stop Dictation" when active
│  Show Preview        ⌥P      │  <-- toggles live transcription preview
│──────────────────────────────│
│  Settings...         ⌘,      │
│  Quit SystemSTT      ⌘Q      │
╰──────────────────────────────╯
```

**Dropdown specifications:**

| Property | Value |
|----------|-------|
| Width | 240px |
| Background | `--bg-translucent` with 20px backdrop blur |
| Corner radius | 10px |
| Border | 1px `--border` |
| Shadow | 0 8px 32px rgba(0, 0, 0, 0.4) |
| Padding | 8px vertical, 0px horizontal |
| Item height | 28px |
| Item padding | 8px 12px |
| Item hover | `--bg-hover` background |
| Divider | 1px `--border`, full width, 4px vertical margin |
| Shortcut text | `--text-secondary`, right-aligned |
| App title | `--text-md` (14px), `--text-primary` |

**Dynamic content:**
- "Dictation Active" / "Dictation Inactive" text changes based on state
- Status dot uses `--accent` when active, `--text-disabled` when idle
- Language and Engine lines reflect current runtime values
- "Start Dictation" / "Stop Dictation" toggles based on state
- "Show Preview" / "Hide Preview" toggles based on preview state

---

## 5. Floating Status Pill

The floating pill is the primary visual indicator during active dictation. It appears when dictation starts and disappears when dictation stops.

### 5.1 Pill States and Layouts

**Default pill (dictation active, no preview):**
```
╭────────────────────────────────╮
│  ● EN  │  ☁ Cloud   │  0:12   │
╰────────────────────────────────╯
  ^         ^             ^
  |         |             └── Elapsed time, --text-xs, --text-secondary
  |         └── Engine indicator, --text-xs, --text-secondary
  └── Recording dot (pulsing) + language, --text-lg, --text-primary
       Dot color: --accent (#8B5CF6)
```

**Pill with live transcription preview toggled on:**
```
╭────────────────────────────────╮
│  ● HE  │  ☁ Cloud   │  0:34   │
├────────────────────────────────┤
│  שלום, this is a test of       │
│  mixed language dictation...   │
╰────────────────────────────────╯
```

**Pill with inline error:**
```
╭────────────────────────────────────╮
│  ⚠ EN  │  ☁ Cloud   │  0:12       │
├────────────────────────────────────┤
│  API timeout -- retrying...        │
╰────────────────────────────────────╯
```

**Pill with voice command acknowledgment:**
```
╭────────────────────────────────────╮
│  ● EN  │  ☁ Cloud   │  1:05       │
├────────────────────────────────────┤
│  ✓ Deleted last sentence           │
╰────────────────────────────────────╯
  (auto-dismisses expansion after 2 seconds)
```

### 5.2 Pill Specifications

| Property | Value |
|----------|-------|
| Min width (collapsed) | 200px |
| Max width (with preview) | 360px |
| Height (collapsed) | 36px |
| Height (with preview) | 36px + preview area (up to 80px, ~3 lines) |
| Background | `--bg-translucent` with 20px backdrop blur |
| Corner radius | 18px (collapsed, full pill shape), 12px (expanded with preview) |
| Border | 1px `--border` |
| Shadow | 0 4px 24px rgba(0, 0, 0, 0.3) |
| Inner padding | 8px 14px |
| Divider between sections | 1px `--border`, vertical, 60% height |
| Divider before preview area | 1px `--border`, horizontal, full width |

### 5.3 Recording Dot Animation

The purple recording dot pulses gently to indicate active recording:

- **Animation:** Scale between 1.0 and 1.3, with opacity between 100% and 70%
- **Duration:** 1.5 seconds per cycle
- **Easing:** ease-in-out
- **Glow:** `--accent-glow` shadow behind the dot (0 0 8px `--accent-glow`)

When dictation is paused or an error occurs, the pulse stops and the dot changes color.

### 5.4 Engine Indicators

| Engine | Icon | Label |
|--------|------|-------|
| Cloud API (OpenAI) | ☁ (cloud symbol) | "Cloud" |
| Local Whisper | ⚙ (gear symbol) or ↓ (down arrow) | "Local" |

These are displayed in `--text-xs` size, `--text-secondary` color. They provide passive awareness of which engine is processing speech.

### 5.5 Live Transcription Preview Area

When toggled on (via `⌥P` or Settings), the preview area appears below the status bar of the pill:

| Property | Value |
|----------|-------|
| Font | Monospace (`SF Mono` / `Cascadia Code`) |
| Font size | `--text-sm` (12px) |
| Text color | `--text-primary` |
| Max visible lines | 3 |
| Scrolling behavior | Auto-scroll to latest text, newest at bottom |
| Max height | 80px (approximately 3 lines with padding) |
| Padding | 8px 14px |
| Background | Same as pill (translucent, continuous) |
| Text direction | Auto-detected (LTR for English, RTL for Hebrew) |
| Mixed direction | Uses Unicode BiDi algorithm; each segment renders in its natural direction |

The preview shows the most recent transcription output as it streams in. Text flows naturally, with Hebrew segments rendering right-to-left and English segments rendering left-to-right. When dictation ends, the preview fades out with the pill.

### 5.6 Positioning and Dragging

| Property | Value |
|----------|-------|
| Default position | Top-center of screen, 48px below the menu bar |
| Draggable | Yes, free drag to any position on screen |
| Drag handle | Entire pill surface acts as drag handle (cursor changes on hover) |
| Position persistence | Saved to user preferences; restored on next session |
| Multi-monitor | Pill stays on the monitor where the focused app is, or where it was last placed |
| Animation on appear | Fade in + slide down (200ms, ease-out) |
| Animation on disappear | Fade out + slide up (150ms, ease-in) |

### 5.7 Inline Error Behavior

When an error or status change occurs during active dictation, the pill handles it inline (ref: MRD NFR-005 graceful error handling):

| Event | Pill Behavior | Duration | Color |
|-------|---------------|----------|-------|
| API timeout | Expand with message: "API timeout -- retrying..." | Until resolved or 5s | `--warning` dot |
| API failure (persistent) | Expand with message: "Cloud API unavailable. Switch to local?" | Until user acts | `--error` dot |
| Mic disconnected | Expand with message: "Microphone disconnected" | Until resolved | `--error` dot |
| Engine switched | Expand with message: "Switched to Local engine" | 3 seconds | `--accent` dot |
| Voice command executed | Expand with message: "Deleted last word" (etc.) | 2 seconds | `--success` text |
| Language change detected | Language label updates in real time | Instant | No expansion needed |

After the display duration, the expansion area collapses smoothly (200ms ease-in-out) and the pill returns to its default state.

---

## 6. Settings Window

### 6.1 Window Properties

| Property | Value |
|----------|-------|
| Width | 480px |
| Height | 420px (fixed, no resize) |
| Background | `--bg-solid` (#1A1A2E), no translucency (solid for readability) |
| Corner radius | 12px |
| Title bar | Custom (not native), with window title and close button |
| Close button | Circular, top-right, `--text-secondary`, hover `--error` |
| Draggable | Yes, via custom title bar area |
| Open shortcut | `⌘,` (standard macOS convention, also accessible from dropdown) |
| Window position | Centered on screen when opened, does not remember position |

### 6.2 Tab Bar

Tabs sit directly below the title bar. Four tabs in v1:

```
[ General ]  [ Engine ]  [ Audio ]  [ Commands ]
```

| Property | Value |
|----------|-------|
| Tab style | Segmented, horizontal, full width of the window |
| Tab height | 36px |
| Active tab | `--accent` text, `--bg-elevated` background, 1px bottom border `--accent` |
| Inactive tab | `--text-secondary` text, transparent background |
| Hover tab | `--text-primary` text, `--bg-hover` background |
| Tab font | `--text-md` (14px), medium weight |
| Tab padding | 16px horizontal |

### 6.3 General Tab

```
╭──────────────────────────────────────────────────╮
│  SystemSTT Settings                         [x]  │
│  [ General ]  [ Engine ]  [ Audio ]  [ Commands ]│
│──────────────────────────────────────────────────│
│                                                  │
│  STARTUP                                         │
│                                                  │
│  Global Hotkey              [ ⌥ Space       ▾ ]  │
│  Start on Login             [●───────────────]   │
│  Show in Dock               [───────────────○]   │
│                                                  │
│  FLOATING INDICATOR                              │
│                                                  │
│  Show status pill           [●───────────────]   │
│  Show live preview          [───────────────○]   │
│  Reset pill position        [    Reset     ]     │
│                                                  │
│  APPLICATION                                     │
│                                                  │
│  Check for updates          [───────────────○]   │
│                                                  │
╰──────────────────────────────────────────────────╯
```

**Field details:**

| Setting | Control | Default | Notes |
|---------|---------|---------|-------|
| Global Hotkey | Dropdown or key recorder | `⌥Space` | Ref MRD FR-001: configurable system-wide hotkey |
| Start on Login | Toggle | Off | Launch as login item |
| Show in Dock | Toggle | Off | Controls LSUIElement / dock visibility |
| Show status pill | Toggle | On | Controls floating pill visibility (ref MRD FR-012) |
| Show live preview | Toggle | Off | Controls transcription preview in pill |
| Reset pill position | Button | -- | Resets pill to default top-center position |
| Check for updates | Toggle | Off | Future: auto-update mechanism |

### 6.4 Engine Tab

```
╭──────────────────────────────────────────────────╮
│  SystemSTT Settings                         [x]  │
│  [ General ]  [ Engine ]  [ Audio ]  [ Commands ]│
│──────────────────────────────────────────────────│
│                                                  │
│  STT ENGINE                                      │
│                                                  │
│  Engine                     (●) Cloud API        │
│                             ( ) Local Whisper     │
│                                                  │
│  ── Cloud API Settings ──────────────────────    │
│                                                  │
│  API Provider               [ OpenAI       ▾ ]   │
│  API Key                    [ •••••••••• ] [👁]   │
│  Status                     ● Connected          │
│                                                  │
│  ── Local Whisper Settings ──────────────────    │
│                                                  │
│  Model Size                 [ Medium       ▾ ]   │
│    tiny | base | small | medium | large          │
│                                                  │
│  ⚠ Large model may be slow on Intel i9.         │
│    Recommended: small or medium.                 │
│                                                  │
│  Model Status               ✓ Loaded (medium)   │
│  Download Model             [  Download  ]       │
│                                                  │
╰──────────────────────────────────────────────────╯
```

**Field details:**

| Setting | Control | Default | Notes |
|---------|---------|---------|-------|
| Engine | Radio buttons | Cloud API | Ref MRD FR-008: switching does not require restart |
| API Provider | Dropdown | OpenAI | Extensible for future providers |
| API Key | Masked text input + reveal toggle | Empty | Ref MRD NFR-006: stored in OS keychain |
| API Status | Status indicator (read-only) | -- | Shows "Connected", "Invalid key", "Unreachable" |
| Model Size | Dropdown | Medium | Ref MRD FR-011: tiny/base/small/medium/large |
| Model Status | Status indicator (read-only) | -- | Shows loaded model or "Not downloaded" |
| Download Model | Button | -- | Downloads selected model; shows progress bar during download |

**Behavioral notes:**
- When "Cloud API" is selected, the Local Whisper Settings section is visually dimmed (`--text-disabled`) but still visible and configurable
- When "Local Whisper" is selected, the Cloud API Settings section is dimmed
- The Intel performance warning (ref MRD section 7, hardware constraints) is always visible in the local section as a static note
- Switching engines takes effect immediately for the next dictation session (ref MRD FR-008)
- API key is stored in the macOS Keychain (ref MRD NFR-006), not in a plaintext config file

### 6.5 Audio Tab

```
╭──────────────────────────────────────────────────╮
│  SystemSTT Settings                         [x]  │
│  [ General ]  [ Engine ]  [ Audio ]  [ Commands ]│
│──────────────────────────────────────────────────│
│                                                  │
│  INPUT                                           │
│                                                  │
│  Input Device               [ USB Mic Pro  ▾ ]   │
│                                                  │
│  Input Level                                     │
│  ████████████░░░░░░░░░░  OK                      │
│                                                  │
│  The level meter is live when this tab is open.  │
│                                                  │
╰──────────────────────────────────────────────────╯
```

**Field details:**

| Setting | Control | Default | Notes |
|---------|---------|---------|-------|
| Input Device | Dropdown | System default | Ref MRD FR-013: lists all available audio input devices |
| Input Level | Live level meter (read-only) | -- | Shows real-time audio input level for selected device |

**Behavioral notes:**
- The input device dropdown dynamically lists available devices. If a device is disconnected, it is removed from the list.
- The level meter runs only when the Audio tab is open (to avoid unnecessary mic access when not needed).
- Level meter colors: green for normal, yellow for loud, red for clipping. The "OK" / "Too quiet" / "Too loud" label updates accordingly.
- This is intentionally minimal. The MRD notes (section 7) that the user has a quality mic and controlled environment, so advanced audio settings (gain, noise gate) are out of scope.

### 6.6 Commands Tab

```
╭──────────────────────────────────────────────────╮
│  SystemSTT Settings                         [x]  │
│  [ General ]  [ Engine ]  [ Audio ]  [ Commands ]│
│──────────────────────────────────────────────────│
│                                                  │
│  VOICE COMMANDS                                  │
│                                                  │
│  Enable voice commands      [●───────────────]   │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  Trigger Phrase          Action             │  │
│  │──────────────────────────────────────────── │  │
│  │  "delete last word"      Delete last word   │  │
│  │  "delete last sentence"  Delete sentence    │  │
│  │  "undo"                  Undo               │  │
│  │  "new line"              Insert line break  │  │
│  │  "new paragraph"         Insert ¶ break     │  │
│  │  "select all"            Select all         │  │
│  │  "copy"                  Copy to clipboard  │  │
│  │  "paste"                 Paste clipboard    │  │
│  │  "stop dictation"        Stop dictation     │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  Voice commands are English-only in v1.          │
│                                                  │
╰──────────────────────────────────────────────────╯
```

**Field details:**

| Setting | Control | Default | Notes |
|---------|---------|---------|-------|
| Enable voice commands | Toggle | On | Ref MRD FR-007: master toggle for voice command recognition |
| Command table | Read-only table | -- | Lists all built-in commands from MRD FR-007 |

**Behavioral notes:**
- In v1, all commands are built-in and not editable. The table is read-only and informational.
- Future v2 may add custom voice commands (ref MRD FR-021), at which point this table becomes editable with an "Add Command" button.
- The note about English-only reflects MRD section 9 (open question: Hebrew voice commands deferred).
- When voice commands are disabled, the table dims to `--text-disabled`.

### 6.7 Form Control Specifications

**Toggle switches:**

| Property | Value |
|----------|-------|
| Width | 40px |
| Height | 22px |
| Track color (off) | `--bg-active` (#3A3A5C) |
| Track color (on) | `--accent` (#8B5CF6) |
| Thumb color | `--text-primary` (#F0F0F5) |
| Corner radius | 11px (full pill) |
| Animation | 150ms ease-in-out |

**Dropdown selects:**

| Property | Value |
|----------|-------|
| Height | 28px |
| Background | `--bg-elevated` |
| Border | 1px `--border` |
| Corner radius | 6px |
| Text | `--text-base`, `--text-primary` |
| Chevron | `--text-secondary`, right side |
| Dropdown list | `--bg-translucent` with backdrop blur, same shadow as main dropdown |

**Buttons:**

| Property | Primary | Secondary |
|----------|---------|-----------|
| Height | 28px | 28px |
| Background | `--accent` | `--bg-elevated` |
| Text color | `#FFFFFF` | `--text-primary` |
| Border | None | 1px `--border` |
| Corner radius | 6px | 6px |
| Hover | `--accent-hover` | `--bg-hover` |

**Radio buttons:**

| Property | Value |
|----------|-------|
| Size | 16px diameter |
| Unselected | 2px border `--text-secondary`, transparent fill |
| Selected | 2px border `--accent`, inner dot `--accent` (8px) |

**Section headers (e.g., "STARTUP", "FLOATING INDICATOR"):**

| Property | Value |
|----------|-------|
| Font | `--text-xs` (10px), weight 600, uppercase, letter-spacing 1px |
| Color | `--text-secondary` |
| Margin | 24px top (first section 16px), 8px bottom |

**Setting rows:**

| Property | Value |
|----------|-------|
| Height | 36px |
| Layout | Label left-aligned, control right-aligned, vertically centered |
| Label font | `--text-base` (13px), `--text-primary` |
| Row spacing | 4px between rows |

---

## 7. Notification and Error Handling UX

### 7.1 Strategy

SystemSTT uses a hybrid notification approach:

- **During active dictation:** All feedback is delivered inline via the floating pill (section 5.7). This keeps the user's attention in context.
- **Background events (dictation inactive):** Native macOS notifications via Notification Center. These are for events that happen when the user is not actively dictating.

### 7.2 Inline Pill Notifications (During Dictation)

See section 5.7 for the full table. The pill expands with a message area below the status bar. Key behaviors:

- Expansion animation: 200ms ease-out
- Collapse animation: 200ms ease-in
- Error messages use `--error` color for the status dot
- Warning messages use `--warning` color
- Success messages (voice command confirmations) use `--success` color for the checkmark
- Messages are single-line, concise, actionable where applicable

### 7.3 macOS Notifications (Background Events)

These use the standard macOS notification framework (UserNotifications).

| Event | Title | Body | Priority |
|-------|-------|------|----------|
| Model download complete | SystemSTT | "Whisper medium model is ready to use" | Normal |
| Engine initialization failure | SystemSTT | "Failed to initialize Cloud API. Check your API key in Settings." | High |
| Microphone disconnected (idle) | SystemSTT | "Your microphone was disconnected" | Normal |
| Accessibility permission needed | SystemSTT | "SystemSTT needs Accessibility access to inject text. Click to open Settings." | High |
| Update available (future) | SystemSTT | "A new version is available" | Low |

**Behavioral notes:**
- Notifications are not sent for events that also show in the pill. If dictation is active and the mic disconnects, the pill handles it. If dictation is inactive, a notification fires.
- Clicking a notification with an action (e.g., "open Settings") opens the relevant settings tab.
- Ref MRD section 9: Accessibility permission guidance is surfaced on first launch via a notification or an onboarding prompt (see section 8).

---

## 8. First Launch / Onboarding

### 8.1 Scope

Onboarding is minimal. The MRD (NFR-007) specifies sensible defaults and minimal setup complexity. The only blocking requirement is granting Accessibility permissions (ref MRD section 9).

### 8.2 Flow

On first launch:

1. **Accessibility Permission Prompt** -- A single modal dialog (custom styled, matching the app's dark theme) explaining why the permission is needed and a button to open System Settings > Privacy > Accessibility. This is the only onboarding screen.

```
╭──────────────────────────────────────────────╮
│                                              │
│       SystemSTT needs Accessibility          │
│       permission to type text into           │
│       other applications.                    │
│                                              │
│       This is required for dictation         │
│       to work system-wide.                   │
│                                              │
│       [ Open System Settings ]               │
│       [ Remind Me Later    ]                 │
│                                              │
╰──────────────────────────────────────────────╯
```

2. **Menu bar icon appears** -- After dismissing the dialog, the app is live in the menu bar with default settings. No further setup required.

3. **Default state** -- The app launches with:
   - Engine: Cloud API (best accuracy for Intel Mac, per MRD section 7)
   - Hotkey: `⌥Space`
   - Language detection: Auto
   - Floating pill: On
   - Live preview: Off
   - Voice commands: On
   - Dock icon: Hidden

If the user has not set an API key and tries to dictate with Cloud API selected, the pill shows: "No API key configured. Open Settings?" with an inline action.

---

## 9. Keyboard Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| `⌥Space` | Toggle dictation on/off | Global (system-wide), configurable |
| `⌥P` | Toggle live transcription preview | Global (when dictation is active) |
| `⌘,` | Open Settings | When dropdown is open or app is focused |
| `⌘Q` | Quit SystemSTT | When dropdown is open or app is focused |

Note: The global hotkey (`⌥Space` default) is configurable in Settings (ref MRD FR-001). The app must register it via macOS accessibility APIs.

---

## 10. Dock Behavior

| Property | Value |
|----------|-------|
| Default dock visibility | Hidden (LSUIElement = YES) |
| Configurable | Yes, via Settings > General > "Show in Dock" toggle |
| Cmd-Tab visibility | Hidden by default; visible when "Show in Dock" is enabled |
| App Switcher behavior | When hidden from dock, Settings window can still be opened via menu bar dropdown |

Ref MRD: SystemSTT is a background utility. Hiding from the dock is the expected default for menu bar apps.

---

## 11. Animations and Transitions

All animations use ease-in-out timing unless otherwise specified. Durations are intentionally short -- this is a utility, not an experience app.

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Pill appear | Fade in + translate Y -8px to 0 | 200ms | ease-out |
| Pill disappear | Fade out + translate Y 0 to -8px | 150ms | ease-in |
| Pill expand (preview/error) | Height expansion | 200ms | ease-in-out |
| Pill collapse | Height reduction | 200ms | ease-in-out |
| Recording dot pulse | Scale 1.0 to 1.3, opacity 100% to 70% | 1500ms loop | ease-in-out |
| Dropdown open | Fade in + scale 0.95 to 1.0 | 150ms | ease-out |
| Dropdown close | Fade out + scale 1.0 to 0.95 | 100ms | ease-in |
| Toggle switch | Thumb translation + track color | 150ms | ease-in-out |
| Tab switch | Content crossfade | 150ms | ease-in-out |
| Error flash on pill | Dot color transition to `--error` | 200ms | ease-in-out |

---

## 12. Accessibility

Even though this is a single-user developer tool, basic accessibility should be maintained for good practice and future-proofing:

| Requirement | Implementation |
|-------------|----------------|
| Keyboard navigation | All settings controls reachable via Tab key |
| Focus indicators | 2px `--accent` outline on focused elements |
| Screen reader labels | All controls have descriptive labels (VoiceOver on macOS) |
| Contrast ratios | All text meets WCAG AA (4.5:1 minimum) against dark backgrounds |
| Reduced motion | Respect `prefers-reduced-motion`: disable pulse animation, use instant transitions |

---

## 13. Platform Considerations

### 13.1 macOS (v1)

| Concern | Approach |
|---------|----------|
| Menu bar integration | NSStatusItem with custom view (icon + label) |
| Floating pill | NSPanel (non-activating, floating level, no shadow in window list) |
| Translucency/blur | NSVisualEffectView with `.behindWindow` material |
| Global hotkey | Carbon `RegisterEventHotKey` or `CGEvent` tap |
| Text injection | Accessibility API (AXUIElement) for cursor-position text insertion |
| Settings window | NSWindow with custom drawing, no native title bar |
| Notifications | UserNotifications framework |
| Keychain | Security framework for API key storage |
| Dock hiding | `LSUIElement` in Info.plist, toggled at runtime |

### 13.2 Windows (v2, Future)

| Concern | Approach |
|---------|----------|
| System tray | NotifyIcon or equivalent |
| Floating pill | WS_EX_TOOLWINDOW, topmost, click-through option |
| Translucency/blur | DWM Acrylic or Mica material |
| Global hotkey | RegisterHotKey API |
| Text injection | SendInput / UI Automation |
| Settings window | Custom-drawn window matching the same design spec |
| Notifications | Windows Toast notifications |
| Credential storage | Windows Credential Manager |

The custom visual design ensures the app looks and feels identical on both platforms, with only the underlying implementation differing.

---

## 14. State Machine Summary

For implementation reference, here is the full state diagram of the app's visual states:

```
                    ┌─────────────┐
                    │    IDLE      │
                    │  Menu bar:   │
                    │  outlined,   │
                    │  dimmed      │
                    │  Pill: hidden│
                    └──────┬──────┘
                           │
                    Hotkey pressed (⌥Space)
                           │
                    ┌──────▼──────┐
                    │   ACTIVE     │
                    │  Menu bar:   │
                    │  filled,     │
                    │  purple,     │
                    │  bright lang │
                    │  Pill: shown │
                    │  Dot: pulsing│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        Error occurs   Voice cmd    Language
              │         detected     changes
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐  ┌───▼────┐
        │  ACTIVE    │ │ ACTIVE │  │ ACTIVE │
        │  +ERROR    │ │ +CMD   │  │ lang   │
        │  Pill:     │ │ Pill:  │  │ label  │
        │  expanded, │ │ expand │  │ updates│
        │  red/amber │ │ brief  │  │ in     │
        │  dot       │ │ ✓ msg  │  │ real   │
        └─────┬─────┘ └───┬────┘  │ time   │
              │            │       └───┬────┘
              └────────────┼───────────┘
                           │
                    Hotkey pressed (⌥Space)
                    or "stop dictation"
                           │
                    ┌──────▼──────┐
                    │    IDLE      │
                    └─────────────┘
```

---

## 15. Asset Requirements

| Asset | Format | Sizes | Notes |
|-------|--------|-------|-------|
| Menu bar mic icon (outlined) | SVG + PNG | 16x16, 32x32 (@2x) | Monochrome, `--text-secondary` |
| Menu bar mic icon (filled) | SVG + PNG | 16x16, 32x32 (@2x) | Monochrome, colored via `--accent` at runtime |
| Menu bar warning icon | SVG + PNG | 16x16, 32x32 (@2x) | Monochrome, colored via `--warning` at runtime |
| Cloud engine icon | SVG | 12x12 | For pill and settings |
| Local engine icon | SVG | 12x12 | For pill and settings |
| App icon (for Dock/About) | ICNS + ICO | 16 through 1024px | Custom branded icon, purple accent |
| Checkmark icon | SVG | 12x12 | For voice command confirmation |
| Warning triangle icon | SVG | 12x12 | For inline errors |

---

## 16. Appendix: Design Decision Log

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Menu bar presence | Icon + mini language label | At-a-glance bilingual awareness without opening dropdown |
| 2 | Dictation indicator | Menu bar change + floating pill (both) | Dual feedback: passive awareness + active confirmation |
| 3 | Floating pill content | Status pill + toggleable live preview | Essential info always visible; transcription detail on demand |
| 4 | Settings window style | Compact single-page with tabs | Bounded settings, quick to scan, efficient to build |
| 5 | Error/notification strategy | Hybrid: pill inline + macOS notifications | Feedback where attention already is |
| 6 | Visual aesthetic | Custom/branded | Cross-platform consistency for Mac and future Windows |
| 7 | Theme | Dark-only with translucent/glassy surfaces | Premium feel, less design surface, developer preference |
| 8 | Accent color | Purple/violet (#8B5CF6) | Distinctive, high contrast on dark, modern feel |
| 9 | Pill positioning | Draggable, position remembered | Adapts to user's workflow and app layouts |
