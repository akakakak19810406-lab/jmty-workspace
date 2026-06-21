---
name: jmty-auto-posting-rules
description: JMTY job-post automation rules for Boost.Work. Use when Codex needs to create, rewrite, image-match, schedule, or submit Jimoty/JMTY job posts from the approved Google Spreadsheet, including remote and factory posting rules, form-field conventions, Kimi WebBridge browser operation, daily limits, and confirmation-pending wait behavior.
---

# JMTY Auto Posting Rules

## Overview

Use this skill to prepare and submit Boost.Work job posts on Jimoty/JMTY from the approved spreadsheet while preserving the user's posting conventions. Treat the spreadsheet row as the source of truth, but normalize fields, title, body, category, image, and posting cadence according to the rules below.

## Source

- Spreadsheet: `https://docs.google.com/spreadsheets/d/1NCSafKOXSPoY1_gqKiVKAuTRDUuGn8-7Vy-uwPFWAbk/edit?gid=1455237937#gid=1455237937`
- Sheet tab: `アカウント情報`
- Company/account name: `Boost.Work`
- Use the post text in the spreadsheet and the image immediately to the left of that post text.
- If a newer spreadsheet is present but the user did not explicitly switch to it, use the URL above.

## Posting Cadence

- Target schedule: from 10:00, every 1.5 hours, up to 10 posts per day.
- Desired daily mix: 9 remote posts and 1 factory post, unless the user changes the mix.
- If the completion page does not show `投稿内容を確認中です`, continue to the next post immediately while staying under 10 posts/day.
- If the completion page shows `投稿内容を確認中です` or mentions average 30 minutes / maximum 1 business day, wait 90 minutes before the next post.
- The user has approved posting without pre-submit confirmation. Do not pause for content approval unless the user explicitly asks to review before posting.
- Stop and ask the user to act manually if a password, 2FA, CAPTCHA, account recovery, or other credential/private-auth step appears.

## Browser Operation

- Use Kimi WebBridge for Jimoty/JMTY and Google Sheets browser tasks because it can access the user's logged-in Chrome session.
- Prefer `snapshot` for reading pages and semantic refs; use `evaluate` for form-field filling, select changes, image DataTransfer uploads, and completion-page text checks.
- If Kimi finds the wrong tab, activate the exact Chrome tab first or call `find_tab` with `active:true`.
- For images, direct upload can fail. Use a JS `DataTransfer` assignment to `#upload_tag`, dispatch `input` and `change`, then wait for an `async_file[...]` hidden input.

## Form Field Rules

- Main category group: `正社員`.
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

- Remote posts: choose random prefectures/cities and avoid duplicate prefectures within the same day.
- Factory posts: use the prefecture found in the factory post text. City/county below the prefecture may be random or the closest matching city.
- Do not fill station names.
- Keep a running count of today's used prefectures and post count in the current work session.

## Text Rewrite Rules

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

- Use the image immediately to the left of the selected post text in the spreadsheet.
- Crop so the full poster/image is visible; avoid cutting off edges, price, role title, QR/CTA-like footer, or right-side elements.
- If the user points out a specific image framing issue, scope the crop fix only to that post type unless they broaden the request.
- For Kindle writer, avoid excess left margin and preserve the right side of the image.
- Verify the final upload preview has an `async_file[...]` hidden input and visually inspect the crop when feasible.

## Submission Workflow

1. Check today's completed post count, used prefectures, and whether the last completion page was confirmation-pending.
2. If the last post was confirmation-pending and 90 minutes have not elapsed, wait.
3. Read the target spreadsheet row and identify the role, text, pay, and image immediately to the left of the text.
4. Rewrite title and body using the rules above.
5. Prepare the image crop and inspect it for full-poster visibility.
6. Open the JMTY new job post form in the logged-in browser.
7. Fill category, region, title, body, company, pay, employment type, working hours, address, and image.
8. Submit without a pre-submit confirmation pause unless the user asked to review.
9. Read the completion page. Record post ID/URL and whether `投稿内容を確認中です` appeared.
10. Continue immediately or wait 90 minutes according to the cadence rules.

## Current Known Post Examples

- Kindle AI writer: title pattern `月収39.6万円｜AI時代に学び稼ぐKindleライター｜完全在宅・WワークOK`; pay field `396000`; category `クリエイティブ -> ライター`.
- Factory auto manufacturing: title pattern `月収40万円｜入社祝い金160万円｜自動車製造スタッフ｜契約社員`; pay field `400000`; category `物流 -> 工場`; factory region from text.
- AI influencer: title pattern `月収42.1万円｜AIを学び収入を伸ばすAIインフルエンサー｜完全在宅・WワークOK`; pay field `421000`; category `クリエイティブ -> 広告業界`.
- SNS operation: title pattern `月収36.8万円｜AIでSNS運用を学び稼ぐ運用スタッフ｜完全在宅・WワークOK`; pay field `368000`; category `企画 -> マーケティング`.
- Video creator: title pattern `月収33.5万円｜AIで動画制作を学び稼ぐ動画クリエイター｜完全在宅・WワークOK`; pay field `335000`; category `クリエイティブ -> ディレクター`.
