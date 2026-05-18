```markdown id="u4k9xp"
# Horilla Model Layer & Core Architecture

## 🎯 Purpose

Horilla extends Django’s ORM with:

- Centralized model imports
- Custom field extensions
- Core reusable base models
- Scalable architecture across apps

---

## 🧠 Project Structure

```

project_root/
│
├── horilla/          # Django PROJECT (settings, urls, db abstraction)
│   └── db/           # ORM abstraction layer
│
├── horilla_core/     # Django APP (core business models)
│
├── manage.py

````

---

## 🧩 1. ORM Abstraction Layer (`horilla.db`)

### ❌ Avoid direct Django usage

```python
from django.db import models
````

---

### ✅ Always use

```python id="a1k2xp"
from horilla.db import models
```

---

## 📍 Entry Point

```python id="b3m8qz"
# horilla/db/__init__.py

from horilla.db import models

__all__ = ["models"]
```

---

## 📍 Extended Models Module

```python id="c7n1tr"
# horilla/db/models/__init__.py

from django.db.models import *
from django.db import models as _django_models

from horilla.db.models.fields import GenericForeignKey

__all__ = list(_django_models.__all__) + ["GenericForeignKey"]
```

✔ Includes:

* All Django model fields
* Custom `GenericForeignKey`

---

## 🔧 Custom GenericForeignKey

### 🚨 Django Limitation

* Only supports `ContentType`
* Does NOT support proxy models

---

### ✅ Horilla Solution

```python id="d4v8nx"
class GenericForeignKey(DjangoGenericForeignKey):
```

### ✔ Enhancements

* Supports proxy models
* Custom `verbose_name`
* Relaxed validation:

```python id="e2m7ka"
issubclass(model, ContentType)
```

---

## 🧩 2. Proxy ContentType Support

```python id="f7n2yk"
class HorillaContentType(ContentType):
    class Meta:
        proxy = True
```

✔ Works seamlessly with custom `GenericForeignKey`

---

## 🧪 Example Usage

```python id="g8x4pq"
content_type = models.ForeignKey(HorillaContentType, ...)
object_id = models.PositiveIntegerField(...)
related_object = models.GenericForeignKey("content_type", "object_id")
```

---

# 🧩 3. Core Models Layer (`horilla_core` app)

## 📍 Central Model Export

```python id="h1z8rw"
# horilla_core/models/__init__.py
```

### 🎯 Purpose

Provides a **single import point** for all core models.

---

### ❌ Avoid scattered imports

```python
from horilla_core.models.company import Company
```

---

### ✅ Use centralized import

```python id="i5k2zs"
from horilla_core.models import Company
```

---

### 📦 Includes Models Like:

* Company
* HorillaUser
* Department, Role
* Activity, RecentlyViewed
* Attachments
* Filters & UI configs
* Business hours & holidays
* Finance models
* Import/Export
* Recycle bin
* System settings
* Visibility controls

---

# 🧩 4. Core Base Models

## 🏢 Company Model

### Features:

* Company details (name, email, website)
* Address & location
* Financial data
* Localization settings
* HQ management (only one HQ)

---

### ⚙️ Smart HQ Logic

```python id="j3n8qp"
if not Company.objects.exclude(pk=self.pk).filter(hq=True).exists():
    self.hq = True
elif self.hq:
    Company.objects.exclude(pk=self.pk).filter(hq=True).update(hq=False)
```

---

## 🔍 CompanyFilteredManager

### Purpose:

Filters queryset automatically based on:

* Active company in request
* Session flag (`show_all_companies`)

---

```python id="k9m2wr"
objects = CompanyFilteredManager()
```

✔ Enables multi-company behavior globally

---

## 🧱 HorillaCoreModel (Base Model)

```python id="l4x7ns"
class HorillaCoreModel(models.Model):
```

### Features:

* Common fields:

  * company
  * created_at / updated_at
  * created_by / updated_by
* Audit logging
* Active flag
* JSON additional info

---

### ⚙️ Auto Field Handling

```python id="m8q2pt"
def save(self, *args, **kwargs):
```

✔ Automatically sets:

* User tracking
* Timestamps
* Company context

---

### 🕓 Audit History

```python id="n2k9yb"
@property
def histories(self)
```

✔ Returns object history

---

### 🔗 Full History Tracking

```python id="o7z3vx"
@property
def full_histories(self)
```

✔ Tracks:

* Own changes
* Related FK objects
* Related GenericForeignKey objects

✔ Uses:

* `HorillaContentType`
* Custom `GenericForeignKey`

---

# ⚠️ Important Guidelines

## ❌ Avoid

```python id="a0h4dg"
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
```

---

## ✅ Always use

```python id="p6t8zx"
from horilla.db import models
```

```python id="q1w4er"
from horilla_core.models import Company
```

---

# 🧩 Benefits

* 🔄 Centralized ORM control
* 🧼 Clean import structure
* 🔧 Extendable fields
* 🧠 AI-friendly architecture
* 🏢 Built-in multi-company support
* 📊 Integrated audit logging
* 🚀 Supports advanced relationships

---

# 📌 Summary

| Feature           | Django   | Horilla     |
| ----------------- | -------- | ----------- |
| Model import      | Direct   | Centralized |
| GenericForeignKey | Limited  | Extended    |
| Proxy ContentType | ❌        | ✅           |
| Base model        | Manual   | Built-in    |
| Multi-company     | Custom   | Built-in    |
| Audit history     | External | Integrated  |

---

# 🏁 Conclusion

Horilla’s architecture separates:

* **Project layer (`horilla`)** → infrastructure & abstraction
* **App layer (`horilla_core`)** → business logic & models

This ensures:

* Clean separation of concerns
* High scalability
* Easy customization

---
