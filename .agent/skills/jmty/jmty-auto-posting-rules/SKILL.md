---
name: jmty-auto-posting-rules
description: JMTY job-post automation rules for the approved Boost.Work and でぐち accounts. Use when Codex needs to create, rewrite, select Drive images, schedule, or submit Jimoty/JMTY job posts from the approved Google Spreadsheet, including remote and factory posting rules, form-field conventions, Kimi WebBridge browser operation, per-account daily limits, and confirmation-pending wait behavior.
---

# JMTY Auto Posting Rules

## Overview

Use this skill to prepare and submit JMTY job posts for the approved accounts while preserving the user's posting conventions. Treat the spreadsheet row as the source of truth for job text and pay, rewrite with `.agent/skills/jmty/jmty-post-rewrite-rules/SKILL.md`, and choose the posting image from the approved Google Drive image folder according to the rules below.

For requests involving both accounts, simultaneous posting, account-specific company names, or per-account pending/cadence management, also read `.agent/skills/jmty/jmty-dual-account-posting/SKILL.md`.

## Source

- Spreadsheet: `https://docs.google.com/spreadsheets/d/1NCSafKOXSPoY1_gqKiVKAuTRDUuGn8-7Vy-uwPFWAbk/edit?gid=1455237937#gid=1455237937`
- Sheet tab: `アカウント情報`
- Company name depends on the logged-in JMTY account:
  - If the logged-in account name is `Boost.Work`, enter `Boost.Work`.
  - If the logged-in account name is `でぐち`, enter `株式会社Keystone`.
  - If another account name appears, stop and ask the user which company name to use.
- Use the post text in the spreadsheet for role, pay, CTA URL, and rewrite direction.
- Do not use the image immediately to the left of the spreadsheet post text for new submissions.
- Approved image library root: `https://drive.google.com/drive/u/0/folders/1aXdFyXpWyIzFGGPUClVOGeQRe1J7ru8x`
- Rewrite source of truth: `.agent/skills/jmty/jmty-post-rewrite-rules/SKILL.md`
- Do not use Gemini GEM or any external GEM prompt for post rewriting unless the user explicitly asks to switch back.
- If a newer spreadsheet is present but the user did not explicitly switch to it, use the URL above.

## Target Accounts

Dual-account behavior is defined in `.agent/skills/jmty/jmty-dual-account-posting/SKILL.md`. The rules below are the short local summary and must stay consistent with that skill.

- When the user asks for posting without naming one account, post for both approved accounts in the same posting cycle:
  - `Boost.Work`
  - `でぐち`
- Treat the two accounts as separate lanes. Each lane has its own company name, post count, used prefectures, confirmation-pending state, and next allowed posting time.
- For simultaneous posting, open and operate each account in its own tab/session when possible. Do not let one account's form state, company name, selected region, or completion result overwrite the other.
- If both accounts are available, create one post for `Boost.Work` and one post for `でぐち` during the same cycle.
- If one account is blocked by `投稿内容を確認中です`, authentication, CAPTCHA, or an unknown company-name mapping, skip only that account and continue with the other account when it is eligible.
- If the browser is currently logged into only one account, use the explicit URL or account switch path the user provides. If the requested account cannot be reached without password, 2FA, CAPTCHA, or private-auth action, stop and ask the user to switch manually.

## Posting Cadence

- Target schedule: from 10:00, every 1.5 hours, up to 10 posts per day per account.
- Desired daily mix per account: 9 remote posts and 1 factory post, unless the user changes the mix.
- If the completion page for an account does not show `投稿内容を確認中です`, that account may continue to the next post immediately while staying under 10 posts/day for that account.
- If the completion page for an account shows `投稿内容を確認中です` or mentions average 30 minutes / maximum 1 business day, pause only that account for 90 minutes or until its posting-management status clears.
- Do not pause the other account just because one account is confirmation-pending.
- The user has approved posting without pre-submit confirmation. Do not pause for content approval unless the user explicitly asks to review before posting.
- Stop and ask the user to act manually if a password, 2FA, CAPTCHA, account recovery, or other credential/private-auth step appears.

