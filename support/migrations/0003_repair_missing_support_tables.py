from django.db import migrations


def repair_missing_support_tables(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        tables = set(schema_editor.connection.introspection.table_names(cursor))

    for model_name in ("Ticket", "TicketMessage"):
        model = apps.get_model("support", model_name)
        if model._meta.db_table not in tables:
            schema_editor.create_model(model)
            tables.add(model._meta.db_table)


class Migration(migrations.Migration):
    dependencies = [("support", "0002_ticket_support_status_priority_idx_and_more")]

    operations = [
        migrations.RunPython(repair_missing_support_tables, migrations.RunPython.noop),
    ]
