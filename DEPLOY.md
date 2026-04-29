# Deployment & Thinkific configuration

This release adds an enrollment-gated access system. The app now refuses
submissions unless Thinkific has reported the enrollment via a signed webhook.

## Deployment ordering (important)

Configure the Thinkific webhook **before** rolling these changes to live
customers. Without it, no new submissions can be made — only enrollments
that have arrived via webhook will be accepted.

1. Set Render env vars (see below).
2. Configure Thinkific webhook (see below).
3. Verify with a test purchase.
4. Deploy this branch to Render.

## 1. Render environment variables

Add to the `cehub-cs-cr-coach` service on Render:

| Variable                    | Required | Notes                                                          |
|-----------------------------|----------|----------------------------------------------------------------|
| `THINKIFIC_WEBHOOK_SECRET`  | yes      | Long random string. Same value goes into Thinkific (step 2).    |
| `THINKIFIC_COURSE_ID`       | yes*     | Course ID for the CS/CR course. *Optional but strongly advised. |

Generate a secret:
```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Find the course ID in Thinkific:
- Admin → Manage Learning Products → Courses → click the CS/CR course.
- The URL contains `/courses/<id>/` — that integer is the course ID.

## 2. Thinkific webhook

Thinkific Admin → **Apps** → **Webhooks** (or **Settings → Code & Analytics →
Webhooks**, depending on your admin layout):

- **Topic:** `enrollment.created` (also add `enrollment.deleted` if you want
  refunds to revoke access automatically).
- **Target URL:** `https://cehub-cs-cr-coach.onrender.com/webhooks/thinkific`
- **Secret:** paste the same value you set as `THINKIFIC_WEBHOOK_SECRET`.

Save. Thinkific will sign each delivery with HMAC-SHA256 in the
`X-Thinkific-Hmac-Sha256` header.

## 3. Iframe URL in the lesson

Your lesson HTML should pass user + enrollment context as URL params using
Thinkific Liquid variables:

```html
<iframe
  src="https://cehub-cs-cr-coach.onrender.com/?user_id={{user.id}}&user_email={{user.email}}&user_name={{user.first_name}} {{user.last_name}}&enrollment_id={{enrollment.id}}"
  width="100%"
  height="900"
  style="border:none;"
></iframe>
```

`enrollment_id` is now **required**. If it is missing, the tool shows an
"Access Restricted" page and refuses uploads.

## 4. Verification

1. Buy or be granted the course as a test student.
2. Open the lesson — the writing coach should load directly into the upload
   view (no manual ID prompt).
3. Submit a draft. Should succeed.
4. Try the same iframe URL in an incognito window with a fake `user_id` and
   `enrollment_id` — should fail with "enrollment is not yet active".
5. Check Render logs for `Thinkific webhook signature mismatch` or other
   errors.

## 5. Backfilling existing enrollments (only if needed)

If you have customers who already enrolled before the webhook was wired up,
their enrollments are not in the database. Two options:

- **Easiest:** ask them to re-enroll, or grant them a new enrollment from the
  Thinkific admin (which fires `enrollment.created`).
- **Programmatic:** export enrollments via the Thinkific Admin API and POST
  each one into the `enrollments` table directly. Out of scope here — open a
  follow-up if needed.

## What changed in the code

- `app/database.py` — new `Enrollment` model.
- `app/main.py`:
  - new `POST /webhooks/thinkific` endpoint, HMAC-verified.
  - `POST /api/submissions` now **requires** `enrollment_id`, verifies it
    exists in the allowlist, and verifies the enrollment belongs to the
    current Thinkific user.
- `app/static/index.html` + `app.js` — manual participant-ID entry removed.
  No URL params → "Access Restricted" view with a link back to the course.
- `.env.example`, `render.yaml` — new env vars.

## Phase 2 (not yet implemented)

- Submission tiers (e.g. 3-pack purchases) instead of strict 1-per-enrollment.
- Backfill admin endpoint for legacy enrollments.
- Per-enrollment one-time access tokens for stronger anti-spoofing.
