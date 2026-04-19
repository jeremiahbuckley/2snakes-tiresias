import { redirect, fail } from '@sveltejs/kit';
import { register } from '$lib/api.js';

/**
 * Try to pull a human-friendly message out of a FastAPI error body.
 * FastAPI returns either { "detail": "..." } for HTTPException or
 * { "detail": [{ "loc": [...], "msg": "..." }, ...] } for Pydantic validation.
 */
function parseApiDetail(detail) {
  if (!detail) return null;
  try {
    const body = JSON.parse(detail);
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      const first = body.detail[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
      return field ? `${field}: ${first.msg}` : first.msg;
    }
  } catch (_) {
    /* fall through */
  }
  return null;
}

/** @type {import('./$types').Actions} */
export const actions = {
  /** Real registration: POST /auth/register → set JWT cookie, redirect to dashboard. */
  default: async ({ request, cookies, url }) => {
    const data = await request.formData();
    const email = data.get('email')?.toString().trim() ?? '';
    const username = data.get('username')?.toString().trim() ?? '';
    const password = data.get('password')?.toString() ?? '';
    const password_confirm = data.get('password_confirm')?.toString() ?? '';
    const display_name = data.get('display_name')?.toString().trim() || null;

    // Echo non-secret fields back to the form on failure so the user
    // doesn't have to retype them.
    const echo = { email, username, display_name };

    if (!email || !username || !password || !password_confirm) {
      return fail(400, {
        ...echo,
        error: 'Email, username, password, and password confirmation are all required.',
      });
    }
    if (password !== password_confirm) {
      return fail(400, { ...echo, error: "Passwords don't match. Please retype them." });
    }
    if (password.length < 8) {
      return fail(400, { ...echo, error: 'Password must be at least 8 characters.' });
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(username) || username.length < 3 || username.length > 64) {
      return fail(400, {
        ...echo,
        error: 'Username must be 3–64 characters (letters, numbers, underscore, dash).',
      });
    }

    let result;
    try {
      result = await register(email, username, password, display_name);
    } catch (err) {
      if (err.status === 409) {
        return fail(409, {
          ...echo,
          error: parseApiDetail(err.detail) ?? 'Email or username already taken.',
        });
      }
      if (err.status === 422) {
        return fail(422, {
          ...echo,
          error: parseApiDetail(err.detail) ?? 'Some fields are invalid. Please check and try again.',
        });
      }
      if (err.status) {
        return fail(err.status, {
          ...echo,
          error: parseApiDetail(err.detail) ?? `Registration failed (${err.status}).`,
        });
      }
      return fail(500, { ...echo, error: 'Could not reach the API. Is the server running?' });
    }

    cookies.set('tiresias_token', result.access_token, {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7, // 7 days, matching login
      secure: process.env.NODE_ENV === 'production',
    });

    const redirectTo = url.searchParams.get('redirect') ?? '/dashboard';
    throw redirect(303, redirectTo);
  },
};
