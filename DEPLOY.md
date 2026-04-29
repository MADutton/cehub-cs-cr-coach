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

- **Model:** `Enrollment`
- **Topic:** `enrollment.created`
- **Target URL:** `https://cehub-cs-cr-coach.onrender.com/webhooks/thinkific?secret=YOUR_SECRET`
  Replace `YOUR_SECRET` with the value of `THINKIFIC_WEBHOOK_SECRET` in Render.

Note: Thinkific basic webhooks (Grow plan) do not send an HMAC header. We
authenticate via the `?secret=` query param in the URL instead. Keep this URL
private — it is the only thing preventing forged webhook deliveries.

Note: `enrollment.deleted` does not exist as a Thinkific topic. To revoke
access after a refund, manually set `revoked = true` on the relevant row in
the `enrollments` database table. Automated refund-revocation is Phase 2.

Save. Thinkific will POST the enrollment payload to your URL on each purchase.

## 3. Iframe URL in the lesson

Thinkific lesson HTML code blocks do **not** render Liquid variables — they
pass `{{user.id}}` as a literal string. Use a plain iframe URL with no params:

```html
<iframe
  src="https://cehub-cs-cr-coach.onrender.com/"
  width="100%"
  height="900"
  style="border:none;"
></iframe>
```

Users will see an email entry form. They enter the email they used to purchase;
the backend looks it up in the enrollment allowlist (populated by the webhook)
and grants access if found. No Liquid required.

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
