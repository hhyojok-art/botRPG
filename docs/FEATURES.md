Features — Bot enhancements

This document lists recent features and how to use them.

1. Badges / Achievements
- `!badges [member]` — List badges a member has earned.
- `!badges show icon <badge_key>` — Show the badge image (from Assets/badges/<badge_key>.png).
- `!badges giftowner <badge_key>` — Staff or bot owner: grant a badge to the server owner.
- `badge select <badge_key>` — Select a badge you own to show in your profile.
- Badge images are loaded from `Assets/badges/`. If an image is missing, a small fallback icon (initials) is generated.

2. Profile
- `!profile [member]` — Renders a profile card image including avatar, level, progress bar, and stats.
- The selected badge (from `badge select`) is shown on the profile card if `Assets/badges/<key>.png` exists.
- When image rendering fails, the bot falls back to a compact embed and will attach the badge thumbnail (prefers asset, otherwise generates initials image).

3. Daily Quests
- `!quest` — Create or show today's quest for the user (random quest chosen from a pool).
- `!progress [amount]` — Report progress toward the active quest. Typically called automatically by other cogs.
- When a quest reaches its target, the bot:
  - Awards configured rewards (gold, XP, item).
  - Deletes the finished quest from the database so `!quest` returns none until a new quest is created.
  - Sends an Undertale-style congratulations image (uses `Assets/fonts/undertale.ttf` if present).

4. Misc
- Several new utilities and safeguards were added: DB helpers for badges, buff support, and fallback handling when assets or Redis are unavailable.

Where assets live
- Badge icons: `Assets/badges/<badge_key>.png`
- Fonts (optional): `Assets/fonts/undertale.ttf` — used for profile / congrats images when present.

Notes for testing
- Restart the bot after code changes to pick up cogs.
- Test flow for daily quests: run `!quest`, then call `!progress` repeatedly (or use `!progress <amount>`) until completion to see reward delivery and the congrats image.

Contact
- If an asset is missing and the fallback looks wrong, add a PNG file named with the badge key under `Assets/badges/` to customize.
