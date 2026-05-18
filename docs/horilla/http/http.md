# Horilla HTTP Utilities

## 🎯 Purpose

The `horilla.http` module provides:

- **Centralized HTTP imports** — common Django HTTP types in one place
- **Secure redirect handling** — validation against open redirects (CWE-601)
- **HTMX-compatible responses** — `HX-Redirect` and `HX-Refresh` where appropriate
- **Custom error handling** — `HttpNotFound` with Horilla’s `404.html` / `error.html` stack

It is the preferred entry point for the symbols it re-exports and for Horilla’s redirect/error helpers.

**Note:** Code examples below use **explicit arguments** (including optional ones) so the full call shape is visible at a glance.

---

## 🧠 Core concept

### ❌ Avoid direct Django imports (for what this package exposes)

```python
# Less ideal when horilla.http already exports it
from django.http import HttpResponse, StreamingHttpResponse
```

```python
# ✅ Preferred
from horilla.http import HttpResponse, StreamingHttpResponse
```

**Simple rule:** If a name appears in the **re-export list** below (for example `HttpResponse`, `StreamingHttpResponse`), import it from **`horilla.http`**. If you need something from Django that is **not** in that list, import it from **`django.http`** instead — `horilla.http` does not include every class Django offers, only the ones Horilla chose to forward.

---

## 📦 Module location

On disk, `horilla/http/` contains the following layout (as in the package directory):

```text
horilla/http/
├── response.py      # HttpNotFound, RedirectResponse, RefreshResponse
├── url_safety.py    # safe_url() — open-redirect safe URL validation (CWE-601)
└── __init__.py      # Package entry: re-exports Django HTTP types + Horilla helpers (__all__)
```

| File / directory | Role |
|------------------|------|
| `response.py` | Custom responses and `HttpNotFound` (`as_response` → Horilla templates). |
| `url_safety.py` | `safe_url(request, next_url, fallback=…)` using `url_has_allowed_host_and_scheme`. |
| `__init__.py` | Re-exports: Django `HttpResponse`, `JsonResponse`, `FileResponse`, redirects, `Http404`, `QueryDict`, plus `safe_url`, `HttpNotFound`, `RedirectResponse`, `RefreshResponse`. |

---

## 🔁 What `horilla.http` provides

### 📍 Re-exported Django classes

- `HttpResponse`
- `JsonResponse`
- `FileResponse`
- `StreamingHttpResponse`
- `HttpResponseRedirect`
- `HttpResponseNotFound`
- `HttpResponseBadRequest`
- `HttpResponseNotAllowed`
- `Http404`
- `QueryDict`

### ➕ Custom utilities

- `safe_url`
- `RedirectResponse`
- `RefreshResponse`
- `HttpNotFound`

---

## 🔐 Safe URL handling

### 📍 Function

```python
safe_url(request, next_url, fallback="/")
```

### 🎯 Purpose

Prevents **open redirect** vulnerabilities (**CWE-601**).

### ✅ Behavior

Validates redirect URLs using Django’s `url_has_allowed_host_and_scheme`. In practice, that means:

- **Same host** as the current request (via `allowed_hosts={request.get_host()}`)
- **Safe scheme** — `require_https` follows `request.is_secure()`

Invalid or empty URLs return `fallback` (default `"/"`).

### 🧪 Example (all parameters explicit)

```python
next_url = safe_url(
    request,
    request.GET.get("next", "/"),
    fallback="/",
)
```

Prevents redirecting users to external malicious sites when `next` is forged or unsafe.

---

## 🔁 `RedirectResponse`

### 📍 Class

```python
class RedirectResponse(HttpResponseRedirect):
    ...
```

### 🎯 Purpose

- Safe redirects (uses `safe_url` internally)
- HTMX-compatible redirects (`HX-Redirect`)
- Prevents open redirects
- Optional Django **messages** via `message=` → `messages.error`
- **Fallback URL** when the target is not safe (`fallback_url`, default `"/"`)
- **HTMX detection** — checks `HX-Request` header

### 🔄 Behavior

| Request type | Result |
|--------------|--------|
| **Normal** | **302** — `Location: <safe-url>` |
| **HTMX** (`HX-Request`) | **200** — `HX-Redirect: <safe-url>` (no `Location`; avoids breaking HTMX flows) |

If `redirect_to` is omitted, the target is taken from **`HTTP_REFERER`**, then validated with `safe_url` against `fallback_url`.