## Browser Operation

- Use Kimi WebBridge for Jimoty/JMTY and Google Sheets browser tasks because it can access the user's logged-in Chrome session.
- Prefer `snapshot` for reading pages and semantic refs; use `evaluate` for form-field filling, select changes, image DataTransfer uploads, and completion-page text checks.
- If Kimi finds the wrong tab, activate the exact Chrome tab first or call `find_tab` with `active:true`.
- For images, direct upload can fail. Use a JS `DataTransfer` assignment to `#upload_tag`, dispatch `input` and `change`, then wait for an `async_file[...]` hidden input.

## Form Field Rules

- Main category group: `正社員`.
- Company name / `article[company_name]`: use the account-specific company name mapping from the Source section. Do not reuse `Boost.Work` when logged in as `でぐち`.
- Employment type: `契約社員`.
- Pay system: `月収`.
- Pay input field: digits only, no decimals or Japanese units. Example: `396000`, `421000`.
- Title/body pay display: use decimal + `万円`. Example: `39.6万円`, `42.1万円`.
- Pay note / pay string: leave blank.
- Working hours for remote posts: `基本的に自由` in both form field and body.
- Station: do not select or fill station. Leave station fields blank.
- Address/work location field: use the selected posting region, such as `宮城県仙台市`, even for remote posts.
- Body location for remote posts: keep it place-neutral, usually `完全在宅（フルリモート）`; do not include `全国` or random place names in the remote body text.

## Category Rules

- Avoid `事務` as the category by default.
- Choose the closest real category and subcategory for the actual job.
- Factory posts: `物流 -> 工場`.
- Canva/designer posts: `クリエイティブ -> デザイン` or closest designer-related subcategory.
- Writer/note/Kindle posts: `クリエイティブ -> ライター`.
- SNS operation posts: prefer `企画 -> マーケティング`.
- AI influencer posts: prefer `クリエイティブ -> 広告業界`.
- Video creator posts: prefer `クリエイティブ -> ディレクター` or the closest video/creative option available.

## Region Rules

- Remote posts: choose random prefectures/cities and avoid duplicate prefectures within the same day for the same account.
- Region history is account-specific. A prefecture used by `Boost.Work` does not block `でぐち`, and a prefecture used by `でぐち` does not block `Boost.Work`.
- Factory posts: use the prefecture found in the factory post text. City/county below the prefecture may be random or the closest matching city.
- Do not fill station names.
- Keep a running count of today's used prefectures and post count per account in the current work session.

## Text Rewrite Rules

- Before rewriting a post, read `.agent/skills/jmty/jmty-post-rewrite-rules/SKILL.md` and follow it as the primary writing instruction.
- Do not use Gemini GEM or any external GEM prompt for rewriting.
- Rewrite from the spreadsheet post text, preserving the job type, pay amount, CTA URL, and overall sales angle.
- Make the title include: monthly pay, AI learning merit/necessity, actual job role, `WワークOK`, and `完全在宅` for remote posts.
- For remote posts, emphasize AI-era value: AI may replace jobs, AI can multiply efficiency and income, others may not yet use AI well, and now is still a good time to start.
- Replace generic or incorrect job labels with actual occupations. Example: `AI活用ライター募集` should become `note記事ライター` when the row is note writing.
- Normalize remote body bullets:
  - `雇用形態：契約社員（WワークOK）`
  - `勤務地：完全在宅（フルリモート）`
  - `勤務時間：基本的に自由`
  - `給与：月収X.X万円目安...`
- End each body with a polished, aspirational closing sentence. Vary the wording. Examples:
  - `時代の変化をいち早く味方につけ、AIと新しい働き方へ向かって第一歩を踏み出す、意欲あるあなたからのご応募を心よりお待ちしております。`
  - `最先端のテクノロジーを駆使しながら、これまでにないスピード感で共に新しいキャリアを築いていける、熱意あふれるあなたからのご応募を心よりお待ちしております。`
  - `変化の激しい時代だからこそ、確かなスキルと場所に縛られない働き方を手に入れたいあなたからのご応募を、選考担当一同お待ちしております。`

