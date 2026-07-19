"""Probe runtime for LOCALIZE probe scripts (shipped to /testbed/.pipe/).

This module removes the framework boilerplate from probe scripts so a probe
can focus on the experiment itself. Typical use inside a probe:

    import probe_runtime
    probe_runtime.setup()          # boots the framework (in-memory database)

    from django.db import models

    class MyModel(models.Model):
        name = models.CharField(max_length=10)

        class Meta:
            app_label = "probe"

    probe_runtime.create_tables(MyModel)   # before touching the database
    MyModel.objects.create(name="x")

Probes that only exercise plain classes or functions do not need this module.

Catatan harness (Lever L#4, autopsi 11964): kelas kegagalan
"probe-crash -> fallback-statis" — probe ber-Model crash di boilerplate
app-registry (ModuleNotFoundError 'probe') lalu model memilih kandidat dari
plausibility statis. Modul ini mematikan boilerplate-nya by construction.
Kompatibilitas: py3.6+ (env testbed image SWE-bench Django).
"""
import sys


def setup(extra_settings=None):
    """Configure minimal Django settings (in-memory sqlite) and boot the app
    registry. Safe to call more than once; returns the django module."""
    import django
    from django.conf import settings

    if not settings.configured:
        base = dict(
            DEBUG=True,
            DATABASES={"default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }},
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
            ],
        )
        if extra_settings:
            base.update(extra_settings)
        settings.configure(**base)
        django.setup()
    return django


def create_tables(*models):
    """Create database tables for ad-hoc probe models (call after setup())."""
    from django.db import connection

    with connection.schema_editor() as editor:
        for model in models:
            editor.create_model(model)


def main():
    sys.stderr.write("probe_runtime is a library for probe scripts; "
                     "import it, do not run it.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