### 🧪 Example

```python
return RedirectResponse(
    request,
    redirect_to="/dashboard/",
    message=None,
    fallback_url="/",
)
```

With a flash message when redirecting after validation failure:

```python
return RedirectResponse(
    request,
    redirect_to="/accounts/profile/",
    message="Please fix the errors below.",
    fallback_url="/",
)
```

---

## 🔄 `RefreshResponse`

### 📍 Class

```python
class RefreshResponse(HttpResponse):
    ...
```

### 🎯 Purpose

Triggers a **full page refresh** safely.

### ⚙️ Behavior

| Request type | Result |
|--------------|--------|
| **HTMX** | **200** — `HX-Refresh: true` |
| **Normal** (with `request`) | **302** — redirect to **safe** current path (`safe_url(request, request.path, fallback_url)`) |

### 🧪 Example

```python
return RefreshResponse(
    request=request,
    fallback_url="/",
)
```

---

## 🚫 `HttpNotFound` (custom 404)

### 📍 Class

```python
class HttpNotFound(Exception):
    ...
```

Constructor: `HttpNotFound(message=..., context=None, template=None)` — if `template` is omitted, **`404.html`** is used.

### 🎯 Purpose

- Custom 404 **exception** with message, optional `context`, optional `template`
- Renders a Horilla **404** via `as_response(request)` (status **404**, `error_message` in context)

### 🧪 Usage

```python
raise HttpNotFound(
    message="Custom error message",
    context={},
    template=None,
)
```

With extra template context and a specific template path:

```python
raise HttpNotFound(
    message="Resource not available.",
    context={"resource_id": resource_id},
    template="404.html",
)
```

### 🔄 Convert to response

`as_response` takes only the request:

```python
return exception.as_response(request)
```

---


## 🎨 Error templates

### 📍 Base template — `templates/error.html`

Shared layout for error pages: supports **full page**, **modal** (`modal`), and **embedded** (`embed`) modes, **dark mode**, and layout that works with **HTMX** (e.g. modal vs full height).

### 📍 404 template — `templates/404.html`

- **Extends** `error.html`
- Shows **Page Not Found** and `{{ error_message }}` (with a default if missing)

### ✨ Example fragment (conceptual)

```html
<h2>Page Not Found</h2>
<p>{{ error_message }}</p>
```

(Actual markup uses Horilla classes and `{% trans %}` — see `templates/404.html`.)

---

## 🧩 Example usage (login-style `next`)

```python
next_url = safe_url(
    request,
    request.GET.get("next", "/"),
    fallback="/",
)

return render(
    request,
    "login.html",
    {
        "next": next_url,
    },
)
```

Ensures the value you pass into the template (and later into redirects) is safe.

---

## ⚠️ Important guidelines

| Avoid | Prefer |
|-------|--------|
| `from django.http import *` | `from horilla.http import ...` for exported names |
| Raw `HttpResponseRedirect(untrusted_url)` | `safe_url(request, url, fallback=...)` or `RedirectResponse` |

**Always validate redirects** with `safe_url` or use `RedirectResponse` / `RefreshResponse`.

---

## 🧩 Benefits

- **Security** — reduces open redirect risk
- **Consistency** — shared HTTP imports (including `StreamingHttpResponse`) and 404 rendering
- **HTMX** — correct `HX-Redirect` / `HX-Refresh` behavior
- **Cleaner imports** — one obvious module for Horilla HTTP patterns

---

## 📌 Summary

| Feature | Django alone | Horilla `horilla.http` |
|---------|----------------|------------------------|
| HTTP imports | Direct, per file | Centralized re-exports + helpers |
| Redirect safety | Manual | Built-in (`safe_url`, response classes) |
| HTMX support | Manual headers | Built into `RedirectResponse` / `RefreshResponse` |
| Custom 404 UX | Varies | `HttpNotFound` + shared templates |
| Streaming responses | `django.http` | Same class via `horilla.http` re-export |

---

## 🏁 Conclusion

The `horilla.http` module:

- Wraps and re-exports selected Django HTTP utilities (including `StreamingHttpResponse`)
- Adds **security** (safe redirects) and **HTMX** behavior
- Standardizes **404** handling through `HttpNotFound` and Horilla error templates

Use it wherever you would otherwise duplicate redirect validation or HTMX header logic.
