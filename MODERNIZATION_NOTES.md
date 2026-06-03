# PowerPayShop Modernization Notes

## What changed

- Added `static/css/modern-shop.css` with a modern marketplace design system: glass cards, improved hero sections, product cards, buttons, tables, navbar, and responsive spacing.
- Rebuilt key templates for a cleaner shop experience:
  - `templates/base.html`
  - `templates/footer.html`
  - `shop/templates/shop/navbar.html`
  - `shop/templates/shop/index.html`
  - `shop/templates/shop/product_grid.html`
  - `shop/templates/shop/product_detail.html`
  - `shop/templates/shop/cart.html`
  - `shop/templates/shop/checkout.html`
  - `shop/templates/shop/vendor_dashboard.html`
  - `shop/templates/shop/add_edit_product.html`
  - `accounts/templates/accounts/login.html`
  - `accounts/templates/accounts/register.html`
  - `accounts/templates/accounts/profile.html`
- Optimized shop views with `select_related`, `prefetch_related`, safer pagination, reusable helper functions, and cleaner cart/promo logic.
- Fixed promo-code discount calculation for the `PromoCode.products` many-to-many relationship.
- Fixed cart quantity updates and made cart counts sum quantities instead of only counting rows.
- Removed hardcoded sensitive credentials from `settings.py`; use environment variables from `.env.example`.
- Made OTP generation use Python `secrets` instead of `random`.
- Removed duplicate support admin view logic and optimized support ticket queries.
- Made gallery uploads optional and restored edit-page gallery image deletion.

## Run locally

```bash
python -m venv venv
source venv/bin/activate   # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # configure values for production
python manage.py migrate
python manage.py runserver
```

## Validation performed

- `python manage.py check` passed.
- Render checks passed for home, login, register, search, and product detail pages.

## Production reminder

Set real values for `DJANGO_SECRET_KEY`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and `MPESA_ENDPOINT` in your environment. Do not commit live credentials unless you enjoy turning security into performance art.
