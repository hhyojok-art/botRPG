Feature Summary — Recent additions

This file highlights the new/updated features and how to use them quickly.

Badges / Achievements
- `!badges [member]` — list badges owned by a member.
- `!badges show icon <badge_key>` — display badge image (Assets/badges/<badge_key>.png).
- `!badges giftowner <badge_key>` — staff or bot owner: grant a badge to the server owner.
- `badge select <badge_key>` — select a badge to show on profile.

Profile
- `!profile [member]` — renders a profile card showing avatar, level, progress, stats, and the selected badge (if asset exists).
- If profile image generation fails, the bot sends a compact embed and attaches the badge thumbnail (uses asset if present, otherwise generates an initials icon).

Daily Quests
- `!quest` — create/show today's quest.
- `!progress [amount]` — report quest progress; when target reached the bot awards rewards, deletes the quest row, and sends an Undertale-style congratulations image.

Assets & Fonts
- Badge icons: `Assets/badges/<badge_key>.png`.
- Optional Undertale font: `Assets/fonts/undertale.ttf` (used for profile and congrats images).

See `docs/FEATURES.md` for full details and testing notes.
