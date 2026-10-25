# Finbo design direction

Owner's direction (2026-10-25, second round): the first design read as "messy, boring and
hard to understand". New brief: **chat-first**, an **animal crew** of named agents, and a
look that is **warm and friendly with some playful boldness**, so it suits young adults and
middle-aged users alike. Designed around what a user wants to do, not around the data.

Dial: ENERGY 2 / RHYTHM 2 / MOTION 2

Design Read: a chat-first personal-finance app for everyday people in India and the US,
in a warm, friendly, character-led style.

## Principles

1. **Ask, don't hunt.** Home is a conversation. Every number is one question away, and
   every starter question is a button.
2. **Someone owns every screen.** Each page belongs to a crew member, so users always know
   who to ask: Money is Penny, Hazel and Snowy; Markets is Bruno.
3. **Plain questions as headings.** "When will I be debt-free?", not "Debt amortisation".
4. **One thing to do next.** Each card ends with at most one primary action.
5. **Same crew everywhere.** Web and Telegram use the same names, avatars, words and numbers.

## The crew (identity system)

| Crew | Job | Avatar | Brand colour | Text colour (light) | Colour (dark) |
|---|---|---|---|---|---|
| Finbo the Fox | Guide, routes questions | 🦊 | `#E8590C` | `#C2410C` | `#FF922B` |
| Penny the Penguin | Spending | 🐧 | `#1971C2` | `#1864AB` | `#74C0FC` |
| Hazel the Squirrel | Safety net | 🐿️ | `#B35C00` | `#9A4E00` | `#FFA94D` |
| Snowy the Owl | Debts | 🦉 | `#6741D9` | `#6741D9` | `#B197FC` |
| Bruno the Bull | Markets | 🐂 | `#2B8A3E` | `#237032` | `#69DB7C` |
| Scout the Otter | News | 🦦 | `#0C8599` | `#0B7285` | `#66D9E8` |

Scout was going to be a ferret; Unicode has no ferret emoji, so Scout is an otter.

**Emoji as avatars (a deliberate exception).** antislop discourages emoji as decoration.
Here each emoji *is* an agent's identity: it appears only inside that agent's avatar badge
(and in Telegram, where custom per-agent images aren't possible), never in body copy.
They can be swapped for illustrated avatars later without changing anything else.
The web app loads **Noto Color Emoji** from Google Fonts (split by character range, so only
the six faces download) so the crew looks the same on every phone and laptop, including
Linux machines with no colour-emoji font.

Crew colours appear only on avatars, crew name labels and the thin progress fills that
belong to that crew member, never on page chrome. All text uses verified shades (contrast
checked with antislop's contrast-check.py: every text pairing is at least 4.5:1).

## Palette (core, neutrals excluded)

| Token | Light | Dark | Role |
|---|---|---|---|
| Page | `#F6F5FB` | `#14121F` | A faint lilac white, so white cards lift off it gently |
| Card | `#FFFFFF` | `#1E1B2C` | Chat bubbles and cards |
| Ink | `#1C1830` | `#F1EFF8` | Text; also the primary button (17:1 with white) |
| Muted | `#5B5670` | `#B3AEC7` | Secondary text (6.4:1 and 8.6:1) |
| Finbo orange | `#FF922B` | `#FF922B` | The one accent: the "send" button, active states, brand moments. Text on it is ink (7.7:1) |

## Type

- **Bricolage Grotesque** (600 to 800): headings and big numbers. It has visible character
  (playful for younger users) while staying a sturdy grotesk (credible for older ones).
- **Figtree** (400 to 700): everything else. Open, generous letterforms that stay legible at
  small sizes, which matters for a wide age range.
- Body text 17px minimum; sentence case everywhere.

## Layout

- **Desktop:** crew list (left), conversation (centre), "My money" panel (right).
- **Tablet:** the crew becomes a row of avatars above the chat; "My money" is its own page.
- **Phone:** avatar row under the header, full-height chat, bottom tab bar
  (Chat, Money, Markets, Plans, Settings).
- **Radius by role:** cards and bubbles 20px, buttons 12px, inputs 14px, quick-question chips
  fully rounded (they are tappable suggestions, the one pill shape).
- **Shadow:** only on what floats (the message composer, menus, dialogs).

## Motion (MOTION 2)

- New messages slide up 8px and fade in: shows what just arrived.
- While a crew member works, a three-dot typing indicator shows in their bubble; it stops as
  soon as the reply lands.
- Approved plans get a short "stamp" scale: confirms the decision registered.
- Nothing loops on its own. All motion is off under prefers-reduced-motion.

## Not decided yet

- Logo: the wordmark is "finbo" set in Bricolage Grotesque; the favicon is Finbo's fox
  emoji. Neither is a designed mark.
