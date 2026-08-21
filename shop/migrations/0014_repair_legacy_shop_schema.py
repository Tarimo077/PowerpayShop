from django.db import migrations


def repair_legacy_shop_schema(apps, schema_editor):
    def table_names():
        with schema_editor.connection.cursor() as cursor:
            return set(schema_editor.connection.introspection.table_names(cursor))

    def ensure_model(model_name):
        model = apps.get_model("shop", model_name)
        tables = table_names()
        if model._meta.db_table not in tables:
            schema_editor.create_model(model)
            return
        for field in model._meta.local_many_to_many:
            through = field.remote_field.through
            if through._meta.auto_created and through._meta.db_table not in tables:
                schema_editor.create_model(through)

    def ensure_field(model_name, field_name):
        model = apps.get_model("shop", model_name)
        if model._meta.db_table not in table_names():
            return
        with schema_editor.connection.cursor() as cursor:
            columns = {
                column.name
                for column in schema_editor.connection.introspection.get_table_description(
                    cursor, model._meta.db_table
                )
            }
        field = model._meta.get_field(field_name)
        if field.column not in columns:
            schema_editor.add_field(model, field)

    ensure_field("Product", "max_stock")
    ensure_field("ProductRating", "review")
    ensure_model("ProductGallery")
    ensure_model("PromoCode")


class Migration(migrations.Migration):
    dependencies = [("shop", "0013_product_shop_prod_vendor_created_idx_and_more")]

    operations = [
        migrations.RunPython(repair_legacy_shop_schema, migrations.RunPython.noop),
    ]
