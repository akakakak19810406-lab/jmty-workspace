---
name: jmty-dual-account-posting
description: Dual-account Jimoty/JMTY posting rules for posting with both Boost.Work and でぐち accounts in the same cycle, including account-specific company names, independent pending states, daily limits, and per-account scheduling.
---

# JMTY Dual Account Posting

## Purpose

Use this skill when the user asks to post on both approved JMTY accounts, post "同時に", or continue posting across the Boost.Work and でぐち accounts.

This skill controls only account selection, account-specific form values, posting order, pending handling, and per-account limits. For source spreadsheet, rewrite, image, category, region, and form-field rules, also read `.agent/skills/jmty/jmty-auto-posting-rules/SKILL.md`.

## Approved Accounts

- `Boost.Work`
- `でぐち`

Do not post from any other account unless the user explicitly approves it and provides the company name to use.

## Company Name Mapping

- If the logged-in JMTY account is `Boost.Work`, enter `Boost.Work` in the company name field.
- If the logged-in JMTY account is `でぐち`, enter `株式会社Keystone` in the company name field.
- If the account name is unclear or different, stop before submitting and ask the user.

Never reuse the company name from the previous account's form state. Confirm or set the company name for each account lane independently.

## Account Lanes

Treat each account as a separate posting lane:

- company name
- selected post row / role
- selected image
- selected region
- used prefectures for the day
- completed post count for the day
- confirmation-pending state
- next allowed posting time
- completion URL / post ID

A block in one lane must not block the other lane unless the block is global, such as JMTY site outage, browser failure, or user cancellation.

## Simultaneous Posting Flow

1. Identify the requested target accounts.
   - If the user says both accounts, simultaneous posting, or does not name a single account, target both `Boost.Work` and `でぐち`.
   - If the user explicitly names one account, target only that account.
2. Open or switch to the correct logged-in browser context for each target account.
3. If both accounts are available, prepare one post per account in the same cycle.
4. Use a separate tab/session per account when possible.
5. Fill and submit the `Boost.Work` post using company name `Boost.Work`.
6. Fill and submit the `でぐち` post using company name `株式会社Keystone`.
7. Read each completion page separately and record its result.
8. If one account is blocked by confirmation-pending, CAPTCHA, authentication, or an unknown account name, skip only that account and continue with the other eligible account.

## Pending And Timing Rules

- Target cadence is every 90 minutes per account from 10:00.
- Daily limit is 10 posts per account.
- If an account completion page shows `投稿内容を確認中です` or mentions average 30 minutes / maximum 1 business day, mark only that account as pending.
- A pending account should not submit another post until 90 minutes have elapsed or the posting-management page shows all posts are no longer受付中/確認中 and have moved to受付終了/cleared status.
- If the completion page does not show `投稿内容を確認中です`, that account may continue to the next post immediately, as long as it stays under 10 posts for the day.
- Do not wait inside a long-running browser session after a submission. End the run cleanly, then start a new run after 90 minutes when scheduling is needed.

## Posting Management Check

Before resuming a pending account:

1. Open that account's JMTY posting management page.
2. Check the current status of recent posts.
3. Resume posting only when all relevant posts for that account are no longer in the active confirmation/受付中 state and have cleared to受付終了 or another completed/non-blocking state.
4. If statuses are ambiguous, stop and ask the user rather than forcing another submission.

## Browser And Auth Safety

- Use Kimi WebBridge for JMTY browser work.
- Stop and ask the user if password entry, 2FA, CAPTCHA, account recovery, or another private authentication step appears.
- If the browser is logged into only one account and the other account cannot be reached through an existing switch path or provided URL, stop and ask the user to switch manually.
- Keep account-specific tabs clearly separated; avoid copying hidden form state or completion URLs between accounts.

## Reporting

For each account attempted, report:

- account name
- company name used
- post role/title
- post ID or completion URL if available
- whether `投稿内容を確認中です` appeared
- whether the lane is eligible for another post now or must wait 90 minutes

Also report skipped accounts and the reason they were skipped.
