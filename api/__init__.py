"""Blueprint HTTP Cofind.

Setiap modul di paket ini memuat satu blueprint untuk satu area API. Registrasi
dilakukan oleh `register_blueprints()` yang dipanggil dari app.py.
"""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from api.admin_routes import bp as admin_bp
    from api.auth_routes import bp as auth_bp
    from api.coffeeshop_routes import bp as coffeeshop_bp
    from api.favorite_routes import bp as favorite_bp
    from api.review_routes import bp as review_bp
    from api.vote_routes import bp as vote_bp
    from api.want_to_visit_routes import bp as want_to_visit_bp

    for blueprint in (
        coffeeshop_bp,
        auth_bp,
        review_bp,
        favorite_bp,
        vote_bp,
        want_to_visit_bp,
        admin_bp,
    ):
        app.register_blueprint(blueprint)