## Image Rules

- New submissions must get images from the approved Google Drive image library root, not from spreadsheet-adjacent cells.
- Open the Drive root and choose the folder that best matches the actual job role. Examples:
  - `Kindleライター`, `note記事ライター`, or other writing roles: choose a writing folder such as Kindle, note, writer, or ライター.
  - `HP/LP制作`, `Web制作`, or `webデザイナー`: choose an HP, LP, Web, website, homepage, or web designer folder.
  - `画像生成アシスタント`: choose an image generation, AI image, creative, or design folder.
  - `SNS運用` or `AIマーケター`: choose an SNS, marketing, marketer, or social media folder.
  - `AIインフルエンサー`: choose an influencer, advertising, SNS, or creator folder.
  - `動画クリエイター`: choose a video, movie, creator, director, or editing folder.
  - `工場` or manufacturing roles: choose a factory, manufacturing, logistics, or 工場 folder.
- If multiple folders fit the role, choose one randomly. If one folder fits, use it.
- From the selected role folder, choose one image file randomly for the post.
- If the role folder has subfolders, use the closest matching subfolder first; otherwise randomly choose from image files in that folder.
- Do not reuse a Drive image in the same posting day when enough alternatives exist.
- If no suitable folder or image can be found, stop and ask the user instead of falling back to spreadsheet-adjacent images.
- Download or otherwise prepare the chosen Drive image for upload, then upload it to JMTY with the usual `#upload_tag` DataTransfer method.
- Verify the final upload preview has an `async_file[...]` hidden input and visually inspect the selected image when feasible.

## Submission Workflow

1. Identify the eligible target accounts for this cycle: `Boost.Work`, `でぐち`, or the single account explicitly requested by the user.
2. For each target account, check today's completed post count, used prefectures, and whether that account's last completion page or posting-management page is confirmation-pending.
3. If one account is confirmation-pending and 90 minutes have not elapsed, skip only that account for this cycle.
4. Read the target spreadsheet row and identify the role, text, pay, and CTA URL.
5. Rewrite title and body using the rules above.
6. Open the approved Google Drive image library, choose the role-matching folder, randomly select one image, and inspect it.
7. Open the JMTY new job post form in the logged-in browser.
8. Fill category, region, title, body, company, pay, employment type, working hours, address, and image.
9. Submit without a pre-submit confirmation pause unless the user asked to review.
10. Read the completion page. Record post ID/URL and whether `投稿内容を確認中です` appeared.
11. Repeat the workflow for the other eligible account in a separate tab/session during the same cycle.
12. Continue immediately or wait 90 minutes per account according to the cadence rules.

## Current Known Post Examples

- Kindle AI writer: title pattern `月収39.6万円｜AI時代に学び稼ぐKindleライター｜完全在宅・WワークOK`; pay field `396000`; category `クリエイティブ -> ライター`.
- Factory auto manufacturing: title pattern `月収40万円｜入社祝い金160万円｜自動車製造スタッフ｜契約社員`; pay field `400000`; category `物流 -> 工場`; factory region from text.
- AI influencer: title pattern `月収42.1万円｜AIを学び収入を伸ばすAIインフルエンサー｜完全在宅・WワークOK`; pay field `421000`; category `クリエイティブ -> 広告業界`.
- SNS operation: title pattern `月収36.8万円｜AIでSNS運用を学び稼ぐ運用スタッフ｜完全在宅・WワークOK`; pay field `368000`; category `企画 -> マーケティング`.
- Video creator: title pattern `月収33.5万円｜AIで動画制作を学び稼ぐ動画クリエイター｜完全在宅・WワークOK`; pay field `335000`; category `クリエイティブ -> ディレクター`.
